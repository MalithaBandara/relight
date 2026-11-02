"""A customer's own call to the outage desk, from the portal (browser microphone), answered by the call agent.

The calls in the scenarios are played by the simulated World; this one is a real person. They tap to talk, the browser
sends each utterance as a short WAV, Muse Voice Transcribe hears it (Muse Spark listens when the language is Sinhala,
which Voice Transcribe lacks), Muse Spark reads the report, and code decides what the agent says next: the same acts and
the same wording rules as every other call (`CallAgent.say`, fixed safety lines never reworded). The questions are the
agent's phase 1 (confirm or ask the address, ask about hazards); when nothing else is worth asking, or the caller hangs
up, the report is filed like any other call and the agent tells them what the control room knows. The tracer's
next-door question is not asked aloud here (no simulated neighbour answers it); it goes out by SMS as for any caller.

Without the Meta API (mock mode, or the owner's GO rule closed) nothing can listen, so the caller types their words and
the keyword parser reads them (labelled `mock (keywords)`), exactly as for unlabelled portal text.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import re
import wave
from typing import TYPE_CHECKING

from . import config
from .callagent import SAFETY, TRANSCRIBE_LANGS
from .locales import HAZARD_NAMES
from .realtime import BIAS

if TYPE_CHECKING:
    from .engine import Engine

MAX_AUDIO = 6 * 1024 * 1024  # a spoken answer is seconds long: 16 kHz mono is ~32 KB per second
MAX_CALLER_TURNS = 8  # then the report is filed with what was said
DENY = {"en": ("no", "not", "wrong", "nope", "nah"), "es": ("no", "incorrecto", "equivocado"),
        "ta": ("இல்லை", "இல்ல", "தவறு"), "si": ("නැහැ", "නෑ", "වැරදියි"), "hi": ("नहीं", "गलत", "नही")}


def denied(text: str, lang: str) -> bool:
    """Did the caller answer 'no' to 'is that your address?' (a short answer, in any of our languages)."""
    words = DENY.get(lang, DENY["en"])
    t = text.lower()
    if lang in ("en", "es"):
        return any(re.search(rf"\b{re.escape(w)}\b", t) for w in words)
    return any(w in t for w in words)


async def listen(engine: Engine, ref: str, lang: str, wav: bytes) -> tuple[str | None, str | None, str]:
    """Save one spoken utterance, then have Voice Transcribe (or Spark, for Sinhala) hear it: (path, words, who heard).

    Shared by the customer's call and a crew's report. `words` is None when nothing could listen or the audio is
    not a short mono 16 or 24 kHz WAV.
    """
    try:
        with wave.open(io.BytesIO(wav)) as w:
            ok = w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() in (16000, 24000)
    except wave.Error:
        ok = False
    if not ok or len(wav) > MAX_AUDIO:
        return None, None, ""
    rel = f"media/uploads/call-{hashlib.sha256(wav).hexdigest()[:16]}.wav"
    path = config.ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(wav)
    agent, client = engine.agent, engine.client
    try:
        if lang in TRANSCRIBE_LANGS:
            res = await asyncio.to_thread(client.transcribe, path, BIAS.get(lang), agent.keywords())
            text, model = (res or {}).get("transcript", "").strip(), "Voice Transcribe"
        else:
            text = await asyncio.to_thread(client.spark_listen, path, agent.lang_name.get(lang, lang))
            text, model = (text or "").strip(), "Muse Spark"
    except Exception as err:  # noqa: BLE001 - no network or a refused request: the caller can type instead
        await engine.log("Code", f"{ref}: could not transcribe the speaker", str(err)[:160], ref)
        return rel, None, ""
    if text:
        engine._count(model)
        await engine.log(model, f"{ref}: speaker heard", text[:160], ref)
    return rel, text or None, model


class PortalCall:
    def __init__(self, engine: Engine, call_id: str, who: str, language: str, now: float) -> None:
        c = engine.db.by_account(who) or engine.db.by_phone(who)
        self.e, self.id, self.t = engine, call_id, now
        self.phone = c.phone if c else (who or None)
        self.event = {"t": now, "type": "complaint", "id": call_id, "channel": "call", "language": language,
                      "from": self.phone, "text": "", "truth": {}, "portal": True}
        self.lang = engine.agent._lang(language)
        self.call: dict = {}
        self.asked: set[str] = set()
        self.skip: set[int] = set()  # caller turns that answered a yes/no question: not part of the report
        self.denied = False
        self.done = False
        self.msg: dict | None = None
        self.account: str | None = None

    # ---- the call ----------------------------------------------------------------------------

    async def start(self) -> dict:
        self.call = await self.e.agent.start(self.event, None, "")
        self.e.agent.live[self.id] = self.call  # lets /api/call/<id>/<turn>.wav find the lines before the report exists
        return self.result(0)

    def result(self, first: int, error: str | None = None) -> dict:
        turns = [{"i": i, "who": t["who"], "text": t["text"], "en": t.get("en"), "model": t.get("model")}
                 for i, t in enumerate(self.call["turns"]) if i >= first]
        out = {"ok": True, "id": self.id, "language": self.lang, "turns": turns, "done": self.done}
        if error:
            out["error"] = error
        if self.done:
            out.update(account=self.account, incident=(self.msg or {}).get("incident"),
                       status=self.msg.get("status") if self.msg else None)
        return out

    def can_listen(self) -> bool:
        return self.e.client.mode == "live" and bool(config.MODEL_API_KEY) and config.api_allowed()

    async def say(self, wav: bytes | None, typed: str) -> dict:
        """One utterance from the caller (audio, or typed words); returns the turns added, ending with the agent's reply."""
        if self.done:
            return self.result(len(self.call["turns"]), "This call has ended.")
        first = len(self.call["turns"])
        model, rel = "Typed in the portal", None
        if wav:
            rel, text, model = await self._listen(wav)
            if not text:
                return self.result(first, "Voice recognition is off in this demo (the Meta API is not available "
                                   "right now): type your message instead." if not self.can_listen()
                                   else "I could not make that out. Please try again, a little closer to the microphone.")
        else:
            text = typed.strip()
            if not text:
                return self.result(first, "Say or type something first.")
        self.call["turns"].append({"who": "caller", "text": text, "model": model, "audio": rel})
        if "confirm_address" in self.asked and "confirmed" not in self.asked:
            self.asked.add("confirmed")
            self.skip.add(len(self.call["turns"]) - 1)
            self.denied = denied(text, self.lang)
        await self._respond()
        return self.result(first)

    async def _listen(self, wav: bytes) -> tuple[str | None, str | None, str]:
        return await listen(self.e, self.id, self.lang, wav)

    # ---- what the agent says next -------------------------------------------------------------

    def _text(self) -> str:
        # one sentence per turn, so a street name cannot run on from the end of the previous answer
        return " ".join(t["text"].rstrip(" .!?") + "." for i, t in enumerate(self.call["turns"])
                        if t["who"] == "caller" and i not in self.skip)

    def _caller_turns(self) -> int:
        return sum(t["who"] == "caller" for t in self.call["turns"])

    async def _respond(self, force: bool = False) -> None:
        eng, ag, call, asked = self.e, self.e.agent, self.call, self.asked
        text = self._text()
        ext = await eng._extract(text, self.event)
        eng._count(ext.model)
        f = ext.fields
        loc = eng._locate(f, None if self.denied else self.phone) if not f["is_junk"] else None
        if not force and not f["is_junk"] and self._caller_turns() < MAX_CALLER_TURNS:
            hazard = f.get("hazard", "none")
            if hazard in SAFETY and "safety" not in asked:
                asked.add("safety")
                await ag.say(call, SAFETY[hazard])
            if not (loc and loc.get("transformer")):
                if "ask_address" not in asked:
                    asked.add("ask_address")
                    await ag.say(call, "ask_address")
                    return
            elif loc.get("method") == "caller ID" and "confirm_address" not in asked:
                asked.add("confirm_address")
                await ag.say(call, "confirm_address", address=ag.address(loc.get("house_no"), loc.get("street")),
                             keep=(loc.get("street"),))
                return
            if hazard == "none" and "ask_hazard" not in asked:
                asked.add("ask_hazard")
                if known := ag._hazard_known(loc or {}):  # earlier callers reported it: warn this one instead of asking
                    await ag.say(call, "known_hazard", what=HAZARD_NAMES[call["language"]][known],
                                 en_kw={"what": HAZARD_NAMES["en"][known]})
                else:
                    await ag.say(call, "ask_hazard")
                    return
        await self._file(text, ext, loc)

    async def _file(self, text: str, ext, loc: dict | None) -> None:
        """File the report like any call (dedup, claim, evidence, hazards), re-trace, then tell the caller."""
        eng, ag, call = self.e, self.e.agent, self.call
        e = {**self.event, "t": max(self.t, eng.elapsed), "text": text}
        async with eng.lock:
            await eng.advance(e["t"])
            msg = await eng._file(e, call, text, ext, loc)
            if msg in eng._calls:
                eng._calls.remove(msg)  # this call is finished below, by turn, not after a replay event
            await eng.recompute()
        self.msg = msg
        f, loc = msg["fields"], msg.get("location") or {}
        if msg["status"] == "junk":
            await ag.say(call, "junk")
        else:
            if msg["status"] == "duplicate":
                first = next((m for m in eng.messages if m["id"] == msg.get("dup_of")), None)
                if first:
                    await ag.say(call, "repeat", at=eng.clock(first["t"]))
            if f.get("hazard") in SAFETY and "safety" not in self.asked:
                await ag.say(call, SAFETY[f["hazard"]])
            if urgent := ag.urgent(f, loc):
                call["escalated"] = True
                await ag.say(call, "escalate")
                await eng.log("Agent", f"{self.id}: urgent call flagged to the control room", urgent, self.id)
            await ag._status(msg)
        await ag.say(call, "close")
        await self._end(msg)
        async with eng.lock:
            await eng._maybe_ask(eng._questions)  # whatever the caller was not asked goes out by SMS

    async def _end(self, msg: dict | None) -> None:
        self.done = True
        self.account = ((msg or {}).get("location") or {}).get("account")
        self.e.agent.live.pop(self.id, None)
        await self.e.broadcast({"type": "call", "id": self.id, "call": self.call, "incident": (msg or {}).get("incident")})
        if msg:
            await self.e.note("Agent", f"{self.id}: portal call answered ({self.e.agent.lang_name.get(self.lang)})",
                              " → ".join(a.replace("_", " ") for a in self.call["acts"]), self.id)

    async def hang_up(self) -> dict:
        """The caller ends the call: what they said so far is filed; a call with nothing said just closes."""
        first = len(self.call["turns"])
        if not self.done:
            if self._caller_turns():
                await self._respond(force=True)
            else:
                await self.e.note("Agent", f"{self.id}: portal call ended before the caller spoke", "", self.id)
                self.done = True
                self.e.agent.live.pop(self.id, None)
        return self.result(first)
