from flask import Blueprint, render_template

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
        (label["row"], label["col"]): label["text"] for label in map_grid["labels"]
    }

    trophic_levels = [
        {
            "id": "producers",
            "name": "Primary Producers",
            "organisms": [
                {"id": "producer-1", "name": "Algae Mat", "row": 2, "col": 4},
                {"id": "producer-2", "name": "Grass Patch", "row": 3, "col": 8},
            ],
        },
        {
            "id": "primary-consumers",
            "name": "Primary Consumers",
            "organisms": [
                {"id": "consumer-1", "name": "Grazing Herd", "row": 4, "col": 8},
                {"id": "consumer-2", "name": "Burrowers", "row": 7, "col": 5},
            ],
        },
        {
            "id": "secondary-consumers",
            "name": "Secondary Consumers",
            "organisms": [
                {"id": "predator-1", "name": "Pack Hunters", "row": 6, "col": 11},
                {"id": "predator-2", "name": "Scavengers", "row": 10, "col": 2},
            ],
        },
        {
            "id": "apex",
            "name": "Apex Predator",
            "organisms": [
                {"id": "apex-1", "name": "Alpha Predator", "row": 8, "col": 12},
            ],
        },
    ]

    return render_template(
        "index.html",
        map_grid=map_grid,
        trophic_levels=trophic_levels,
    )
