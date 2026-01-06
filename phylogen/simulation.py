
import copy
import json
import random
from pathlib import Path
from threading import Lock
from typing import Dict, Iterable, List, Optional, Tuple

from Organisim import Organism
from evoultion import EvolutionContext, advance_population, prepare_evolution

DEFAULT_TRAIT_NAMES = ["Camouflage", "Metabolism", "Defense", "Senses"]

"""Runtime logic for orchestrating the habitat simulation loop."""

def _trait_penalties(gene_pool: List, ideal_traits: Iterable[float]) -> List[float]:
    """Weight individuals by how poorly they match the trophic targets."""
    if not gene_pool:
        return []

    ideal = list(ideal_traits or [])
    if not ideal:
        return [1.0] * len(gene_pool)

    penalties: List[float] = []
    for genome in gene_pool:
        try:
            genome_values = list(genome)
        except TypeError:
            genome_values = [genome]

        delta = 0.0
        harsh_excess = 0.0
        for gene_value, target in zip(genome_values, ideal):
            diff = abs(gene_value - target)
            delta += diff
            if diff > 0.35:
                harsh_excess += (diff - 0.35)

        # Harshly punish genomes with traits far from ideal
        penalty = delta * (1.0 + 4.0 * harsh_excess)
        penalties.append(max(penalty, 1e-6))

    return penalties


def _apply_weighted_deaths(gene_pool: List, ideal_traits: Iterable[float], kill_count: int) -> List:
    """Remove individuals using a roulette wheel scaled by trait penalties."""
    if kill_count <= 0 or not gene_pool:
        return gene_pool
 
    survivors = list(gene_pool)
    for _ in range(min(kill_count, len(survivors))):
        weights = _trait_penalties(survivors, ideal_traits)
        total = sum(weights)
        if total <= 0:
            index = random.randrange(len(survivors))
        else:
            threshold = random.random() * total
            running = 0.0
            index = len(survivors) - 1
            for idx, weight in enumerate(weights):
                running += weight
                if threshold <= running:
                    index = idx
                    break
        survivors.pop(index)

    return survivors


def _average_genome(gene_pool: List) -> List[float]:
    """Return the mean value for each gene position in the population."""
    if not gene_pool:
        return []

    totals: List[float] = []
    counts: List[int] = []
    for genome in gene_pool:
        try:
            values = list(genome)
        except TypeError:
            values = [genome]

        if len(values) > len(totals):
            totals.extend(0.0 for _ in range(len(values) - len(totals)))
            counts.extend(0 for _ in range(len(values) - len(counts)))

        for index, value in enumerate(values):
            totals[index] += float(value)
            counts[index] += 1

    return [
        round(total / count, 4) if count else 0.0
        for total, count in zip(totals, counts)
    ]


def resolvePredation(organism_lookup, cycle_summary):
    level_lookup = SIMULATION_STATE.get("level_lookup", {})
    relations_map = _relations_lookup()
    behavior_map = _behavior_lookup()

    for organism in organism_lookup.values():
        genes = list(organism.getGenes() or [])
        population_size = len(genes)
        if population_size == 0:
            continue

        ideal_traits = organism.getEffectiveIdealTraits()
        level_id = level_lookup.get(organism.getId())
        relations = relations_map.get(level_id, {"prey": [], "predators": []})
        prey_levels = relations.get("prey", [])
        behavior = behavior_map.get(organism.id, {})
        prey_ids = behavior.get("prey_ids", [])

        catches_made = organism.getCaughtPreyCount()
        times_caught = organism.getTimesCaught()

        starvation_rate = 0.0
        if prey_levels or prey_ids:
            if catches_made <= 0:
                starvation_rate = 0.6  # harsh penalty for failing to hunt
            elif catches_made == 1:
                starvation_rate = 0.1  # minimal attrition once fed
            elif catches_made == 5: #reward good predation
                starvation_rate = 0.01
            else:
                starvation_rate = 0.05  # tiny attrition even for successful predators

        if starvation_rate > 0.0 and population_size:
            losses = int(round(population_size * starvation_rate))
            genes = _apply_weighted_deaths(genes, ideal_traits, losses)
            population_size = len(genes)

        predation_rate = 0.0
        if times_caught > 0 and population_size:
            if times_caught < 5:
                predation_rate = min(0.02 * times_caught, 0.08)
            else:
                predation_rate = min(0.08 + 0.06 * (times_caught - 4), 0.6)

        if predation_rate > 0.0 and population_size:
            losses = int(round(population_size * predation_rate))
            genes = _apply_weighted_deaths(genes, ideal_traits, losses)

        organism.setGenes(genes)
        organism.setSize(len(genes))

    return 1


