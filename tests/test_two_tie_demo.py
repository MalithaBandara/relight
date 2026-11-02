import asyncio
import heapq
import os
import unittest

os.environ["MODEL_MODE"] = "mock"
from relight.engine import Engine
from relight.scenario import MAX_CLOCK_S, Replayer, load


class TestTwoTieDemo(unittest.TestCase):
    """The engine offers several safe plans for one fault on a feeder with two ties, and recommends the best."""

    def test_engine_offers_three_safe_plans_and_recommends_most_customers(self):
        sc = load("two_tie_demo")

        async def quiet(m):
            pass

        engine = Engine(sc, quiet)
        replayer = Replayer(sc, engine.handle)
        engine.sim = replayer
        offered: list[dict] = []

        async def run():
            clock = 0.0
            while clock < MAX_CLOCK_S and not offered:
                if replayer.queue and replayer.queue[0][0] <= clock:
                    _, _, e = heapq.heappop(replayer.queue)
                    await replayer.deliver(e)
                    continue
                clock += 30
                await engine.advance(clock)
                for inc in engine.incidents:
                    if any(p["safe"] for p in inc["plans"]):
                        offered.extend(inc["plans"])

        asyncio.run(run())
        safe = [p for p in offered if p["safe"] and p["customers"] > 0]
        self.assertGreaterEqual(len(safe), 3)
        self.assertEqual({tuple(p["ties"]) for p in safe}, {("TS-E",), ("TS-N",), ("TS-E", "TS-N")})
        recommended = [p for p in safe if p["recommended"]]
        self.assertEqual(len(recommended), 1)
        self.assertEqual(recommended[0]["customers"], max(p["customers"] for p in safe))
        self.assertEqual(tuple(recommended[0]["ties"]), ("TS-E", "TS-N"))
        # the plans that close one tie only restore part of what the recommended plan does
        for p in safe:
            if p is not recommended[0]:
                self.assertLess(p["customers"], recommended[0]["customers"])
        # a plan that would energise the faulted section is offered as blocked, with a reason
        blocked = [p for p in offered if not p["safe"]]
        self.assertTrue(blocked)
        self.assertTrue(all(p["blocked_by"] for p in blocked))


if __name__ == "__main__":
    unittest.main()
