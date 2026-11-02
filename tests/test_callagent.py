import os
import unittest

os.environ["MODEL_MODE"] = "mock"
from relight.scenario import load
from relight.engine import Engine
from relight.locales import KIND_NAME


class TestCallAgentLocalKind(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sc = load("galle_storm")
        async def quiet(m): pass
        cls.engine = Engine(sc, quiet)
        cls.agent = cls.engine.agent

    def test_english_returns_plain_text(self):
        for phrase in ["pole down", "tree on line", "live wire on road", "wire down", "blown fuse", "service wire down"]:
            self.assertEqual(self.agent.local_kind(phrase, "en"), phrase)

    def test_local_languages_return_translated_phrases(self):
        mapping = {
            "pole down": "pole_down",
            "tree on line": "tree_on_line",
            "live wire on road": "live_wire",
            "wire down": "wire_down",
            "blown fuse": "blown_fuse",
            "service wire down": "service_wire",
        }
        for lang in ["si", "ta", "es", "hi"]:
            for phrase, key in mapping.items():
                expected = KIND_NAME[lang][key]
                got = self.agent.local_kind(phrase, lang)
                self.assertEqual(got, expected, f"Failed for {lang} {phrase}")

    def test_unknown_cause_phrase(self):
        for lang in ["si", "ta", "es", "hi"]:
            expected = KIND_NAME[lang]["unknown"]
            got = self.agent.local_kind("cause unknown", lang)
            self.assertEqual(got, expected)


if __name__ == "__main__":
    unittest.main()