def _advance_evolution_cycle() -> None:
    """Sync organism genes with evolution state and advance each trophic level."""
    evolution_state = SIMULATION_STATE.get("evolution") or {}
    if not evolution_state:
        return

    organism_lookup = SIMULATION_STATE.get("organisms", {})
    level_lookup = SIMULATION_STATE.get("level_lookup", {})

    for level_id, data in evolution_state.items():
        population = data.get("population")
        context = data.get("context")
        generations = data.get("generations_per_cycle", 1)
        if population is None or context is None:
            continue

        members = [
            organism
            for organism in organism_lookup.values()
            if level_lookup.get(organism.id) == level_id
        ]
        if not members:
            population.clear()
            continue

        # Capture current distribution after predation.
        share_values = [len(member.getGenes() or []) for member in members]
        aggregated: List = []
        for member in members:
            aggregated.extend(member.getGenes() or [])

        population[:] = aggregated
        override_targets = None
        for member in members:
            effective_traits = member.getEffectiveIdealTraits()
            if effective_traits:
                override_targets = tuple(effective_traits)
                break
        context.target_traits_override = override_targets
        if not population:
            for member in members:
                member.setGenes([])
                member.setSize(0)
            continue

        if generations:
            advance_population(population, context, generations=generations)

        total_population = len(population)
        if total_population == 0:
            for member in members:
                member.setGenes([])
                member.setSize(0)
            continue

        total_shares = sum(share_values)
        if total_shares <= 0:
            share_values = [1 for _ in members]
            total_shares = len(share_values) or 1

        counts = []
        for share in share_values:
            fraction = share / total_shares if total_shares else 0.0
            counts.append(int(round(total_population * fraction)))

        allocated = sum(counts)
        idx = 0
        while allocated != total_population and members:
            slot = idx % len(counts)
            if allocated < total_population:
                counts[slot] += 1
                allocated += 1
            else:
                if counts[slot] > 0:
                    counts[slot] -= 1
                    allocated -= 1
            idx += 1
            if idx > len(counts) * 8:
                break

        population_index = 0
        for member, count in zip(members, counts):
            take = min(count, len(population) - population_index)
            assigned = []
            if take > 0:
                assigned = list(population[population_index : population_index + take])
                population_index += take
            member.setGenes(assigned)
            member.setSize(len(assigned))

        if population_index < len(population) and members:
            extras = list(population[population_index:])
            if extras:
                richest = max(
                    members,
                    key=lambda organism: len(organism.getGenes() or []), #returns len(organism.getGenes) if existent if not len([]) which is 0
                ) 
                updated = list(richest.getGenes() or [])
                updated.extend(extras)
                richest.setGenes(updated)
                richest.setSize(len(updated))

DEFAULT_BIOME_ID = "ocean"

LEVEL_ORDER = [
    "producers",
    "primary-consumers",
    "secondary-consumers",
    "tertiary-consumers",
    "apex",
]

# Shared simulation/trait settings reused across all biomes.
BASE_LEVEL_SETTINGS: Dict[str, Dict] = {
    "producers": {
        "id": "producers",
        "name": "Primary Producers",
        "trait_names": DEFAULT_TRAIT_NAMES,
        "simulation": {
            "seed": 1024,
            "population_size": 160,
            "target_traits": [0.05, 0.5, 0.4, 0.9],
            "generations": 30,
            "min_population_size": 120,
            "max_population_size": 240,
            "immigration_rate": 0.25,
            "immigration_chance": 0.55,
            "immigration_variation": 0.35,
            "fecundity": 1.25,
            "fecundity_variation": 0.20,
        },
    },
    "primary-consumers": {
        "id": "primary-consumers",
        "name": "Primary Consumers",
        "trait_names": DEFAULT_TRAIT_NAMES,
        "simulation": {
            "seed": 2048,
            "population_size": 110,
            "target_traits": [0.35, 0.55, 0.15, 0.8],
            "generations": 28,
            "min_population_size": 80,
            "max_population_size": 170,
            "immigration_rate": 0.22,
            "immigration_chance": 0.5,
            "immigration_variation": 0.3,
            "fecundity": 1.15,
            "fecundity_variation": 0.18,
        },
    },
    "secondary-consumers": {
        "id": "secondary-consumers",
        "name": "Secondary Consumers",
        "trait_names": DEFAULT_TRAIT_NAMES,
        "simulation": {
            "seed": 4096,
            "population_size": 75,
            "target_traits": [0.45, 0.6, 0.25, 0.75],
            "generations": 26,
            "min_population_size": 55,
            "max_population_size": 120,
            "immigration_rate": 0.18,
            "immigration_chance": 0.45,
            "immigration_variation": 0.25,
            "fecundity": 1.05,
            "fecundity_variation": 0.15,
        },
    },
    "tertiary-consumers": {
        "id": "tertiary-consumers",
        "name": "Tertiary Consumers",
        "trait_names": DEFAULT_TRAIT_NAMES,
        "simulation": {
            "seed": 8192,
            "population_size": 45,
            "target_traits": [0.01, 0.7, 0.6, 0.75],
            "generations": 24,
            "min_population_size": 30,
            "max_population_size": 80,
            "immigration_rate": 0.14,
            "immigration_chance": 0.4,
            "immigration_variation": 0.22,
            "fecundity": 0.95,
            "fecundity_variation": 0.12,
        },
    },
    "apex": {
        "id": "apex",
        "name": "Apex Predator",
        "trait_names": DEFAULT_TRAIT_NAMES,
        "simulation": {
            "seed": 16384,
            "population_size": 25,
            "target_traits": [0.7, 0.85, 0.45, 0.3],
            "generations": 22,
            "min_population_size": 15,
            "max_population_size": 45,
            "immigration_rate": 0.08,
            "immigration_chance": 0.35,
            "immigration_variation": 0.18,
            "fecundity": 0.85,
            "fecundity_variation": 0.1,
        },
    },
}

