# Tests for skillcheck.py (jamshell by MV2 of Munim, Inc., made with AI agents; Apache-2.0).
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skillcheck  # noqa: E402

# Shaped like jamshell 0.5's shell.html: the credits element carries data-say, the DEMO block has markers.
SHELL = "\n".join([
    "<html><body>",
    '<div id="credits" data-say="credits">Made by MV2 of Munim, Inc. with AI agents (Anthropic Claude).</div>',
    "<script>",
    "const W = 720;",
    "// -----",
    '// DEMO (replace in a jam game): "Pop", tap the bubbles.',
    "// A game object needs: name, howTo",
    "// -----",
    "const Game = {",
    '  name: "Pop",',
    "};",
    "// ---------- end of DEMO ----------",
    "$('gameName').textContent = Game.name;",
    "</script></body></html>",
])

GAME = "\n".join([
    "const Game = {",
    '  name: "Star Catch",',
    '  words: { en: { credits: "Made by Your Name with AI agents (Anthropic Claude)." } },',
    "};",
])

SKILL = "\n".join([
    "---", "name: x", "---", "# x",
    "1. Clone:", "   ```sh", "   git clone y", "   ```",
    "```js example-game",
    GAME,
    "```",
    "Text.",
    "```json example-steps",
    '{"viewports": [{"name": "phone", "width": 720, "height": 1280}], "steps": [{"wait": 1}]}',
    "```",
    "```sh",
    "echo untagged",
    "```",
    "",
])

HERE = os.path.dirname(os.path.abspath(__file__))
REAL_SKILL = os.path.join(HERE, "..", "..", "skills", "jamshell", "SKILL.md")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class ExtractTest(unittest.TestCase):
    def test_tagged_blocks_only(self):
        b = skillcheck.extract(SKILL)
        self.assertEqual(sorted(b), ["example-game", "example-steps"])
        self.assertTrue(b["example-game"].startswith("const Game = {"))
        self.assertEqual(json.loads(b["example-steps"])["steps"], [{"wait": 1}])

    def test_duplicate_tag_refused(self):
        with self.assertRaises(ValueError):
            skillcheck.extract(SKILL + "```js example-game\nconst Game = {};\n```\n")

    @unittest.skipUnless(os.path.exists(REAL_SKILL), "SKILL.md not next to the tool")
    def test_real_skill_has_both_blocks(self):
        md = read(REAL_SKILL)
        b = skillcheck.extract(md)
        self.assertIn("example-game", b)
        self.assertIn("example-steps", b)
        steps = json.loads(b["example-steps"])
        self.assertIn("selftest", steps)
        self.assertTrue(steps["steps"])
        game = b["example-game"]
        for member in ("name:", "howTo:", "start(", "update(", "draw(", "tests(", "words:"):
            self.assertIn(member, game)
        self.assertEqual(game.count("{") - game.count("}"), 0)
        credits = skillcheck.example_credits(game)
        # the playtest reads the credits strip back and must expect exactly the example's line
        self.assertIn(credits, [s.get("expect") for s in steps["steps"]])
        # the skill must no longer tell agents to edit the credits element by hand
        self.assertNotIn("Edit the `<div id=\"credits\">`", md)


class SpliceTest(unittest.TestCase):
    def test_replaces_only_the_game_object(self):
        out = skillcheck.splice(SHELL, GAME + "\n")
        self.assertIn('name: "Star Catch"', out)
        self.assertNotIn('name: "Pop"', out)
        self.assertIn("// DEMO (replace in a jam game)", out)
        self.assertIn("end of DEMO", out)
        self.assertIn("$('gameName').textContent = Game.name;", out)
        self.assertIn("const W = 720;", out)
        self.assertIn('data-say="credits"', out)
        self.assertEqual(out.count("const Game"), 1)

    def test_needs_markers(self):
        with self.assertRaises(ValueError):
            skillcheck.splice(SHELL.replace("end of DEMO", "end"), "const Game = {};")
        with self.assertRaises(ValueError):
            skillcheck.splice(SHELL, "let Thing = {};")


class CreditsTest(unittest.TestCase):
    def test_reads_words_en_credits(self):
        self.assertEqual(skillcheck.example_credits(GAME), "Made by Your Name with AI agents (Anthropic Claude).")

    def test_other_language_is_not_english(self):
        g = 'const Game = {\n  words: { fr: { credits: "Fait avec des agents d\'IA" } },\n};'
        with self.assertRaises(ValueError):
            skillcheck.example_credits(g)

    def test_needs_ai_words(self):
        with self.assertRaises(ValueError):
            skillcheck.example_credits('const Game = { words: { en: { credits: "Made by me" } } };')
        with self.assertRaises(ValueError):
            skillcheck.example_credits('const Game = { name: "x" };')


class BuildTest(unittest.TestCase):
    def test_build_writes_dist_and_steps(self):
        with tempfile.TemporaryDirectory() as d:
            skill, shell = os.path.join(d, "SKILL.md"), os.path.join(d, "shell.html")
            with open(skill, "w", encoding="utf-8") as f:
                f.write(SKILL)
            with open(shell, "w", encoding="utf-8") as f:
                f.write(SHELL)
            out = os.path.join(d, "out")
            s = skillcheck.build(skill, shell, out)
            self.assertEqual(s["viewports"], ["phone"])
            self.assertEqual(s["skillcheck"], skillcheck.VERSION)
            self.assertIn("with AI agents", s["credits"])
            html = read(os.path.join(out, "dist", "index.html"))
            self.assertIn("Star Catch", html)
            self.assertIn("Made by Your Name with AI agents", html)
            self.assertTrue(os.path.exists(os.path.join(out, "steps.json")))
            self.assertEqual(skillcheck.main(["build", "--skill", skill, "--shell", shell, "--out", out]), 0)
            self.assertEqual(skillcheck.main(["build", "--skill", shell, "--shell", shell, "--out", out]), 1)

    def test_build_refuses_game_without_credits(self):
        with tempfile.TemporaryDirectory() as d:
            skill, shell = os.path.join(d, "SKILL.md"), os.path.join(d, "shell.html")
            with open(skill, "w", encoding="utf-8") as f:
                f.write(SKILL.replace("credits:", "thanks:"))
            with open(shell, "w", encoding="utf-8") as f:
                f.write(SHELL)
            self.assertEqual(skillcheck.main(["build", "--skill", skill, "--shell", shell,
                                              "--out", os.path.join(d, "out")]), 1)


if __name__ == "__main__":
    unittest.main()
