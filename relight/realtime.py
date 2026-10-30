"""Realtime speech: a phone line heard by Muse Voice Transcribe as it is spoken.

Every live call gets one realtime session (wss://api.meta.ai/v1/asr/realtime) for its whole length, the way a phone
line would be tapped: what the caller and a call-taker say goes down the same socket as 24 kHz PCM in 80 ms frames,
paced at real time, with silence in between (the service closes a stream that falls behind real time). The agent's
own lines are not sent: their words are known, and their late transcripts were mistaken for the caller's next turn
in the first live run. A turn belongs to whoever's audio was on the line when Voice Transcribe heard it start
(`speechStart`); in DIARIZATION mode its speaker label (A, B, ...) is shown, not trusted, since the first live run
gave the agent's and the caller's voices the same label. A call-taker's microphone is mixed into the same frames. Words appear as partial transcripts while the person is still speaking, so the agent and the copilot can
act on a turn the moment it ends rather than after the call.

The handshake carries the language bias and the feeder's street names as `keywords`, so local street names are
recognised. Sinhala is not one of Voice Transcribe's languages: for a Sinhala line Spark listens to each utterance
once it ends.

What a live session hears for a recorded utterance is cached by the clip and the session settings, so a replay shows
the same partial and final transcripts at the same pace for free. Without the API (no key, mock mode, or the owner's
GO rule) the script is paced out word by word over the clip's length and labelled `mock (script)`; microphone audio
is not transcribed then.

The protocol follows Meta's Voice API reference (RealtimeHandshakeRequest, ServerMessage); it has not been run against
the live service yet.
"""

from __future__ import annotations

import array
import asyncio
import contextlib
import hashlib
import json
import time
import wave
from pathlib import Path
from typing import Awaitable, Callable

from . import config
from .models import wav_pcm

RATE = 24000
FRAME_MS = 80
FRAME_BYTES = RATE * 2 * FRAME_MS // 1000  # 3,840 bytes per frame
SILENCE = bytes(FRAME_BYTES)
URL = "wss://api.meta.ai/v1/asr/realtime"
FINAL_WAIT_S = 6.0  # how long after an utterance ends to wait for its final transcript (live: ~3.5 s)
BIAS = {"en": ["English"], "ta": ["Tamil", "English"], "hi": ["Hindi", "English"], "es": ["Spanish", "English"]}
REALTIME_LANGS = set(BIAS)  # Sinhala is not one of Voice Transcribe's languages
MAX_KEYWORDS = 100
SPEED = 1.0  # tests speed up the pacing of scripted and cached utterances (never a live socket)

Event = dict  # {"kind": "partial" | "final", "text", "role", "speaker", "ms"}


