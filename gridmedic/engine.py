"""The triage loop: each incoming event becomes evidence, the tracer re-locates faults,
the planner re-ranks the repair queue, and the agent asks customers questions when
two explanations are still close.

Evidence is always rebuilt from the stored messages, so when Muse Spark reviews what
the offline model (Muse Glimmer) extracted during a network outage and corrects it,
the faults are simply recomputed from the corrected record.

Every step is logged to a timeline tagged with the model (or code) that did it.
"""

from __future__ import annotations

import asyncio
from collections import Counter

import httpx
from typing import Any, Awaitable, Callable

from . import config
from .customers import CustomerDB
from .extract import Extractor
from .grid import get_feeder, haversine_m
from .models import ModelClient
from .planner import Crew, Job, schedule, score
from .tracer import Damage, Evidence, Tracer
from .vision import analyse_photo

LOCATED_AT = 0.8  # confidence at which a fault counts as located
ASK_BELOW = 0.85  # confidence below which the agent asks a customer to disambiguate
PROBE_GAP_S = 120
REVIEW_FIELDS = ["street", "house_no", "symptom", "hazard", "is_junk"]

QUESTION = {
    "en": "Outage desk: we are locating a fault near you. Is the power on at your home right now? Reply YES or NO.",
    "si": "විදුලි දෝෂ අංශය: ඔබේ ප්‍රදේශයේ දෝෂයක් සොයමින් සිටිමු. දැන් ඔබේ නිවසේ විදුලිය තිබේද? ඔව් හෝ නැත ලෙස පිළිතුරු දෙන්න.",
    "ta": "மின் தடை பிரிவு: உங்கள் பகுதியில் ஒரு கோளாறைக் கண்டறிகிறோம். இப்போது உங்கள் வீட்டில் மின்சாரம் உள்ளதா? ஆம் அல்லது இல்லை என்று பதிலளிக்கவும்.",
}
NOTICE = {
    "en": "Outage desk: we have found the fault affecting your supply ({kind}). A crew is assigned. Estimated restoration in about {eta}.",
    "si": "විදුලි දෝෂ අංශය: ඔබේ සැපයුමට බලපාන දෝෂය සොයාගෙන ඇත ({kind}). කණ්ඩායමක් යොදවා ඇත. විදුලිය නැවත ලැබීමට ආසන්න කාලය {eta}.",
    "ta": "மின் தடை பிரிவு: உங்கள் மின் விநியோகத்தை பாதித்த கோளாறு கண்டறியப்பட்டது ({kind}). குழு அனுப்பப்பட்டுள்ளது. மின்சாரம் மீண்டும் வர சுமார் {eta}.",
}
LANG_NAME = {"en": "English", "si": "Sinhala", "ta": "Tamil"}
KIND_TITLE = {"pole_down": "Pole down", "tree_on_line": "Tree on line", "live_wire": "Live wire on road",
              "wire_down": "Wire down", "blown_fuse": "Blown fuse", "unknown": "Outage, cause unknown"}

EXPLAIN_SYSTEM = """You are the reasoning voice of GridMedic, an outage-triage agent for a distribution utility.
Given the facts the fault tracer used, explain to the control-room dispatcher in at most two short
sentences why this fault is located where it is and what to send. Plain language, no hedging, no lists."""
NOTICE_SYSTEM = """Write a short SMS from an electricity utility's outage desk to a customer, in the requested
language and script. Say the fault affecting them has been found, a crew is assigned, and give the
estimated restoration time exactly as provided. One or two sentences, polite, no emojis."""

Broadcast = Callable[[dict], Awaitable[None]]


def fmt_eta(minutes: float) -> str:
    h, m = divmod(int(round(minutes / 10.0) * 10), 60)
    return f"{h} h {m} min" if h else f"{m} min"


