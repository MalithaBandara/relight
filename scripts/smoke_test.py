"""Check the Meta Model API key and each model Relight uses, one small call each.

Usage:  python scripts/smoke_test.py [path/to/audio.wav] [path/to/photo.jpg]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from relight import config  # noqa: E402
from relight.extract import COMPLAINT_SCHEMA, COMPLAINT_SYSTEM  # noqa: E402
from relight.models import ModelClient  # noqa: E402


def step(name, fn):
    try:
        out = fn()
        print(f"[ok]   {name}: {str(out)[:300]}")
    except httpx.HTTPStatusError as e:
        print(f"[fail] {name}: HTTP {e.response.status_code} {e.response.text[:300]}")
    except Exception as e:  # noqa: BLE001 - report anything, keep going
        print(f"[fail] {name}: {type(e).__name__}: {e}")


def main() -> None:
    if not config.MODEL_API_KEY:
        sys.exit("MODEL_API_KEY is not set. Copy .env.example to .env and add your key.")
    client = ModelClient(mode="live")
    headers = {"Authorization": f"Bearer {config.MODEL_API_KEY}"}

    step("list models", lambda: [m["id"] for m in httpx.get(f"{config.META_API_BASE}/models", headers=headers,
                                                               timeout=30).raise_for_status().json()["data"]])
    step(f"{config.SPARK_MODEL} Sinhala extraction", lambda: client.spark_json(
        COMPLAINT_SYSTEM, "රෝහල පාරේ අංක 47 විදුලිය නැහැ. ලොකු සද්දයක් ආවා, කණුවක් වැටිලා වගේ.",
        COMPLAINT_SCHEMA, "Complaint"))
    step(f"{config.SPARK_MODEL} Tamil extraction", lambda: client.spark_json(
        COMPLAINT_SYSTEM, "சினமன் கார்டன்ஸ் லேன் 64, மின்சாரம் இல்லை. எங்கள் பக்கத்தில் மட்டும்.",
        COMPLAINT_SCHEMA, "Complaint"))
    args = [Path(a) for a in sys.argv[1:]]
    for a in args:
        if a.suffix.lower() == ".wav":
            step(f"Voice Transcribe {a.name}", lambda a=a: client.transcribe(a, ["English", "Tamil"]))
        elif a.suffix.lower() in (".jpg", ".jpeg", ".png"):
            step(f"SAM 3.1 'utility pole' on {a.name}", lambda a=a: client.segment_image(a, "utility pole"))
    if not args:
        print("(pass a .wav and a .jpg to also test Voice Transcribe and SAM 3.1)")


if __name__ == "__main__":
    main()
