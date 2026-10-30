"""Thin client for the Meta Model API (Muse Spark, Muse Voice Transcribe, SAM 3.1).

Every response is cached on disk, keyed by a hash of the request, so a scenario
replays identically without spending credits. In mock mode (no API key) calls are
served from that cache, and anything not cached returns None so the caller can
fall back to labelled ground truth. Each call is logged with the model that served
it so the UI can show which Meta model did what.
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from . import config

TIMEOUT = httpx.Timeout(120, connect=10)


class ModelClient:
    _blocked_warned = False

    def __init__(self, mode: str | None = None) -> None:
        self.mode = mode or config.MODEL_MODE
        self.base = config.META_API_BASE
        self.headers = {"Authorization": f"Bearer {config.MODEL_API_KEY}"}
        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ---- cache ------------------------------------------------------------

    def _key(self, kind: str, payload: Any) -> Path:
        h = hashlib.sha256(json.dumps([kind, payload], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return config.CACHE_DIR / f"{kind}-{h[:24]}.json"

    def _cached(self, kind: str, payload: Any, call) -> Any | None:
        path = self._key(kind, payload)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        if self.mode != "live":
            return None
        if not config.api_allowed():  # see config.api_allowed: the owner has not allowed paid calls right now
            if not ModelClient._blocked_warned:
                ModelClient._blocked_warned = True
                print("Meta Model API call blocked: the owner has not allowed API use (GO). Using cache/mock.",
                      file=sys.stderr)
            return None
        result = call()
        path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        return result

    # ---- Muse Spark -------------------------------------------------------

    def spark_json(self, system: str, user: str | list, schema: dict, name: str,
                   model: str | None = None, base: str | None = None) -> dict | None:
        """Chat completion constrained to a JSON schema. `user` may be a list of content parts."""
        model = model or config.SPARK_MODEL
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": name, "schema": schema}},
        }

        def call():
            r = httpx.post(f"{base or self.base}/chat/completions", json=body, headers=self.headers, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()

        resp = self._cached("spark", body, call)
        if resp is None:
            return None
        content = resp["choices"][0]["message"]["content"]
        return json.loads(_strip_fences(content))

    def spark_text(self, system: str, user: str, model: str | None = None) -> str | None:
        body = {"model": model or config.SPARK_MODEL,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}

        def call():
            r = httpx.post(f"{self.base}/chat/completions", json=body, headers=self.headers, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()

        resp = self._cached("spark", body, call)
        return resp["choices"][0]["message"]["content"] if resp else None

    def spark_listen(self, audio_path: Path, language: str) -> str | None:
        """Spark transcribes a call itself, for languages Voice Transcribe lacks (Sinhala).

        Spark accepts audio input; the content-part shape below follows the OpenAI-compatible convention and has
        not been checked against the live API yet.
        """
        audio = Path(audio_path).read_bytes()
        system = f"Transcribe this phone call. It is in {language}; write it in {language}'s own script. " \
                 "Return only the words spoken."
        key = {"model": config.SPARK_MODEL, "system": system, "audio_sha": hashlib.sha256(audio).hexdigest()}

        def call():
            body = {"model": config.SPARK_MODEL, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": [{"type": "input_audio", "input_audio": {
                    "data": base64.b64encode(audio).decode(), "format": "wav"}}]}]}
            r = httpx.post(f"{self.base}/chat/completions", json=body, headers=self.headers, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()

        resp = self._cached("spark-audio", key, call)
        return resp["choices"][0]["message"]["content"].strip() if resp else None

    # ---- Muse Voice Transcribe -------------------------------------------

    def transcribe(self, audio_path: Path, language_bias: list[str] | None = None) -> dict | None:
        audio = _wav_16k(Path(audio_path).read_bytes())
        request = {"mode": "ENDPOINTING", "model": config.TRANSCRIBE_MODEL, "audioEncoding": "WAV"}
        if language_bias:
            request["languageBias"] = language_bias
        key = {"request": request, "audio_sha": hashlib.sha256(audio).hexdigest()}

        def call():
            r = httpx.post(
                f"{self.base}/asr/transcribe",
                params={"sessionId": f"relight-{int(time.time() * 1000)}"},
                headers=self.headers,
                files={"request": (None, json.dumps(request), "application/json"),
                       "audio": (Path(audio_path).name, audio, "audio/wav")},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            return r.json()

        return self._cached("asr", key, call)

    # ---- SAM 3.1 ----------------------------------------------------------

    def segment_image(self, image_path: Path, prompt: str, confidence: bool = True) -> list[dict] | None:
        """Text-prompted segmentation. Returns [{id, box: (x1,y1,x2,y2), w, h, conf, mask}] per match."""
        data = Path(image_path).read_bytes()
        mime = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
        body = {
            "model": config.SAM_MODEL,
            "input": [{"role": "user", "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": f"data:{mime};base64,{base64.b64encode(data).decode()}"},
            ]}],
            "metadata": {"include_confidence": "true"} if confidence else {},
        }
        key = {"prompt": prompt, "image_sha": hashlib.sha256(data).hexdigest(), "conf": confidence}

        def call():
            r = httpx.post(f"{self.base}/responses", json=body, headers=self.headers, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()

        resp = self._cached("sam", key, call)
        return parse_sam_records(_response_text(resp)) if resp else None

    def segment_video(self, video_path: Path, prompt: str) -> list[dict] | None:
        """Text-prompted tracking through a clip. Records carry `frame` and the object `id` that persists across
        frames. The `input_video` part mirrors `input_image`; its exact field name is unverified against the API.
        """
        data = Path(video_path).read_bytes()
        mime = mimetypes.guess_type(str(video_path))[0] or "video/mp4"
        key = {"prompt": prompt, "video_sha": hashlib.sha256(data).hexdigest()}

        def call():
            body = {
                "model": config.SAM_MODEL,
                "input": [{"role": "user", "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_video", "video_url": f"data:{mime};base64,{base64.b64encode(data).decode()}"},
                ]}],
                "metadata": {"include_confidence": "true"},
            }
            r = httpx.post(f"{self.base}/responses", json=body, headers=self.headers, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()

        resp = self._cached("sam-video", key, call)
        return parse_sam_records(_response_text(resp)) if resp else None

    def spark_video_json(self, system: str, text: str, video_path: Path, schema: dict, name: str) -> dict | None:
        """Spark watches a clip and answers in JSON. The `video_url` content part follows the OpenAI-compatible
        image convention; unverified against the live API.
        """
        data = Path(video_path).read_bytes()
        mime = mimetypes.guess_type(str(video_path))[0] or "video/mp4"
        key = {"model": config.SPARK_MODEL, "system": system, "text": text, "schema": schema,
               "video_sha": hashlib.sha256(data).hexdigest()}

        def call():
            body = {
                "model": config.SPARK_MODEL,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": [
                    {"type": "text", "text": text},
                    {"type": "video_url", "video_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}},
                ]}],
                "response_format": {"type": "json_schema", "json_schema": {"name": name, "schema": schema}},
            }
            r = httpx.post(f"{self.base}/chat/completions", json=body, headers=self.headers, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()

        resp = self._cached("spark-video", key, call)
        return json.loads(_strip_fences(resp["choices"][0]["message"]["content"])) if resp else None


def _wav_16k(data: bytes) -> bytes:
    """Voice Transcribe takes mono 16-bit WAV at 16 or 24 kHz only. Phone calls are 8 kHz, so upsample them (the
    audio keeps its phone-line bandwidth; only the container rate changes)."""
    import io
    import wave
    with wave.open(io.BytesIO(data)) as w:
        rate, channels, width, frames = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.readframes(w.getnframes())
    if rate in (16000, 24000) and channels == 1 and width == 2:
        return data
    import array
    samples = array.array("h", frames)
    if channels > 1:
        samples = array.array("h", samples[::channels])
    out = array.array("h")
    step = rate / 16000  # linear interpolation onto the 16 kHz grid
    n = len(samples)
    for i in range(int(n / step)):
        x = i * step
        j = int(x)
        a, b = samples[j], samples[min(j + 1, n - 1)]
        out.append(int(a + (b - a) * (x - j)))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(out.tobytes())
    return buf.getvalue()


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    return s


def _response_text(resp: dict) -> str:
    """Concatenate output_text from a Responses API result."""
    if "output_text" in resp:
        return resp["output_text"]
    parts = []
    for item in resp.get("output", []):
        for c in item.get("content", []):
            if c.get("type") in ("output_text", "text"):
                parts.append(c.get("text", ""))
    return "\n".join(parts)


_TOKEN = re.compile(r"<\|(box|mask);([^|]*)\|>")


def parse_sam_records(text: str) -> list[dict]:
    """Parse SAM 3.1 special-token output: `<id><|box;x1=..;..|><|mask;..;data=H,W,<enc>payload|>`.

    Boxes are in source pixels. The mask payload is kept encoded (base85); box
    geometry is enough for the measurements Relight makes.
    """
    records: list[dict] = []
    for line in text.splitlines():
        frame = None
        if m := re.match(r"\s*<(\d+)f>", line):
            frame = int(m.group(1))
        current: dict | None = None
        for kind, fields in _TOKEN.findall(line):
            kv = dict(f.split("=", 1) for f in fields.split(";") if "=" in f)
            if kind == "box":
                current = {
                    "frame": frame,
                    "box": tuple(float(kv[k]) for k in ("x1", "y1", "x2", "y2")),
                    "w": float(kv.get("w", 0)), "h": float(kv.get("h", 0)),
                    "conf": float(kv["c"]) if "c" in kv else None,
                }
                records.append(current)
            elif kind == "mask" and current is not None:
                current["mask"] = kv.get("data")
        # Object ids precede each box token; attach them in order.
        ids = re.findall(r"(\d+)\s*<\|box", line)
        for rec, oid in zip([r for r in records if r["frame"] == frame][-len(ids):] if ids else [], ids):
            rec["id"] = int(oid)
    return records
