# Static checks for kits/platform.js (jamshell platform kit). Stdlib only.
# The behaviour tests are kits/platform.test.cjs (run with: node --test kits/).
# Made by MV2 of Munim, Inc. with AI agents (Anthropic Claude). Licence: Apache-2.0.
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _find(name, subdirs):
    for sub in subdirs:
        path = os.path.join(HERE, *sub, name) if sub else os.path.join(HERE, name)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(name)


KIT = _find("platform.js", [("kits",), ()])
DEMO_CANDIDATES = [("examples",), ()]


class PlatformKitStatic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(KIT, encoding="utf-8") as f:
            cls.src = f.read()

    def test_header_licence_and_credit(self):
        head = self.src[:800]
        self.assertIn("Apache-2.0", head)
        self.assertIn("with AI agents", head)
        self.assertIn("MV2 of Munim, Inc.", head)

    def test_version_matches_header(self):
        m = re.search(r'var VERSION = "(\d+\.\d+\.\d+)"', self.src)
        self.assertIsNotNone(m)
        self.assertIn("platform kit " + m.group(1), self.src[:200])

    def test_no_network_or_eval(self):
        for bad in ("fetch(", "XMLHttpRequest", "WebSocket", "import(", "eval(", "new Function"):
            self.assertNotIn(bad, self.src, bad)
        # the only URL allowed is the repo link in the header comment
        urls = re.findall(r"https?://[^\s\"')]+", self.src)
        self.assertEqual(urls, ["https://github.com/munimtechnologies/jamshell"])

    def test_exports(self):
        m = re.search(r"return \{\s*VERSION:(.*?)\};\s*\}\);\s*$", self.src, re.S)
        self.assertIsNotNone(m, "export block at the end")
        block = m.group(1)
        for name in ("world", "body", "step", "resize", "setGravity", "ticker", "recorder",
                     "replayer", "snap", "restore", "history", "follow", "drawTiles", "overlaps"):
            self.assertRegex(block, r"\b%s: %s\b" % (name, name), name)

    def test_brackets_balance(self):
        # crude but useful: strip strings and comments, then count brackets
        s = re.sub(r"/\*.*?\*/", "", self.src, flags=re.S)
        s = re.sub(r"//[^\n]*", "", s)
        s = re.sub(r'"(?:\\.|[^"\\])*"', '""', s)
        for o, c in ("()", "[]", "{}"):
            self.assertEqual(s.count(o), s.count(c), o + c)

    def test_umd_wrapper(self):
        self.assertIn('typeof module === "object" && module.exports', self.src)
        self.assertIn("root.Platform = api", self.src)

    def test_demo_page_if_present(self):
        demo = None
        for sub in DEMO_CANDIDATES:
            p = os.path.join(HERE, *sub, "platform.html") if sub else os.path.join(HERE, "platform.html")
            if os.path.exists(p):
                demo = p
                break
        if demo is None:
            self.skipTest("demo page not shipped with this test")
        with open(demo, encoding="utf-8") as f:
            html = f.read()
        self.assertIn('src="../kits/platform.js"', html)
        self.assertIn("with AI agents", html)
        self.assertIn("Apache-2.0", html)
        self.assertNotRegex(html, r"<script[^>]+src=\"https?:")


if __name__ == "__main__":
    unittest.main(verbosity=2)
