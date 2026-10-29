"""Distribution feeder model: IEEE 34-bus topology laid over Galle, Sri Lanka.

The topology (buses, sections and section lengths) follows the IEEE PES 34-bus test
feeder. Lengths are compressed (square-root scaling) so the 58-mile rural feeder fits a
town without squashing its short urban branches to nothing, and each
section gets a compass heading so the tree can be drawn on a real map. Protective
devices and service transformers are synthetic but placed the way a utility would:
a substation breaker, reclosers on long branches, fuses on laterals, and a fused
service transformer every ~100 m of line.

Only topology matters for fault location: when a device opens, every transformer
downstream of it loses power. Tracing upstream from a group of complaining
transformers to the device that explains them is the core of GridMedic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import cached_property

TRANSFORMER_SPACING_M = 100

# Substation location (inland Galle, north of the harbour).
ORIGIN = (6.0525, 80.2105)

# (from_bus, to_bus, length_ft, heading_deg, street)
SECTIONS: list[tuple[str, str, float, float, str]] = [
    ("800", "802", 2580, 60, "Substation Road"),
    ("802", "806", 1730, 60, "Wakwella Road"),
    ("806", "808", 32230, 62, "Wakwella Road"),
    ("808", "810", 5804, 330, "Kumbalwella Lane"),
    ("808", "812", 37500, 75, "Baddegama Road"),
    ("812", "814", 29730, 78, "Baddegama Road"),
    ("814", "850", 10, 78, "Baddegama Road"),
    ("850", "816", 310, 78, "Baddegama Road"),
    ("816", "818", 1710, 5, "Temple Road"),
    ("818", "820", 48150, 10, "Temple Road"),
    ("820", "822", 13740, 345, "Pumping Station Road"),
    ("816", "824", 10210, 95, "Karapitiya Road"),
    ("824", "826", 3030, 125, "School Lane"),
    ("824", "828", 840, 80, "Karapitiya Road"),
    ("828", "830", 20440, 80, "Karapitiya Road"),
    ("830", "854", 520, 80, "Karapitiya Road"),
    ("854", "856", 23330, 140, "Hospital Road"),
    ("854", "852", 36830, 55, "Hirimbura Road"),
    ("852", "832", 10, 55, "Hirimbura Road"),
    ("832", "888", 10, 115, "Mill Road"),
    ("888", "890", 10560, 115, "Mill Road"),
    ("832", "858", 4900, 25, "Upper Dickson Road"),
    ("858", "864", 1620, 300, "Bo Tree Lane"),
    ("858", "834", 5830, 40, "Upper Dickson Road"),
    ("834", "842", 280, 100, "Mosque Road"),
    ("842", "844", 1350, 100, "Mosque Road"),
    ("844", "846", 3640, 85, "Market Street"),
    ("846", "848", 530, 40, "Market Street"),
    ("834", "860", 2020, 5, "Church Street"),
    ("860", "836", 2680, 5, "Church Street"),
    ("836", "840", 860, 320, "Lake Road"),
    ("836", "862", 280, 60, "Cinnamon Gardens Lane"),
    ("862", "838", 4860, 60, "Cinnamon Gardens Lane"),
]

# (device_id, kind, section "from-to", scada_monitored, label)
# A device sits at the upstream end of its section and de-energises everything below it.
DEVICES: list[tuple[str, str, str, bool, str]] = [
    ("BRK-1", "breaker", "800-802", True, "Substation feeder breaker"),
    ("REC-1", "recloser", "854-856", True, "Hospital Road recloser"),
    ("REC-2", "recloser", "816-818", True, "Temple Road recloser"),
    ("REC-3", "recloser", "832-858", True, "Upper Dickson Road recloser"),
    ("FUS-810", "fuse", "808-810", False, "Kumbalwella Lane fuse"),
    ("FUS-822", "fuse", "820-822", False, "Pumping Station Road fuse"),
    ("FUS-826", "fuse", "824-826", False, "School Lane fuse"),
    ("FUS-888", "fuse", "832-888", False, "Mill Road fuse"),
    ("FUS-864", "fuse", "858-864", False, "Bo Tree Lane fuse"),
    ("FUS-842", "fuse", "834-842", False, "Mosque Road fuse"),
    ("FUS-848", "fuse", "846-848", False, "Market Street fuse"),
    ("FUS-840", "fuse", "836-840", False, "Lake Road fuse"),
    ("FUS-862", "fuse", "836-862", False, "Cinnamon Gardens Lane fuse"),
]

# Remote-controlled switches the control room can operate. Sectionalising switches sit at the
# upstream end of a section like a device; the tie switch joins this feeder's far end to a
# neighbouring feeder (Feeder 2) and is normally open.
# (switch_id, kind, section or bus, normally_open, label)
SWITCHES: list[tuple[str, str, str, bool, str]] = [
    ("SW-818", "switch", "818-820", False, "Temple Road sectionalising switch"),
    ("SW-820", "switch", "820-822", False, "Pumping Station Road sectionalising switch"),
    ("TS-1", "tie", "822", True, "Tie switch to Feeder 2"),
]
FEEDER2_BUS = "F2"  # Feeder 2 supply point, reached only through TS-1


@dataclass
class Section:
    id: str
    from_bus: str
    to_bus: str
    length_m: float
    heading: float
    street: str
    coords: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class Transformer:
    id: str
    section: str
    offset_m: float  # distance from the section's upstream bus
    lat: float
    lon: float
    kva: int


@dataclass
class Device:
    id: str
    kind: str  # breaker | recloser | fuse | xfmr_fuse
    section: str
    scada: bool
    label: str
    lat: float
    lon: float


def _move(lat: float, lon: float, heading_deg: float, dist_m: float) -> tuple[float, float]:
    rad = math.radians(heading_deg)
    dlat = dist_m * math.cos(rad) / 111_320
    dlon = dist_m * math.sin(rad) / (111_320 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


class Feeder:
    def __init__(self) -> None:
        self.bus_pos: dict[str, tuple[float, float]] = {"800": ORIGIN}
        self.sections: dict[str, Section] = {}
        self.children: dict[str, list[str]] = {}  # bus -> downstream section ids
        self.parent_section: dict[str, str] = {}  # bus -> section feeding it
        for frm, to, ft, heading, street in SECTIONS:
            # Regulators and the in-line transformer (10 ft) stay as short stubs.
            length = 120 + 3 * math.sqrt(ft) if ft > 10 else 15
            start = self.bus_pos[frm]
            end = _move(*start, heading, length)
            self.bus_pos[to] = end
            sid = f"{frm}-{to}"
            self.sections[sid] = Section(sid, frm, to, length, heading, street, [start, end])
            self.children.setdefault(frm, []).append(sid)
            self.parent_section[to] = sid

        self.transformers: dict[str, Transformer] = {}
        n = 0
        for sec in self.sections.values():
            count = int(sec.length_m // TRANSFORMER_SPACING_M)
            for i in range(count):
                offset = (i + 0.5) * sec.length_m / count
                lat, lon = _move(*self.bus_pos[sec.from_bus], sec.heading, offset)
                # Pole-mounted transformers sit beside the line, alternating sides.
                lat, lon = _move(lat, lon, sec.heading + (90 if i % 2 else -90), 12)
                n += 1
                tid = f"T-{n:03d}"
                self.transformers[tid] = Transformer(tid, sec.id, offset, lat, lon, 100 if n % 3 else 160)

        self.devices: dict[str, Device] = {}
        for did, kind, sid, scada, label in DEVICES:
            lat, lon = _move(*self.bus_pos[self.sections[sid].from_bus], self.sections[sid].heading, 8)
            self.devices[did] = Device(did, kind, sid, scada, label, lat, lon)
        # Feeder 2 comes in beyond bus 822; TS-1 sits on the gap.
        self.bus_pos[FEEDER2_BUS] = _move(*self.bus_pos["822"], 20, 260)
        self.switches: dict[str, Device] = {}
        for sid, kind, where, normally_open, label in SWITCHES:
            if kind == "tie":
                lat, lon = _move(*self.bus_pos[where], 20, 130)
                self.switches[sid] = Device(sid, kind, where, True, label, lat, lon)
            else:
                lat, lon = _move(*self.bus_pos[self.sections[where].from_bus], self.sections[where].heading, 20)
                self.switches[sid] = Device(sid, kind, where, True, label, lat, lon)
        self.normally_open = {sid for sid, _, _, no, _ in SWITCHES if no}
        # Every service transformer is protected by its own drop-out fuse.
        for t in self.transformers.values():
            did = f"XF-{t.id[2:]}"
            self.devices[did] = Device(did, "xfmr_fuse", t.section, False, f"Transformer {t.id} fuse", t.lat, t.lon)

    # ---- topology queries -------------------------------------------------

    def sections_below(self, section_id: str) -> list[str]:
        """The section itself plus every section in the subtree it feeds."""
        out, stack = [], [section_id]
        while stack:
            sid = stack.pop()
            out.append(sid)
            stack.extend(self.children.get(self.sections[sid].to_bus, []))
        return out

    @cached_property
    def _transformers_by_section(self) -> dict[str, list[str]]:
        by: dict[str, list[str]] = {}
        for t in self.transformers.values():
            by.setdefault(t.section, []).append(t.id)
        return by

    @cached_property
    def downstream(self) -> dict[str, frozenset[str]]:
        """Device id -> transformers that lose power when it opens."""
        out: dict[str, frozenset[str]] = {}
        for d in self.devices.values():
            if d.kind == "xfmr_fuse":
                out[d.id] = frozenset({"T-" + d.id[3:]})
            else:
                out[d.id] = frozenset(
                    t for sid in self.sections_below(d.section) for t in self._transformers_by_section.get(sid, [])
                )
        return out

    def upstream_devices(self, transformer_id: str) -> list[str]:
        """Protective devices between a transformer and the substation, nearest first."""
        t = self.transformers[transformer_id]
        chain = [f"XF-{transformer_id[2:]}"]
        sid: str | None = t.section
        device_at = {d.section: d.id for d in self.devices.values() if d.kind != "xfmr_fuse"}
        while sid:
            if sid in device_at:
                chain.append(device_at[sid])
            sid = self.parent_section.get(self.sections[sid].from_bus)
        return chain

    def point_on_section(self, section_id: str, offset_m: float) -> tuple[float, float]:
        sec = self.sections[section_id]
        return _move(*self.bus_pos[sec.from_bus], sec.heading, min(max(offset_m, 0), sec.length_m))

    def to_geojson(self) -> dict:
        feats = []
        for s in self.sections.values():
            feats.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in s.coords]},
                "properties": {"kind": "section", "id": s.id, "street": s.street},
            })
        for t in self.transformers.values():
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [t.lon, t.lat]},
                "properties": {"kind": "transformer", "id": t.id, "section": t.section, "kva": t.kva},
            })
        tie_bus = next(s.section for s in self.switches.values() if s.kind == "tie")
        a, b = self.bus_pos[tie_bus], self.bus_pos[FEEDER2_BUS]
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[a[1], a[0]], [b[1], b[0]]]},
            "properties": {"kind": "tie_line", "id": "TIE-1", "street": "Feeder 2 tie"},
        })
        feats.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": [b[1], b[0]]},
            "properties": {"kind": "feeder2", "id": FEEDER2_BUS, "label": "Feeder 2 (Karapitiya side)"},
        })
        for s in self.switches.values():
            feats.append({
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [s.lon, s.lat]},
                "properties": {"kind": s.kind, "id": s.id, "label": s.label, "scada": True},
            })
        for d in self.devices.values():
            if d.kind == "xfmr_fuse":
                continue
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [d.lon, d.lat]},
                "properties": {"kind": d.kind, "id": d.id, "label": d.label, "scada": d.scada},
            })
        return {"type": "FeatureCollection", "features": feats}


_feeder: Feeder | None = None


def get_feeder() -> Feeder:
    global _feeder
    if _feeder is None:
        _feeder = Feeder()
    return _feeder
