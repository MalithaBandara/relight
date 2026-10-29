"""Paper map to grid model: Muse Spark reads a photo of a single-line diagram.

Many utilities that lack smart meters also lack a digital network model; the feeder
exists only as a single-line diagram on paper. GridMedic photographs it and has Muse
Spark return the topology (buses, connections, protective devices), then scores the
result against the known feeder so the accuracy is a number, not a claim.

`render_diagram` draws the IEEE 34-bus feeder as a hand-sketched single-line diagram
to print, photograph and feed back in.
"""

from __future__ import annotations

import base64
import mimetypes
import random
from pathlib import Path

from .grid import DEVICES, SECTIONS
from .models import ModelClient

DIAGRAM_SCHEMA = {
    "type": "object",
    "properties": {
        "connections": {
            "type": "array",
            "description": "Every line between two bus labels, upstream bus first",
            "items": {"type": "object", "properties": {"from": {"type": "string"}, "to": {"type": "string"}},
                      "required": ["from", "to"]},
        },
        "devices": {
            "type": "array",
            "description": "Protective devices drawn on a line",
            "items": {"type": "object", "properties": {
                "label": {"type": "string"},
                "type": {"type": "string", "enum": ["breaker", "recloser", "fuse", "other"]},
                "from": {"type": "string"}, "to": {"type": "string"}},
                "required": ["label", "type", "from", "to"]},
        },
        "source_bus": {"type": "string", "description": "Bus where the substation feeds the line"},
    },
    "required": ["connections", "devices", "source_bus"],
}
DIAGRAM_SYSTEM = """You digitise electricity distribution single-line diagrams. Read every bus label (numbers
like 800, 802), every line connecting two buses, and every protective device drawn on a line
(breaker, recloser, fuse) with its label. Report connections upstream bus first, starting from the
substation. Only report what is drawn; do not infer lines that are not there."""

FONT_CANDIDATES = ["C:/Windows/Fonts/segoepr.ttf", "C:/Windows/Fonts/comic.ttf",
                   "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf", "DejaVuSans.ttf"]


def truth() -> dict:
    connections = {(a, b) for a, b, *_ in SECTIONS}
    devices = {d[2]: (d[0], d[1]) for d in DEVICES}  # section -> (label, type)
    return {"connections": connections, "devices": devices}


def score(result: dict) -> dict:
    t = truth()
    got = {(c["from"].strip(), c["to"].strip()) for c in result.get("connections", [])}
    undirected = lambda s: {frozenset(x) for x in s}  # noqa: E731
    tp = undirected(got) & undirected(t["connections"])
    reversed_ = sum(1 for a, b in got if (b, a) in t["connections"])
    dev_hits = []
    for d in result.get("devices", []):
        sid = f"{d['from']}-{d['to']}"
        rsid = f"{d['to']}-{d['from']}"
        want = t["devices"].get(sid) or t["devices"].get(rsid)
        dev_hits.append(bool(want and want[1] == d["type"]))
    n_true, n_got = len(t["connections"]), len(got)
    return {
        "connections_correct": len(tp), "connections_total": n_true, "connections_reported": n_got,
        "precision": round(len(tp) / n_got, 3) if n_got else 0.0,
        "recall": round(len(tp) / n_true, 3), "reversed": reversed_,
        "devices_correct": sum(dev_hits), "devices_total": len(t["devices"]),
        "missing": sorted("-".join(sorted(x)) for x in undirected(t["connections"]) - tp),
        "extra": sorted("-".join(sorted(x)) for x in undirected(got) - undirected(t["connections"])),
    }


def read_diagram(client: ModelClient, image: Path) -> tuple[dict, str]:
    """Returns (topology, model label). Falls back to the true topology in mock mode."""
    mime = mimetypes.guess_type(str(image))[0] or "image/jpeg"
    url = f"data:{mime};base64,{base64.b64encode(Path(image).read_bytes()).decode()}"
    content = [{"type": "text", "text": "Digitise this single-line diagram."},
               {"type": "image_url", "image_url": {"url": url}}]
    try:
        out = client.spark_json(DIAGRAM_SYSTEM, content, DIAGRAM_SCHEMA, "Feeder")
    except Exception:  # noqa: BLE001
        out = None
    if out is not None:
        return out, "Muse Spark"
    return {
        "connections": [{"from": a, "to": b} for a, b, *_ in SECTIONS],
        "devices": [{"label": d[0], "type": d[1], "from": d[2].split("-")[0], "to": d[2].split("-")[1]}
                    for d in DEVICES],
        "source_bus": "800",
    }, "mock (ground truth)"


