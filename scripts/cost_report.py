"""What the model calls cost: measured per storm and per channel from the cache, then an estimate for a real utility.

Usage:  python scripts/cost_report.py [scenario ...]     writes eval/cost.json

Replays run in mock mode, so no request can leave this machine and the script costs nothing. Two counts, because they
answer different questions:
- `bill`: each unique request once, which is what one live run pays (identical requests are served from the cache).
- per channel: every request as replayed, so repeats count again. That is the cautious figure for a deployment that does
  not reuse responses. It is why a call's cost here is not a share of `bill`.

The utility estimate is arithmetic on stated assumptions. Nothing in it has been measured at a utility. Prices are from
https://dev.meta.ai/docs/pricing-rate-limits and https://www.twilio.com/en-us/voice/pricing/us (read 2026-11-04).
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import heapq
import io
import json
import os
import statistics
import sys
from pathlib import Path

os.environ["MODEL_MODE"] = "mock"  # before config is imported: this script must never make a paid request
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from relight.engine import Engine  # noqa: E402
from relight.models import ASR_PRICE_HOUR, SPARK_PRICE_IN, SPARK_PRICE_OUT, ModelClient  # noqa: E402
from relight.scenario import MAX_CLOCK_S, Replayer, load  # noqa: E402

STEP_S = 30
SCENARIOS = ["galle_storm", "houston_hurricane", "chennai_cyclone", "house_fuse", "tree_on_line", "hospital_generator"]
SAM_PER_IMAGE, SAM_PER_FRAME = 2.50 / 1000, 0.20 / 1000

# Assumptions for the utility estimate. Change these to fit a real utility.
CUSTOMERS = 100_000
REPORT_RATE = 0.20  # share of customers who report once in a major storm (Chennai's scenario has about 10%)
CALL_SHARE = 0.50  # the rest arrive as text
HANDED_TO_HUMAN = 0.10  # calls the agent hands to a person
CALL_MIN = 3
SPARK_PER_CALL = 0.015  # above the largest voiced or unvoiced call measured (1.45 cents)
SPARK_PER_TEXT = 0.005  # above the largest channel mean measured (0.41 cents)
DAMAGE_REVIEW = 10.0  # photos and clips; Galle's drone clip, 40 photos and their Spark readings cost under $1
LINE_LOCAL_MIN, LINE_TOLL_FREE_MIN = 0.0085, 0.022  # Twilio, US, receiving a call
LIVE_CONTACT = 8.01  # Gartner 2019 poll, live channels, all industries


def spark_asr_spend(client: ModelClient) -> float:
    usd = client.audio_s / 3600 * ASR_PRICE_HOUR
    for kind in ("spark", "spark-audio"):
        t = client.tally.get(kind)
        if t:
            usd += (t["tokens_in"] * SPARK_PRICE_IN + t["tokens_out"] * SPARK_PRICE_OUT) / 1e6
    return usd


async def replay(name: str) -> dict:
    seen: set[Path] = set()
    original_key = ModelClient._key

    def key(self, kind, payload):
        path = original_key(self, kind, payload)
        if path.exists():
            seen.add(path)
        return path

    ModelClient._key = key
    try:
        sc = load(name)

        async def quiet(_msg):
            pass

        engine = Engine(sc, quiet)
        per_channel: dict[str, list[float]] = collections.defaultdict(list)
        handle = engine.handle

        async def measured(event):
            before = spark_asr_spend(engine.client)
            result = await handle(event)
            per_channel[event.get("channel") or event.get("type") or "?"].append(spark_asr_spend(engine.client) - before)
            return result

        replayer = Replayer(sc, measured)
        engine.sim = replayer
        clock = 0.0
        while clock < MAX_CLOCK_S:
            if replayer.queue and replayer.queue[0][0] <= clock:
                _, _, event = heapq.heappop(replayer.queue)
                await replayer.deliver(event)
                continue
            if not replayer.queue and clock >= sc["duration_s"] and not engine.busy():
                break
            clock += STEP_S
            await engine.advance(clock)
            for inc in engine.incidents:
                for plan in inc["plans"]:
                    if plan["safe"] and plan["customers"] and not inc["switching"] and inc["status"] != "restored":
                        await engine.apply_plan(inc["id"], plan["id"])
    finally:
        ModelClient._key = original_key

    tokens_in = tokens_out = images = frames = 0
    for path in seen:
        data = json.loads(path.read_text(encoding="utf-8"))
        usage = data.get("usage") if isinstance(data, dict) else None
        if not isinstance(usage, dict):
            continue
        if path.name.startswith("sam"):
            images += usage.get("images_processed", 0) or 0
            frames += usage.get("video_frames_processed", 0) or 0
        else:
            tokens_in += usage.get("prompt_tokens", 0) or 0
            tokens_out += usage.get("completion_tokens", 0) or 0
    spark = (tokens_in * SPARK_PRICE_IN + tokens_out * SPARK_PRICE_OUT) / 1e6
    asr = engine.client.audio_s / 3600 * ASR_PRICE_HOUR
    sam = images * SAM_PER_IMAGE + frames * SAM_PER_FRAME
    messages = len(engine.messages)
    total = spark + asr + sam
    return {
        "scenario": name,
        "messages": messages,
        "unique_requests": len(seen),
        "bill_usd": {"spark": round(spark, 3), "voice_transcribe": round(asr, 3), "sam": round(sam, 3),
                     "total": round(total, 2)},
        "per_message_cents": round(total / messages * 100, 2) if messages else None,
        "sam_usage": {"images": images, "video_frames": frames},
        "per_channel_cents": {ch: {"n": len(xs), "mean": round(statistics.mean(xs) * 100, 2),
                                   "max": round(max(xs) * 100, 2)} for ch, xs in sorted(per_channel.items())},
    }


def utility_estimate() -> dict:
    reports = CUSTOMERS * REPORT_RATE
    calls = reports * CALL_SHARE
    texts = reports - calls
    model_per_call = SPARK_PER_CALL + CALL_MIN / 60 * ASR_PRICE_HOUR
    humans = calls * HANDED_TO_HUMAN

    def storm(line_per_min: float) -> dict:
        per_call = model_per_call + CALL_MIN * line_per_min
        usage = calls * per_call + texts * SPARK_PER_TEXT + DAMAGE_REVIEW
        return {"per_call_cents": round(per_call * 100, 1), "usage_usd": round(usage),
                "with_handovers_usd": round(usage + humans * LIVE_CONTACT)}

    return {
        "assumptions": {"customers": CUSTOMERS, "report_rate": REPORT_RATE, "call_share": CALL_SHARE,
                        "handed_to_human": HANDED_TO_HUMAN, "call_minutes": CALL_MIN},
        "calls": round(calls), "texts": round(texts),
        "model_per_call_cents": round(model_per_call * 100, 1),
        "local_line": storm(LINE_LOCAL_MIN), "toll_free_line": storm(LINE_TOLL_FREE_MIN),
        "all_calls_live_usd": round(calls * LIVE_CONTACT),
    }


async def main(names: list[str]) -> None:
    runs = []
    for name in names:
        with contextlib.redirect_stdout(io.StringIO()):  # the engine's own output is not the point here
            runs.append(await replay(name))
        r = runs[-1]
        print(f"{r['scenario']:<20} messages {r['messages']:>5}  requests {r['unique_requests']:>5}  "
              f"${r['bill_usd']['total']:>5.2f}  {r['per_message_cents']} cents per message  {r['bill_usd']}")
        print(f"{'':<20} {r['per_channel_cents']}")
    estimate = utility_estimate()
    print(json.dumps(estimate, indent=1))
    out = ROOT / "eval" / "cost.json"
    out.write_text(json.dumps({"runs": runs, "utility_estimate": estimate}, indent=1) + "\n", encoding="utf-8")
    print(f"written: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or SCENARIOS))
