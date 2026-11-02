import asyncio
import heapq
import os
import unittest

os.environ["MODEL_MODE"] = "mock"
from relight.scenario import load, Replayer
from relight.engine import Engine


class TestOneHouseDark(unittest.TestCase):
    def test_one_house_dark_why_is_none(self):
        """The one-house-dark path produces an incident whose `why` is None."""
        sc = load("galle_storm")
        async def quiet(m): pass
        engine = Engine(sc, quiet)
        replayer = Replayer(sc, engine.handle)
        engine.sim = replayer

        async def run_until_isolated():
            clock = 0.0
            # Run past the isolated report threshold (ISOLATED_AFTER_S = 150 s from call at ~900s)
            while clock <= 1060:
                if replayer.queue and replayer.queue[0][0] <= clock:
                    _, _, e = heapq.heappop(replayer.queue)
                    await replayer.deliver(e)
                    continue
                clock += 30
                await engine.advance(clock)

        asyncio.run(run_until_isolated())

        # The one-house-dark path produces an incident with kind == "service_wire"
        isolated = [inc for inc in engine.incidents if inc.get("kind") == "service_wire"]
        self.assertTrue(bool(isolated), "Isolated service wire incident should be created")
        for inc in isolated:
            self.assertIsNone(inc.get("why"), f"Incident {inc['id']} why block must be None")


if __name__ == "__main__":
    unittest.main()