def render_diagram(path: Path, seed: int = 7) -> Path:
    """Draw the feeder as a hand-sketched single-line diagram (PNG) for printing."""
    from PIL import Image, ImageDraw, ImageFont

    rng = random.Random(seed)
    children: dict[str, list[str]] = {}
    for a, b, *_ in SECTIONS:
        children.setdefault(a, []).append(b)
    # Tidy tree layout: leaves get consecutive columns, parents sit over their children.
    col: dict[str, float] = {}
    depth: dict[str, int] = {}
    counter = [0]

    def place(bus: str, d: int) -> None:
        depth[bus] = d
        kids = children.get(bus, [])
        for k in kids:
            place(k, d + 1)
        if kids:
            col[bus] = sum(col[k] for k in kids) / len(kids)
        else:
            col[bus] = counter[0]
            counter[0] += 1

    place("800", 0)
    W, H = 1900, 1400
    xs, ys = 1620 / max(counter[0] - 1, 1), 1150 / max(depth.values())
    pos = {b: (150 + col[b] * xs + rng.uniform(-6, 6), 120 + depth[b] * ys + rng.uniform(-6, 6)) for b in col}
    img = Image.new("RGB", (W, H), (250, 248, 240))
    draw = ImageDraw.Draw(img)
    font = next((ImageFont.truetype(f, 26) for f in FONT_CANDIDATES if Path(f).exists()), ImageFont.load_default())
    small = next((ImageFont.truetype(f, 20) for f in FONT_CANDIDATES if Path(f).exists()), ImageFont.load_default())
    ink = (30, 40, 90)

    def wobbly(p, q):
        pts = [p]
        for i in range(1, 6):
            t = i / 6
            pts.append((p[0] + (q[0] - p[0]) * t + rng.uniform(-2.5, 2.5), p[1] + (q[1] - p[1]) * t + rng.uniform(-2.5, 2.5)))
        pts.append(q)
        draw.line(pts, fill=ink, width=3, joint="curve")

    dev_on = {d[2]: d for d in DEVICES}
    for a, b, *_ in SECTIONS:
        pa, pb = pos[a], pos[b]
        elbow = (pb[0], pa[1])  # draw as right-angle runs, like a real one-line
        wobbly(pa, elbow)
        wobbly(elbow, pb)
        if (d := dev_on.get(f"{a}-{b}")):
            cx, cy = pb[0], (pa[1] + pb[1]) / 2
            if d[1] == "fuse":
                draw.rectangle([cx - 9, cy - 18, cx + 9, cy + 18], outline=ink, width=3, fill=(250, 248, 240))
                draw.line([(cx, cy - 18), (cx, cy + 18)], fill=ink, width=2)
            else:
                draw.rectangle([cx - 16, cy - 16, cx + 16, cy + 16], outline=ink, width=3,
                               fill=(250, 248, 240) if d[1] == "recloser" else ink)
                if d[1] == "recloser":
                    draw.text((cx - 6, cy - 13), "R", fill=ink, font=small)
            tw = draw.textlength(d[0], font=small)
            draw.text((cx - 24 - tw, cy - 12), d[0], fill=(150, 30, 30), font=small)
    for b, (x, y) in pos.items():
        draw.line([(x - 22, y), (x + 22, y)], fill=ink, width=6)
        draw.text((x + 8, y - 34), b, fill=ink, font=font)
    sx, sy = pos["800"]
    draw.ellipse([sx - 30, sy - 95, sx + 30, sy - 35], outline=ink, width=3)
    draw.text((sx + 40, sy - 80), "Wakwella substation", fill=ink, font=font)
    draw.line([(sx, sy - 35), (sx, sy)], fill=ink, width=3)
    draw.text((60, H - 70), "Feeder 1 - single line diagram (not to scale)   R = recloser   [|] = fuse",
              fill=ink, font=small)
    img = img.rotate(rng.uniform(-1.5, 1.5), expand=False, fillcolor=(235, 232, 222))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path
