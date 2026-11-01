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


VIDEO_SCHEMA = {
    "type": "object",
    "properties": {
        **PHOTO_SCHEMA["properties"],
        "at_seconds": {"type": "number", "description": "Time in the clip where the damage is clearest"},
    },
    "required": PHOTO_SCHEMA["required"] + ["at_seconds"],
}
VIDEO_SYSTEM = """You assess storm damage to electricity distribution lines from short videos sent by customers,
crews and drone patrols. Say what is damaged, how severe it is, whether it endangers the public, when in the clip
the damage is clearest, and which objects should be tracked through the clip (use short concrete noun phrases)."""


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


TAG_SCHEMA = {
    "type": "object",
    "properties": {
        "readable": {"type": "boolean", "description": "true only if a pole number plate is legible"},
        "tag": {"type": ["string", "null"], "description": "The characters on the plate exactly as printed, or null"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "note": {"type": "string"},
    },
    "required": ["readable", "tag", "confidence", "note"],
}
TAG_SYSTEM = """You read the identification plate fixed to an electricity distribution pole. Return the characters
on the plate exactly as printed (letters, digits, dashes, slashes), nothing added or guessed. If the plate is blurred,
cut off or not in the picture, say it is not readable and return null for the tag."""
TAG_PROMPT = "pole number plate"
TAG_MIN_PX = 320  # Spark gets the plate crop enlarged to at least this size on its short side


def _crop_plate(path: Path, box: tuple[float, float, float, float]) -> tuple[bytes, tuple[int, int]]:
    """The plate and a margin around it, enlarged: the plate is a few dozen pixels in a street photo."""
    import io

    from PIL import Image
    with Image.open(path) as im:
        im = im.convert("RGB")
        x1, y1, x2, y2 = box
        padx, pady = (x2 - x1) * 0.25, (y2 - y1) * 0.25
        crop = im.crop((max(int(x1 - padx), 0), max(int(y1 - pady), 0),
                        min(int(x2 + padx), im.width), min(int(y2 + pady), im.height)))
        scale = min(max(TAG_MIN_PX / max(min(crop.size), 1), 1.0), 6.0)
        crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)
        out = io.BytesIO()
        crop.save(out, "JPEG", quality=90)
        return out.getvalue(), crop.size


def read_pole_tag(client: ModelClient, rel_path: str, truth_tag: str | None = None) -> dict | None:
    """SAM 3.1 finds the pole's number plate, Muse Spark reads the enlarged plate. None when no plate is in the photo.

    `truth_tag` is the tag a scenario says the photo carries; it answers only when no model can (mock mode).
    Returns {tag, readable, confidence, note, box, crop, models, mock}. The tag is only text: poles.PoleRegister
    decides which pole it names.
    """
    import base64
    import hashlib

    path = config.ROOT / rel_path
    mock = {"tag": truth_tag, "readable": True, "confidence": "high", "box": None, "crop": None,
            "note": "(mock) tag taken from the scenario; Muse Spark and SAM 3.1 read it once the API is on",
            "models": ["mock (ground truth)"], "mock": True}
    if not path.exists():
        return mock if truth_tag else None
    plates = client.segment_image(path, TAG_PROMPT)
    models = ["SAM 3.1"] if plates is not None else []
    box = max((p for p in plates or [] if p.get("box")), key=lambda p: p.get("conf") or 0, default=None)
    if box is not None:
        jpeg, size = _crop_plate(path, box["box"])
        digest = hashlib.sha256(jpeg).hexdigest()[:16]
        crop_rel = f"media/uploads/tag_{digest}.jpg"
        (config.ROOT / crop_rel).parent.mkdir(parents=True, exist_ok=True)
        (config.ROOT / crop_rel).write_bytes(jpeg)
        url = f"data:image/jpeg;base64,{base64.b64encode(jpeg).decode()}"
        user = [{"type": "text", "text": "Read the pole number plate in this close-up."},
                {"type": "image_url", "image_url": {"url": url}}]
    elif plates is None:
        return mock if truth_tag else None  # nobody could look
    else:
        # SAM saw no plate; Spark gets one look at the whole photo before we give up (plates can be tiny).
        crop_rel, size = None, None
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        url = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
        user = [{"type": "text", "text": "Read the pole number plate in this photo, if one is legible."},
                {"type": "image_url", "image_url": {"url": url}}]
    info = client.spark_json(TAG_SYSTEM, user, TAG_SCHEMA, "PoleTag")
    if info is None:
        return mock if truth_tag else None
    models.append("Muse Spark")
    tag = (info.get("tag") or "").strip() or None
    readable = bool(info.get("readable")) and tag is not None
    if not readable and box is None:
        return None  # no plate found by either model: nothing to report
    return {"tag": tag if readable else None, "readable": readable, "confidence": info.get("confidence", "low"),
            "note": info.get("note", ""), "box": list(box["box"]) if box else None, "crop": crop_rel,
            "models": models, "mock": False}