# length of each generation
MAX_CYCLE_STEPS = 30

#predators can out-compete prey
DEFAULT_SPEED_BY_LEVEL = {
    "apex": 3,
    "tertiary-consumers": 2,
    "secondary-consumers": 2,
    "primary-consumers": 2,
    "producers": 2,
}

# Random move jitter keeps paths from looking overly deterministic.
RANDOM_DIRECTION_CHANCE = 0.5

DEFAULT_TROPHIC_RELATIONS = {
    "producers": {"prey": [], "predators": ["primary-consumers"]},
    "primary-consumers": {"prey": ["producers"], "predators": ["secondary-consumers"]},
    "secondary-consumers": {"prey": ["primary-consumers", "producers"], "predators": ["tertiary-consumers", "apex"]},
    "tertiary-consumers": {"prey": ["secondary-consumers", "primary-consumers"], "predators": ["apex"]},
    "apex": {"prey": ["tertiary-consumers", "secondary-consumers"], "predators": []},
}

OCEAN_ORGANISM_BEHAVIORS: Dict[str, Dict[str, List[str]]] = {
    "consumer-1": {"prey_ids": ["producer-2", "producer-1"]},  # ex. Shrimp Swarm eats alagage and plankton
    "consumer-2": {"prey_ids": ["producer-2", "producer-1"]},  # ex. Krill Cloud eats alage and plankton
    "predator-2": {"prey_ids": ["consumer-1", "consumer-2"]},  # ex. Jellyfish Bloom eats krill and shrimp
    "predator-3": {"prey_ids": ["predator-1"]},  # ex. Seal Pod eats Lobster 
    "predator-4": {"prey_ids": ["predator-2"]},  # ex. Whale Shark eats Jellyfish Bloom
    "apex" : {"prey" : ["predator-3", "predator-4"]} #ex. orca eats Whale sharks and seals
}

RAINFOREST_ORGANISM_BEHAVIORS: Dict[str, Dict[str, List[str]]] = {
    "rf-consumer-1": {"prey_ids": ["rf-producer-1", "rf-producer-2"]},
    "rf-consumer-2": {"prey_ids": ["rf-producer-1", "rf-producer-2"]},
    "rf-predator-1": {"prey_ids": ["rf-consumer-1", "rf-consumer-2"]},
    "rf-predator-2": {"prey_ids": ["rf-consumer-2"]},
    "rf-predator-3": {"prey_ids": ["rf-predator-1", "rf-predator-2"]},
    "rf-predator-4": {"prey_ids": ["rf-predator-1", "rf-predator-2", "rf-consumer-1"]},
    "rf-apex-1": {"prey_ids": ["rf-predator-3", "rf-predator-4"]},
}

