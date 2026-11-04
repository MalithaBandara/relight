import asyncio
import heapq
import os
import unittest

os.environ["MODEL_MODE"] = "mock"
from relight.engine import Engine, NOTICE_GAP_S, NOTICE_MOVED_S
from relight.scenario import MAX_CLOCK_S, Replayer, load


def fake_engine() -> tuple[Engine, dict]:
    """An engine holding one incident, with a crew at work, and two customers told it would finish at t=3600."""
    async def quiet(m): pass
    engine = Engine(load("galle_storm"), quiet)
    engine.elapsed = 1800.0
    engine.messages = [{"id": "C1", "from": "0771", "language": "si"}, {"id": "C2", "from": "0772", "language": "en"}]
    inc = {"id": "I1", "title": "Tree on line", "kind": "tree_on_line", "status": "on site", "eta": 3600.0,
           "steps": [{"status": "onsite", "end_t": 3600.0, "minutes": 30}], "reports": ["C1", "C2"],
           "told_eta": {"0771": 3600.0, "0772": 3600.0}, "eta_update_t": None}
    return engine, inc


class TestNoticeUpdate(unittest.TestCase):
    def test_small_change_sends_nothing(self):
        engine, inc = fake_engine()
        inc["steps"][0]["end_t"] += NOTICE_MOVED_S - 60
        asyncio.run(engine._notify_change(inc))
        self.assertEqual(engine.notices, [])

    def test_moved_estimate_is_sent_once_in_each_language(self):
        engine, inc = fake_engine()
        inc["steps"][0]["end_t"] += NOTICE_MOVED_S
        asyncio.run(engine._notify_change(inc))
        self.assertEqual({n["language"]: n["to"] for n in engine.notices}, {"si": ["0771"], "en": ["0772"]})
        eta = engine.clock(inc["steps"][0]["end_t"])
        for n in engine.notices:
            self.assertIn(eta, n["text"])
            self.assertEqual((n["kind"], n["model"]), ("eta_update", "Code (template)"))
        engine.elapsed += NOTICE_GAP_S
        asyncio.run(engine._notify_change(inc))  # already told: nothing more
        self.assertEqual(len(engine.notices), 2)

    def test_earlier_estimate_is_also_sent(self):
        engine, inc = fake_engine()
        inc["steps"][0]["end_t"] -= NOTICE_MOVED_S
        asyncio.run(engine._notify_change(inc))
        self.assertEqual(len(engine.notices), 2)

    def test_second_update_waits_for_the_gap(self):
        engine, inc = fake_engine()
        inc["steps"][0]["end_t"] += NOTICE_MOVED_S
        asyncio.run(engine._notify_change(inc))
        sent = len(engine.notices)
        inc["steps"][0]["end_t"] += NOTICE_MOVED_S + NOTICE_GAP_S
        engine.elapsed += NOTICE_GAP_S - 60
        asyncio.run(engine._notify_change(inc))
        self.assertEqual(len(engine.notices), sent)
        engine.elapsed += 60
        asyncio.run(engine._notify_change(inc))
        self.assertEqual(len(engine.notices), sent + 2)

    def test_stored_estimate_is_left_alone(self):
        """The call agent's lines quote inc["eta"]; only the next scoring may change it, or cached wording would miss."""
        engine, inc = fake_engine()
        inc["steps"][0]["end_t"] += NOTICE_MOVED_S
        asyncio.run(engine._notify_change(inc))
        self.assertEqual(inc["eta"], 3600.0)

    def test_every_language_has_an_update_template(self):
        for name in ("galle_storm", "houston_hurricane", "chennai_cyclone"):
            async def quiet(m): pass
            loc = Engine(load(name), quiet).loc
            self.assertEqual(set(loc["notice_update"]), set(loc["notice"]), name)

    def test_galle_customers_hear_the_estimate_that_came_true(self):
        """Lake Road looks like a blown fuse, a crew finds a service wire, and the job then waits for a line crew."""
        sc = load("galle_storm")
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
                clock += 30
                await engine.advance(clock)
                for inc in engine.incidents:
                    for p in inc["plans"]:
                        if p["safe"] and p["customers"] and not inc["switching"] and inc["status"] != "restored":
                            await engine.apply_plan(inc["id"], p["id"])

        asyncio.run(run())
        changed = next(i for i in engine.incidents if i["mind_changed"] and i["told_eta"])
        self.assertTrue(any(n["kind"] == "eta_update" and n["fault"] == changed["id"] for n in engine.notices))
        for told in changed["told_eta"].values():
            self.assertLess(abs(changed["restored_at"] - told), NOTICE_MOVED_S + NOTICE_GAP_S)


if __name__ == "__main__":
    unittest.main()
