"""Download and trim the third-party storm clips used as customer videos and the drone patrol.

They are not ours to redistribute, so they are git-ignored; this rebuilds them after a fresh clone.
Sources and credits: media/videos/CREDITS.md. Needs yt-dlp (`pip install yt-dlp`) and ffmpeg on PATH.

Usage:  python scripts/fetch_videos.py [--force]
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# target: (url, start_s, length_s or None, max width). Clips are re-encoded small to keep model requests cheap;
# the drone clip also drops to 10 fps, because SAM 3.1 refused it at 7.6 MB (HTTP 413) and bills per frame.
CLIPS = {
    "media/drone/temple_road_span.mp4": ("https://www.youtube.com/watch?v=ChaqvH8k02g", 30, 32, 854),
    "media/videos/tree_on_live_line.mp4": ("https://www.facebook.com/watch/?v=1033433662993562", 0, None, 720),
    "media/videos/indonesia_tree_explosion.mp4": ("https://www.youtube.com/shorts/T0CASmx3fkU", 0, None, 720),
    "media/videos/limb_on_pole.mp4": ("https://www.facebook.com/watch/?v=2942484986199463", 0, None, 720),
    "media/videos/salina_tree_on_pole.mp4": ("https://www.facebook.com/watch/?v=1084130850192135", 0, None, 720),
}


def fetch(target: Path, url: str, start: int, length: int | None, width: int) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.mp4"
        subprocess.run([sys.executable, "-m", "yt_dlp", "-q", "--no-playlist", "-f",
                        "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/b", "--merge-output-format", "mp4",
                        "-o", str(raw), url], check=True)
        cut = ["-ss", str(start)] + (["-t", str(length)] if length else [])
        drone = "drone" in target.parts
        audio = ["-an"] if drone else ["-c:a", "aac", "-b:a", "64k"]
        vf = f"scale='min({width},iw)':-2" + (",fps=10" if drone else "")
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", *cut, "-i", str(raw), "-vf", vf, "-c:v", "libx264",
                        "-crf", "30" if drone else "28", "-preset", "slow", *audio, str(target)], check=True)


def main() -> None:
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH")
    force = "--force" in sys.argv
    for rel, (url, start, length, width) in CLIPS.items():
        target = ROOT / rel
        if target.exists() and not force:
            print(f"have  {rel}")
            continue
        try:
            fetch(target, url, start, length, width)
            print(f"saved {rel}")
        except subprocess.CalledProcessError as err:
            print(f"FAILED {rel}: {err}")


if __name__ == "__main__":
    main()
