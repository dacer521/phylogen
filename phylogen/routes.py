from flask import Blueprint, current_app, jsonify, render_template, request

from .simulation import (
    build_trophic_levels,
    initialize_simulation_state,
    persist_simulation_state,
    reset_simulation_history,
    step_simulation,
)

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    map_grid = {
        "rows": 12,
        "cols": 16,
        "labels": [
            # {"row": 2, "col": 4, "text": "Watering Hole"},
            # {"row": 6, "col": 10, "text": "Nest"},
            # {"row": 9, "col": 3, "text": "Food Storage"},
        ],
    }
    map_grid["label_lookup"] = {
        (label["row"] - 1, label["col"] - 1): label["text"] for label in map_grid["labels"]
    }

    trophic_levels, evolution_state = build_trophic_levels()
    initialize_simulation_state(trophic_levels, map_grid, evolution_state)

    return render_template(
        "index.html",
        map_grid=map_grid,
        trophic_levels=trophic_levels,
    )


@bp.route('/api/simulation/step', methods=['POST'])
def simulation_step():
    result = step_simulation()
    return jsonify(result)


@bp.route('/api/simulation/save', methods=['POST'])
def simulation_save():
    payload = request.get_json(silent=True) or {}
    cycle = payload.get("cycle")
    summary = payload.get("summary", [])
    organisms = payload.get("organisms", [])

    try:
        persist_simulation_state(cycle, summary, organisms)
        return jsonify({"status": "ok"})
    except OSError as exc:
        current_app.logger.exception("Failed to persist simulation state")
        return jsonify({"status": "error", "message": str(exc)}), 500


@bp.route('/api/simulation/reset', methods=['POST'])
def simulation_reset():
    try:
        reset_simulation_history()
        return jsonify({"status": "ok"})
    except OSError as exc:
        current_app.logger.exception("Failed to reset simulation history")
        return jsonify({"status": "error", "message": str(exc)}), 500
