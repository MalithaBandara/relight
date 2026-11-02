"""A small synthetic feeder with two normally-open ties, built to exercise multi-tie switching plans.

Not a real network and not an independent benchmark: it exists so that one fault can be restored through more than
one tie. A pole down on Elm Avenue (B1-B2) trips the main recloser; after isolating it, the dark customers on Birch
Lane can come back through the east tie and those on Aspen Road through the north tie, so three safe plans exist
(east only, north only, both) and the planner recommends the one that restores most.

              B4 -- B5            (Willow Way, healthy)
              |
 B0 == B1 == B2 -- B3 ~~ F_EAST   (B1-B2 Elm Avenue; B2-B3 Birch Lane; tie TS-E)
 (REC-MAIN)      |
                 B6 ~~ F_NORTH    (Aspen Road; tie TS-N)
"""

from __future__ import annotations

from .config import DATA_DIR
from .customers import CustomerDB
from .grid import Feeder, _move
from .grid_ieee123 import ORIGIN, build_ieee123_database

_feeder: Feeder | None = None


def twotie_spec(origin: tuple[float, float] = ORIGIN) -> dict:
    b0 = origin
    b1 = _move(*b0, 180, 450)
    b2 = _move(*b1, 90, 450)
    b3 = _move(*b2, 90, 400)
    b6 = _move(*b2, 0, 400)
    b4 = _move(*b1, 270, 400)
    b5 = _move(*b4, 270, 400)
    buses = {"B0": b0, "SUB": b0, "B1": b1, "B2": b2, "B3": b3, "B4": b4, "B5": b5, "B6": b6,
             "F_EAST": _move(*b3, 90, 250), "F_NORTH": _move(*b6, 0, 250)}
    sections = [
        {"id": "B0-B1", "from": "B0", "to": "B1", "coords": [b0, b1], "street": "Cedar Main Street"},
        {"id": "B1-B2", "from": "B1", "to": "B2", "coords": [b1, b2], "street": "Elm Avenue"},
        {"id": "B2-B3", "from": "B2", "to": "B3", "coords": [b2, b3], "street": "Birch Lane"},
        {"id": "B2-B6", "from": "B2", "to": "B6", "coords": [b2, b6], "street": "Aspen Road"},
        {"id": "B1-B4", "from": "B1", "to": "B4", "coords": [b1, b4], "street": "Willow Way"},
        {"id": "B4-B5", "from": "B4", "to": "B5", "coords": [b4, b5], "street": "Willow Way West"},
    ]
    return {
        "root": "B0",
        "buses": buses,
        "sections": sections,
        "devices": [("REC-MAIN", "recloser", "B0-B1", True, "Main recloser REC-MAIN")],
        "switches": [
            ("SW-E1", "switch", "B1-B2", False, "Sectionalising switch SW-E1 (Elm Avenue)"),
            ("SW-E2", "switch", "B2-B3", False, "Sectionalising switch SW-E2 (Birch Lane)"),
            ("SW-N1", "switch", "B2-B6", False, "Sectionalising switch SW-N1 (Aspen Road)"),
            ("SW-W1", "switch", "B1-B4", False, "Sectionalising switch SW-W1 (Willow Way)"),
            ("TS-E", "tie", "B3", "F_EAST", True, "East tie TS-E"),
            ("TS-N", "tie", "B6", "F_NORTH", True, "North tie TS-N"),
        ],
        "external_feeders": [
            {"bus": "F_EAST", "pos": buses["F_EAST"], "label": "East Grid"},
            {"bus": "F_NORTH", "pos": buses["F_NORTH"], "label": "North Grid"},
        ],
        "transformer_spacing": 100,
        "substation_label": "Demo substation (bus B0)",
    }


def get_twotie_feeder() -> Feeder:
    global _feeder
    if _feeder is None:
        _feeder = Feeder(twotie_spec())
    return _feeder


def twotie_database(feeder: Feeder) -> CustomerDB:
    path = DATA_DIR / "twotie.db"
    return CustomerDB(path, build=lambda pth: build_ieee123_database(pth, feeder))
