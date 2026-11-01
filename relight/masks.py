"""Pixel masks from SAM 3.1: what the outlines say that boxes cannot.

SAM returns a box and a mask for every object. Boxes tell where something is; the mask says what shape it has, so code
can measure how far a pole leans, how much a wire sags between its ends, and whether a fallen tree really touches a
wire, and can draw the outlines over the photo or the clip. The mask payload is Meta's own base85 lossless coding,
decoded with Meta's `meta-sam-parser` (pure Python, no network). Masks are box-local rasters of 0/1 bytes.

Decoding costs ~4 microseconds per pixel in pure Python, so a whole clip is slow. Decoded masks are cached under
.cache/masks, and `survey` decodes only a bounded sample of frames. Everything here is an estimate from one camera
view: lean and sag are angles and ratios, not surveyed values, and are shown as flags for the crew, never as facts that
move the fault.
"""

from __future__ import annotations

import hashlib
import math
import pickle
import subprocess
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import config

CACHE = config.CACHE_DIR.parent / "masks"
OVERLAY_DIR = config.ROOT / "media" / "overlays"
SAMPLE_FRAMES = 12  # frames decoded per clip for the survey
LEAN_FLAG_DEG = 15.0
MIN_ELONGATION = 9.0  # long axis at least 3x the short axis (variance ratio); otherwise the view is not side-on
SAG_FLAG = 1.5  # a wire sagging this many times the median of the others is flagged
SAG_MIN = 0.02  # ... and by at least this share of its own span
COLOURS = {"pole": (61, 142, 255), "wire": (255, 176, 32), "obstruction": (230, 57, 70)}
ALPHA = 120


def kind(prompt: str) -> str:
    from .vision import LINE_WORDS
    low = prompt.lower()
    if "pole" in low:
        return "pole"
    if any(w in low for w in LINE_WORDS):
        return "wire"
    return "obstruction"


# ---- decoding ---------------------------------------------------------------------------

def _decode_payload(args: tuple[str, int, int]) -> bytes | None:
    from meta_sam_parser import SegmentationMask, decode_mask_to_raster
    payload, w, h = args
    enc = {"~": "lossless", "!": "one_bit"}.get(payload[:1])
    if enc is None or w <= 0 or h <= 0:
        return None
    try:
        return decode_mask_to_raster(SegmentationMask(enc, payload, w, h))
    except Exception:  # noqa: BLE001 - a mask that will not decode is skipped, not fatal
        return None


def _parts(rec: dict) -> tuple[str, int, int] | None:
    data = rec.get("mask")
    if not data or data.count(",") < 2:
        return None
    h, w, payload = data.split(",", 2)
    return (payload, int(w), int(h)) if payload else None


class Mask:
    """One decoded mask placed in the frame: `rows` of 0/1 bytes starting at (x, y)."""

    __slots__ = ("x", "y", "w", "h", "data")

    def __init__(self, x: int, y: int, w: int, h: int, data: bytes) -> None:
        self.x, self.y, self.w, self.h, self.data = x, y, w, h, data

    def row(self, y: int) -> bytes:
        return self.data[(y - self.y) * self.w:(y - self.y + 1) * self.w]

    def area(self) -> int:
        return self.data.count(1)


def _place(rec: dict, data: bytes | None) -> Mask | None:
    parts = _parts(rec)
    if data is None or parts is None:
        return None
    return Mask(int(rec["box"][0]), int(rec["box"][1]), parts[1], parts[2], data)


def decode_records(records: list[dict], workers: int = 1) -> list[Mask | None]:
    """Decode masks for these records (in order), optionally across processes."""
    jobs = [_parts(r) for r in records]
    todo = [j for j in jobs if j is not None]
    if workers > 1 and len(todo) > 8:
        with ProcessPoolExecutor(workers) as pool:
            done = list(pool.map(_decode_payload, todo, chunksize=4))
    else:
        done = [_decode_payload(j) for j in todo]
    it = iter(done)
    return [_place(r, next(it)) if j is not None else None for r, j in zip(records, jobs)]


