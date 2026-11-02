"""A field crew's own report, sent from the crew page (voice, text, photo), read back and confirmed by the crew.

The scenarios' crews are played by the simulated World. This is a real person in the field: they pick their crew,
say or type what they see, and may attach a photo. Voice Transcribe hears it (Muse Spark listens when the language is
Sinhala), Muse Spark reads it as a crew report (damage, location, whether the device is healthy, houses without supply,
crews needed), and the agent reads back what it understood, as is standard on utility radio. Nothing changes until the
crew confirms; "not correct" takes a corrected report and reads it back again (three read-backs at most, then the last
reading is filed). A confirmed report goes through the same path as a scripted one (`Engine._crew_filed`): the
incident's diagnosis may change, the crew's photo is analysed, and the agent acknowledges.

Without the Meta API a typed report is read by keywords (`mock (keywords)`); spoken audio needs the API.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from . import config
from .callagent import crew_summary
from .portalcall import listen

if TYPE_CHECKING:
    from .engine import Engine

MAX_READBACKS = 3


class CrewReport:
    def __init__(self, engine: Engine, rid: str, crew: dict, language: str, now: float, media: str | None = None) -> None:
        self.e, self.id, self.crew = engine, rid, crew
        self.lang = engine.agent._lang(language)
        self.event = {"t": now, "type": "crew_note", "id": rid, "crew": crew["name"], "language": self.lang, "text": "",
                      "incident": crew["incident"], "truth": {}, "human": True}
        if media:
            self.event["video" if Path(media).suffix in (".mp4", ".mov", ".webm") else "photo"] = media
        self.call: dict = {}
        self.ext = None
        self.readbacks = 0
        self.done = False
        self.incident: str | None = None

    def can_listen(self) -> bool:
        return self.e.client.mode == "live" and bool(config.MODEL_API_KEY) and config.api_allowed()

    def result(self, first: int, error: str | None = None) -> dict:
        turns = [{"i": i, "who": t["who"], "text": t["text"], "en": t.get("en"), "model": t.get("model"),
                  "act": t.get("act")} for i, t in enumerate(self.call["turns"]) if i >= first]
        out = {"ok": True, "id": self.id, "crew": self.crew["name"], "language": self.lang, "turns": turns,
               "state": "done" if self.done else "confirm", "readbacks": self.readbacks}
        if error:
            out["error"] = error
        if self.done:
            inc = self.e._incident(self.incident)
            out["incident"] = self.incident
            out["incident_title"] = inc["title"] if inc else None
            out["incident_label"] = inc["label"] if inc else None
        return out

    async def _hear(self, wav: bytes | None, text: str) -> tuple[str | None, str, str | None, str | None]:
        """(words, who heard, saved audio, why nothing was heard)."""
        if wav:
            rel, said, model = await listen(self.e, self.id, self.lang, wav)
            if said:
                return said, model, rel, None
            return None, "", rel, ("Voice recognition is off in this demo (the Meta API is not available right now): "
                                   "type your report instead." if not self.can_listen()
                                   else "I could not make that out. Please say it again, closer to the microphone.")
        text = text.strip()
        return (text, "Typed on the crew page", None, None) if text else (None, "", None, "Say or type your report first.")

    def _crew_text(self) -> str:
        return ". ".join(t["text"].rstrip(" .!?") for t in self.call["turns"] if t["who"] == "crew")

    async def begin(self, wav: bytes | None, text: str) -> dict:
        said, model, rel, why = await self._hear(wav, text)
        if not said:
            return {"ok": True, "id": None, "turns": [], "state": "new", "error": why}
        self.event["text"], self.event["audio"] = said, rel
        self.call = self.e.agent.crew_start(self.event, said, model)
        await self._readback()
        return self.result(0)

    async def _readback(self) -> None:
        agent = self.e.agent
        self.ext = await asyncio.to_thread(self.e.extractor.crew_note, self._crew_text(), {})
        self.e._count(self.ext.model)
        f = self.ext.fields
        self.readbacks += 1
        await agent.say(self.call, "readback", summary=crew_summary(f, self.lang),
                        en_kw={"summary": crew_summary(f, "en")}, keep=(f.get("street"),))

    async def answer(self, ok: bool, wav: bytes | None, text: str) -> dict:
        """The crew's reply to the read-back: 'correct', or a corrected report that is read back again."""
        if self.done:
            return self.result(len(self.call["turns"]), "This report is already filed.")
        first = len(self.call["turns"])
        if ok:
            await self._file()
            return self.result(first)
        said, model, rel, why = await self._hear(wav, text)
        if not said:
            return self.result(first, why or "Say or type the correction.")
        self.call["turns"].append({"who": "crew", "text": said, "model": model, "audio": rel})
        if self.readbacks >= MAX_READBACKS:
            await self._file()  # three read-backs: file the last reading rather than keep the crew waiting
        else:
            await self._readback()
        return self.result(first)

    async def _file(self) -> None:
        eng, e = self.e, self.event
        text = self._crew_text()
        e["text"] = text
        async with eng.lock:
            await eng.advance(max(e["t"], eng.elapsed))
            e["t"] = max(e["t"], eng.elapsed)
            await eng._crew_filed(e, self.call, self.ext, text)
            await eng.recompute()
        msg = next((m for m in reversed(eng.messages) if m["id"] == self.id), None)
        self.incident = (msg or {}).get("incident")
        self.done = True
        await eng.broadcast({"type": "call", "id": self.id, "call": self.call, "incident": self.incident})
