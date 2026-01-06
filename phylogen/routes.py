from typing import Optional
from pathlib import Path
import uuid

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from .simulation import (
    SIMULATION_STATE,
    build_trophic_levels,
    DEFAULT_BIOME_ID,
    DEFAULT_TRAIT_NAMES,
    _get_biome_config,
    initialize_simulation_state,
    persist_simulation_state,
    replace_first_species,
    reset_simulation_history,
    step_simulation,
)

bp = Blueprint('main', __name__)

LEVEL_ALIAS_MAP = {
    "producer": "producers",
    "producers": "producers",
    "primary-consumer": "primary-consumers",
    "primary-consumers": "primary-consumers",
    "secondary-consumer": "secondary-consumers",
    "secondary-consumers": "secondary-consumers",
    "tertiary-consumer": "tertiary-consumers",
    "tertiary-consumers": "tertiary-consumers",
    "apex": "apex",
    "apex-predator": "apex",
    "apex predators": "apex",
}


def _normalize_level_id(raw_value: Optional[str]) -> Optional[str]:
    if not raw_value:
        return None
    key = raw_value.strip().lower()
    return LEVEL_ALIAS_MAP.get(key, key)


def _build_map_context(biome_id="ocean"):
    biome_config = _get_biome_config(biome_id)
    biome_name = biome_config.get("name", "Evolution Simulator")
    map_grid = biome_config.get("map", {"rows": 12, "cols": 16, "labels": []})
    map_grid["label_lookup"] = {
        (label["row"] - 1, label["col"] - 1): label["text"] for label in map_grid["labels"]
    }

    trophic_levels, evolution_state = build_trophic_levels(biome_config)
    initialize_simulation_state(trophic_levels, map_grid, evolution_state, biome_config=biome_config)

    return {
        "map_grid": map_grid,
        "trophic_levels": trophic_levels,
        "biome_name": biome_name,
        "biome_id": biome_config.get("id", biome_id),
    }


@bp.route('/')
def index():
    return render_template("index.html")


@bp.route('/ocean')
def ocean():
    context = _build_map_context("ocean")
    return render_template(
        "simulation.html",
        **context,
    )


@bp.route('/rainforest')
def rainforest():
    context = _build_map_context("rainforest")
    return render_template(
        "simulation.html",
        **context,
    )

@bp.route('/about')
def about():
    return render_template("about.html")


@bp.route('/species/define', methods=['GET', 'POST'])
def define_species():
    biome_id = request.values.get("biome") or DEFAULT_BIOME_ID
    biome_config = _get_biome_config(biome_id)
    biome_trait_names = biome_config.get("trait_names", DEFAULT_TRAIT_NAMES)
    next_url = request.values.get("next") or request.referrer
    if not next_url:
        if biome_id == "rainforest":
            next_url = url_for('main.rainforest')
        else:
            next_url = url_for('main.ocean')

    if request.method == 'POST':
        if SIMULATION_STATE.get("biome_id") != biome_id:
            map_grid = biome_config.get("map", {"rows": 12, "cols": 16, "labels": []})
            map_grid["label_lookup"] = {
                (label["row"] - 1, label["col"] - 1): label["text"] for label in map_grid["labels"]
            }
            trophic_levels, evolution_state = build_trophic_levels(biome_config)
            initialize_simulation_state(trophic_levels, map_grid, evolution_state, biome_config=biome_config)

        species_name = request.form.get("name", "").strip()
        species_level = _normalize_level_id(request.form.get("trophic_level"))
        moves_value = (request.form.get("moves") or "yes").strip().lower()
        is_mobile = moves_value not in ("no", "false", "0")

        user_ideal_traits = []
        for index, trait_name in enumerate(biome_trait_names):
            raw_value = request.form.get(f"target_trait_{index}")
            if raw_value is None or raw_value == "":
                continue
            try:
                numeric = float(raw_value)
            except (TypeError, ValueError):
                continue
            clamped = max(0.0, min(1.0, numeric))
            user_ideal_traits.append(clamped)

        if not user_ideal_traits:
            user_ideal_traits = None

        species_data = {
            "name": species_name,
            "trophic_level": species_level,
            "moves": is_mobile,
            "user_ideal_traits": user_ideal_traits,
        }

        image = request.files.get("species_image")
        image_path = None
        if image and image.filename:
            uploads_dir = Path(current_app.static_folder or "") / "uploads"
            try:
                uploads_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                current_app.logger.exception("Failed to create uploads directory at %s", uploads_dir)
                uploads_dir = None

            filename = secure_filename(image.filename)
            if not filename:
                filename = "species-image"

            if uploads_dir:
                unique_name = f"{uuid.uuid4().hex}_{filename}"
                destination = uploads_dir / unique_name
                try:
                    image.save(destination)
                    image_path = f"uploads/{unique_name}"
                except OSError:
                    current_app.logger.exception("Failed to save uploaded species image to %s", destination)

        if image_path:
            species_data["image_path"] = image_path

        current_app.logger.info("Received species definition: %s", species_data)

        if species_level:
            replaced = replace_first_species(
                species_level,
                name=species_name,
                image_path=image_path,
                moves=is_mobile,
                user_ideal_traits=user_ideal_traits,
            )
            if not replaced:
                current_app.logger.warning("Unable to replace organism for level '%s'", species_level)
        else:
            current_app.logger.warning("Custom species submitted without a trophic level selection")

        return redirect(next_url)

    return render_template(
        "define-species.html",
        next_url=next_url,
        trait_names=biome_trait_names,
        biome_id=biome_id,
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


@bp.route('/api/simulation/extinct', methods=['GET'])
def simulation_extinct():
    extinct = SIMULATION_STATE.get("extinct") or set()
    return jsonify({"extinct": list(extinct)})
