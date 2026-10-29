"""Muse Spark turns raw complaints and crew reports into structured evidence.

The model only reads and normalises text; it never decides where a fault is.
In mock mode (no API key and nothing cached) the scenario's labelled ground truth
stands in for the model output, and the result is flagged so the UI can say so.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import ModelClient

SYMPTOMS = ["no_power", "partial_power", "flicker", "power_on", "none"]
HAZARDS = ["none", "live_wire", "wire_down", "pole_down", "tree_on_line", "fire", "transformer_bang"]
DAMAGE = ["none", "live_wire", "wire_down", "pole_down", "tree_on_line", "blown_fuse", "transformer_failure",
          "service_wire", "other"]

COMPLAINT_SCHEMA = {
    "type": "object",
    "properties": {
        "language": {"type": "string", "description": "ISO 639-1 code of the message language"},
        "account_no": {"type": ["string", "null"], "description": "10-digit electricity account number if given"},
        "street": {"type": ["string", "null"], "description": "Street name in English transliteration, e.g. 'Hospital Road'"},
        "house_no": {"type": ["integer", "null"]},
        "landmark": {"type": ["string", "null"], "description": "Landmark mentioned, in English, e.g. 'temple', 'market'"},
        "symptom": {"type": "string", "enum": SYMPTOMS},
        "hazard": {"type": "string", "enum": HAZARDS},
        "cause_hint": {"type": ["string", "null"], "description": "Cause the caller mentions (tree, bang, lightning...)"},
        "is_junk": {"type": "boolean", "description": "True for spam, pranks, or messages with no outage information"},
        "summary_en": {"type": "string", "description": "One-line English translation/summary"},
    },
    "required": ["language", "account_no", "street", "house_no", "landmark", "symptom", "hazard",
                 "cause_hint", "is_junk", "summary_en"],
}

COMPLAINT_SYSTEM = """You triage messages sent to an electricity utility in Galle, Sri Lanka during a storm.
Messages arrive as transcribed phone calls, WhatsApp and SMS, in English, Sinhala (script or romanised
"Singlish") or Tamil. Extract exactly what the sender says; never invent an address.
- street: transliterate to the English street name used locally (රෝහල පාර / ஹாஸ்பிடல் ரோட் -> Hospital Road,
  ටෙම්පල් පාර -> Temple Road, සිනමන් ගාඩන්ස් පටුමග -> Cinnamon Gardens Lane, මාර්කට් වීදිය -> Market Street).
- symptom: no_power (fully off), partial_power (dim lights, half power, low voltage), flicker,
  power_on (sender says their power is on), none (no supply information).
- hazard: anything dangerous to the public: live_wire (sparking or energised wire), wire_down, pole_down,
  tree_on_line, fire, transformer_bang. 'none' if nothing dangerous is described.
