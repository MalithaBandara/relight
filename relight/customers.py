"""Synthetic customer database: ~2,000 accounts mapped to service transformers.

Real utilities know which transformer serves each account (the "customer-to-
transformer" connectivity). That mapping is what lets a complaint be placed on the
grid. Everything here is generated from a fixed seed, so addresses quoted in the
scenario script always resolve to the same customer.
"""

from __future__ import annotations

import random
import re
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher

from .config import DATA_DIR, DB_PATH
from .grid import Feeder, _move, get_feeder

SEED = 34
CUSTOMERS_PER_TRANSFORMER = (16, 26)

FIRST_NAMES = [
    "Nimal", "Kamala", "Sunil", "Chandani", "Ruwan", "Dilani", "Pradeep", "Ishara", "Kasun", "Tharushi",
    "Mohamed", "Fathima", "Rizwan", "Ayesha", "Murugan", "Kavitha", "Suresh", "Priya", "Lalith", "Sandya",
    "Asanka", "Nadeesha", "Chaminda", "Hasini", "Janaka", "Nilmini", "Farook", "Shiyama", "Rajan", "Malini",
]
SURNAMES = [
    "Perera", "Fernando", "de Silva", "Jayasinghe", "Wickramasinghe", "Gunawardena", "Rathnayake", "Weerasinghe",
    "Abeysekara", "Senanayake", "Kumarasinghe", "Hettiarachchi", "Marikar", "Lafir", "Sivakumar", "Rajendran",
    "Amarasinghe", "Karunaratne", "Dissanayake", "Ekanayake",
]

# Landmarks people mention instead of an address: (name, aliases, section, offset_m, critical_load)
LANDMARKS: list[tuple[str, list[str], str, float, str | None]] = [
    ("Galle Teaching Hospital annex", ["hospital", "rohala", "රෝහල", "மருத்துவமனை"], "854-856", 320, "hospital"),
    ("Wakwella water pumping station", ["pumping station", "water board", "ජල පොම්පාගාරය"], "820-822", 280, "water"),
    ("Central College", ["central college", "school", "පාසල"], "824-826", 120, "shelter"),
    ("Sri Sudarshanarama Temple", ["temple", "pansala", "පන්සල", "கோவில்"], "818-820", 150, None),
    ("Jumma Mosque", ["mosque", "palliya", "පල්ලිය", "பள்ளிவாசல்"], "842-844", 60, None),
    ("St. Mary's Church", ["church", "dewalaya", "தேவாலயம்"], "860-836", 90, None),
    ("the big Bo tree junction", ["bo tree", "bodhiya", "බෝධිය"], "858-864", 40, None),
    ("Wakwella bus stand", ["bus stand", "bus halt", "bus stop"], "806-808", 260, None),
    ("the rice mill", ["rice mill", "mill", "හාල් මෝල"], "888-890", 150, None),
    ("the market", ["market", "pola", "පොළ", "சந்தை"], "844-846", 100, None),
]


@dataclass
class Customer:
    account_no: str
    name: str
    phone: str
    street: str
    house_no: int
    transformer_id: str
    lat: float
    lon: float
    critical: str | None


