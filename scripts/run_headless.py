"""Replay a scenario instantly (no UI), let the crews work it through, and print the outcome.

Usage:  python scripts/run_headless.py [scenario] [--timeline] [--no-switching]

By default the operator approves every safe switching plan as soon as it is offered.
"""

import asyncio
import heapq
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from relight.engine import Engine  # noqa: E402
from relight.scenario import MAX_CLOCK_S, Replayer, load  # noqa: E402

STEP_S = 30


async def main(name: str, show_timeline: bool, switching: bool) -> None:
    sc = load(name)

    async def quiet(_msg):
        pass

    engine = Engine(sc, quiet)
    clock_str = engine.clock
    replayer = Replayer(sc, engine.handle)
    engine.sim = replayer
    clock = 0.0
    while clock < MAX_CLOCK_S:
        if replayer.queue and replayer.queue[0][0] <= clock:
            _, _, e = heapq.heappop(replayer.queue)
            await replayer.deliver(e)
            continue
        if not replayer.queue and clock >= sc["duration_s"] and not engine.busy():
            break
        clock += STEP_S
        await engine.advance(clock)
        if switching:
            for inc in engine.incidents:
                for p in inc["plans"]:
                    if p["safe"] and p["customers"] and not inc["switching"] and inc["status"] != "restored":
                        await engine.apply_plan(inc["id"], p["id"])

    if show_timeline:
        for x in engine.timeline:
            print(f"{x['clock']}  [{x['model']}] {x['title']}  {x['detail'][:120]}")
        print()
    s = engine.snapshot()
    c = s["counts"]
    print(f"mode={s['mode']}  messages={c['messages']}  duplicates={c['duplicates']}  junk={c['junk']}  "
          f"BD SMS={c['bd_sms']}  languages={c['languages']}  notified={c['notified']}  end={s['clock']}")
    print("\nIncidents:")
    for i in sorted(engine.incidents, key=lambda i: i["located_at"]):
        flags = (" MIND-CHANGED" if i["mind_changed"] else "") + (" AFTER-RESTORE" if i["after_restore"] else "") + \
                (f" switched {len(i['switching'])} ops" if i["switching"] else "")
        print(f"  {i['id']} {i['title']:<20} {i['label']:<38} located {clock_str(i['located_at'])} "
              f"restored {clock_str(i['restored_at']) if i['restored_at'] else '-'}{flags}")
        for h in i["history"]:
            print(f"       ↺ {h['before']} -> {h['after']}")
    print("\nAgent questions:")
    for p in s["probes"]:
        print(f"  {p['id']} {clock_str(p['t'])} {p['fault']} vs {p['rival']} -> {p['street']} {p['house_no']}: {p['answer']}")
    print("\nAgainst ground truth:")
    for t in s["truth"]:
        print(f"  {t['id']} {t['title']:<58} found={t['found']}  located "
              f"{clock_str(t['located_at']) if t['located_at'] is not None else '-'}  restored "
              f"{clock_str(t['restored_at']) if t['restored_at'] else '-'}")
    print(f"\nWhat-if customer-minutes: Relight {s['plan']['customer_minutes']:,} vs first-call-first-served "
          f"{s['baseline']['customer_minutes']:,}; live wire made safe after {s['plan']['hazard_wait_min']} vs "
          f"{s['baseline']['hazard_wait_min']} min")
    print(f"Still dark at the end: {c['customers_out']} customers (believed); "
          f"world says {len(replayer.world.still_dark(list(engine.feeder.transformers)))}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    asyncio.run(main(args[0] if args else "galle_storm", "--timeline" in sys.argv, "--no-switching" not in sys.argv))
