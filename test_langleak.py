"""Tests for langleak.py's word checks and make_fixtures.py (no browser). Apache-2.0, MV2 of Munim, Inc."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import langleak as ll  # noqa: E402
import make_fixtures as mf  # noqa: E402

SHELL_EN = {"lang": "English", "play": "Play", "pause": "Pause", "paused": "Paused", "gameOver": "Game over",
            "best": "Best: {0}", "score": "Score {0} · best {1}"}
SHELL_FR = {"lang": "Français", "play": "Jouer", "pause": "Pause", "paused": "Pause", "gameOver": "Partie terminée",
            "best": "Record : {0}", "score": "Score {0} · record {1}"}


class Words(unittest.TestCase):
    def test_english_in_french(self):
        self.assertEqual(ll.other_language_words("Tap the bubbles", "fr"), ["tap", "the"])
        self.assertEqual(ll.other_language_words("Touchez les bulles", "fr"), [])

    def test_french_in_english(self):
        self.assertEqual(ll.other_language_words("Touchez les bulles", "en"), ["les", "touchez"])
        self.assertEqual(ll.other_language_words("éclate", "en"), ["éclate"])
        self.assertEqual(ll.other_language_words("Tap the bubbles before they float away.", "en"), [])

    def test_shared_words_are_not_flagged(self):
        for text in ("Score 3 · record 5", "Pause", "Bonus x2", "Combo !", "On y va"):
            self.assertEqual(ll.other_language_words(text, "fr"), [], text)

    def test_english_only_phrases(self):
        en_only = ll.english_only_phrases(SHELL_EN, SHELL_FR)
        self.assertIn("game over", en_only)
        self.assertIn("paused", en_only)
        self.assertNotIn("pause", en_only)       # the same in both
        self.assertNotIn("english", en_only)     # the switch button's label
        self.assertEqual(ll.other_language_words("Game over", "fr", en_only), ["game", "game over", "over"])
        self.assertEqual(ll.other_language_words("Pause", "fr", en_only), [])
        self.assertEqual(ll.other_language_words("Pausedx", "fr", en_only), [])  # whole words only

    def test_allow_list(self):
        self.assertEqual(ll.other_language_words("Rush Order", "fr", allow=frozenset({"rush", "order"})), [])
        self.assertEqual(ll.other_language_words("Go!", "fr", allow=frozenset({"go"})), [])

    def test_missing_keys(self):
        self.assertEqual(ll.missing_keys({"fr": {"a": 1}, "en": {"a": 1, "b": 2}}), {"fr": ["b"]})
        self.assertEqual(ll.missing_keys({"fr": {}, "en": {}}), {})
        self.assertEqual(ll.missing_keys(None), {})

    def test_lines(self):
        self.assertEqual(ll.lines(" Jouer \n\n Son : activé\n"), ["Jouer", "Son : activé"])


class Fixtures(unittest.TestCase):
    SHELL = "\n".join(["const Game = {", mf.NAME, "  start(rand) {", "    " + mf.GO, "  },",
                       "  onTap() { if (x) { " + mf.LEVEL + "; } },", "};", mf.OPT_IN])

    def test_leaky_offers_two_languages_and_keeps_english(self):
        text = mf.leaky(self.SHELL)
        self.assertIn("Game.words = { fr: {}, en: {} };\n" + mf.OPT_IN, text)
        self.assertIn(mf.GO, text)

    def test_clean_says_everything(self):
        text = mf.clean(self.SHELL)
        for old in (mf.NAME, mf.GO, mf.LEVEL):
            self.assertNotIn(old, text)
        self.assertIn('say("goSub")', text)
        self.assertIn('say("level", level + 2)', text)
        self.assertIn("get howTo()", text)

    def test_a_missing_anchor_stops(self):
        with self.assertRaises(SystemExit):
            mf.clean("nothing here")


if __name__ == "__main__":
    unittest.main()
