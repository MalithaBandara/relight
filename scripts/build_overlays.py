"""Draw SAM 3.1's outlines over the storm clips and photos, from the cached SAM responses (no API calls).

Poles are tinted blue, wires amber, anything else (a fallen tree) red. Output goes to media/overlays/ (git-ignored);
the console's map popup shows the overlay when one exists. Decoding masks is slow in pure Python, so it runs across
processes.

Usage:  python scripts/build_overlays.py [media files...]      (default: the drone clip and every cached photo/video)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from relight import config, masks  # noqa: E402
from relight.models import ModelClient  # noqa: E402

VIDEO = {".mp4", ".mov", ".webm"}
PROMPTS = ["utility pole", "power line", "fallen tree trunk", "overhead power lines", "tree", "power pole"]


def cached_records(client: ModelClient, path: Path) -> dict[str, list[dict]]:
    """SAM records already in the cache for this file; a prompt nobody asked about is simply absent (no API call:
    the client only calls out when the API is allowed, and this script never asks for that)."""
    seg = client.segment_video if path.suffix.lower() in VIDEO else client.segment_image
    found = {}
    for prompt in PROMPTS:
        if (recs := seg(path, prompt)):
            found[prompt] = recs
    return found


def main() -> None:
    client = ModelClient(mode="mock")  # mock: cached responses only, never a request
    targets = [Path(a) for a in sys.argv[1:]] or [
        *sorted((config.ROOT / "media" / "drone").glob("*.mp4")),
        *sorted((config.ROOT / "media" / "videos").glob("*.mp4")),
        *sorted((config.ROOT / "media" / "photos").glob("*.jpg")),
    ]
    for path in targets:
        recs = cached_records(client, path)
        if not recs:
            print(f"{path.name}: no cached SAM response, skipped")
            continue
        out = masks.OVERLAY_DIR / f"{path.stem}_sam{'.mp4' if path.suffix.lower() in VIDEO else '.jpg'}"
        t0 = time.time()
        fn = masks.overlay_video if path.suffix.lower() in VIDEO else masks.overlay_image
        done = fn(path, recs, out)
        print(f"{path.name}: {'wrote ' + str(done.relative_to(config.ROOT)) if done else 'nothing to draw'} "
              f"({time.time() - t0:.0f}s, prompts: {', '.join(recs)})")


if __name__ == "__main__":
    main()
