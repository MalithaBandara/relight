import asyncio
import heapq
import os
import unittest

os.environ["MODEL_MODE"] = "mock"
from relight.scenario import load, Replayer
from relight.engine import Engine
from relight.tracer import call_probability


class TestTracerWhy(unittest.TestCase):
    def _run_and_verify_why(self, scenario_name: str) -> int:
        sc = load(scenario_name)
        async def quiet(m): pass
        engine = Engine(sc, quiet)
        replayer = Replayer(sc, engine.handle)
        engine.sim = replayer

        verified_count = 0
        orig_locate = engine.tracer.locate

        def verify_locate(ev, elapsed_s):
            nonlocal verified_count
            loc = orig_locate(ev, elapsed_s)
            if loc:
                hyp = [L.candidate for L in loc]
                q = call_probability(elapsed_s)
                gain = engine.tracer._per_transformer(ev, q)
                s_hyp = engine.tracer.score(hyp, ev, gain)
                for L in loc:
                    rest = [h for h in hyp if h is not L.candidate]
                    s_rest = engine.tracer.score(rest, ev, gain)
                    real_marginal = s_hyp - s_rest

                    # Check 1: total equals real marginal score within 0.1
                    self.assertAlmostEqual(L.why["total"], real_marginal, delta=0.1,
                                           msg=f"Incident {L.candidate.id} why.total {L.why['total']} != real marginal {real_marginal:.2f}")

                    # Check 2: sources sum to total within 0.1
                    sources = L.why.get("sources", [])
                    self.assertTrue(bool(sources), f"Incident {L.candidate.id} sources must not be empty")
                    s_sum = sum(s["score"] for s in sources)
                    self.assertAlmostEqual(s_sum, L.why["total"], delta=0.1,
                                           msg=f"Incident {L.candidate.id} sources sum {s_sum:.2f} != total {L.why['total']:.2f}")

                    verified_count += 1
            return loc

        engine.tracer.locate = verify_locate

        async def run():
            clock = 0.0
            while clock < sc["duration_s"]:
                if replayer.queue and replayer.queue[0][0] <= clock:
                    _, _, e = heapq.heappop(replayer.queue)
                    await replayer.deliver(e)
                    continue
                if not replayer.queue and not engine.busy():
                    break
                clock += 30
                await engine.advance(clock)

        asyncio.run(run())
        return verified_count

    def test_galle_why_marginal_and_sources(self):
        count = self._run_and_verify_why("galle_storm")
        self.assertTrue(count >= 4, f"Expected at least 4 located candidates verified, got {count}")

    def test_houston_why_marginal_and_sources(self):
        count = self._run_and_verify_why("houston_hurricane")
        self.assertTrue(count >= 4, f"Expected at least 4 located candidates verified, got {count}")


if __name__ == "__main__":
    unittest.main()
