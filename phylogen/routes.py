from flask import Blueprint, render_template

from Organisim import Organism

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    map_grid = {
        "rows": 12,
        "cols": 16,
        "labels": [
            {"row": 2, "col": 4, "text": "Watering Hole"},
            {"row": 6, "col": 10, "text": "Nest"},
            {"row": 9, "col": 3, "text": "Food Storage"},
        ],
    }
    map_grid["label_lookup"] = {
    (label["row"]-1, label["col"]-1): label["text"] for label in map_grid["labels"]
    }


    trophic_levels = [
        {
            "id": "producers",
            "name": "Primary Producers",
            "organisms": [
                Organism("producer-1", "Alage", 1, 4, "../static/images/sprites/ocean/alage.png"),
                Organism("producer-2", "Grass Patch", 3, 8, "../static/images/sprites/ocean/plankton.webp"),
            ],
        },
        {
            "id": "primary-consumers",
            "name": "Primary Consumers",
            "organisms": [
                Organism("consumer-1", "Shrimp", 4, 8, "../static/images/sprites/ocean/shrimp.png"),
                Organism("consumer-2", "Krill", 7, 5, "../static/images/sprites/ocean/krill.png"),
            ],
        },
        {
            "id": "secondary-consumers",
            "name": "Secondary Consumers",
            "organisms": [
                Organism("predator-1", "Lobster", 6, 11, "../static/images/sprites/ocean/lobster.png"),
                Organism("predator-2", "Jellyfish", 10, 2, "../static/images/sprites/ocean/jellyfish.png"),
            ],
        },
        {
            "id": "tertiary-consumers",
            "name": "Tertiary Consumers",
            "organisms" :[
                Organism("predator-3", "Seal", 11, 12, "../static/images/sprites/ocean/seal.png"),
                Organism("predator-4", "Whale Shark", 6, 5, "../static/images/sprites/ocean/whale-shark.png"),
            ],
        },
        {
            "id": "apex",
            "name": "Apex Predator",
            "organisms": [
                Organism("apex-1", "Orca", 8, 12, "../static/images/sprites/ocean/orca.png"),
            ],
        },
    ]

    return render_template(
        "index.html",
        map_grid=map_grid,
        trophic_levels=trophic_levels,
    )
