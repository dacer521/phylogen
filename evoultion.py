import copy
import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from deap import base, creator, tools


@dataclass
class EvolutionContext:
    """Container for the DEAP toolbox and knobs required to advance a population."""

    toolbox: base.Toolbox
    target_traits: Sequence[float]
    min_population_size: int
    max_population_size: int
    immigration_rate: float
    immigration_chance: float
    immigration_variation: float
    fecundity: float
    fecundity_variation: float
    crossover_probability: float
    mutation_probability: float
    elite_count: int
    perfectly_matching_score: int
    target_population_baseline: int
    target_traits_override: Optional[Sequence[float]] = None


def _ensure_creators() -> None:
    """Define shared DEAP creator classes exactly once."""
    if not hasattr(creator, "FitnessMax"):
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))

    if not hasattr(creator, "EvoIndividual"):
        creator.create("EvoIndividual", list, fitness=creator.FitnessMax)


def _scaled_fitness(population: List) -> List[float]:
    """Normalize fitness scores so roulette selection remains stable."""
    if not population:
        return []

    raw_scores = [individual.fitness.values[0] for individual in population]
    minimum = min(raw_scores)
    offset = -minimum + 1e-9 if minimum < 0 else 1e-9
    return [score + offset for score in raw_scores]


def _select_roulette_scaled(population: List, count: int) -> List:
    """Roulette selection that uses scaled fitness to keep probabilities positive."""
    if count <= 0 or not population:
        return []

    weights = _scaled_fitness(population)
    if not weights or sum(weights) <= 0:
        return random.choices(population, k=count)
    return random.choices(population, weights=weights, k=count)


def _roll_immigration_quota(current_size: int, context: EvolutionContext) -> int:
    """Draw the number of immigrants for the next generation."""
    if current_size == 0 or random.random() > context.immigration_chance:
        return 0

    base_count = max(1, int(round(current_size * context.immigration_rate)))
    variance = max(1, int(round(base_count * context.immigration_variation)))
    lower = max(1, base_count - variance)
    upper = base_count + variance
    candidate = random.randint(lower, upper)
    available_space = max(0, context.max_population_size - current_size)
    return max(0, min(candidate, available_space))


def prepare_evolution(
    population_size: int,
    target_traits: Sequence[float],
    *,
    min_population_size: int = 10,
    max_population_size: int = 200,
    immigration_rate: float = 0.1,
    immigration_chance: float = 0.35,
    immigration_variation: float = 0.25,
    fecundity: float = 1.0,
    fecundity_variation: float = 0.15,
    crossover_probability: float = 0.7,
    mutation_probability: float = 0.3,
    elite_count: int = 2,):
    """
    Configure the DEAP toolbox and seed an initial population.

    Returns the population list (suitable for in-place mutation) and an EvolutionContext
    that can be reused for subsequent generational updates.
    """
    if fecundity <= 0:
        raise ValueError("fecundity must be greater than zero.")
    if fecundity_variation < 0:
        raise ValueError("fecundity_variation cannot be negative.")

    _ensure_creators()

    trait_count = len(target_traits)
    toolbox = base.Toolbox()
    base_population = max(min_population_size, min(max_population_size, population_size))
    target_population_baseline = max(
        min_population_size,
        min(max_population_size, int(round(base_population * fecundity))),
    )
    perfectly_matching_score = trait_count

    def clone(individual):
        """Deep-copy helper because newer DEAP builds skip tools.clone."""
        return copy.deepcopy(individual)

    def clamp_traits(individual):
        """Keep trait values inside [0, 1] for easier interpretation."""
        for index, gene in enumerate(individual):
            individual[index] = min(max(gene, 0.0), 1.0)

    toolbox.register("attr_trait", random.random)
    toolbox.register("individual", tools.initRepeat, creator.EvoIndividual, toolbox.attr_trait, trait_count)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("clone", clone)
    toolbox.register("mate", tools.cxBlend, alpha=0.5)
    toolbox.register("mutate", tools.mutGaussian, mu=0.0, sigma=0.25, indpb=0.6)
    toolbox.register("clamp_traits", clamp_traits)

    context = EvolutionContext(
        toolbox=toolbox,
        target_traits=tuple(target_traits),
        min_population_size=min_population_size,
        max_population_size=max_population_size,
        immigration_rate=immigration_rate,
        immigration_chance=immigration_chance,
        immigration_variation=immigration_variation,
        fecundity=fecundity,
        fecundity_variation=fecundity_variation,
        crossover_probability=crossover_probability,
        mutation_probability=mutation_probability,
        elite_count=elite_count,
        perfectly_matching_score=perfectly_matching_score,
        target_population_baseline=target_population_baseline,
    )

    def evaluate(individual, _context=context):
        """
        Score individuals by similarity to the current target traits.

        A perfect match returns `perfectly_matching_score` and larger scores mean higher fitness.
        """
        targets = _context.target_traits_override or _context.target_traits
        difference = sum(abs(gene - target) for gene, target in zip(individual, targets))
        return (_context.perfectly_matching_score - difference,)

    toolbox.register("evaluate", evaluate)
    population = toolbox.population(n=base_population)

    return population, context


