# skillcheck.py 0.2.0 - checks that the example code in skills/jamshell/SKILL.md really works with jamshell.
# Part of jamshell by MV2 of Munim, Inc. (mv2@munimtech.com), made with AI agents. Apache-2.0.
#
# build: reads the fenced blocks tagged "example-game" (```js example-game) and "example-steps"
# (```json example-steps) from SKILL.md, splices the game object into a copy of shell.html in place of the
# DEMO game object (exactly as the skill tells an agent to), and writes <out>/dist/index.html and
# <out>/steps.json. The real checks are then jamshell's own tools: index.html#selftest, playcheck.py with
# the steps, and package.py.
#
# 0.2.0: the maker's credits now come from the example game's words.en.credits, as the skill says. 0.1.0
# rewrote the <div id="credits"> element instead; that never matched jamshell 0.5's element (it carries
# data-say="credits"), and in 0.5 the shell overwrites that element's text from its word table on load.
#
#   python skillcheck.py build --skill skills/jamshell/SKILL.md --shell shell.html --out /tmp/skillcheck
import argparse
import json
import os
import re
import sys

VERSION = "0.2.0"
FENCE = re.compile(r"^```([A-Za-z0-9_+-]*)[ \t]+([A-Za-z0-9_-]+)[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
DEMO_LINE = "// DEMO (replace in a jam game)"
END_LINE = "end of DEMO"
# words: { en: { credits: "..." } } in the example game object
CREDITS_WORD = re.compile(r'\ben\s*:\s*\{[^{}]*\bcredits\s*:\s*"([^"\\]*)"')


def extract(md):
    """Tagged fenced blocks of a Markdown text, as {tag: code}. A tag may appear only once."""
    blocks = {}
    for m in FENCE.finditer(md):
        tag = m.group(2)
        if tag in blocks:
            raise ValueError("block %r appears more than once" % tag)
        blocks[tag] = m.group(3)
    return blocks


def splice(shell, game_js):
    """shell.html with its DEMO game object replaced by game_js (the DEMO comment and end marker stay)."""
    lines = shell.split("\n")
    demo = [i for i, l in enumerate(lines) if DEMO_LINE in l]
    end = [i for i, l in enumerate(lines) if END_LINE in l]
    if len(demo) != 1 or len(end) != 1:
        raise ValueError("expected one DEMO line and one end-of-DEMO line, found %d and %d" % (len(demo), len(end)))
    starts = [i for i in range(demo[0], end[0]) if lines[i].startswith("const Game")]
    if len(starts) != 1:
        raise ValueError("expected one 'const Game' line inside the DEMO block, found %d" % len(starts))
    if "const Game =" not in game_js:
        raise ValueError("the example does not define const Game")
    new = lines[:starts[0]] + game_js.rstrip("\n").split("\n") + lines[end[0]:]
    return "\n".join(new)


def example_credits(game_js):
    """The English credits line the example game sets in words.en.credits; it must say 'with AI agents'."""
    m = CREDITS_WORD.search(game_js)
    if not m:
        raise ValueError("the example game sets no words.en.credits")
    if "with AI agents" not in m.group(1):
        raise ValueError("the example's credits must keep the words 'with AI agents'")
    return m.group(1)


def build(skill_path, shell_path, out_dir):
    with open(skill_path, encoding="utf-8") as f:
        blocks = extract(f.read())
    missing = [t for t in ("example-game", "example-steps") if t not in blocks]
    if missing:
        raise ValueError("SKILL.md lacks blocks: %s" % ", ".join(missing))
    steps = json.loads(blocks["example-steps"])
    credits = example_credits(blocks["example-game"])
    with open(shell_path, encoding="utf-8") as f:
        html = splice(f.read(), blocks["example-game"])
    dist = os.path.join(out_dir, "dist")
    os.makedirs(dist, exist_ok=True)
    with open(os.path.join(dist, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    with open(os.path.join(out_dir, "steps.json"), "w", encoding="utf-8") as f:
        json.dump(steps, f, indent=2)
    summary = {"skillcheck": VERSION, "blocks": sorted(blocks), "game_lines": blocks["example-game"].count("\n"),
               "credits": credits, "steps": len(steps.get("steps", [])),
               "viewports": [v["name"] for v in steps["viewports"]], "index_bytes": len(html.encode("utf-8"))}
    with open(os.path.join(out_dir, "build.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--skill", required=True)
    b.add_argument("--shell", required=True)
    b.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try:
        print(json.dumps(build(a.skill, a.shell, a.out), indent=2))
    except (ValueError, OSError) as e:
        print("skillcheck build failed: %s" % e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