def _pack(m: Mask) -> tuple:
    return (m.x, m.y, m.w, m.h, zlib.compress(m.data, 1))


def _unpack(t: tuple) -> Mask:
    return Mask(t[0], t[1], t[2], t[3], zlib.decompress(t[4]))


def _cache_path(media: Path, tag: str) -> Path:
    sha = hashlib.sha256(Path(media).read_bytes()).hexdigest()[:16]
    return CACHE / f"{sha}-{hashlib.sha256(tag.encode()).hexdigest()[:8]}.pkl"


def masks_for(media: Path, tag: str, records: list[dict], workers: int = 1) -> dict[tuple, Mask]:
    """Masks keyed by (object id, frame), decoded once and cached on disk. `tag` names this request (prompt + sample)."""
    path = _cache_path(media, tag)
    if path.exists():
        return {k: _unpack(v) for k, v in pickle.loads(path.read_bytes()).items()}
    out: dict[tuple, Mask] = {}
    for rec, m in zip(records, decode_records(records, workers)):
        if m is not None:
            out.setdefault((rec.get("id"), rec.get("frame")), m)
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps({k: _pack(v) for k, v in out.items()}))
    return out


# ---- measurements -----------------------------------------------------------------------

def lean_deg(m: Mask) -> float | None:
    """Angle of the mask's long axis from vertical: ~0 for a standing pole, ~90 for one lying down."""
    n = sx = sy = sxx = syy = sxy = 0
    for y in range(m.h):
        row = m.data[y * m.w:(y + 1) * m.w]
        xs = [i for i, v in enumerate(row) if v]
        if not xs:
            continue
        k, s = len(xs), sum(xs)
        n += k
        sx += s
        sy += y * k
        sxx += sum(i * i for i in xs)
        syy += y * y * k
        sxy += y * s
    if n < 30:
        return None
    cx, cy = sx / n, sy / n
    mu20, mu02, mu11 = sxx / n - cx * cx, syy / n - cy * cy, sxy / n - cx * cy
    spread = math.hypot((mu20 - mu02) / 2, mu11)
    major, minor = (mu20 + mu02) / 2 + spread, (mu20 + mu02) / 2 - spread
    if minor <= 0 or major / minor < MIN_ELONGATION:  # a blob (a pole seen from above, a crossarm): no axis to read
        return None
    theta = 0.5 * math.atan2(2 * mu11, mu20 - mu02)  # long axis, from the x axis
    return round(90 - abs(math.degrees(theta)), 1)


def photo_lean(records: dict[str, list[dict]]) -> float | None:
    """Lean of the largest outlined pole in a photo (one decode). From street level this is a rough angle."""
    poles = [r for p, recs in records.items() if kind(p) == "pole" for r in recs if r.get("mask") and r.get("box")]
    if not poles:
        return None
    biggest = max(poles, key=lambda r: (r["box"][2] - r["box"][0]) * (r["box"][3] - r["box"][1]))
    m = decode_records([biggest])[0]
    return lean_deg(m) if m is not None else None