BIOME_PRESETS: Dict[str, Dict] = {
    "ocean": {
        "id": "ocean",
        "name": "Ocean Biome",
        "map": {"rows": 12, "cols": 16, "labels": []},
        "trait_names": ["Buoyancy", "Filter Efficiency", "Armor", "Echo Sensing"],
        "organisms": {
            "producers": [
                {"id": "producer-1", "name": "Kelp Forest", "row": 1, "col": 4, "image": "images/sprites/ocean/alage.png", "share": 0.35, "moves": False, "trait_names": ["Frond Growth", "Sunlight Capture", "Holdfast Strength", "Wave Tolerance"]},
                {"id": "producer-2", "name": "Plankton Bloom", "row": 3, "col": 8, "image": "images/sprites/ocean/plankton.png", "share": 0.65, "trait_names": ["Drift Control", "Reproduction Rate", "Nutrient Uptake", "Light Sensitivity"]},
            ],
            "primary-consumers": [
                {"id": "consumer-1", "name": "Shrimp Swarm", "row": 4, "col": 8, "image": "images/sprites/ocean/shrimp.png", "share": 0.55, "trait_names": ["Shell Thickness", "Filter Appendages", "Burrow Speed", "Predator Awareness"]},
                {"id": "consumer-2", "name": "Krill Cloud", "row": 7, "col": 5, "image": "images/sprites/ocean/krill.png", "share": 0.45, "trait_names": ["Schooling Cohesion", "Molting Rate", "Filter Efficiency", "Light Response"]},
            ],
            "secondary-consumers": [
                {"id": "predator-1", "name": "Lobster Patrol", "row": 6, "col": 11, "image": "images/sprites/ocean/lobster.png", "share": 0.4, "trait_names": ["Claw Strength", "Carapace Armor", "Scuttle Speed", "Chemoreception"]},
                {"id": "predator-2", "name": "Jellyfish Bloom", "row": 10, "col": 2, "image": "images/sprites/ocean/jellyfish.png", "share": 0.6, "trait_names": ["Tentacle Length", "Nematocyst Potency", "Bell Pulsing", "Current Riding"]},
            ],
            "tertiary-consumers": [
                {"id": "predator-3", "name": "Seal Pod", "row": 11, "col": 12, "image": "images/sprites/ocean/seal.png", "share": 0.6, "trait_names": ["Blubber Thickness", "Dive Depth", "Flipper Power", "Echolocation"]},
                {"id": "predator-4", "name": "Whale Shark Pair", "row": 6, "col": 5, "image": "images/sprites/ocean/whale-shark.png", "share": 0.4, "trait_names": ["Gill Filtering", "Mouth Gape", "Cruise Endurance", "Thermoregulation"]},
            ],
            "apex": [
                {"id": "apex-1", "name": "Orca Pod", "row": 8, "col": 12, "image": "images/sprites/ocean/orca.png", "share": 1.0, "trait_names": ["Sonar Precision", "Pack Coordination", "Burst Speed", "Bite Force"]},
            ],
        },
        "behaviors": OCEAN_ORGANISM_BEHAVIORS,
        "speed_by_level": DEFAULT_SPEED_BY_LEVEL,
        "relations": DEFAULT_TROPHIC_RELATIONS,
    },
    "rainforest": {
        "id": "rainforest",
        "name": "Rainforest Biome",
        "map": {"rows": 12, "cols": 16, "labels": []},
        "trait_names": ["Canopy Camouflage", "Metabolism", "Defense/Venom", "Senses"],
        "organisms": {
            "producers": [
                {"id": "rf-producer-1", "name": "Bamboo Grove", "row": 2, "col": 3, "image": "images/sprites/rainforest/bamboo.png", "share": 0.55, "moves": False, "trait_names": ["Culm Growth", "Canopy Reach", "Root Spread", "Water Storage"]},
                {"id": "rf-producer-2", "name": "Coconut Cluster", "row": 5, "col": 10, "image": "images/sprites/rainforest/coconut.png", "share": 0.45, "moves": False, "trait_names": ["Light Capture", "Fruit Yield", "Salt Tolerance", "Wind Resilience"]},
            ],
            "primary-consumers": [
                {"id": "rf-consumer-1", "name": "Aphid Swarm", "row": 4, "col": 6, "image": "images/sprites/rainforest/aphid.png", "share": 0.5, "trait_names": ["Sap Intake", "Reproduction Rate", "Wing Development", "Ant Signaling"]},
                {"id": "rf-consumer-2", "name": "Spider Mite Cluster", "row": 7, "col": 9, "image": "images/sprites/rainforest/spidermite.png", "share": 0.5, "trait_names": ["Web Density", "Leaf Hiding", "Egg Survival", "Dispersal Speed"]},
            ],
            "secondary-consumers": [
                {"id": "rf-predator-1", "name": "Poison Dart Frog", "row": 6, "col": 5, "image": "images/sprites/rainforest/poisondartfrog.png", "share": 0.55, "trait_names": ["Skin Toxin", "Tongue Snap", "Moisture Retention", "Camouflage"]},
                {"id": "rf-predator-2", "name": "Tarantula Ambush", "row": 9, "col": 4, "image": "images/sprites/rainforest/tarantula.png", "share": 0.45, "trait_names": ["Venom Potency", "Silk Strength", "Pounce Speed", "Vibration Sense"]},
            ],
            "tertiary-consumers": [
                {"id": "rf-predator-3", "name": "Ocelot Patrol", "row": 10, "col": 13, "image": "images/sprites/rainforest/ocelot.png", "share": 0.5, "trait_names": ["Stealth Stalk", "Climbing Grip", "Night Vision", "Leap Power"]},
                {"id": "rf-predator-4", "name": "Canopy Anaconda", "row": 5, "col": 14, "image": "images/sprites/rainforest/anaconda.png", "share": 0.5, "trait_names": ["Constriction Force", "Heat Sensing", "Branch Balance", "Ambush Patience"]},
            ],
            "apex": [
                {"id": "rf-apex-1", "name": "Jaguar Stalk", "row": 8, "col": 12, "image": "images/sprites/rainforest/jaguar.png", "share": 1.0, "trait_names": ["Bite Force", "Swim Ability", "Camouflage", "Sprint Speed"]},
            ],
        },
        "behaviors": RAINFOREST_ORGANISM_BEHAVIORS,
        "speed_by_level": DEFAULT_SPEED_BY_LEVEL,
        "relations": DEFAULT_TROPHIC_RELATIONS,
    },
}

STATE_LOCK: Lock = Lock()
SIMULATION_STATE: Dict = {
    "organisms": {},
    "level_lookup": {},
    "home_positions": {},
    "grid": {"rows": 0, "cols": 0},
    "cycle": 0,
    "evolution": {},
    "biome_id": DEFAULT_BIOME_ID,
    "biome_config": None,
    "relations": DEFAULT_TROPHIC_RELATIONS,
    "speed_by_level": DEFAULT_SPEED_BY_LEVEL,
    "behaviors": OCEAN_ORGANISM_BEHAVIORS,
}

STATE_LOG_PATH = Path(__file__).resolve().parent.parent / "simulation_state.json"

