"""Two test pages from jamshell 0.5.0's demo for langleak.py (Apache-2.0). MV2 of Munim, Inc., made with AI agents.

    python make_fixtures.py --shell shell.html --out DIR

leaky.html offers French and English but keeps the demo's English name, how-to and banners (langleak must flag
them in French); clean.html words them all through say() in both languages (langleak must pass it).
"""
import argparse
import os

OPT_IN = "addWords(Game.words);"
NAME = ('  name: "Pop", howTo: "Tap the bubbles before they float away. Gold stars are worth 3. '
        'Three misses and it\'s over.",')
GO = 'fx.banner("Go!", "pop the bubbles");'
LEVEL = 'fx.banner("Level " + (level + 2), "faster bubbles")'
WORDS = '''  words: {
    fr: { howTo: "Touchez les bulles avant qu'elles s'envolent. Les étoiles dorées valent 3. Trois ratés et c'est fini.",
          go: "C'est parti !", goSub: "éclate les bulles", level: "Niveau {0}", levelSub: "bulles plus rapides" },
    en: { howTo: "Tap the bubbles before they float away. Gold stars are worth 3. Three misses and it's over.",
          go: "Go!", goSub: "pop the bubbles", level: "Level {0}", levelSub: "faster bubbles" },
  },
  name: "Pop", get howTo() { return say("howTo"); },'''


def once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit("expected exactly one %r" % old)
    return text.replace(old, new)


def leaky(shell):
    return once(shell, OPT_IN, "Game.words = { fr: {}, en: {} };\n" + OPT_IN)


def clean(shell):
    text = once(shell, NAME, WORDS)
    text = once(text, GO, 'fx.banner(say("go"), say("goSub"));')
    return once(text, LEVEL, 'fx.banner(say("level", level + 2), say("levelSub"))')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shell", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    shell = open(a.shell, encoding="utf-8").read()
    os.makedirs(a.out, exist_ok=True)
    for name, make in (("leaky.html", leaky), ("clean.html", clean)):
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as f:
            f.write(make(shell))
    print("wrote leaky.html and clean.html to", a.out)


if __name__ == "__main__":
    main()
