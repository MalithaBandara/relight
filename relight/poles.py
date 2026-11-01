"""Pole register: every pole of a feeder with its tag, so a photographed tag names an exact asset.

The feeder only models sections and service transformers, so the register places a pole every POLE_SPACING_M along
each section and numbers them in section order. The register is synthetic (fictional tags, like the customers);
a scenario can add `pole_aliases` for tags that appear in its photos. A model reads the plate (vision.read_pole_tag),
code finds the pole: the model never decides where a pole is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .grid import Feeder, haversine_m

POLE_SPACING_M = 45.0
# What OCR confuses on a stencilled plate; both sides are compared after folding.
CONFUSABLE = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2", "G": "6"})


@dataclass
class Pole:
    id: str
    tag: str
    section: str
    offset_m: float
    lat: float
    lon: float
    transformer: str | None  # the nearest service transformer on the same section (what the tracer works with)


def normalise(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


class PoleRegister:
    def __init__(self, feeder: Feeder, prefix: str = "P") -> None:
        self.feeder = feeder
        self.poles: dict[str, Pole] = {}
        by_section: dict[str, list] = {}
        for t in feeder.transformers.values():
            by_section.setdefault(t.section, []).append(t)
        n = 0
        for sec in feeder.sections.values():
            count = max(int(sec.length_m // POLE_SPACING_M), 1) + 1
            for i in range(count):
                offset = i * sec.length_m / (count - 1) if count > 1 else 0.0
                lat, lon = feeder.point_on_section(sec.id, offset)
                n += 1
                near = min(by_section.get(sec.id, []), key=lambda t: abs(t.offset_m - offset), default=None)
                tag = f"{prefix}-{n:04d}"
                self.poles[tag] = Pole(tag, tag, sec.id, round(offset, 1), lat, lon, near.id if near else None)
        self._exact = {normalise(t): t for t in self.poles}
        self._aliases: dict[str, str] = {}

    def nearest(self, lat: float, lon: float) -> Pole:
        return min(self.poles.values(), key=lambda p: haversine_m((p.lat, p.lon), (lat, lon)))

    def alias(self, tag: str, pole_id: str) -> None:
        """A tag that appears in a scenario's photos stands for this pole."""
        if key := normalise(tag):
            self._aliases[key] = pole_id

    def lookup(self, text: str | None) -> tuple[Pole | None, str]:
        """The pole a plate names, and how it was matched ('exact', 'OCR-tolerant', or why not)."""
        key = normalise(text or "")
        if len(key) < 3:
            return None, "no tag read"
        if key in self._aliases:
            return self.poles[self._aliases[key]], "exact"
        if key in self._exact:
            return self.poles[self._exact[key]], "exact"
        folded = key.translate(CONFUSABLE)
        hits = {self._exact[k] for k in self._exact if k.translate(CONFUSABLE) == folded}
        hits |= {self._aliases[k] for k in self._aliases if k.translate(CONFUSABLE) == folded}
        if len(hits) == 1:
            return self.poles[next(iter(hits))], "OCR-tolerant"
        return None, "tag not in the register" if not hits else "tag matches several poles"