def _compose_biome_config(preset: Dict) -> Dict:
    """Build a full biome config by merging shared level settings with biome organisms."""
    resolved = copy.deepcopy(preset)
    organisms_by_level = resolved.get("organisms", {})
    trait_names_override = resolved.get("trait_names")

    trophic_levels: List[Dict] = []
    for level_id in LEVEL_ORDER:
        base_level = copy.deepcopy(BASE_LEVEL_SETTINGS.get(level_id, {}))
        base_level["trait_names"] = trait_names_override or base_level.get("trait_names") or DEFAULT_TRAIT_NAMES
        base_level["organisms"] = copy.deepcopy(organisms_by_level.get(level_id, []))
        trophic_levels.append(base_level)

    resolved["trophic_levels"] = trophic_levels
    resolved["map"] = copy.deepcopy(resolved.get("map", {"rows": 12, "cols": 16, "labels": []}))
    resolved["relations"] = copy.deepcopy(resolved.get("relations", DEFAULT_TROPHIC_RELATIONS))
    resolved["speed_by_level"] = copy.deepcopy(resolved.get("speed_by_level", DEFAULT_SPEED_BY_LEVEL))
    resolved["behaviors"] = copy.deepcopy(resolved.get("behaviors", {}))
    return resolved

def _get_biome_config(biome_id: Optional[str]) -> Dict:
    """Return a deep copy of the biome preset so mutations stay scoped."""
    requested = biome_id or SIMULATION_STATE.get("biome_id") or DEFAULT_BIOME_ID
    cached_config = SIMULATION_STATE.get("biome_config") or {}

    if cached_config.get("id") == requested:
        return copy.deepcopy(cached_config)

    fallback = BIOME_PRESETS.get(DEFAULT_BIOME_ID, {})
    base = BIOME_PRESETS.get(requested, fallback)
    return _compose_biome_config(base or fallback)


def _relations_lookup() -> Dict[str, Dict[str, List[str]]]:
    return SIMULATION_STATE.get("relations") or DEFAULT_TROPHIC_RELATIONS


def _speed_lookup() -> Dict[str, int]:
    return SIMULATION_STATE.get("speed_by_level") or DEFAULT_SPEED_BY_LEVEL


def _behavior_lookup() -> Dict[str, Dict[str, List[str]]]:
    return SIMULATION_STATE.get("behaviors") or {}


def _run_simulation(settings: Dict) -> Tuple[List, EvolutionContext]:
    """Configure evolution for a trophic level and run the initial generations."""
    seed = settings.get("seed")
    simulation_kwargs = {key: value for key, value in settings.items() if key != "seed"}
    generations = simulation_kwargs.pop("generations", 0)
    previous_state = None
    if seed is not None:
        previous_state = random.getstate()
        random.seed(seed)

    try:
        population, context = prepare_evolution(**simulation_kwargs)
        if generations:
            advance_population(population, context, generations=generations)
        return population, context
    finally:
        if previous_state is not None:
            random.setstate(previous_state)


def build_trophic_levels(
    biome_config: Optional[Dict] = None,
) -> Tuple[List[Dict], Dict[str, Dict[str, object]]]:
    """Run GA simulations for each trophic level and build organism metadata."""
    config = biome_config or _get_biome_config(SIMULATION_STATE.get("biome_id"))
    trophic_levels: List[Dict] = []
    evolution_state: Dict[str, Dict[str, object]] = {}

    for level in config.get("trophic_levels", []):
        population, context = _run_simulation(level["simulation"])
        population_count = len(population)
        organism_configs = level["organisms"]
        level_id = level["id"]
        level_trait_names = level.get("trait_names") or DEFAULT_TRAIT_NAMES

        evolution_state[level_id] = {
            "population": population,
            "context": context,
            "generations_per_cycle": level["simulation"].get("generations_per_cycle", 1),
        }

        organisms: List[Organism] = []
        if population_count <= 0:
            organisms = [
                Organism(
                    organism_cfg["id"],
                    organism_cfg["name"],
                    organism_cfg["row"],
                    organism_cfg["col"],
                    0,
                    organism_cfg["image"],
                    moves=organism_cfg.get("moves", True),
                    ideal_traits=level["simulation"].get("target_traits"),
                    user_ideal_traits=organism_cfg.get("user_ideal_traits"),
                    trait_names=organism_cfg.get("trait_names", level_trait_names),
                )
                for organism_cfg in organism_configs
            ]
        else:
            shares = [organism.get("share", 1.0) for organism in organism_configs]
            share_total = sum(shares) if any(shares) else float(len(organism_configs) or 1)
            counts: List[int] = []

            for share in shares:
                fraction = (share / share_total) if share_total else 0.0
                estimated = int(round(population_count * fraction))
                counts.append(max(1, estimated))

            allocated = sum(counts)
            idx = 0
            while allocated != population_count and organism_configs:
                slot = idx % len(counts)
                if allocated < population_count:
                    counts[slot] += 1
                    allocated += 1
                else:
                    if counts[slot] > 1:
                        counts[slot] -= 1
                        allocated -= 1
                idx += 1
                if idx > len(counts) * 8:
                    break

            population_index = 0
            for index, organism_cfg in enumerate(organism_configs):
                requested = counts[index] if index < len(counts) else 0
                take = min(requested, population_count - population_index)
                assigned = []
                if take > 0:
                    assigned = list(population[population_index : population_index + take])
                    population_index += take

                organism = Organism(
                    organism_cfg["id"],
                    organism_cfg["name"],
                    organism_cfg["row"],
                    organism_cfg["col"],
                    len(assigned),
                    organism_cfg["image"],
                    moves=organism_cfg.get("moves", True),
                    ideal_traits=level["simulation"].get("target_traits"),
                    user_ideal_traits=organism_cfg.get("user_ideal_traits"),
                    trait_names=organism_cfg.get("trait_names", level_trait_names),
                )
                organism.setGenes(assigned)
                organism.setSize(len(assigned))
                organisms.append(organism)

            if population_index < population_count and organisms:
                extras = list(population[population_index:])
                if extras:
                    first = organisms[0]
                    updated = list(first.getGenes() or [])
                    updated.extend(extras)
                    first.setGenes(updated)
                    first.setSize(len(updated))

        trophic_levels.append(
            {
                "id": level_id,
                "name": level["name"],
                "organisms": organisms,
                "population_count": population_count,
            }
        )

    return trophic_levels, evolution_state


