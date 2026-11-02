import os
import unittest

os.environ["MODEL_MODE"] = "mock"
from relight.scenario import load
from relight.packs import network
from relight.grid import Feeder
from relight.network import NetworkState, Plan, check_plan, restoration_plans


class TestSwitchingPlanBlocked(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sc = load("galle_storm")
        cls.feeder, cls.db = network(sc)
        cls.customers = cls.db.counts_by_transformer()

    def setUp(self):
        # Tie switch TS-1 is open, upstream recloser REC-2 is open (isolating downstream sections)
        self.belief = NetworkState()
        self.belief.open.add("TS-1")
        self.belief.open.add("REC-2")
        self.plan = Plan("close_tie", "Close tie TS-1 to backfeed", [("close", "TS-1")])

    def test_blocked_energising_fault(self):
        """A plan that energises a known faulted section must be blocked."""
        self.belief.faulted.add("820-822")
        checked = check_plan(self.feeder, self.belief, self.plan, work_zones={}, customers=self.customers)
        self.assertFalse(checked.safe)
        self.assertEqual(checked.blocked_by, "would re-energise the faulted section")
        self.assertIn("would re-energise the faulted section", checked.reason)

    def test_blocked_energising_suspect_zone(self):
        """A plan that energises an unconfirmed suspect zone must be blocked."""
        self.belief.suspect.add("820-822")
        checked = check_plan(self.feeder, self.belief, self.plan, work_zones={}, customers=self.customers)
        self.assertFalse(checked.safe)
        self.assertEqual(checked.blocked_by, "unconfirmed fault in zone")
        self.assertIn("inside a fault zone whose exact location is not confirmed yet", checked.reason)

    def test_blocked_energising_crew_work_zone(self):
        """A plan that energises a section where a crew is currently working must be blocked."""
        work_zones = {"820-822": "CREW-L1"}
        checked = check_plan(self.feeder, self.belief, self.plan, work_zones=work_zones, customers=self.customers)
        self.assertFalse(checked.safe)
        self.assertEqual(checked.blocked_by, f"crew CREW-L1 working on {self.feeder.sections['820-822'].street}")
        self.assertIn("where CREW-L1 is working", checked.reason)


class TestMultiTieSwitching(unittest.TestCase):
    """Item 8: multiple normally-open ties in restoration switching and safety checks."""

    @classmethod
    def setUpClass(cls):
        # Feeder with two branches and two ties:
        # Root B0 -> B1 -> B2 (East Branch) -> B3
        #                 -> B4 (West Branch) -> B5
        # Tie TS-E at B3 connects to external feeder F_EAST
        # Tie TS-W at B5 connects to external feeder F_WEST
        spec = {
            "root": "B0",
            "buses": {
                "B0": (6.0, 80.0),
                "B1": (6.01, 80.0),
                "B2": (6.01, 80.01),
                "B3": (6.01, 80.02),
                "B4": (6.01, 79.99),
                "B5": (6.01, 79.98),
            },
            "sections": [
                {"id": "B0-B1", "from": "B0", "to": "B1", "coords": [(6.0, 80.0), (6.01, 80.0)], "street": "Main St"},
                {"id": "B1-B2", "from": "B1", "to": "B2", "coords": [(6.01, 80.0), (6.01, 80.01)], "street": "East Branch"},
                {"id": "B2-B3", "from": "B2", "to": "B3", "coords": [(6.01, 80.01), (6.01, 80.02)], "street": "Far East St"},
                {"id": "B1-B4", "from": "B1", "to": "B4", "coords": [(6.01, 80.0), (6.01, 79.99)], "street": "West Branch"},
                {"id": "B4-B5", "from": "B4", "to": "B5", "coords": [(6.01, 79.99), (6.01, 79.98)], "street": "Far West St"},
            ],
            "devices": [
                ("REC-MAIN", "recloser", "B0-B1", True, "Main recloser"),
            ],
            "external_feeders": [
                {"bus": "F_EAST", "pos": (6.01, 80.03), "label": "East Grid"},
                {"bus": "F_WEST", "pos": (6.01, 79.97), "label": "West Grid"},
            ],
            "switches": [
                ("SW-E1", "switch", "B1-B2", False, "East upstream sectionaliser"),
                ("SW-E2", "switch", "B2-B3", False, "East downstream sectionaliser"),
                ("SW-W1", "switch", "B1-B4", False, "West sectionaliser"),
                ("TS-E", "tie", "B3", "F_EAST", True, "East Tie"),
                ("TS-W", "tie", "B5", "F_WEST", True, "West Tie"),
            ],
            "transformer_spacing": 200,
        }
        cls.feeder = Feeder(spec)
        cls.customers = {t.id: 50 for t in cls.feeder.transformers.values()}

    def setUp(self):
        self.belief = NetworkState()
        self.belief.open.add("REC-MAIN")
        self.belief.open.add("TS-E")
        self.belief.open.add("TS-W")

    def test_multi_tie_plan_blocked_by_fault(self):
        """A plan that closes both ties is blocked if one tie would energise a faulted section."""
        self.belief.faulted.add("B2-B3")
        plan_both = Plan("both_ties", "Open SW-E1, close West tie, close East tie",
                         [("open", "SW-E1"), ("close", "TS-W"), ("close", "TS-E")])
        checked = check_plan(self.feeder, self.belief, plan_both, work_zones={}, customers=self.customers)
        self.assertFalse(checked.safe)
        self.assertEqual(checked.blocked_by, "would re-energise the faulted section")
        self.assertIn("Step 3 (close TS-E) would re-energise the faulted section B2-B3", checked.reason)

    def test_multi_tie_plan_blocked_by_suspect_zone(self):
        """A plan closing both ties is blocked if one tie energises an unconfirmed suspect zone."""
        self.belief.suspect.add("B2-B3")
        plan_both = Plan("both_ties", "Open SW-E1, close West tie, close East tie",
                         [("open", "SW-E1"), ("close", "TS-W"), ("close", "TS-E")])
        checked = check_plan(self.feeder, self.belief, plan_both, work_zones={}, customers=self.customers)
        self.assertFalse(checked.safe)
        self.assertEqual(checked.blocked_by, "unconfirmed fault in zone")

    def test_multi_tie_plan_blocked_by_crew_zone(self):
        """A plan closing both ties is blocked if one tie energises a section where a crew is working."""
        work_zones = {"B2-B3": "CREW-E1"}
        plan_both = Plan("both_ties", "Open SW-E1, close West tie, close East tie",
                         [("open", "SW-E1"), ("close", "TS-W"), ("close", "TS-E")])
        checked = check_plan(self.feeder, self.belief, plan_both, work_zones=work_zones, customers=self.customers)
        self.assertFalse(checked.safe)
        self.assertEqual(checked.blocked_by, "crew CREW-E1 working on Far East St")

    def test_recommend_plan_with_most_customers_or_fewest_ops(self):
        """When multiple safe plans exist, the one restoring the most customers is recommended."""
        self.belief.faulted.add("B1-B2")
        plans = restoration_plans(self.feeder, self.belief, "B1-B2", "REC-MAIN", work_zones={}, customers=self.customers)
        safe_plans = [p for p in plans if p.safe and p.customers > 0]
        self.assertGreater(len(safe_plans), 1)
        recommended = [p for p in safe_plans if p.recommended]
        self.assertEqual(len(recommended), 1)
        # The recommended plan restores the maximum customers (1000)
        self.assertEqual(recommended[0].customers, max(p.customers for p in safe_plans))
        # Between isolate-TS-E (4 ops, 1000 cust) and isolate-all (5 ops, 1000 cust), 4 ops is preferred
        self.assertEqual(recommended[0].id, "isolate-TS-E")
        # Plans with fewer customers than max are marked partial
        for p in safe_plans:
            if p.customers < recommended[0].customers:
                self.assertTrue(p.partial)


if __name__ == "__main__":
    unittest.main()