def _photo_overlay(path: Path, records: dict[str, list[dict]]) -> str | None:
    """The photo with SAM's outlines tinted (media/overlays); built once per photo, None if nothing was outlined."""
    from . import masks
    if not records:
        return None
    out = masks.OVERLAY_DIR / f"{path.stem}_sam.jpg"
    try:
        if out.exists() or masks.overlay_image(path, records, out):
            return out.relative_to(config.ROOT).as_posix()
    except Exception:  # noqa: BLE001 - outlines are a nicety: never lose the analysis over them
        pass
    return None


def analyse_photo(client: ModelClient, rel_path: str, truth_damage: str | None) -> dict:
    """Returns {damage, severity, public_hazard, description, clearance_m, objects, models, mock}."""
    path = config.ROOT / rel_path
    if not path.exists():
        return {"damage": truth_damage or "other", "severity": "high", "public_hazard": truth_damage == "live_wire",
                "description": f"(photo not added yet: {Path(rel_path).name})", "clearance_m": None,
                "objects": {}, "models": ["mock (ground truth)"], "mock": True, "has_image": False}
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
                "description": "(mock) not analysed yet: Muse Spark and SAM 3.1 run once the API key is set",
                "segment_prompts": []}
        models = ["mock (ground truth)"]
    prompts = list(dict.fromkeys(["utility pole", "power line"] + info.get("segment_prompts", [])))[:4]
    records = {}
    for p in prompts:
        recs = client.segment_image(path, p)
        if recs is not None:
            records[p] = recs
    if records:
        models.append("SAM 3.1")
    overlay = _photo_overlay(path, records)
    try:
        from . import masks
        lean = masks.photo_lean(records)
    except Exception:  # noqa: BLE001
        lean = None
    clearance = _clearance_m(records)
    if clearance is not None and clearance < ROAD_CLEARANCE_M:
        info["public_hazard"] = True
    return {**{k: v for k, v in info.items() if k != "segment_prompts"}, "clearance_m": clearance,
            "objects": {p: [{"box": r["box"], "conf": r.get("conf")} for r in recs] for p, recs in records.items()},
            "image_size": next(((r["w"], r["h"]) for recs in records.values() for r in recs), None),
            "overlay": overlay, "pole_lean_deg": lean, "models": models, "mock": models[0].startswith("mock"), "has_image": True}


LINE_WORDS = ("line", "wire", "conductor", "cable")
DOWN_WORDS = ("fallen", "broken", "snapped", "leaning", "down", "collapsed")
MIN_TRACK_FRAMES = 5  # a track shorter than this is flicker, not an object
PERSISTENT = 0.4  # a wire counts as followed if its track spans this share of the clip
CROSS_SHARE = 0.5  # an obstruction crosses a wire if they overlap in this share of the frames they share
LYING_ASPECT = 1.2  # a pole whose box is this much wider than tall is lying down


def _tracks(records: list[dict]) -> dict[int | None, dict[int, tuple]]:
    """records -> {object id: {frame: box}}; the first box wins when a frame repeats."""
    out: dict[int | None, dict[int, tuple]] = {}
    for r in records:
        if r.get("frame") is not None and r.get("box"):
            out.setdefault(r.get("id"), {}).setdefault(r["frame"], r["box"])
    return out