def initialize_simulation_state(
    trophic_levels: List[Dict],
    map_grid: Dict,
    evolution_state: Dict[str, Dict[str, object]],
    *,
    biome_config: Optional[Dict] = None,
) -> None:
    """Seed the shared simulation state with organisms and map geometry."""
    with STATE_LOCK:
        organism_lookup = {}
        level_lookup = {}
        home_positions = {}
        for level in trophic_levels:
            level_id = level["id"]
            for organism in level["organisms"]:
                organism.resetCycle()
                organism_lookup[organism.id] = organism
                level_lookup[organism.id] = level_id
                home_positions[organism.id] = (organism.getY(), organism.getX())

        SIMULATION_STATE["organisms"] = organism_lookup
        SIMULATION_STATE["level_lookup"] = level_lookup
        SIMULATION_STATE["home_positions"] = home_positions
        SIMULATION_STATE["grid"] = {
            "rows": map_grid["rows"],
            "cols": map_grid["cols"],
        }
        SIMULATION_STATE["cycle"] = 0
        SIMULATION_STATE["evolution"] = evolution_state
        resolved_biome = biome_config or _get_biome_config(DEFAULT_BIOME_ID)
        SIMULATION_STATE["biome_config"] = resolved_biome
        SIMULATION_STATE["biome_id"] = resolved_biome.get("id", SIMULATION_STATE.get("biome_id", DEFAULT_BIOME_ID))
        SIMULATION_STATE["relations"] = resolved_biome.get("relations") or BIOME_PRESETS[DEFAULT_BIOME_ID]["relations"]
        SIMULATION_STATE["speed_by_level"] = resolved_biome.get("speed_by_level") or BIOME_PRESETS[DEFAULT_BIOME_ID]["speed_by_level"]
        SIMULATION_STATE["behaviors"] = resolved_biome.get("behaviors") or BIOME_PRESETS[DEFAULT_BIOME_ID]["behaviors"]


def replace_first_species(
    level_id: str,
    *,
        name: str,
        image_path: Optional[str] = None,
        moves: Optional[bool] = None,
        user_ideal_traits: Optional[list] = None,
) -> bool:
    """Replace the first organism entry for a trophic level with a new species."""
    if not level_id or not name:
        return False

    with STATE_LOCK:
        biome_config = SIMULATION_STATE.get("biome_config") or _get_biome_config(SIMULATION_STATE.get("biome_id"))
        trophic_config = biome_config.get("trophic_levels") if isinstance(biome_config, dict) else None
        target_level = None
        for level in trophic_config or []:
            if level.get("id") == level_id:
                target_level = level
                break

        if not target_level:
            return False

        organisms = target_level.get("organisms") or []
        if not organisms:
            return False

        primary = organisms[0]
        organism_id = primary.get("id")
        primary["name"] = name
        if image_path:
            primary["image"] = image_path
        if moves is not None:
            primary["moves"] = moves
        if user_ideal_traits is not None:
            primary["user_ideal_traits"] = user_ideal_traits

        organism_lookup = SIMULATION_STATE.get("organisms", {})
        organism = organism_lookup.get(organism_id)
        if organism:
            organism.name = name
            if image_path:
                organism.imagePath = image_path
            if moves is not None:
                organism.setMoves(moves)
            if user_ideal_traits is not None:
                organism.setUserIdealTraits(user_ideal_traits)

        SIMULATION_STATE["biome_config"] = biome_config
        return True

def _clamp_step(value: int) -> int:
    """Normalize a delta to -1, 0, or 1 so movement stays grid-aligned."""
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _direction_towards(source: Organism, target: Organism) -> Tuple[int, int]:
    """Return the single-step direction vector from source to target."""
    row_delta = target.getY() - source.getY()
    col_delta = target.getX() - source.getX()
    return _clamp_step(row_delta), _clamp_step(col_delta)


def _direction_from_levels(origin: Organism, level_ids: List[str], toward: bool) -> Tuple[int, int]:
    """Pick the direction toward or away from the nearest organism in the supplied levels."""
    if not level_ids:
        return 0, 0

    closest: Tuple[int, int] = (0, 0)
    closest_distance = None

    for candidate in SIMULATION_STATE["organisms"].values():
        if candidate.id == origin.id:
            continue
        candidate_level = SIMULATION_STATE["level_lookup"].get(candidate.id)
        if candidate_level not in level_ids:
            continue

        direction = _direction_towards(origin, candidate)
        if direction == (0, 0):
            closest = direction
            closest_distance = 0
            break

        manhattan = abs(candidate.getY() - origin.getY()) + abs(candidate.getX() - origin.getX())
        if closest_distance is None or manhattan < closest_distance:
            closest = direction
            closest_distance = manhattan

    if closest_distance is None:
        return 0, 0

    return closest if toward else (-closest[0], -closest[1])