def clip_seconds(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


class Line:
    """One phone call's realtime transcription session. `on_event` gets partial and final transcripts per utterance."""

    def __init__(self, client, call_id: str, language: str, keywords: list[str] | None = None,
                 on_event: Callable[[Event], Awaitable[None]] | None = None, diarize: bool = True) -> None:
        self.client, self.id, self.lang = client, call_id, language
        self.keywords = [k for k in dict.fromkeys(keywords or []) if k][:MAX_KEYWORDS]
        self.on_event = on_event
        self.mode = "DIARIZATION" if diarize else "ENDPOINTING"
        self.ws = None
        self.live = False
        self.error: str | None = None
        self._out: bytearray = bytearray()  # audio waiting to go down the line (a clip being played)
        self._mic: bytearray = bytearray()  # call-taker microphone, mixed into the same frames
        self._sent_ms = 0
        self._spans: list[tuple[int, int, str]] = []  # (start_ms, end_ms, role) of audio put on the line
        self._turns: dict[int, dict] = {}
        self._current: int | None = None  # turnId being spoken
        self._utt: dict | None = None  # the utterance being recorded for the cache
        self._tasks: list[asyncio.Task] = []
        self._finals: asyncio.Queue = asyncio.Queue()

    # ---- session ----------------------------------------------------------------------

    def can_stream(self) -> bool:
        return (self.lang in REALTIME_LANGS and self.client.mode == "live" and bool(config.MODEL_API_KEY)
                and config.api_allowed())

    async def open(self) -> None:
        if not self.can_stream():
            return
        try:
            import websockets
            self.ws = await websockets.connect(f"{URL}?sessionId=relight-{self.id}-{int(time.time() * 1000)}",
                                               max_size=2 ** 22, open_timeout=10)
            hello = {"authorization": {"accessToken": f"Bearer {config.MODEL_API_KEY}"}, "audioEncoding": "PCM_24KHZ",
                     "model": config.TRANSCRIBE_MODEL, "mode": self.mode, "partialMode": "CUMULATIVE",
                     "emitAudioProgress": False, "languageBias": BIAS[self.lang]}
            if self.keywords:
                hello["keywords"] = self.keywords
            await self.ws.send(json.dumps(hello))
            ack = json.loads(await asyncio.wait_for(self.ws.recv(), 10))
            if "sessionId" not in ack:
                raise RuntimeError(ack.get("message") or "handshake refused")
        except Exception as err:  # noqa: BLE001 - no socket: the line falls back to cache / script
            self.error = f"realtime transcription unavailable: {str(err)[:160]}"
            with contextlib.suppress(Exception):
                await self.ws.close()
            self.ws = None
            return
        self.live = True
        self._tasks = [asyncio.create_task(self._pump()), asyncio.create_task(self._read())]

    async def close(self) -> None:
        if not self.live:
            return
        self.live = False
        with contextlib.suppress(Exception):
            await self.ws.send(json.dumps({"type": "endStream"}))
            await asyncio.wait_for(self._tasks[1], 5)
        for t in self._tasks:
            t.cancel()
        with contextlib.suppress(Exception):
            await self.ws.close()

    async def _pump(self) -> None:
        """Send one 80 ms frame every 80 ms: the clip being played, mixed with the microphone, or silence."""
        start = time.monotonic()
        n = 0
        try:
            while self.live:
                clip, mic = bytes(self._out[:FRAME_BYTES]), bytes(self._mic[:FRAME_BYTES])
                del self._out[:FRAME_BYTES], self._mic[:FRAME_BYTES]
                await self.ws.send(_mix(clip, mic))
                n += 1
                self._sent_ms = n * FRAME_MS
                await asyncio.sleep(max(0.0, start + n * FRAME_MS / 1000 - time.monotonic()))
        except Exception as err:  # noqa: BLE001
            self.error = f"realtime line dropped: {str(err)[:160]}"
            self.live = False

    async def _read(self) -> None:
        try:
            async for raw in self.ws:
                if isinstance(raw, bytes):
                    continue
                await self._server(json.loads(raw))
        except Exception as err:  # noqa: BLE001
            self.error = self.error or f"realtime line closed: {str(err)[:160]}"

    async def _server(self, m: dict) -> None:
        kind, ms = m.get("type"), int(m.get("audioProcessedMs") or self._sent_ms)
        if kind == "error":
            self.error = m.get("message", "error")
        elif kind == "speechStart":
            self._turns[m["turnId"]] = {"text": "", "role": self._role_at(ms), "start": ms}
            self._current = m["turnId"]
        elif kind == "transcript" and m.get("transcript"):
            tid = self._current
            turn = self._turns.setdefault(tid, {"text": "", "role": self._role_at(ms), "start": ms})
            turn["text"] = m["transcript"].strip()
            await self._emit({"kind": "partial", "text": turn["text"], "role": turn["role"], "ms": ms,
                              "start": turn["start"], "speaker": turn.get("speaker")})
        elif kind == "speaker":
            # Labels the span just transcribed. Shown to the operator; who spoke is decided by time, not by label.
            if (tid := self._current) in self._turns:
                self._turns[tid]["speaker"] = m["label"]
        elif kind == "speechComplete":
            turn = self._turns.pop(m["turnId"], {"role": self._role_at(ms), "start": ms})
            text = (m.get("transcript") or turn.get("text", "")).strip()
            ev = {"kind": "final", "text": text, "role": turn["role"], "ms": ms, "start": turn["start"],
                  "speaker": turn.get("speaker")}
            await self._emit(ev)
            await self._finals.put(ev)

    def _role_at(self, ms: int) -> str:
        best = None
        for a, b, role in self._spans:
            if a - 400 <= ms <= b + 1500:
                best = role
        return best or "unknown"  # heard while nobody was on the line: noise, never anyone's turn

    async def _emit(self, ev: Event) -> None:
        if self._utt is not None and ev["role"] == self._utt["role"]:
            self._utt["events"].append({**ev, "at": round(time.monotonic() - self._utt["t0"], 2)})
        if self.on_event:
            await self.on_event(ev)

    # ---- speaking on the line -----------------------------------------------------------

    async def play(self, path: Path | None, role: str, script: str, seconds: float | None = None,
                   listen: bool = True) -> tuple[str, str]:
        """Put one utterance on the line and wait until it has been spoken and heard.

        Returns (what Voice Transcribe heard, the model that heard it); the script when nothing could listen.
        `path` may be None (no text-to-speech available): the script is paced out over `seconds`. With `listen`
        False (the agent's own lines, whose words are known) nothing is sent: the line carries silence meanwhile.
        """
        seconds = seconds or (clip_seconds(path) if path else max(1.5, len(script.split()) / 2.6))
        if not self.live:  # a live socket always runs at real time
            seconds /= SPEED
        if not listen:
            await asyncio.sleep(seconds)
            return script, "Agent"
        if path is None:
            await self._pace(script, role, seconds, "mock (script)")
            return script, "mock (script)"
        data = Path(path).read_bytes()
        key = self.client._key("asr-rt", {"audio_sha": hashlib.sha256(data).hexdigest(), "lang": self.lang,
                                          "mode": self.mode, "keywords": self.keywords})
        if key.exists():
            cached = json.loads(key.read_text(encoding="utf-8"))
            await self._replay(cached["events"], role, seconds)
            return cached["text"], "Voice Transcribe (realtime)"
        if not self.live:
            await self._pace(script, role, seconds, "mock (script)")
            return script, "mock (script)"
        pcm = wav_pcm(data, RATE)
        while not self._finals.empty():
            self._finals.get_nowait()
        start = self._sent_ms + len(self._out) * FRAME_MS // FRAME_BYTES
        end = start + len(pcm) * 1000 // (RATE * 2)
        self._spans.append((start, end, role))
        self._utt = {"role": role, "t0": time.monotonic(), "events": []}
        self._out.extend(pcm)
        await asyncio.sleep(max(0.0, (end - self._sent_ms) / 1000))  # until the whole clip has gone down the line
        heard = []
        deadline = time.monotonic() + FINAL_WAIT_S
        while time.monotonic() < deadline:
            try:
                ev = await asyncio.wait_for(self._finals.get(), max(0.05, deadline - time.monotonic()))
            except asyncio.TimeoutError:
                break
            if start - 300 <= ev["start"] <= end:  # a turn that began during this utterance
                heard.append(ev["text"])
                deadline = time.monotonic() + 0.8  # a long utterance may end in more than one turn
        utt, self._utt = self._utt, None
        text = " ".join(t for t in heard if t).strip()
        if not text:
            return script, "mock (script)"
        key.write_text(json.dumps({"text": text, "events": utt["events"]}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        return text, "Voice Transcribe (realtime)"

    def mic(self, pcm: bytes) -> None:
        """Call-taker microphone frames (24 kHz mono s16le) from the console, mixed into the line."""
        if self.live:
            if not self._spans or self._spans[-1][2] != "mic" or self._spans[-1][1] < self._sent_ms - 500:
                self._spans.append((self._sent_ms, self._sent_ms + 1000, "mic"))
            else:
                a, _, r = self._spans[-1]
                self._spans[-1] = (a, self._sent_ms + 1000, r)
            self._mic.extend(pcm)

    async def _pace(self, script: str, role: str, seconds: float, model: str) -> None:
        """No listener: show the script word by word as if it were being heard."""
        words = script.split()
        if not words:
            await asyncio.sleep(seconds)
            return
        step = seconds / len(words)
        shown = []
        for w in words:
            await asyncio.sleep(step)
            shown.append(w)
            if self.on_event and (len(shown) % 3 == 0 or len(shown) == len(words)):
                await self.on_event({"kind": "partial", "text": " ".join(shown), "role": role, "model": model})
        if self.on_event:
            await self.on_event({"kind": "final", "text": script, "role": role, "model": model})

    async def _replay(self, events: list[dict], role: str, seconds: float) -> None:
        t0 = time.monotonic()
        for ev in events:
            await asyncio.sleep(max(0.0, t0 + ev["at"] / SPEED - time.monotonic()))
            if self.on_event:
                await self.on_event({**ev, "role": role, "model": "Voice Transcribe (realtime)"})
        await asyncio.sleep(max(0.0, t0 + seconds - time.monotonic()))


def _mix(a: bytes, b: bytes) -> bytes:
    if not b:
        return a.ljust(FRAME_BYTES, b"\0")
    if not a:
        return b.ljust(FRAME_BYTES, b"\0")
    x, y = array.array("h", a.ljust(FRAME_BYTES, b"\0")), array.array("h", b.ljust(FRAME_BYTES, b"\0"))
    return array.array("h", (max(-32768, min(32767, p + q)) for p, q in zip(x, y))).tobytes()