def _median(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[len(xs) // 2]


def _crosses(obstruction: dict[int, tuple], wire: dict[int, tuple]) -> bool:
    """The obstruction's box sits over most of the wire's width and reaches its height in most shared frames."""
    shared = obstruction.keys() & wire.keys()
    if not shared:
        return False
    hits = 0
    for f in shared:
        ox1, oy1, ox2, oy2 = obstruction[f]
        wx1, wy1, wx2, wy2 = wire[f]
        across = min(ox2, wx2) - max(ox1, wx1)
        hits += across >= 0.5 * (wx2 - wx1) and min(oy2, wy2) > max(oy1, wy1)
    return hits / len(shared) >= CROSS_SHARE


def drone_survey(tracks: dict[str, list[dict]]) -> dict | None:
    """What a patrol clip shows, counted from SAM 3.1's tracks (code counts; the model only outlines).

    Poles and wires are counted as tracks followed through the clip, which is not the number of poles on the
    feeder: a drone passes some poles and a wire is followed in pieces. An obstruction (a fallen tree, debris) is
    checked against every wire followed: it crosses a wire when their boxes overlap in most shared frames. A pole
    whose box is wider than tall is reported as lying. Boxes only, so sag cannot be measured yet (masks are not decoded).
    """
    frames_total = max((r["frame"] for recs in tracks.values() for r in recs if r.get("frame") is not None),
                       default=-1) + 1
    if frames_total <= 0:
        return None
    poles: list[dict] = []
    wires: list[tuple[str, int, dict]] = []
    blockers: list[tuple[str, int, dict]] = []
    for prompt, recs in tracks.items():
        low = prompt.lower()
        is_pole = "pole" in low
        is_line = any(w in low for w in LINE_WORDS)
        for oid, frames in _tracks(recs).items():
            if len(frames) < MIN_TRACK_FRAMES:
                continue
            if is_pole:
                boxes = list(frames.values())
                w = _median([b[2] - b[0] for b in boxes])
                h = _median([b[3] - b[1] for b in boxes])
                poles.append({"prompt": prompt, "id": oid, "frames": len(frames), "lying": w > LYING_ASPECT * h
                              or (any(x in low for x in DOWN_WORDS) and w >= h)})
            elif is_line:
                wires.append((prompt, oid, frames))
            else:
                blockers.append((prompt, oid, frames))
    followed = [(p, i, fr) for p, i, fr in wires if (max(fr) - min(fr) + 1) / frames_total >= PERSISTENT]
    crossings = [{"object": p, "wires_crossed": sum(_crosses(fr, w) for _, _, w in followed),
                  "share_of_clip": round((max(fr) - min(fr) + 1) / frames_total, 2)} for p, _, fr in blockers]
    lying = sum(p["lying"] for p in poles)
    flags = []
    if lying:
        flags.append(f"{lying} pole{'s' if lying > 1 else ''} look{'s' if lying == 1 else ''} to be lying down")
    for c in crossings:
        if c["wires_crossed"]:
            flags.append(f"{c['object']} crosses {c['wires_crossed']} of {len(followed)} wires followed")
    return {"poles": {"followed": len(poles), "lying": lying},
            "wires": {"followed": len(followed), "pieces": len(wires)},
            "obstructions": crossings, "frames": frames_total, "flags": flags}


def _mask_survey(path: Path, records: dict[str, list[dict]], survey: dict) -> tuple[dict, str | None]:
    """Add what the pixel masks say (lean, sag, real contact) to the box-based survey; its flags replace the box ones."""
    from . import masks
    try:
        m = masks.survey(path, records, workers=1)
    except Exception:  # noqa: BLE001 - masks are an upgrade over boxes, not a requirement
        m = None
    overlay = masks.OVERLAY_DIR / f"{path.stem}_sam.mp4"
    overlay_rel = overlay.relative_to(config.ROOT).as_posix() if overlay.exists() else None
    if m is None:
        return survey, overlay_rel
    survey = {**survey, "masks": m,
              "flags": [f for f in survey["flags"] if "crosses" not in f] + masks.flags(m)}
    return survey, overlay_rel


def analyse_video(client: ModelClient, rel_path: str, truth_damage: str | None, source: str = "customer") -> dict:
    """A customer's or drone patrol's clip: Spark watches it and names the damage; SAM 3.1 tracks every pole and
    wire through it, so code can say how many it followed. Same shape as analyse_photo plus `tracked`."""
    path = config.ROOT / rel_path
    mock = {"damage": truth_damage or "other", "severity": "high", "public_hazard": truth_damage == "live_wire",
            "clearance_m": None, "objects": {}, "tracked": {}, "at_seconds": None, "kind": "video", "source": source}
    if not path.exists():
        return {**mock, "description": f"(video not added yet: {Path(rel_path).name})",
                "models": ["mock (ground truth)"], "mock": True, "has_image": False}
    who = "a drone patrolling the line" if source == "drone" else "a customer"
    info = client.spark_video_json(VIDEO_SYSTEM, f"Assess the damage in this clip, filmed by {who}.", path,
                                   VIDEO_SCHEMA, "DamageVideo")
    models = ["Muse Spark"]
    if info is None:
        info = {k: v for k, v in mock.items() if k in VIDEO_SCHEMA["properties"]}
        info.update(description="(mock) not analysed yet: Muse Spark and SAM 3.1 run once the API key is set",
                    segment_prompts=[])
        models = ["mock (ground truth)"]
    prompts = list(dict.fromkeys(["utility pole", "power line"] + info.get("segment_prompts", [])))[:4]
    tracked, records = {}, {}
    for p in prompts:
        recs = client.segment_video(path, p)
        if recs is None:
            continue
        records[p] = recs
        ids = {r.get("id") for r in recs if r.get("id") is not None}
        frames = {r["frame"] for r in recs if r.get("frame") is not None}
        tracked[p] = {"objects": len(ids) or max((sum(r["frame"] == f for r in recs) for f in frames), default=0),
                      "frames": len(frames)}
    if tracked:
        models.append("SAM 3.1")
    survey = drone_survey(records) if source == "drone" and records else None
    overlay = None
    if survey is not None:
        survey, overlay = _mask_survey(path, records, survey)
    return {**mock, **{k: v for k, v in info.items() if k != "segment_prompts"}, "tracked": tracked,
            "survey": survey, "overlay": overlay,
            "models": models, "mock": models[0].startswith("mock"), "has_image": True}