def _direction_from_targets(origin, target_ids, toward):   
    """Pick the direction toward or away from specific organism ids."""
    if not target_ids:
        return 0, 0

    closest: Tuple[int, int] = (0, 0)
    closest_distance = None

    for target_id in target_ids:
        candidate = SIMULATION_STATE["organisms"].get(target_id)
        if candidate is None or candidate.id == origin.id:
            continue

        direction = _direction_towards(origin, candidate)
        if direction == (0, 0):
            closest = direction
            closest_distance = 0
            break

        manhattan = abs(candidate.getY() - origin.getY()) + abs(candidate.getX() - origin.getX())
        if closest_distance is None or manhattan < closest_distance:
            closest = direction
            closest_distance = manhattan

    if closest_distance is None:
        return 0, 0

    return closest if toward else (-closest[0], -closest[1])


def _calculate_move_delta(organism: Organism, relations: Dict[str, List[str]], current_step: int, speed: int):
    """Blend prey pursuit, predator avoidance, and randomness into a movement vector."""
    prey_levels = relations.get("prey", []) 
    predator_levels = relations.get("predators", [])

    behavior = _behavior_lookup().get(organism.id, {})
    specific_prey_ids = behavior.get("prey_ids", [])
    specific_predator_ids = behavior.get("predator_ids", [])

    #calling helper function

    prey_direction = _direction_from_targets(organism, specific_prey_ids, toward=True)
    if prey_direction == (0, 0):
        prey_direction = _direction_from_levels(organism, prey_levels, toward=True)

    predator_direction = _direction_from_targets(organism, specific_predator_ids, toward=False)
    if predator_direction == (0, 0):
        predator_direction = _direction_from_levels(organism, predator_levels, toward=False)

    prey_weight = max(2, speed) if (prey_levels or specific_prey_ids) else 1
    if specific_prey_ids:
        prey_weight = max(prey_weight, speed + 1)

    if (
        (prey_levels or specific_prey_ids)
        and not organism.hasCaughtPrey()
        and current_step >= MAX_CYCLE_STEPS - 1
    ):
        base_row, base_col = prey_direction
    else:
        base_row = prey_direction[0] * prey_weight + predator_direction[0]
        base_col = prey_direction[1] * prey_weight + predator_direction[1]

    if random.random() < RANDOM_DIRECTION_CHANCE:
        base_row += random.choice([-1, 0, 1])
    if random.random() < RANDOM_DIRECTION_CHANCE:
        base_col += random.choice([-1, 0, 1])

    row_step = _clamp_step(base_row)
    col_step = _clamp_step(base_col)

    if row_step == 0 and col_step == 0:
        row_step = random.choice([-1, 0, 1])
        col_step = random.choice([-1, 0, 1])
        if row_step == 0 and col_step == 0:
            row_step = random.choice([-1, 1])

    row_delta = max(-speed, min(speed, row_step * speed))
    col_delta = max(-speed, min(speed, col_step * speed))
    return row_delta, col_delta