def sag_ratio(m: Mask) -> float | None:
    """How far the wire's centre line drops below the straight line between its ends, as a share of its span."""
    cols: dict[int, tuple[int, int]] = {}
    for y in range(m.h):
        row = m.data[y * m.w:(y + 1) * m.w]
        for x, v in enumerate(row):
            if v:
                n, s = cols.get(x, (0, 0))
                cols[x] = (n + 1, s + y)
    if len(cols) < max(m.w * 0.6, 20):
        return None
    xs = sorted(cols)
    centre = {x: cols[x][1] / cols[x][0] for x in xs}
    k = max(len(xs) // 12, 1)
    x0, x1 = sum(xs[:k]) / k, sum(xs[-k:]) / k
    y0, y1 = sum(centre[x] for x in xs[:k]) / k, sum(centre[x] for x in xs[-k:]) / k
    if x1 - x0 < 20:
        return None
    drop = max(centre[x] - (y0 + (y1 - y0) * (x - x0) / (x1 - x0)) for x in xs)
    return round(drop / (x1 - x0), 3)


def touches(a: Mask, b: Mask) -> bool:
    """Do the two masks share a pixel? Rows are compared as integers, so this is fast."""
    x0, x1 = max(a.x, b.x), min(a.x + a.w, b.x + b.w)
    y0, y1 = max(a.y, b.y), min(a.y + a.h, b.y + b.h)
    if x0 >= x1 or y0 >= y1:
        return False
    for y in range(y0, y1):
        ra = a.row(y)[x0 - a.x:x1 - a.x]
        rb = b.row(y)[x0 - b.x:x1 - b.x]
        if int.from_bytes(ra, "big") & int.from_bytes(rb, "big"):
            return True
    return False


def _pick_frames(records: dict[str, list[dict]], k: int) -> set[int]:
    frames = sorted({r["frame"] for recs in records.values() for r in recs if r.get("frame") is not None})
    if len(frames) <= k:
        return set(frames)
    step = (len(frames) - 1) / (k - 1)
    return {frames[round(i * step)] for i in range(k)}


def survey(media: Path, records: dict[str, list[dict]], workers: int = 4) -> dict | None:
    """Lean of each pole, sag of each long wire and which wires an obstruction touches, from a sample of frames."""
    picked = _pick_frames(records, SAMPLE_FRAMES)
    if not picked:
        return None
    by_kind: dict[str, dict[tuple, Mask]] = {"pole": {}, "wire": {}, "obstruction": {}}
    names: dict[str, str] = {}
    frame_w = 0
    for prompt, recs in records.items():
        sample = [r for r in recs if r.get("frame") in picked and r.get("mask") and r.get("box")]
        frame_w = max([frame_w] + [int(r.get("w") or 0) for r in sample])
        got = masks_for(media, f"{prompt}|{sorted(picked)}", sample, workers)
        for (oid, frame), m in got.items():
            key = (prompt, oid, frame)
            by_kind[kind(prompt)][key] = m
            names[prompt] = kind(prompt)
    poles: dict[tuple, list[float]] = {}
    for (prompt, oid, _), m in by_kind["pole"].items():
        if (lean := lean_deg(m)) is not None:
            poles.setdefault((prompt, oid), []).append(lean)
    wires: dict[tuple, list[float]] = {}
    for (prompt, oid, _), m in by_kind["wire"].items():
        if frame_w and m.w >= 0.5 * frame_w and (s := sag_ratio(m)) is not None:
            wires.setdefault((prompt, oid), []).append(s)
    med = lambda xs: sorted(xs)[len(xs) // 2]  # noqa: E731
    wire_sag = {k: med(v) for k, v in wires.items() if len(v) >= 2}
    long_wires = {(p, o) for (p, o, _), m in by_kind["wire"].items() if frame_w and m.w >= 0.5 * frame_w}
    contact: dict[str, set] = {}
    seen_obstructions: dict[str, int] = {}
    for (op, oo, of), om in by_kind["obstruction"].items():
        seen_obstructions[op] = seen_obstructions.get(op, 0) + 1
        for (wp, wo, wf), wm in by_kind["wire"].items():
            if wf == of and (wp, wo) in long_wires and touches(om, wm):
                contact.setdefault(op, set()).add((wp, wo))
    return {
        "frames": sorted(picked),
        "poles": [{"id": f"{p}#{o}", "lean_deg": med(v), "frames": len(v)} for (p, o), v in sorted(poles.items(), key=str)],
        "wires": [{"id": f"{p}#{o}", "sag": s} for (p, o), s in sorted(wire_sag.items(), key=str)],
        "wires_long": len(long_wires),
        "obstructions": [{"object": p, "wires_touched": len(contact.get(p, ())), "frames": n}
                         for p, n in sorted(seen_obstructions.items())],
        "median_sag": med(list(wire_sag.values())) if wire_sag else None,
    }


def flags(s: dict) -> list[str]:
    """Plain-language flags from a survey, with the thresholds that raised them."""
    out = []
    for p in s["poles"]:
        if p["lean_deg"] >= LEAN_FLAG_DEG:
            out.append(f"pole {p['id']} leans about {p['lean_deg']:.0f} degrees")
    sags = [w["sag"] for w in s["wires"]]
    if len(sags) >= 3:
        base = sorted(sags)[len(sags) // 2]
        for w in s["wires"]:
            if w["sag"] >= SAG_MIN and w["sag"] >= SAG_FLAG * max(base, 0.005):
                out.append(f"wire {w['id']} sags {w['sag']:.1%} of its span, {w['sag'] / max(base, 0.005):.1f}x the median")
    for o in s["obstructions"]:
        if o["wires_touched"]:
            out.append(f"{o['object']} touches {o['wires_touched']} of {s['wires_long']} long wires (pixel overlap)")
    return out


# ---- drawing ----------------------------------------------------------------------------

def _paint(im, m: Mask, colour: tuple[int, int, int]) -> None:
    from PIL import Image
    lut = bytes([0, ALPHA]) + bytes(254)
    alpha = Image.frombytes("L", (m.w, m.h), m.data.translate(lut))
    im.paste(Image.new("RGB", (m.w, m.h), colour), (m.x, m.y), alpha)


def overlay_image(path: Path, records: dict[str, list[dict]], out: Path) -> Path | None:
    """The photo with every outlined object tinted: poles blue, wires amber, anything else red."""
    from PIL import Image
    painted = 0
    with Image.open(path) as src:
        im = src.convert("RGB")
    for prompt, recs in records.items():
        recs = [r for r in recs if r.get("mask") and r.get("box")]
        for rec, m in zip(recs, decode_records(recs)):
            if m is not None:
                _paint(im, m, COLOURS[kind(prompt)])
                painted += 1
    if not painted:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=88)
    return out


def _probe(path: Path) -> tuple[int, int, float]:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,avg_frame_rate", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    w, h, rate = r.stdout.strip().split(",")[:3]
    num, den = rate.split("/")
    return int(w), int(h), float(num) / float(den or 1)


def overlay_video(path: Path, records: dict[str, list[dict]], out: Path, workers: int = 8, hold: int = 3) -> Path | None:
    """The clip with SAM's outlines tinted on every frame (an outline is held for `hold` frames when SAM skipped one)."""
    from PIL import Image, ImageDraw
    w, h, fps = _probe(path)
    per_frame: dict[int, list[tuple[str, Mask]]] = {}
    for prompt, recs in records.items():
        recs = [r for r in recs if r.get("mask") and r.get("box") and r.get("frame") is not None]
        for rec, m in zip(recs, decode_records(recs, workers)):
            if m is None:
                continue
            for f in range(rec["frame"], rec["frame"] + hold):
                per_frame.setdefault(f, []).append((kind(prompt), m))
    if not per_frame:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                            "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "26",
                            "-preset", "fast", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    n = 0
    legend = [("pole", "pole"), ("wire", "wire"), ("obstruction", "tree / debris")]
    while chunk := dec.stdout.read(w * h * 3):
        if len(chunk) < w * h * 3:
            break
        im = Image.frombytes("RGB", (w, h), chunk)
        done: set[int] = set()
        for k, m in per_frame.get(n, []):
            if id(m) not in done:
                _paint(im, m, COLOURS[k])
                done.add(id(m))
        d = ImageDraw.Draw(im)
        for i, (k, label) in enumerate(legend):
            d.rectangle((8, 8 + i * 14, 18, 18 + i * 14), fill=COLOURS[k])
            d.text((24, 7 + i * 14), label, fill=(255, 255, 255))
        enc.stdin.write(im.tobytes())
        n += 1
    enc.stdin.close()
    dec.wait()
    enc.wait()
    return out if enc.returncode == 0 else None
