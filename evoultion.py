import copy
import random
from typing import List, Sequence

from deap import base, creator, tools


def evaluate_species( #potentially rename since this is just breeding basically? idk.
    population_size: int, 
    target_traits: Sequence[float],
    generations: int = 20,
    min_population_size: int = 10,
    max_population_size: int = 200, #max pop size is static not dynamic carrying capacity like in nature: Fix this.
    immigration_rate: float = 0.1,
    immigration_chance: float = 0.35,
    immigration_variation: float = 0.25,
    fecundity: float = 1.0,
    fecundity_variation: float = 0.15,
) -> List:
    """
    Run a DEAP simulation that will run a simple simulation of evoultion
    """
    if fecundity <= 0:
        raise ValueError("fecundity must be greater than zero.")
    if fecundity_variation < 0:
        raise ValueError("fecundity_variation cannot be negative.")

    if not hasattr(creator, "FitnessMax"):
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))

    if not hasattr(creator, "EvoIndividual"):
        creator.create("EvoIndividual", list, fitness=creator.FitnessMax)

    trait_count = len(target_traits)
    crossover_probability = 0.7
    mutation_probability = 0.3
    elite_count = 2
    perfectly_matching_score = trait_count

    def clone(individual):
        """Deep-copy helper because newer DEAP builds skip tools.clone."""
        return copy.deepcopy(individual)

    def clamp_traits(individual):
        """Keep trait values inside [0, 1] for easier interpretation."""
        for index, gene in enumerate(individual):
            individual[index] = min(max(gene, 0.0), 1.0)

    def evaluate(individual):
        """
        Score individuals by similarity to the target: the closer they are, the better.

        A perfect match returns `perfectly_matching_score` and larger scores mean higher fitness.
        """
        difference = sum(abs(gene - target) for gene, target in zip(individual, target_traits))
        return (perfectly_matching_score - difference,)

    def scaled_fitness(population):
        """makes fitness scores more similar in magnitude for the sake of genetic diversity"""
        raw_scores = [individual.fitness.values[0] for individual in population]
        minimum = min(raw_scores)
        offset = -minimum + 1e-9 if minimum < 0 else 1e-9
        return [score + offset for score in raw_scores]

    def roll_immigration_quota(current_size: int) -> int:
        """Draw the number of immigrants for the next generation."""
        if current_size == 0 or random.random() > immigration_chance:
            return 0

        base_count = max(1, int(round(current_size * immigration_rate)))
        variance = max(1, int(round(base_count * immigration_variation)))
        lower = max(1, base_count - variance)
        upper = base_count + variance
        candidate = random.randint(lower, upper)
        available_space = max(0, max_population_size - current_size) #should be dynamic based on carrying capacity
        return max(0, min(candidate, available_space))

    toolbox = base.Toolbox() #registering deap stuff
    toolbox.register("attr_trait", random.random)
    toolbox.register("individual", tools.initRepeat, creator.EvoIndividual, toolbox.attr_trait, trait_count)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("clone", clone)
    toolbox.register("evaluate", evaluate)
    toolbox.register("mate", tools.cxBlend, alpha=0.5)
    toolbox.register("mutate", tools.mutGaussian, mu=0.0, sigma=0.25, indpb=0.6)

    base_population = max(min_population_size, min(max_population_size, population_size))
    target_population_baseline = max(
        min_population_size,
        min(max_population_size, int(round(base_population * fecundity))),
    )

    population = toolbox.population(n=base_population)

    for generation in range(1, generations + 1): 
        invalid_individuals = [ind for ind in population if not ind.fitness.valid] #gives fitness to all immigrants and unregistered such organisims
        for individual, fitness in zip(invalid_individuals, map(toolbox.evaluate, invalid_individuals)):
            individual.fitness.values = fitness

        scaled_scores = scaled_fitness(population) #scales
        current_size = len(population)
        immigration_quota = roll_immigration_quota(current_size) #figures out immigration
        parent_slots = max(current_size, 0)
        elite_to_keep = min(elite_count, parent_slots)
        variation_span = max(1, int(round(target_population_baseline * fecundity_variation)))
        lower_bound = max(min_population_size, target_population_baseline - variation_span)
        upper_bound = min(max_population_size, target_population_baseline + variation_span)
        if upper_bound < lower_bound:
            upper_bound = lower_bound
        target_population = random.randint(lower_bound, upper_bound) #aims to keep population roughly the same as happens in nature

        elite_parents = [] #elitism to preserve best animals
        for elite in tools.selBest(population, elite_to_keep):
            elite_clone = toolbox.clone(elite)
            elite_clone.elite_parent = True
            elite_parents.append(elite_clone)

        roulette_slots = parent_slots - elite_to_keep #roulette evoultion to simulate sexual selection
        other_parents = []
        if roulette_slots > 0:
            selected = tools.selRoulette(population, roulette_slots)
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
            if elite_in_pair or random.random() < crossover_probability:
                toolbox.mate(parent1, parent2)
                clamp_traits(parent1)
                clamp_traits(parent2)
                if hasattr(parent1.fitness, "values"):
                    del parent1.fitness.values
                if hasattr(parent2.fitness, "values"):
                    del parent2.fitness.values

            if random.random() < mutation_probability: #mutation for genetic diversity
                toolbox.mutate(parent1)
                clamp_traits(parent1)
                if hasattr(parent1.fitness, "values"):
                    del parent1.fitness.values

            if random.random() < mutation_probability:
                toolbox.mutate(parent2)
                clamp_traits(parent2)
                if hasattr(parent2.fitness, "values"):
                    del parent2.fitness.values

            offspring.extend([parent1, parent2])

        immigrants = [toolbox.individual() for _ in range(immigration_quota)]

        new_generation = offspring + immigrants

        if len(new_generation) < target_population:
            deficit = target_population - len(new_generation)
            new_generation.extend(toolbox.individual() for _ in range(deficit))

        if len(new_generation) > target_population:
            elites = tools.selBest(new_generation, min(elite_count, target_population))
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

        population[:] = new_generation #replaces the old with the new

        invalid_individuals = [ind for ind in population if not ind.fitness.valid]
        for individual, fitness in zip(invalid_individuals, map(toolbox.evaluate, invalid_individuals)):
            individual.fitness.values = fitness

        """
        testing code
        best_individual = tools.selBest(population, 1)[0]
        average_score = sum(ind.fitness.values[0] for ind in population) / len(population)

        genes = " ".join(f"{gene:.2f}" for gene in best_individual)
         print(
             f"Generation {generation:02d} | pop {len(population)} | best {best_individual.fitness.values[0]:.2f}/"
             f"{perfectly_matching_score} | avg {average_score:.2f} | best genes [{genes}] "
             f"| immigrants {immigration_quota}"
         )
        """
    return population

#testing call
# final_population = evaluate_species(
#     population_size=50,
#     target_traits=[0.6, 0.2, 0.8, 0.4],
#     generations=300,
#     min_population_size=20,
#     max_population_size=120,
#     immigration_rate=0.12,
#     immigration_chance=0.4,
#     immigration_variation=0.3,
#     fecundity=1.0,
#     fecundity_variation=0.25,
# )

# print(f"Simulation finished with {len(final_population)} individuals.")
