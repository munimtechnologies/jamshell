"""Package a browser game for an itch.io jam upload, refusing what must not ship (Apache-2.0).
By MV2 of Munim, Inc., made with AI agents (Anthropic Claude).

    python3 package.py --dist dist --zip /out/game-itch.zip --credits "made with AI agents" [--forbid FILE]

dist/ must hold index.html at its top level (itch.io serves that file). The zip keeps dist's layout with
index.html at the zip's top level. The run fails if any text file in dist carries a string listed in a
--forbid file (one per line, optionally "text<TAB>reason"; lines starting with # are skipped; keep that
file private and out of every download), loads anything from the network (a jam build must run offline
from its own files), lacks the AI-disclosure credits text, or breaks itch.io's limits (1,000 files;
200 MB per file; 500 MB unpacked). Writes package.json next to the zip.
"""
import argparse
import json
import os
import re
import sys
import zipfile

TEXT_EXT = {".html", ".htm", ".js", ".mjs", ".css", ".json", ".txt", ".md", ".svg"}
# a resource the browser would fetch from another host: src=, <link href=>, CSS url(), fetch()/import()/from.
# A plain <a href> link is fine: it only opens when a player clicks it.
REMOTE = r"""["'`]?(?:https?:)?//"""
NETWORK = re.compile("|".join([
    r"\bsrc\s*=\s*" + REMOTE,
    r"<link\b[^>]*\bhref\s*=\s*" + REMOTE,
    r"url\(\s*" + REMOTE,
    r"""\b(?:fetch|import)\s*\(\s*["'`](?:https?:)?//""",
    r"""\bfrom\s+["'](?:https?:)?//""",
]), re.I)
MAX_FILES, MAX_FILE, MAX_TOTAL = 1000, 200 * 2**20, 500 * 2**20


def load_forbidden(paths):
    """(text, reason) pairs from --forbid files. The reasons, not the texts, go into the report."""
    pairs = []
    for path in paths or []:
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.rstrip("\r\n")
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                text, _, why = line.partition("\t")
                pairs.append((text.strip(), why.strip() or "forbidden text (line %d)" % n))
    return [(t, w) for t, w in pairs if t]


def network_loads(text):
    """Snippets of text that would make the browser fetch something from another host."""
    return [text[max(0, m.start() - 20):m.end() + 40] for m in NETWORK.finditer(text)]


def check_dist(dist, credits, forbidden=()):
    problems, files, total = [], [], 0
    if not os.path.isfile(os.path.join(dist, "index.html")):
        problems.append("dist has no top-level index.html")
    found_credits = False
    for root, _, names in os.walk(dist):
        for n in names:
            path = os.path.join(root, n)
            rel = os.path.relpath(path, dist).replace(os.sep, "/")
            size = os.path.getsize(path)
            files.append(rel)
            total += size
            if size > MAX_FILE:
                problems.append("%s is larger than 200 MB" % rel)
            if os.path.splitext(n)[1].lower() not in TEXT_EXT:
                continue
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            low = text.lower()
            problems += ["%s: %s" % (rel, why) for needle, why in forbidden if needle.lower() in low]
            problems += ["%s loads from the network: %s" % (rel, s.strip()) for s in network_loads(text)]
            found_credits = found_credits or (credits.lower() in low)
    if not found_credits:
        problems.append("no file contains the credits text %r" % credits)
    if len(files) > MAX_FILES:
        problems.append("%d files; itch.io allows 1,000" % len(files))
    if total > MAX_TOTAL:
        problems.append("%d bytes unpacked; itch.io allows 500 MB" % total)
    return problems, sorted(files), total


def build_zip(dist, zip_path, files):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(os.path.join(dist, rel), rel)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True)
    ap.add_argument("--zip", required=True)
    ap.add_argument("--credits", required=True, help="AI-disclosure text the game must show")
    ap.add_argument("--forbid", action="append", default=[],
                    help="private file of texts that must not ship (repeatable)")
    a = ap.parse_args()
    forbidden = load_forbidden(a.forbid)
    problems, files, total = check_dist(a.dist, a.credits, forbidden)
    report = {"ok": not problems, "problems": problems, "files": files, "unpacked_bytes": total,
              "forbidden_checked": len(forbidden)}
    if not problems:
        os.makedirs(os.path.dirname(os.path.abspath(a.zip)), exist_ok=True)
        build_zip(a.dist, a.zip, files)
        with zipfile.ZipFile(a.zip) as z:
            report["zip_names"] = z.namelist()
        report["zip_bytes"] = os.path.getsize(a.zip)
    out = os.path.splitext(a.zip)[0] + ".package.json"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