class Engine:
    def __init__(self, scenario: dict, broadcast: Broadcast, on_probe: Callable[[dict], None]) -> None:
        self.feeder = get_feeder()
        self.db = CustomerDB()
        self.client = ModelClient()
        self.extractor = Extractor(self.client)
        # Muse Glimmer served locally (vLLM / llama.cpp, OpenAI-compatible); always "live" because it is local.
        self.glimmer = Extractor(ModelClient(mode="live"), model=config.GLIMMER_MODEL, base=config.GLIMMER_BASE,
                                 label="Muse Glimmer (offline)")
        self.tracer = Tracer(self.feeder, self.db.counts_by_transformer())
        self.critical = self.db.critical_by_transformer()
        self.scenario = scenario
        self.broadcast = broadcast
        self.on_probe = on_probe
        self.crews = [Crew(c["id"], c["name"], set(c["skills"]), *self.feeder.bus_pos[c["base"]])
                      for c in scenario["crews"]]
        self.reset()

    def reset(self) -> None:
        self.elapsed = 0.0
        self.offline = False
        self.queued: list[dict] = []  # calls waiting for cloud transcription while offline
        self.messages: list[dict] = []
        self.timeline: list[dict] = []
        self.field_damage: list[Damage] = []  # from photos and drone clips
        self.scada_open: set[str] = set()
        self.probes: list[dict] = []
        self.notices: list[dict] = []
        self.explained: dict[str, str] = {}  # fault id -> kind it was explained as
        self.faults: list[dict] = []
        self.plan: dict = {}
        self.baseline: dict = {}
        self.located_at: dict[str, float] = {}
        self.model_calls: Counter = Counter()
        self._rebuild()

    # ---- helpers ------------------------------------------------------------

    async def log(self, model: str, title: str, detail: str = "", ref: str | None = None) -> None:
        entry = {"t": round(self.elapsed), "model": model, "title": title, "detail": detail, "ref": ref}
        self.timeline.append(entry)
        if not model.startswith(("Code", "SCADA", "Agent", "mock", "Network")):
            for m in model.split(" + "):
                self.model_calls[m] += 1
        await self.broadcast({"type": "timeline", "entry": entry})

    def _locate(self, fields: dict, sender: str | None) -> dict:
        """Place a message on the grid: account, then address, then caller ID, then landmark."""
        c = None
        method = None
        if fields.get("account_no"):
            c, method = self.db.by_account(fields["account_no"]), "account number"
        if c is None and fields.get("street") and fields.get("house_no"):
            c, s = self.db.by_address(fields["street"], fields["house_no"])
            method = f"address match ({s:.0%})" if c else None
        if c is None and sender:
            c, method = self.db.by_phone(sender), "caller ID"
            if c and fields.get("street"):
                street, _ = self.db.match_street(fields["street"])
                if street and street != c.street:
                    c, method = None, None  # calling about somewhere else
        if c:
            return {"account": c.account_no, "name": c.name, "transformer": c.transformer_id,
                    "lat": c.lat, "lon": c.lon, "method": method, "street": c.street, "house_no": c.house_no}
        lm = self.db.match_landmark(" ".join(filter(None, [fields.get("landmark"), fields.get("street")])))
        if lm:
            return {"account": None, "transformer": lm["transformer_id"], "lat": lm["lat"], "lon": lm["lon"],
                    "method": f"landmark: {lm['name']}"}
        if fields.get("street"):
            street, s = self.db.match_street(fields["street"])
            if street and s > 0.6:
                xf = [t for t in self.feeder.transformers.values()
                      if self.feeder.sections[t.section].street == street]
                if xf:
                    t = xf[len(xf) // 2]
                    return {"account": None, "transformer": None, "lat": t.lat, "lon": t.lon,
                            "method": f"street only: {street}", "street_xf": t.id}
        return {"account": None, "transformer": None, "lat": None, "lon": None, "method": "not located"}

    def _damage(self, source: str, kind: str, loc: dict, strength: float) -> Damage | None:
        xf = loc.get("transformer") or loc.get("street_xf")
        if not xf or kind in ("none", "other"):
            return None
        t = self.feeder.transformers[xf]
        return Damage(source, kind, t.section, xf, strength, loc["lat"], loc["lon"])

    def _hazard(self, msg_id: str, kind: str, loc: dict, text: str, t: float) -> dict | None:
        if kind not in ("live_wire", "wire_down", "pole_down", "fire") or loc.get("lat") is None:
            return None
        for h in self.hazards:
            if h["kind"] == kind and haversine_m((h["lat"], h["lon"]), (loc["lat"], loc["lon"])) < 250:
                h["evidence"].append(msg_id)
                return h
        h = {"id": f"H{len(self.hazards) + 1}", "kind": kind, "lat": loc["lat"], "lon": loc["lon"],
             "evidence": [msg_id], "first_t": round(t), "text": text}
        self.hazards.append(h)
        return h

    # ---- evidence: always derived from the stored messages ----------------------

    def _rebuild(self) -> None:
        self.ev = Evidence(scada_open=set(self.scada_open), damage=list(self.field_damage))
        self.seen: dict[str, str] = {}
        self.hazards: list[dict] = []
        self.languages: dict[str, str] = {}
        for m in self.messages:
            self._apply(m)

    def _apply(self, m: dict) -> None:
        """Turn one extracted message into evidence (dedup, reports, probes, hazards, damage)."""
        f, loc = m["fields"], m.get("location") or {}
        if m["channel"] == "crew":
            if d := self._damage(m["id"], f["damage"], loc, 4.0):
                self.ev.damage.append(d)
            if f.get("energised"):
                self._hazard(m["id"], "live_wire", loc, f["summary_en"], m["t"])
            return
        if f.get("is_junk"):
            m["status"] = "junk"
            return
        key = loc.get("account") or m.get("from") or m["id"]
        if key in self.seen and self.seen[key] != m["id"] and not m.get("probe_reply"):
            m["status"], m["dup_of"] = "duplicate", self.seen[key]
            return
        self.seen.setdefault(key, m["id"])
        m["status"] = "new"
        xf = loc.get("transformer")
        if m.get("probe_reply") and xf:
            self.ev.probes[xf] = f["symptom"] == "power_on"
        elif xf and f["symptom"] in ("no_power", "partial_power", "flicker"):
            self.ev.reports.setdefault(xf, set()).add(key)
            self.ev.report_ids.setdefault(xf, []).append(m["id"])
            if f["symptom"] != "no_power":
                self.ev.partial.setdefault(xf, set()).add(key)
            self.languages[xf] = m["language"]  # latest reporter's language
        if f["hazard"] != "none":
            if d := self._damage(m["id"], f["hazard"], loc, 1.5):
                self.ev.damage.append(d)
            self._hazard(m["id"], f["hazard"], loc, f.get("summary_en", ""), m["t"])

    # ---- event handlers -------------------------------------------------------

    async def handle(self, event: dict) -> None:
        self.elapsed = event["t"]
        kind = event["type"]
        if kind == "scada":
            await self._scada(event)
        elif kind == "complaint":
            if self.offline and event["channel"] == "call":
                self.queued.append(event)
                await self.log("Network", f"{event['id']}: call recorded, queued for transcription",
                               "Voice Transcribe is a cloud model; the network is down", event["id"])
                return
            await self._complaint(event)
        elif kind == "crew_note":
            await self._crew_note(event)
        elif kind == "drone":
            await self._drone(event)
        await self.recompute()

    async def _scada(self, e: dict) -> None:
        dev = self.feeder.devices[e["device"]]
        if e["event"] == "lockout":
            self.scada_open.add(dev.id)
            self.ev.scada_open.add(dev.id)
        await self.log("SCADA", f"{dev.label} ({dev.id}): {e['event']}",
                       "locked out, needs a crew" if e["event"] == "lockout" else "")
        await self.broadcast({"type": "scada", "device": dev.id, "event": e["event"], "t": e["t"]})

    async def _transcript(self, e: dict) -> str:
        audio = e.get("audio")
        if audio and (config.ROOT / audio).exists():
            bias = {"en": ["English"], "ta": ["Tamil", "English"], "si": ["English"]}.get(e.get("language"))
            try:
                res = await asyncio.to_thread(self.client.transcribe, config.ROOT / audio, bias)
            except Exception as err:  # noqa: BLE001
                res = None
                await self.log("Code", f"{e['id']}: transcription failed, using text", str(err)[:160], e["id"])
            if res:
                await self.log("Voice Transcribe", f"{e['id']}: call transcribed", res["transcript"][:160], e["id"])
                return res["transcript"]
        return e["text"]

    async def _extract(self, text: str, e: dict):
        ex = self.glimmer if self.offline else self.extractor
        out = await asyncio.to_thread(ex.complaint, text, e.get("truth", {}), e.get("language", "en"))
        if out.mock and self.offline:
            out.model = "mock (Glimmer not running)"
        return out

    async def _complaint(self, e: dict) -> None:
        text = (await self._transcript(e)) if e["channel"] == "call" else e["text"]
        ext = await self._extract(text, e)
        f = ext.fields
        msg = {"id": e["id"], "t": e["t"], "channel": e["channel"], "language": f.get("language") or e.get("language"),
               "from": e.get("from"), "text": text, "fields": f, "model": ext.model, "photo": e.get("photo"),
               "probe_reply": e.get("probe_reply"), "event": e}
        await self.log(ext.model, f"{e['id']}: {f['symptom'].replace('_', ' ')}"
                       + (f", hazard {f['hazard'].replace('_', ' ')}" if f["hazard"] != "none" else "")
                       + (" (junk)" if f["is_junk"] else ""), f.get("summary_en", "")[:160], e["id"])
        if not f["is_junk"]:
            msg["location"] = self._locate(f, e.get("from"))
        n_hazards = len(self.hazards)
        self.messages.append(msg)
        self._apply(msg)
        loc = msg.get("location") or {}
        if msg["status"] == "duplicate":
            await self.log("Code", f"{e['id']}: duplicate of {msg['dup_of']}",
                           f"same {'account' if loc.get('account') else 'sender'}", e["id"])
        elif msg["status"] == "new":
            xf = loc.get("transformer")
            await self.log("Code", f"{e['id']}: located by {loc['method']}",
                           f"{loc.get('street', '')} {loc.get('house_no') or ''} -> transformer {xf}" if xf else "",
                           e["id"])
            if e.get("probe_reply") and xf:
                on = f["symptom"] == "power_on"
                for p in self.probes:
                    if p["id"] == e["probe_reply"]:
                        p["answer"], p["answered_t"] = ("power ON" if on else "power OFF"), e["t"]
                await self.log("Agent", f"Answer from {xf}: power is {'ON' if on else 'OFF'}",
                               "rules out the wider outage" if on else "the outage extends here", e["id"])
        if len(self.hazards) > n_hazards:
            h = self.hazards[-1]
            await self.log("Code", f"Hazard {h['id']}: {h['kind'].replace('_', ' ')} reported",
                           "public safety, ranked above every outage", e["id"])
        await self.broadcast({"type": "message", "message": _public(msg)})
        if e.get("photo") and msg["status"] != "junk":
            await self._photo(e["id"], e["photo"], loc, f["hazard"], 2.5)

    async def _photo(self, ref: str, path: str, loc: dict, truth_damage: str, strength: float) -> None:
        try:
            res = await asyncio.to_thread(analyse_photo, self.client, path, truth_damage)
        except Exception as err:  # noqa: BLE001
            await self.log("Code", f"{ref}: photo analysis failed", str(err)[:160], ref)
            return
        detail = res["description"]
        if res.get("clearance_m") is not None:
            detail += f" | wire clearance ~{res['clearance_m']} m"
        await self.log(" + ".join(res["models"]), f"{ref}: photo shows {res['damage'].replace('_', ' ')}", detail, ref)
        if d := self._damage(ref + "/photo", res["damage"], loc, strength):
            self.field_damage.append(d)
            self.ev.damage.append(d)
        await self.broadcast({"type": "photo", "ref": ref, "path": path, "analysis": res, "lat": loc.get("lat"),
                              "lon": loc.get("lon")})

    async def _crew_note(self, e: dict) -> None:
        text = await self._transcript(e)
        ex = self.glimmer if self.offline else self.extractor
        ext = await asyncio.to_thread(ex.crew_note, text, e.get("truth", {}))
        f = ext.fields
        loc = self._locate(f, None)
        await self.log(ext.model, f"{e['id']} ({e['crew']}): {f['damage'].replace('_', ' ')}", f["summary_en"][:160],
                       e["id"])
        msg = {"id": e["id"], "t": e["t"], "channel": "crew", "language": e.get("language", "en"),
               "from": e["crew"], "text": text, "fields": f, "model": ext.model, "location": loc, "status": "crew",
               "event": e}
        self.messages.append(msg)
        self._apply(msg)
        await self.broadcast({"type": "message", "message": _public(msg)})
        if e.get("photo"):
            await self._photo(e["id"], e["photo"], loc, f["damage"], 3.0)

    async def _drone(self, e: dict) -> None:
        truth = e.get("truth", {})
        loc = self._locate(truth, None)
        exists = (config.ROOT / e["file"]).exists()
        await self.log("SAM 3.1" if exists else "mock (ground truth)",
                       f"{e['id']}: drone clip shows {truth.get('damage', 'damage').replace('_', ' ')}",
                       e.get("caption", "") + ("" if exists else " (clip not added yet)"), e["id"])
        if d := self._damage(e["id"], truth.get("damage", "other"), loc, 3.0):
            self.field_damage.append(d)
            self.ev.damage.append(d)
        await self.broadcast({"type": "drone", "ref": e["id"], "path": e["file"], "lat": loc.get("lat"),
                              "lon": loc.get("lon"), "caption": e.get("caption")})

    # ---- network outage: Glimmer offline, Spark reconciles afterwards -------------

    async def set_offline(self, offline: bool) -> None:
        if offline == self.offline:
            return
        self.offline = offline
        if offline:
            try:
                httpx.get(f"{config.GLIMMER_BASE}/models", timeout=1.5).raise_for_status()
                self.glimmer.enabled = True
            except Exception:  # noqa: BLE001
                self.glimmer.enabled = False
            await self.log("Network", "Network down: switching to Muse Glimmer on this laptop",
                           "text messages keep flowing through the open-weights model; calls queue for transcription"
                           + ("" if self.glimmer.enabled else f" (no Glimmer server at {config.GLIMMER_BASE}: mock)"))
        else:
            await self.log("Network", "Network back: Muse Spark reviews the offline work",
                           f"{len(self.queued)} queued calls to transcribe")
            await self._reconcile()
            queued, self.queued = self.queued, []
            for e in queued:
                await self._complaint(e)
        await self.broadcast({"type": "network", "offline": offline})
        await self.recompute()

    async def _reconcile(self) -> None:
        reviewed = corrected = 0
        for m in self.messages:
            if not m["model"].startswith(("Muse Glimmer", "mock (Glimmer")) or m["channel"] == "crew":
                continue
            e = m["event"]
            ext = await asyncio.to_thread(self.extractor.complaint, m["text"], e.get("truth", {}), e.get("language", "en"))
            reviewed += 1
            diffs = [k for k in REVIEW_FIELDS if ext.fields.get(k) != m["fields"].get(k)]
            if diffs:
                corrected += 1
                await self.log(ext.model, f"{m['id']}: corrected offline extraction",
                               "; ".join(f"{k}: {m['fields'].get(k)} -> {ext.fields.get(k)}" for k in diffs), m["id"])
                m["fields"] = ext.fields
                if not ext.fields["is_junk"]:
                    m["location"] = self._locate(ext.fields, m.get("from"))
            m["model"] = f"{m['model']} ✓ {ext.model}"
        self._rebuild()
        await self.log("Code", f"Offline review: {reviewed} messages checked, {corrected} corrected",
                       "evidence rebuilt from the corrected record")
        await self.broadcast({"type": "messages", "messages": [_public(m) for m in self.messages]})

    # ---- reasoning --------------------------------------------------------------

    def _fault_kind(self, located) -> str:
        kinds = Counter(d.kind for d in located.damage)
        if kinds:
            if "live_wire" in kinds:
                return "live_wire"
            return kinds.most_common(1)[0][0].replace("transformer_bang", "blown_fuse").replace(
                "transformer_failure", "blown_fuse")
        return "unknown"

    async def recompute(self) -> None:
        located = self.tracer.locate(self.ev, self.elapsed)
        faults, jobs = [], []
        for L in located:
            c = L.candidate
            kind = self._fault_kind(L)
            customers = sum(self.tracer.n.get(t, 0) for t in c.out)
            crit = [x for t in c.out for x in self.critical.get(t, [])]
            pts = [(d.lat, d.lon) for d in L.damage]
            lat, lon = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)) if pts else (c.lat, c.lon)
            report_ids = [i for t in c.out for i in self.ev.report_ids.get(t, [])]
            first_t = min((m["t"] for m in self.messages if m["id"] in report_ids), default=self.elapsed)
            if L.confidence >= LOCATED_AT and c.id not in self.located_at:
                self.located_at[c.id] = self.elapsed
                await self.log("Code", f"Located: {c.label}",
                               f"{L.confidence:.0%} confident; " + "; ".join(L.reasons), c.id)
            hazard_live = any(h["kind"] == "live_wire" and any(d.source.split("/")[0] in h["evidence"] for d in L.damage)
                              for h in self.hazards)
            job = Job(c.id, f"{KIND_TITLE[kind]}: {c.label}", kind, lat, lon, customers, L.confidence, crit, first_t,
                      hazard_live or kind == "live_wire")
            score(job)
            jobs.append(job)
            faults.append({
                "id": c.id, "device": c.id, "device_kind": c.kind, "label": c.label, "kind": kind,
                "title": KIND_TITLE[kind], "confidence": round(L.confidence, 3),
                "alternative": {"id": L.alternative.id, "label": L.alternative.label,
                                "confidence": round(L.alt_confidence, 3)} if L.alternative else None,
                "transformers": sorted(c.out), "customers_out": customers, "critical": crit,
                "lat": lat, "lon": lon, "device_lat": c.lat, "device_lon": c.lon, "reasons": L.reasons,
                "evidence": report_ids + [d.source for d in L.damage], "priority": job.priority,
                "breakdown": job.breakdown, "located_at": self.located_at.get(c.id),
                **next(({"explanation": x["explanation"], "explanation_model": x.get("explanation_model")}
                        for x in self.faults if x["id"] == c.id), {"explanation": None}),
            })
        self.plan = schedule(jobs, self.crews)
        self.baseline = schedule(jobs, self.crews, baseline=True)
        by_id = {p["fault_id"]: p for p in self.plan["plan"]}
        for f in faults:
            f["dispatch"] = by_id.get(f["id"])
        faults.sort(key=lambda f: -f["priority"])
        self.faults = faults
        await self._maybe_ask(located)
        for f in faults:
            if f["confidence"] < LOCATED_AT:
                continue
            if self.explained.get(f["id"]) != f["kind"]:
                await self._explain(f)
            if f["kind"] != "unknown":  # only promise a time once we know what broke
                await self._notify(f)
        await self.broadcast({"type": "state", "state": self.snapshot(include_log=False)})

    async def _explain(self, f: dict) -> None:
        """Muse Spark turns the tracer's facts into a dispatcher-facing sentence (once per located fault/kind)."""
        self.explained[f["id"]] = f["kind"]
        steps = "; ".join(f"{s['crew_name']}: {s['task']}" for s in (f["dispatch"] or {}).get("steps", []))
        facts = (f"Fault: {f['title']} at {f['label']} ({f['device']}). Confidence {f['confidence']:.0%}. "
                 f"Evidence: {'; '.join(f['reasons'])}. Customers out: {f['customers_out']}. "
                 f"Critical loads: {', '.join(f['critical']) or 'none'}. Rival explanation: "
                 f"{f['alternative']['label'] if f['alternative'] else 'none'}. Planned crews: {steps or 'none'}.")
        text, model = None, "Muse Spark"
        if not self.offline:
            try:
                text = await asyncio.to_thread(self.client.spark_text, EXPLAIN_SYSTEM, facts)
            except Exception:  # noqa: BLE001
                text = None
        if not text:
            model = "mock (template)"
            text = (f"{f['title']} at {f['label']}: {f['reasons'][0] if f['reasons'] else 'evidence matches'}. "
                    f"Send {steps or 'a troubleshooter'}.")
        f["explanation"], f["explanation_model"] = text.strip(), model
        await self.log(model, f"Why {f['device']}: {f['title'].lower()}", f["explanation"], f["id"])

    async def _notify(self, f: dict) -> None:
        """Tell every customer who reported this fault when their power should be back, in their language."""
        if not f["dispatch"]:
            return
        eta = fmt_eta(f["dispatch"]["restore_min"])
        notified = {to for n in self.notices for to in n["to"]}
        recipients = [m for m in self.messages if m.get("status") == "new" and m["id"] in f["evidence"]
                      and m["channel"] != "crew" and m.get("from") and m["from"] not in notified]
        first = not any(n["fault"] == f["id"] for n in self.notices)
        by_lang: dict[str, list[dict]] = {}
        for m in recipients:
            by_lang.setdefault(m["language"] if m["language"] in NOTICE else "en", []).append(m)
        for lang, ms in by_lang.items():
            kind = KIND_TITLE[f["kind"]].lower()
            text, model = None, "Muse Spark"
            if not self.offline:
                try:
                    text = await asyncio.to_thread(
                        self.client.spark_text, NOTICE_SYSTEM,
                        f"Language: {LANG_NAME[lang]}. Fault type: {kind}. Estimated restoration: {eta}.")
                except Exception:  # noqa: BLE001
                    text = None
            if not text:
                text, model = NOTICE[lang].format(kind=kind, eta=eta), "mock (template)"
            notice = {"id": f"U{len(self.notices) + 1}", "t": round(self.elapsed), "fault": f["id"], "language": lang,
                      "text": text.strip(), "to": [m["from"] for m in ms], "model": model}
            self.notices.append(notice)
            await self.broadcast({"type": "notice", "notice": notice})
        if recipients and first:  # later reporters get the same update without a timeline entry each
            await self.log("Agent", f"Restoration update sent to {len(recipients)} customers",
                           f"{f['title']}: back in about {eta}; languages {', '.join(sorted(by_lang))}", f["id"])

    async def _maybe_ask(self, located) -> None:
        """Ask the customer whose answer best separates the top explanation from its rival."""
        for L in located:
            if L.confidence >= ASK_BELOW or L.alternative is None:
                continue
            c, alt = L.candidate, L.alternative
            if any(p["fault"] == c.id and (p.get("answer") is None or self.elapsed - p["t"] < PROBE_GAP_S)
                   for p in self.probes):
                continue
            diff = (c.out ^ alt.out) - set(self.ev.reports) - set(self.ev.probes)
            if not diff:
                continue
            reported = [self.feeder.transformers[t] for t in c.out if t in self.ev.reports]

            def dist(tid):
                t = self.feeder.transformers[tid]
                return min(haversine_m((t.lat, t.lon), (r.lat, r.lon)) for r in reported) if reported else 0

            target = min(diff, key=dist)
            customers = [x for x in self.db.customers_on(target) if not x.critical]
            if not customers:
                continue
            who = customers[len(self.probes) % len(customers)]
            langs = [self.languages[t] for t in c.out if t in self.languages]
            lang = langs[-1] if langs else "en"
            probe = {"id": f"Q{len(self.probes) + 1}", "t": round(self.elapsed), "fault": c.id, "rival": alt.id,
                     "transformer": target, "to": who.phone, "name": who.name, "street": who.street,
                     "house_no": who.house_no, "language": lang, "text": QUESTION.get(lang, QUESTION["en"]),
                     "answer": None, "lat": who.lat, "lon": who.lon}
            self.probes.append(probe)
            only = c.id if target in c.out else alt.id
            await self.log("Agent", f"Asking {who.street} {who.house_no} (transformer {target})",
                           f"{c.id} {L.confidence:.0%} vs {alt.id} {L.alt_confidence:.0%}: their answer separates "
                           f"the two (only {only} would cut their supply)", probe["id"])
            await self.broadcast({"type": "probe", "probe": probe})
            self.on_probe(probe)

    # ---- output ------------------------------------------------------------------

    def score_against_truth(self) -> list[dict]:
        out = []
        for tf in self.scenario["faults"]:
            hit = next((f for f in self.faults if f["device"] == tf["device"]), None)
            out.append({"id": tf["id"], "title": tf["title"], "device": tf["device"],
                        "found": bool(hit and hit["confidence"] >= LOCATED_AT),
                        "located_at": self.located_at.get(tf["device"]),
                        "confidence": hit["confidence"] if hit else 0})
        return out

    def snapshot(self, include_log: bool = True) -> dict[str, Any]:
        s = {
            "elapsed": self.elapsed, "mode": self.client.mode, "offline": self.offline, "faults": self.faults,
            "hazards": self.hazards, "probes": self.probes, "plan": self.plan, "baseline": self.baseline,
            "scada_open": sorted(self.ev.scada_open), "truth": self.score_against_truth(),
            "counts": {
                "messages": len(self.messages),
                "duplicates": sum(m.get("status") == "duplicate" for m in self.messages),
                "junk": sum(m.get("status") == "junk" for m in self.messages),
                "languages": dict(Counter(m["language"] for m in self.messages)),
                "model_calls": dict(self.model_calls),
                "notified": sum(len(n["to"]) for n in self.notices),
                "queued": len(self.queued),
            },
        }
        if include_log:
            s["messages"] = [_public(m) for m in self.messages]
            s["timeline"], s["notices"] = self.timeline, self.notices
        return s


def _public(m: dict) -> dict:
    """Message as sent to the browser (without the raw scenario event and its labels)."""
    return {k: v for k, v in m.items() if k != "event"}