- is_junk: spam, pranks, unrelated requests, or abuse with no outage information."""

CREW_SCHEMA = {
    "type": "object",
    "properties": {
        "street": {"type": ["string", "null"]},
        "house_no": {"type": ["integer", "null"]},
        "landmark": {"type": ["string", "null"]},
        "damage": {"type": "string", "enum": DAMAGE},
        "energised": {"type": "boolean", "description": "True if the crew says the conductor is live/arcing"},
        "device_ok": {"type": "boolean",
                      "description": "True if the crew says the device they were sent to (transformer, fuse, line) is healthy"},
        "house_from": {"type": ["integer", "null"], "description": "First house number without supply, if a range is given"},
        "house_to": {"type": ["integer", "null"], "description": "Last house number without supply, if a range is given"},
        "crew_needs": {"type": "array", "items": {"type": "string", "enum": ["line", "bucket_truck", "vegetation", "troubleshooter"]}},
        "summary_en": {"type": "string"},
    },
    "required": ["street", "house_no", "landmark", "damage", "energised", "device_ok", "house_from", "house_to",
                 "crew_needs", "summary_en"],
}

CREW_SYSTEM = """You read field reports from electricity utility patrol crews in Galle, Sri Lanka.
Extract where the damage is, what it is, whether the line is still energised, whether the device the crew was
sent to is actually healthy (device_ok), the house range left without supply, and which crews are needed.
damage: service_wire is a low-voltage wire from the street to houses; blown_fuse is a transformer drop-out fuse.
Crews:
line (line crew), bucket_truck (aerial lift for pole/conductor work), vegetation (tree removal),
troubleshooter (single technician, e.g. to replace a fuse)."""


@dataclass
class Extraction:
    fields: dict
    model: str  # which model produced it, or "mock (ground truth)"
    mock: bool = False
    notes: list[str] = field(default_factory=list)


class Extractor:
    def __init__(self, client: ModelClient, model: str | None = None, base: str | None = None,
                 label: str = "Muse Spark") -> None:
        self.client, self.model, self.base, self.label = client, model, base, label
        self.last_error: str | None = None
        self.enabled = True  # False skips the model entirely (e.g. local server not running)

    def _call(self, system: str, text: str, schema: dict, name: str) -> dict | None:
        """Model call that degrades to None (and mock output) instead of failing the pipeline."""
        if not self.enabled:
            return None
        try:
            self.last_error = None
            return self.client.spark_json(system, text, schema, name, model=self.model, base=self.base)
        except Exception as e:  # noqa: BLE001 - network, HTTP and parse errors all fall back
            self.last_error = f"{type(e).__name__}: {e}"[:200]
            return None

    def complaint(self, text: str, truth: dict, language: str) -> Extraction:
        out = self._call(COMPLAINT_SYSTEM, text, COMPLAINT_SCHEMA, "Complaint")
        if out is not None:
            return Extraction(out, self.label)
        if not truth:
            return Extraction(_keyword_fields(text, language), "mock (keywords)", mock=True)
        return Extraction({
            "language": language,
            "account_no": truth.get("account_no"),
            "street": truth.get("street"),
            "house_no": truth.get("house_no"),
            "landmark": truth.get("landmark"),
            "symptom": truth.get("symptom", "none"),
            "hazard": truth.get("hazard", "none"),
            "cause_hint": None,
            "is_junk": bool(truth.get("junk")),
            "summary_en": text if language == "en" else f"[{language}] {text}",
        }, "mock (ground truth)", mock=True)

    def crew_note(self, text: str, truth: dict) -> Extraction:
        out = self._call(CREW_SYSTEM, text, CREW_SCHEMA, "CrewReport")
        if out is not None:
            return Extraction(out, self.label)
        needs = {"pole_down": ["line", "bucket_truck"], "tree_on_line": ["vegetation", "line"],
                 "blown_fuse": ["troubleshooter"], "live_wire": ["line"], "service_wire": ["line"]}.get(truth.get("damage"), [])
        return Extraction({
            "street": truth.get("street"), "house_no": truth.get("house_no"), "landmark": truth.get("landmark"),
            "damage": truth.get("damage", "other"), "energised": truth.get("damage") == "live_wire",
            "device_ok": bool(truth.get("device_ok")), "house_from": truth.get("house_from"),
            "house_to": truth.get("house_to"), "crew_needs": needs, "summary_en": text,
        }, "mock (ground truth)", mock=True)


def _keyword_fields(text: str, language: str) -> dict:
    """Last-resort reading of an unlabelled message (mock mode, e.g. typed live into the portal)."""
    t = text.lower()
    hazard = "none"
    for words, h in ((("spark", "ගිනි", "தீப்பொறி"), "live_wire"), (("pole", "කණු", "கம்ப"), "pole_down"),
                     (("tree", "ගහ", "மரம்"), "tree_on_line"), (("wire", "වයර", "கம்பி"), "wire_down")):
        if any(re.search(rf"\b{w}", t) if w.isascii() else w in t for w in words):
            hazard = h
            break
    m = (re.search(r"(\d{1,3})\s*,?\s*([A-Za-z][A-Za-z ]+?(?:road|rd|street|st|lane|mawatha))\b", text, re.I)
         or re.search(r"([A-Za-z][A-Za-z ]+?(?:road|rd|street|st|lane))\s*,?\s*(?:no\.?\s*)?(\d{1,3})", text, re.I))
    street = house = None
    if m:
        a, b = m.group(1), m.group(2)
        house, street = (int(a), b) if a.isdigit() else (int(b), a)
    acct = re.search(r"\b\d{10}\b", text)
    return {"language": language, "account_no": acct.group(0) if acct else None,
            "street": street.strip() if street else None, "house_no": house, "landmark": None if street else text,
            "symptom": "no_power", "hazard": hazard, "cause_hint": None, "is_junk": False, "summary_en": text}