def create_database(path) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE customers (
            account_no TEXT PRIMARY KEY, name TEXT, phone TEXT UNIQUE, street TEXT, house_no INTEGER,
            transformer_id TEXT, lat REAL, lon REAL, critical TEXT
        );
        CREATE INDEX idx_street ON customers(street, house_no);
        CREATE INDEX idx_xfmr ON customers(transformer_id);
        CREATE TABLE landmarks (name TEXT, aliases TEXT, transformer_id TEXT, lat REAL, lon REAL, critical TEXT);
        """
    )
    return con


def build_database(path=DB_PATH, feeder: Feeder | None = None) -> None:
    """Galle: customers spread along each IEEE section, numbered house by house along the street."""
    feeder = feeder or get_feeder()
    rng = random.Random(SEED)
    con = create_database(path)

    house_counter: dict[str, int] = {}
    used_accounts: set[str] = set()
    used_phones: set[str] = set()
    for sid, sec in feeder.sections.items():
        xfmrs = sorted((t for t in feeder.transformers.values() if t.section == sid), key=lambda t: t.offset_m)
        if not xfmrs:
            continue
        n = sum(rng.randint(*CUSTOMERS_PER_TRANSFORMER) for _ in xfmrs)
        for i in range(n):
            offset = (i + 0.5) * sec.length_m / n
            side = 1 if i % 2 else -1
            lat, lon = feeder.point_on_section(sid, offset)
            lat, lon = _move(lat, lon, feeder.bearing_at(sid, offset) + 90 * side, rng.uniform(15, 45))
            nearest = min(xfmrs, key=lambda t: abs(t.offset_m - offset))
            house_counter[sec.street] = house_counter.get(sec.street, 0) + 1
            while (acct := f"{rng.randint(0, 9_999_999_999):010d}") in used_accounts:
                pass
            used_accounts.add(acct)
            while (phone := f"07{rng.choice('01245678')}{rng.randint(0, 9_999_999):07d}") in used_phones:
                pass
            used_phones.add(phone)
            con.execute(
                "INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,NULL)",
                (acct, f"{rng.choice(FIRST_NAMES)} {rng.choice(SURNAMES)}", phone, sec.street,
                 house_counter[sec.street], nearest.id, lat, lon),
            )

    for i, (name, aliases, sid, offset, critical) in enumerate(LANDMARKS):
        lat, lon = feeder.point_on_section(sid, offset)
        xfmrs = [t for t in feeder.transformers.values() if t.section == sid]
        nearest = min(xfmrs, key=lambda t: abs(t.offset_m - offset))
        con.execute("INSERT INTO landmarks VALUES (?,?,?,?,?,?)",
                    (name, "|".join(aliases), nearest.id, lat, lon, critical))
        if critical:
            # The critical facility is itself a customer on that transformer.
            con.execute(
                "INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?)",
                (f"90000000{i:02d}", name, f"09122{i:05d}", feeder.sections[sid].street, 0, nearest.id, lat, lon,
                 critical),
            )
    con.commit()
    con.close()


class CustomerDB:
    """Read-only lookups used to place complaints on the grid."""

    def __init__(self, path=DB_PATH, build=None) -> None:
        if not path.exists():
            (build or build_database)(path)
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.streets = [r[0] for r in self.con.execute("SELECT DISTINCT street FROM customers")]
        self.landmarks = [dict(r) for r in self.con.execute("SELECT * FROM landmarks")]

    def _row(self, r) -> Customer | None:
        return Customer(**dict(r)) if r else None

    def by_account(self, account_no: str) -> Customer | None:
        digits = re.sub(r"\D", "", account_no or "")
        return self._row(self.con.execute("SELECT * FROM customers WHERE account_no=?", (digits,)).fetchone())

    def by_phone(self, phone: str) -> Customer | None:
        digits = re.sub(r"\D", "", phone or "")
        if digits.startswith("94"):
            digits = "0" + digits[2:]
        return self._row(self.con.execute("SELECT * FROM customers WHERE phone=?", (digits,)).fetchone())

    def match_street(self, street: str) -> tuple[str | None, float]:
        if not street:
            return None, 0.0
        s = street.lower().replace("rd", "road").strip()
        best = max(self.streets, key=lambda x: SequenceMatcher(None, s, x.lower()).ratio())
        return best, SequenceMatcher(None, s, best.lower()).ratio()

    def by_address(self, street: str, house_no: int | None) -> tuple[Customer | None, float]:
        name, score = self.match_street(street)
        if not name or score < 0.6:
            return None, 0.0
        if house_no is None:
            return None, score
        r = self.con.execute(
            "SELECT * FROM customers WHERE street=? ORDER BY ABS(house_no-?) LIMIT 1", (name, house_no)
        ).fetchone()
        return self._row(r), score

    def match_landmark(self, text: str) -> dict | None:
        t = (text or "").lower()
        for lm in self.landmarks:
            if lm["name"].lower() in t or any(a.lower() in t for a in lm["aliases"].split("|")):
                return lm
        return None

    def customers_on(self, transformer_id: str) -> list[Customer]:
        rows = self.con.execute("SELECT * FROM customers WHERE transformer_id=?", (transformer_id,))
        return [Customer(**dict(r)) for r in rows]

    def counts_by_transformer(self) -> dict[str, int]:
        return {r[0]: r[1] for r in self.con.execute(
            "SELECT transformer_id, COUNT(*) FROM customers GROUP BY transformer_id")}

    def critical_by_transformer(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for r in self.con.execute("SELECT transformer_id, name, critical FROM customers WHERE critical IS NOT NULL"):
            out.setdefault(r[0], []).append(f"{r[1]} ({r[2]})")
        return out

    def street_ranges(self) -> dict[str, tuple[int, int]]:
        return {r[0]: (r[1], r[2]) for r in self.con.execute(
            "SELECT street, MIN(house_no), MAX(house_no) FROM customers WHERE house_no>0 GROUP BY street")}
