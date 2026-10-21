"""Tests for package.py (Apache-2.0). By MV2 of Munim, Inc., made with AI agents (Anthropic Claude).

    python -m unittest -v test_package.py

Set FORBID_FILE to a private --forbid file to also check that no file shipped from this folder carries
any of its texts.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

import package

HERE = os.path.dirname(os.path.abspath(__file__))
SHIPPED = ["package.py", "test_package.py"]
GAME = "<!doctype html><title>t</title><p>Made by MV2 of Munim, Inc. with AI agents</p>"


def make_dist(root, html=GAME, extra=None):
    dist = os.path.join(root, "dist")
    os.makedirs(dist)
    with open(os.path.join(dist, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    for name, text in (extra or {}).items():
        with open(os.path.join(dist, name), "w", encoding="utf-8") as f:
            f.write(text)
    return dist


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


class Forbidden(unittest.TestCase):
    def test_parses_reasons_comments_and_blanks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(os.path.join(tmp, "f.txt"), "# private\n\nAlpha Lane\tstreet\nbeta@example.org\n  \n")
            self.assertEqual(package.load_forbidden([path]),
                             [("Alpha Lane", "street"), ("beta@example.org", "forbidden text (line 4)")])

    def test_no_files_means_nothing_forbidden(self):
        self.assertEqual(package.load_forbidden([]), [])
        self.assertEqual(package.load_forbidden(None), [])

    def test_flags_any_case_and_reports_reason_not_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = make_dist(tmp, extra={"notes.txt": "see ALPHA LANE"})
            problems, _, _ = package.check_dist(dist, "with AI agents", [("Alpha Lane", "street")])
            self.assertEqual(problems, ["notes.txt: street"])
            self.assertNotIn("Alpha", " ".join(problems))

    def test_binary_files_are_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = make_dist(tmp, extra={"pic.png": "Alpha Lane"})
            problems, files, _ = package.check_dist(dist, "with AI agents", [("Alpha Lane", "street")])
            self.assertEqual(problems, [])
            self.assertEqual(files, ["index.html", "pic.png"])


class CheckDist(unittest.TestCase):
    def test_old_two_argument_call_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems, files, total = package.check_dist(make_dist(tmp), "with AI agents")
            self.assertEqual((problems, files), ([], ["index.html"]))
            self.assertEqual(total, len(GAME.encode("utf-8")))

    def test_needs_index_and_credits(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = make_dist(tmp, html="<p>no credits here</p>")
            os.rename(os.path.join(dist, "index.html"), os.path.join(dist, "game.html"))
            problems, _, _ = package.check_dist(dist, "with AI agents")
            self.assertIn("dist has no top-level index.html", problems)
            self.assertIn("no file contains the credits text 'with AI agents'", problems)

    def test_network_loads_fail_but_plain_links_pass(self):
        self.assertTrue(package.network_loads('<script src="https://cdn.example.com/x.js"></script>'))
        self.assertTrue(package.network_loads("fetch('//api.example.com/a')"))
        self.assertTrue(package.network_loads("body{background:url(https://x.example/a.png)}"))
        self.assertEqual(package.network_loads('<a href="https://munimv2.itch.io/jamshell">jamshell</a>'), [])


class Main(unittest.TestCase):
    def test_zip_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = make_dist(tmp)
            forbid = write(os.path.join(tmp, "f.txt"), "Alpha Lane\tstreet\n")
            out = os.path.join(tmp, "out", "game-itch.zip")
            r = subprocess.run([sys.executable, os.path.join(HERE, "package.py"), "--dist", dist, "--zip", out,
                                "--credits", "with AI agents", "--forbid", forbid],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            with zipfile.ZipFile(out) as z:
                self.assertEqual(z.namelist(), ["index.html"])
            with open(os.path.join(tmp, "out", "game-itch.package.json"), encoding="utf-8") as f:
                report = json.load(f)
            self.assertTrue(report["ok"])
            self.assertEqual(report["forbidden_checked"], 1)

    def test_forbidden_text_stops_the_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = make_dist(tmp, html=GAME + "<p>Alpha Lane</p>")
            forbid = write(os.path.join(tmp, "f.txt"), "Alpha Lane\tstreet\n")
            out = os.path.join(tmp, "game-itch.zip")
            r = subprocess.run([sys.executable, os.path.join(HERE, "package.py"), "--dist", dist, "--zip", out,
                                "--credits", "with AI agents", "--forbid", forbid],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertFalse(os.path.exists(out))
            self.assertNotIn("Alpha", r.stdout)


class ShippedFilesAreClean(unittest.TestCase):
    def test_no_private_email_in_shipped_files(self):
        for name in SHIPPED:
            with open(os.path.join(HERE, name), encoding="utf-8") as f:
                self.assertNotIn("@" + "gmail.", f.read().lower(), name)

    @unittest.skipUnless(os.environ.get("FORBID_FILE"), "FORBID_FILE not set")
    def test_no_forbidden_text_in_shipped_files(self):
        forbidden = package.load_forbidden([os.environ["FORBID_FILE"]])
        self.assertTrue(forbidden)
        for name in SHIPPED:
            with open(os.path.join(HERE, name), encoding="utf-8") as f:
                low = f.read().lower()
            hits = [why for text, why in forbidden if text.lower() in low]
            self.assertEqual(hits, [], name)


if __name__ == "__main__":
    unittest.main()
