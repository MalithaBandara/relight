import os
import unittest

os.environ["MODEL_MODE"] = "mock"
from relight.callagent import facts_kept


class TestFactsKept(unittest.TestCase):
    def test_accepts_when_all_kept(self):
        # Keeps exact number
        self.assertEqual(facts_kept("restore 23 customers", "restore 23 customers", ()), [])
        # Keeps time across Sinhala
        self.assertEqual(facts_kept("around 15:20", "சுமார் 15:20 மணிக்கு", ()), [])
        # Keeps number in Sinhala script
        self.assertEqual(facts_kept("number 52", "අංක 52 අසල", ()), [])
        # Keeps street and id
        self.assertEqual(facts_kept("logged against I2", "සටහන් කළා I2 යටතේ", ("I2",)), [])
        self.assertEqual(facts_kept("on Hospital Road", "Hospital Road ළඟ", ("Hospital Road",)), [])
        self.assertEqual(facts_kept("on Hospital Road", "hospital road", ("Hospital Road",)), [])

    def test_rejects_when_number_changed(self):
        # Number altered
        dropped = facts_kept("restore 23 customers", "restore 123 customers", ())
        self.assertIn("23", dropped)
        # Range altered
        dropped = facts_kept("houses 6 to 14", "houses 16 to 14", ())
        self.assertIn("6", dropped)
        dropped = facts_kept("houses 6 to 14", "houses 6 to 16", ())
        self.assertIn("14", dropped)

    def test_rejects_when_time_changed(self):
        dropped = facts_kept("around 15:20", "around 5:20", ())
        self.assertIn("15:20", dropped)

    def test_rejects_when_id_changed(self):
        dropped = facts_kept("logged against I2", "logged against I20", ("I2",))
        self.assertTrue(bool(dropped))
        dropped = facts_kept("logged against I2", "logged against I3", ("I2",))
        self.assertTrue(bool(dropped))

    def test_rejects_when_street_changed(self):
        dropped = facts_kept("on Hospital Road", "ஆஸ்பத்திரி ரோடு", ("Hospital Road",))
        self.assertIn("Hospital Road", dropped)


if __name__ == "__main__":
    unittest.main()
