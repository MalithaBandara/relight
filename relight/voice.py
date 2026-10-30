"""Text to speech for the call agent and the simulated callers.

Meta's models listen (Voice Transcribe) and think (Spark) but none of them speaks, so the agent's voice comes from
Microsoft's neural voices through edge-tts. Every clip is shaped like a phone line (300-3400 Hz, faint hiss,
compression, 8 kHz mono WAV) and cached on disk by its words and voice, so a line is only synthesised once.
Optional: without edge-tts or ffmpeg the console simply shows the call as text.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import MEDIA_DIR

try:
    import edge_tts
except ImportError:  # media extra not installed
    edge_tts = None

TTS_DIR = MEDIA_DIR / "audio" / "tts"

# Lead-in silence, telephone band, faint pink-noise hiss, compression, 8 kHz.
PHONE_FILTER = (
    "[0:a]aformat=channel_layouts=mono,adelay=300,apad=pad_dur=0.4,highpass=f=300,lowpass=f=3400,"
    "volume=1.4[v];"
    "anoisesrc=color=pink:amplitude=0.012:sample_rate=24000,highpass=f=300,lowpass=f=3400[n];"
    "[v][n]amix=inputs=2:duration=first:normalize=0,"
    "acompressor=threshold=0.1:ratio=4:attack=5:release=80,aresample=8000"
)


def available() -> bool:
    return edge_tts is not None and shutil.which("ffmpeg") is not None


def phone(src: Path, dst: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-filter_complex", PHONE_FILTER,
                    "-ac", "1", "-ar", "8000", "-c:a", "pcm_s16le", str(dst)], check=True)


async def synthesize(text: str, voice: str, rate: str = "+0%", out: Path | None = None) -> Path:
    """Speak `text` as a phone-quality WAV; cached under media/audio/tts unless `out` is given."""
    if not available():
        raise RuntimeError("text to speech needs edge-tts and ffmpeg")
    if out is None:
        key = hashlib.sha256(f"{voice}|{rate}|{text}".encode()).hexdigest()[:20]
        out = TTS_DIR / f"{key}.wav"
        if out.exists():
            return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        mp3 = Path(tmp) / "speech.mp3"
        await edge_tts.Communicate(text, voice, rate=rate).save(str(mp3))
        phone(mp3, out)
    return out
