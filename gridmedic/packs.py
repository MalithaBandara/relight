"""Scenario packs: which network, customers, language and message formats a scenario runs on.

A scenario file's "pack" block names its network (the IEEE 34-bus feeder over Galle, or a
feeder generated from real OpenStreetMap roads) and its locale. Networks and customer
databases are built once and cached.
"""

from __future__ import annotations

from .config import DATA_DIR
from .customers import CustomerDB
from .grid import Feeder, get_feeder
from .locales import LOCALES

_cache: dict[str, tuple[Feeder, CustomerDB]] = {}

DEFAULT_PACK = {"locale": "sri_lanka", "network": {"type": "ieee34"}, "start_hour": 15, "languages": ["en", "si", "ta"]}


def pack(sc: dict) -> dict:
    return {**DEFAULT_PACK, **sc.get("pack", {})}


def locale(sc: dict) -> dict:
    return LOCALES[pack(sc)["locale"]]


def network(sc: dict) -> tuple[Feeder, CustomerDB]:
    """The feeder and customer database for a scenario (built on first use)."""
    p = pack(sc)
    net = p["network"]
    key = net.get("area", "ieee34")
    if key in _cache:
        return _cache[key]
    if net["type"] == "ieee34":
        feeder = get_feeder()
        db = CustomerDB(DATA_DIR / "gridmedic.db")
    else:
        from .osmnet import build_customers, build_spec

        spec = build_spec(net["area"], net)
        feeder = Feeder(spec)
        path = DATA_DIR / f"{net['area']}.db"
        db = CustomerDB(path, build=lambda pth: build_customers(pth, feeder, net["area"], net, locale(sc)))
    _cache[key] = (feeder, db)
    return feeder, db
