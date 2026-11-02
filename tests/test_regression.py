import asyncio
import heapq
import os
import unittest

os.environ["MODEL_MODE"] = "mock"
from relight.scenario import load, Replayer, MAX_CLOCK_S
from relight.engine import Engine

STEP_S = 30


class TestScenarioRegression(unittest.TestCase):
    def _run_scenario(self, name: str) -> tuple[int, int, int]:
        sc = load(name)
        async def quiet(m): pass
        engine = Engine(sc, quiet)
        replayer = Replayer(sc, engine.handle)
        engine.sim = replayer

        async def run():
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
                for inc in engine.incidents:
                    for p in inc["plans"]:
                        if p["safe"] and p["customers"] and not inc["switching"] and inc["status"] != "restored":
                            await engine.apply_plan(inc["id"], p["id"])

        asyncio.run(run())
        snap = engine.snapshot()
        found = sum(1 for t in snap["truth"] if t["found"])
        total = len(snap["truth"])
        still_dark = len(replayer.world.still_dark(list(engine.feeder.transformers)))
        return found, total, still_dark

    def test_galle_storm(self):
        found, total, dark = self._run_scenario("galle_storm")
        self.assertEqual(total, 6)
        self.assertEqual(found, 6)
        self.assertEqual(dark, 0)

    def test_houston_hurricane(self):
        found, total, dark = self._run_scenario("houston_hurricane")
        self.assertEqual(total, 7)
        self.assertEqual(found, 7)
        self.assertEqual(dark, 0)

    def test_chennai_cyclone(self):
        found, total, dark = self._run_scenario("chennai_cyclone")
        self.assertEqual(total, 9)
        self.assertEqual(found, 9)
        self.assertEqual(dark, 0)

    def test_house_fuse(self):
        found, total, dark = self._run_scenario("house_fuse")
        self.assertEqual(total, 1)
        self.assertEqual(found, 1)
        self.assertEqual(dark, 0)

    def test_tree_on_line(self):
        found, total, dark = self._run_scenario("tree_on_line")
        self.assertEqual(total, 1)
        self.assertEqual(found, 1)
        self.assertEqual(dark, 0)

    def test_hospital_generator(self):
        found, total, dark = self._run_scenario("hospital_generator")
        self.assertEqual(total, 3)
        self.assertEqual(found, 3)
        self.assertEqual(dark, 0)

    def test_two_tie_demo(self):
        found, total, dark = self._run_scenario("two_tie_demo")
        self.assertEqual(total, 1)
        self.assertEqual(found, 1)
        self.assertEqual(dark, 0)

    def test_ieee123_storm_reported_result(self):
        """The independent feeder is a measurement, not a pass mark: it must run to the end and match the README."""
        found, total, dark = self._run_scenario("ieee123_storm")
        self.assertEqual(total, 5)
        self.assertEqual((found, dark), (4, 16))  # F1 missed, 16 customers dark: the numbers the README reports


if __name__ == "__main__":
    unittest.main()