def advance_population(population: List, context: EvolutionContext, generations: int = 1) -> List:
    """
    Advance a population by one or more generations using the supplied context.

    The population list is mutated in place and also returned for convenience.
    """
    if generations <= 0 or not population:
        return population

    toolbox = context.toolbox

    for _ in range(generations):
        invalid_individuals = [ind for ind in population if not ind.fitness.valid]
        for individual, fitness in zip(invalid_individuals, map(toolbox.evaluate, invalid_individuals)):
            individual.fitness.values = fitness

        _scaled_fitness(population)
        current_size = len(population)
        immigration_quota = _roll_immigration_quota(current_size, context)
        parent_slots = max(current_size, 0)
        elite_to_keep = min(context.elite_count, parent_slots)
        variation_span = max(1, int(round(context.target_population_baseline * context.fecundity_variation)))
        lower_bound = max(context.min_population_size, context.target_population_baseline - variation_span)
        upper_bound = min(context.max_population_size, context.target_population_baseline + variation_span)
        if upper_bound < lower_bound:
            upper_bound = lower_bound
        target_population = random.randint(lower_bound, upper_bound)

        elite_parents = []
        for elite in tools.selBest(population, elite_to_keep):
            elite_clone = toolbox.clone(elite)
            elite_clone.elite_parent = True
            elite_parents.append(elite_clone)

        roulette_slots = parent_slots - elite_to_keep
        other_parents = []
        if roulette_slots > 0:
            selected = _select_roulette_scaled(population, roulette_slots)
            other_parents = [toolbox.clone(individual) for individual in selected]

        random.shuffle(other_parents)

        breeding_pairs = []
        remaining_elites = elite_parents[:]
        while remaining_elites:
            elite = remaining_elites.pop(0)
            partner = other_parents.pop(0) if other_parents else None
            if partner is None and remaining_elites:
                partner = remaining_elites.pop(0)
            if partner is not None:
                breeding_pairs.append((elite, partner))

        while len(other_parents) >= 2:
            breeding_pairs.append((other_parents.pop(0), other_parents.pop(0)))

        offspring = []
        for parent1, parent2 in breeding_pairs:
            elite_in_pair = getattr(parent1, "elite_parent", False) or getattr(parent2, "elite_parent", False)
            if elite_in_pair or random.random() < context.crossover_probability:
                toolbox.mate(parent1, parent2)
                toolbox.clamp_traits(parent1)
                toolbox.clamp_traits(parent2)
                if hasattr(parent1.fitness, "values"):
                    del parent1.fitness.values
                if hasattr(parent2.fitness, "values"):
                    del parent2.fitness.values

            if random.random() < context.mutation_probability:
                toolbox.mutate(parent1)
                toolbox.clamp_traits(parent1)
                if hasattr(parent1.fitness, "values"):
                    del parent1.fitness.values

            if random.random() < context.mutation_probability:
                toolbox.mutate(parent2)
                toolbox.clamp_traits(parent2)
                if hasattr(parent2.fitness, "values"):
                    del parent2.fitness.values

            offspring.extend([parent1, parent2])

        immigrants = [toolbox.individual() for _ in range(immigration_quota)]

        elite_copies = [toolbox.clone(elite) for elite in elite_parents]

        new_generation = offspring + immigrants + elite_copies

        if len(new_generation) < target_population:
            deficit = target_population - len(new_generation)
            new_generation.extend(toolbox.individual() for _ in range(deficit))

        if len(new_generation) > target_population:
            elites = tools.selBest(new_generation, min(context.elite_count, target_population))
            elite_ids = {id(ind) for ind in elites}
            remaining_slots = target_population - len(elites)
            if remaining_slots > 0:
                others = [ind for ind in new_generation if id(ind) not in elite_ids]
                sampled = (
                    random.sample(others, remaining_slots)
                    if remaining_slots <= len(others)
                    else others[:remaining_slots]
                )
                new_generation = elites + sampled
            else:
                new_generation = elites

        population[:] = new_generation

        invalid_individuals = [ind for ind in population if not ind.fitness.valid]
        for individual, fitness in zip(invalid_individuals, map(toolbox.evaluate, invalid_individuals)):
            individual.fitness.values = fitness

    return population


def evaluate_species(
    population_size: int,
    target_traits: Sequence[float],
    generations: int = 20,
    min_population_size: int = 10,
    max_population_size: int = 200,
    immigration_rate: float = 0.1,
    immigration_chance: float = 0.35,
    immigration_variation: float = 0.25,
    fecundity: float = 1.0,
    fecundity_variation: float = 0.15,
) -> List:
    """
    Run a DEAP simulation that executes `generations` rounds of evolution.
    """
    population, context = prepare_evolution(
        population_size,
        target_traits,
        min_population_size=min_population_size,
        max_population_size=max_population_size,
        immigration_rate=immigration_rate,
        immigration_chance=immigration_chance,
        immigration_variation=immigration_variation,
        fecundity=fecundity,
        fecundity_variation=fecundity_variation,
    )
    advance_population(population, context, generations=generations)
    return population


# if __name__ == "__main__":
#     print("Starting evaluate_species test run...")
#     final_population = evaluate_species(
#         population_size=50,
#         target_traits=[0.6, 0.2, 0.8, 0.4],
#         generations=10,
#         min_population_size=20,
#         max_population_size=120,
#         immigration_rate=0.12,
#         immigration_chance=0.4,
#         immigration_variation=0.3,
#         fecundity=1.0,
#         fecundity_variation=0.25,
#     )
#     print(f"Simulation finished with {len(final_population)} individuals.")
