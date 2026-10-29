"""Replay a scenario instantly (no UI) and print what GridMedic concluded.

Usage:  python scripts/run_headless.py [--timeline]
"""

import asyncio
import heapq
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gridmedic.engine import Engine  # noqa: E402
from gridmedic.scenario import Replayer, load  # noqa: E402


async def main(show_timeline: bool) -> None:
    sc = load()

    async def quiet(_msg):
        pass

    replayer: Replayer
    engine = Engine(sc, quiet, on_probe=lambda p: replayer.schedule_probe_reply(p))
    replayer = Replayer(sc, engine.handle)
    while replayer.queue:
        _, _, e = heapq.heappop(replayer.queue)
        await engine.handle(e)

    if show_timeline:
        for x in engine.timeline:
            print(f"{x['t']:>5}s  [{x['model']}] {x['title']}  {x['detail'][:110]}")
        print()
    s = engine.snapshot()
    print(f"mode={s['mode']}  messages={s['counts']['messages']}  duplicates={s['counts']['duplicates']}  "
          f"junk={s['counts']['junk']}  languages={s['counts']['languages']}")
    print("\nRepair queue:")
    for f in s["faults"]:
        d = f["dispatch"]
        crews = ", ".join(f"{st['crew']}:{st['task']}" for st in d["steps"])
        print(f"  {f['priority']:>7}  {f['title']:<22} {f['device']:<14} conf {f['confidence']:.2f}  "
              f"{f['customers_out']:>4} cust  restore +{d['restore_min']} min  [{crews}]")
    print("\nAgent questions:")
    for p in s["probes"]:
        print(f"  {p['id']} t={p['t']} {p['fault']} vs {p['rival']} -> ask {p['street']} {p['house_no']} "
              f"({p['transformer']}, {p['language']}): {p['answer']}")
    print("\nAgainst ground truth:")
    for t in s["truth"]:
        print(f"  {t['id']} {t['title']:<48} found={t['found']}  located at t={t['located_at']}")
    print(f"\nCustomer-minutes: GridMedic {s['plan']['customer_minutes']:,} vs first-call-first-served "
          f"{s['baseline']['customer_minutes']:,}; live wire made safe after "
          f"{s['plan']['hazard_wait_min']} vs {s['baseline']['hazard_wait_min']} min")


if __name__ == "__main__":
    asyncio.run(main("--timeline" in sys.argv))
