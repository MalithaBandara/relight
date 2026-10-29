"""Damage photos and drone clips: Muse Spark says what broke, SAM 3.1 measures it.

SAM 3.1 outlines the pole, the conductor and any tree. Using the pole as a ruler
(Sri Lankan distribution poles are ~9 m above ground), the gap between the lowest
point of the conductor and the ground becomes a clearance in metres: a wire below
the 5.5 m road clearance is a public hazard, whatever the photo caption says.
"""

from __future__ import annotations

from pathlib import Path

from . import config
from .models import ModelClient

POLE_HEIGHT_M = 9.0
ROAD_CLEARANCE_M = 5.5

PHOTO_SCHEMA = {
    "type": "object",
    "properties": {
        "damage": {"type": "string", "enum": ["none", "live_wire", "wire_down", "pole_down", "tree_on_line",
                                               "blown_fuse", "transformer_failure", "other"]},
        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
        "public_hazard": {"type": "boolean"},
        "description": {"type": "string"},
        "segment_prompts": {"type": "array", "items": {"type": "string"},
                            "description": "Short noun phrases naming objects to outline, e.g. 'utility pole'"},
    },
    "required": ["damage", "severity", "public_hazard", "description", "segment_prompts"],
}
PHOTO_SYSTEM = """You assess storm damage to electricity distribution lines from photos sent by customers
and crews. Say what is damaged, how severe it is, whether it endangers the public, and which objects
should be outlined to measure the damage (use short concrete noun phrases)."""


def _clearance_m(records: dict[str, list[dict]]) -> float | None:
    poles = [r for r in records.get("utility pole", []) if r.get("box")]
    wires = [r for r in records.get("power line", []) if r.get("box")]
    if not poles or not wires:
        return None
    pole = max(poles, key=lambda r: r["box"][3] - r["box"][1])
    x1, y1, x2, y2 = pole["box"]
    px_per_m = (y2 - y1) / POLE_HEIGHT_M
    if px_per_m <= 0:
        return None
    lowest_wire = max(w["box"][3] for w in wires)
    return round(max(y2 - lowest_wire, 0) / px_per_m, 1)


def analyse_photo(client: ModelClient, rel_path: str, truth_damage: str | None) -> dict:
    """Returns {damage, severity, public_hazard, description, clearance_m, objects, models, mock}."""
    path = config.ROOT / rel_path
    if not path.exists():
        return {"damage": truth_damage or "other", "severity": "high", "public_hazard": truth_damage == "live_wire",
                "description": f"(photo not added yet: {Path(rel_path).name})", "clearance_m": None,
                "objects": {}, "models": ["mock (ground truth)"], "mock": True}
    import base64
    import mimetypes
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    data_url = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
    content = [{"type": "text", "text": "Assess the damage in this photo."},
               {"type": "image_url", "image_url": {"url": data_url}}]
    info = client.spark_json(PHOTO_SYSTEM, content, PHOTO_SCHEMA, "DamagePhoto")
    models = ["Muse Spark"]
    if info is None:
        info = {"damage": truth_damage or "other", "severity": "high", "public_hazard": truth_damage == "live_wire",
                "description": "(mock) model output not cached", "segment_prompts": []}
        models = ["mock (ground truth)"]
    prompts = list(dict.fromkeys(["utility pole", "power line"] + info.get("segment_prompts", [])))[:4]
    records = {}
    for p in prompts:
        recs = client.segment_image(path, p)
        if recs is not None:
            records[p] = recs
    if records:
        models.append("SAM 3.1")
    clearance = _clearance_m(records)
    if clearance is not None and clearance < ROAD_CLEARANCE_M:
        info["public_hazard"] = True
    return {**{k: v for k, v in info.items() if k != "segment_prompts"}, "clearance_m": clearance,
            "objects": {p: [{"box": r["box"], "conf": r.get("conf")} for r in recs] for p, recs in records.items()},
            "image_size": next(((r["w"], r["h"]) for recs in records.values() for r in recs), None),
            "models": models, "mock": models[0].startswith("mock")}
