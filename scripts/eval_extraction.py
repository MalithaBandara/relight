"""Score complaint extraction against the scenario's labels, per language.

Runs every scenario complaint through the extractor (Muse Spark) and reports field accuracy by language. Results are
written to eval/extraction-<model>.json for the README and the demo video.

Usage:  python scripts/eval_extraction.py [scenario] [--replay]
        scenario defaults to galle_storm; --replay scores the engine's own cached readings from a replay (no API calls)
"""

import asyncio
import heapq
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from relight import config  # noqa: E402
from relight import packs  # noqa: E402
from relight.engine import Engine  # noqa: E402
from relight.scenario import MAX_CLOCK_S, Replayer  # noqa: E402
from relight.extract import Extractor  # noqa: E402
from relight.models import ModelClient  # noqa: E402
from relight.scenario import load  # noqa: E402

WORKERS = 6
STEP_S = 30  # as in run_headless.py
FIELDS = ["street", "house_no", "symptom", "hazard", "junk"]


async def replayed(sc: dict) -> list[dict]:
    """Replay the scenario as scripts/run_headless.py does (same clock steps, so follow-up texts and therefore cache
    keys match the live run) and return the engine's processed messages."""
    async def quiet(_msg):
        pass

    engine = Engine(sc, quiet)
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
        for inc in engine.incidents:  # the operator approves safe plans, as in run_headless
            for p in inc["plans"]:
                if p["safe"] and p["customers"] and not inc["switching"] and inc["status"] != "restored":
                    await engine.apply_plan(inc["id"], p["id"])
    return engine.messages


def main() -> None:
    client = ModelClient(mode="live")
    ex = Extractor(client)
    if not config.MODEL_API_KEY:
        sys.exit("MODEL_API_KEY is not set; mock output would just echo the labels.")
    name = next((a for a in sys.argv[1:] if not a.startswith("--")), "galle_storm")
    sc = load(name)
    db = packs.network(sc)[1]
    hits: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    rows, skipped = [], []
    events = [e for e in sc["events"] if e["type"] == "complaint"]
    if "--replay" in sys.argv:
        # Score what the engine itself extracted in a replay (cached live answers: free). Calls are read from their
        # transcripts, and SMS codes need no model, so only Muse Spark's own readings are scored.
        done = {m["id"]: m for m in asyncio.run(replayed(sc)) if m.get("fields")}
        results = [(done[e["id"]]["model"], done[e["id"]]["fields"]) if e["id"] in done else ("mock (missing)", {})
                   for e in events]
        results = [(m if m.startswith("Muse") else "mock (not a Spark reading)", f) for m, f in results]
    else:
        with ThreadPoolExecutor(WORKERS) as pool:  # each call takes seconds; the client and its cache are thread-safe
            results = [(x.model, x.fields) for x in pool.map(
                lambda e: ex.complaint(e["text"], e["truth"], e["language"]), events)]
    for e, (model_label, out) in zip(events, results):
        if model_label.startswith("mock"):  # no live answer (no key, or API not allowed): scoring it would be a lie
            skipped.append(e["id"])
            continue
        truth = e["truth"]
        got_street = db.match_street(out.get("street") or "")[0] if out.get("street") else None
        checks = {
            "street": got_street == truth.get("street") if truth.get("street") else True,
            "house_no": out.get("house_no") == truth.get("house_no") if truth.get("house_no") else True,
            "symptom": out.get("symptom") == truth.get("symptom"),
            "hazard": out.get("hazard") == truth.get("hazard"),
            "junk": bool(out.get("is_junk")) == bool(truth.get("junk")),
        }
        for f, ok in checks.items():
            hits[e["language"]][f].append(ok)
            hits["all"][f].append(ok)
        rows.append({"id": e["id"], "language": e["language"], "checks": checks, "output": out})
        bad = [f for f, ok in checks.items() if not ok]
        print(f"{e['id']:<4} {e['language']}  {'ok' if not bad else 'MISS ' + ','.join(bad)}")
    if skipped:
        print(f"\n{len(skipped)} of {len(events)} complaints had no live answer and are not scored.")
    if not rows:
        sys.exit("Nothing was scored: no live model answers (is the API allowed for this run?).")

    print(f"\n{'lang':<5} " + " ".join(f"{f:>9}" for f in FIELDS) + "   n")
    summary = {}
    for lang, fs in sorted(hits.items()):
        summary[lang] = {f: round(sum(v) / len(v), 3) for f, v in fs.items()}
        n = len(next(iter(fs.values())))
        print(f"{lang:<5} " + " ".join(f"{summary[lang][f]:>9.0%}" for f in FIELDS) + f"  {n:>2}")
    out_dir = config.ROOT / "eval"
    out_dir.mkdir(exist_ok=True)
    model = config.SPARK_MODEL
    (out_dir / f"extraction-{model}-{name}.json").write_text(
        json.dumps({"model": model, "scenario": name, "summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8")


if __name__ == "__main__":
    main()