def step_simulation() -> Dict[str, Iterable[Dict]]:
    """Advance the simulation one tick and report organism state updates."""
    with STATE_LOCK:
        organism_lookup = SIMULATION_STATE.get("organisms", {})
        if not organism_lookup:
            return {"organisms": [], "cycleComplete": False, "cycleSummary": []}

        grid = SIMULATION_STATE["grid"]
        relations_map = _relations_lookup()
        speed_map = _speed_lookup()
        planned_moves: List[Tuple[str, int, int]] = []

        for organism in organism_lookup.values():
            current_step = organism.getCycleSteps()
            if current_step >= MAX_CYCLE_STEPS:
                continue

            level_id = SIMULATION_STATE["level_lookup"].get(organism.id)
            relations = relations_map.get(level_id, {"prey": [], "predators": []})
            speed = speed_map.get(level_id, 1)

            row_delta = 0
            col_delta = 0
            if organism.canMove():
                row_delta, col_delta = _calculate_move_delta(organism, relations, current_step, speed)

            if row_delta or col_delta:
                new_row = organism.getY() + row_delta
                new_col = organism.getX() + col_delta

                new_row = max(1, min(grid["rows"], new_row))
                new_col = max(1, min(grid["cols"], new_col))

                if new_row != organism.getY() or new_col != organism.getX():
                    planned_moves.append((organism.id, new_row, new_col))

            organism.advanceCycle()

        for organism_id, new_row, new_col in planned_moves:
            organism = organism_lookup[organism_id]
            organism.setY(new_row)
            organism.setX(new_col)

        position_map: Dict[Tuple[int, int], List[Organism]] = {}
        for organism in organism_lookup.values():
            position_map.setdefault((organism.getY(), organism.getX()), []).append(organism)

        penalty_cache: Dict[str, float] = {}
        quality_cache: Dict[str, float] = {}

        def _penalty_for(organism: Organism) -> float:
            """Cache harsh penalty so capture odds reflect trait quality."""
            cached = penalty_cache.get(organism.id)
            if cached is not None:
                return cached
            penalties = _trait_penalties(
                organism.getGenes() or [],
                organism.getEffectiveIdealTraits(),
            )
            if not penalties:
                value = 0.0
            else:
                value = sum(penalties) / len(penalties)
            penalty_cache[organism.id] = value
            return value

        def _capture_quality(organism: Organism) -> float:
            """Translate penalties into a catch/escape skill score."""
            cached = quality_cache.get(organism.id)
            if cached is not None:
                return cached
            penalty = _penalty_for(organism)
            # If the population has no genes, treat quality as very poor.
            quality = 0.1 if not (organism.getGenes() or []) else 1.0 / (1.0 + penalty)
            bounded = max(0.01, min(0.99, quality))
            quality_cache[organism.id] = bounded
            return bounded

        for occupants in position_map.values():
            if len(occupants) < 2:
                continue
            occupant_levels = {
                organism.id: SIMULATION_STATE["level_lookup"].get(organism.id)
                for organism in occupants
            }
            for organism in occupants:
                level_id = occupant_levels.get(organism.id)
                relations = relations_map.get(level_id, {"prey": [], "predators": []})
                prey_levels = relations.get("prey", [])
                if organism.hasCaughtPrey():
                    continue
                behavior = _behavior_lookup().get(organism.id, {})
                prey_ids = behavior.get("prey_ids", [])
                if not prey_levels and not prey_ids:
                    continue
                caught_targets = [
                    other
                    for other in occupants
                    if other.id != organism.id
                    and (
                        (prey_levels and occupant_levels.get(other.id) in prey_levels)
                        or (prey_ids and other.id in prey_ids)
                    )
                ]
                if caught_targets:
                    predator_quality = _capture_quality(organism)
                    for prey in caught_targets:
                        prey_quality = _capture_quality(prey)
                        relative_edge = predator_quality / (predator_quality + prey_quality + 1e-9)
                        success_chance = max(0.01, min(0.95, relative_edge * predator_quality))
                        if random.random() < success_chance:
                            organism.incrementCaughtPrey()
                            prey.incrementTimesCaught()

        cycle_complete = all(
            organism.getCycleSteps() >= MAX_CYCLE_STEPS for organism in organism_lookup.values()
        )
        cycle_summary: List[Dict[str, bool]] = []
        cycle_index = SIMULATION_STATE.get("cycle", 0)

        if cycle_complete:
            cycle_summary = [
                {
                    "id": organism.id,
                    "caughtPrey": organism.hasCaughtPrey(),
                    "caughtPreyCount": organism.getCaughtPreyCount(),
                    "wasCaught": organism.wasCaught(),
                    "timesCaught": organism.getTimesCaught(),
                }
                for organism in organism_lookup.values()
            ]

            resolvePredation(organism_lookup, cycle_summary)
            _advance_evolution_cycle()

            home_positions = SIMULATION_STATE.get("home_positions", {})

            for organism in organism_lookup.values():
                home = home_positions.get(organism.id)
                if home:
                    organism.setY(home[0])
                    organism.setX(home[1])

        updates = []
        for organism in organism_lookup.values():
            genes = organism.getGenes() or []
            population_size = len(genes)
            average_genome = _average_genome(genes)
            if population_size != organism.getSize():
                organism.setSize(population_size)
            updates.append(
                {
                    "id": organism.id,
                    "row": organism.getY(),
                    "col": organism.getX(),
                    "caughtPrey": organism.hasCaughtPrey(),
                    "caughtPreyCount": organism.getCaughtPreyCount(),
                    "wasCaught": organism.wasCaught(),
                    "timesCaught": organism.getTimesCaught(),
                    "cycleStep": organism.getCycleSteps(),
                    "canMove": organism.canMove(),
                    "population": population_size,
                    "averageGenome": average_genome,
                    "traitNames": organism.getTraitNames(),
                }
            )

        if cycle_complete:

            for organism in organism_lookup.values():
                organism.resetCycle()
            SIMULATION_STATE["cycle"] = cycle_index + 1

        return {
            "organisms": updates,
            "cycleComplete": cycle_complete,
            "cycleSummary": cycle_summary,
            "cycleIndex": cycle_index,
        }


def persist_simulation_state(cycle, summary, organisms) -> None:
    """Append or replace historical cycle state on disk for later inspection."""
    entry = {
        "cycle": cycle,
        "summary": summary,
        "organisms": organisms,
    }

    with STATE_LOCK:
        history: List[Dict] = []
        if STATE_LOG_PATH.exists():
            try:
                history = json.loads(STATE_LOG_PATH.read_text())
                if not isinstance(history, list):
                    history = []
            except (OSError, json.JSONDecodeError):
                history = []

        filtered = [item for item in history if item.get("cycle") != cycle]
        filtered.append(entry)
        STATE_LOG_PATH.write_text(json.dumps(filtered, indent=2))


def reset_simulation_history() -> None:
    """Clear the on-disk simulation history."""
    with STATE_LOCK:
        STATE_LOG_PATH.write_text(json.dumps([], indent=2))
