"""Find words of the wrong language in a jamshell game (Apache-2.0). MV2 of Munim, Inc., made with AI agents.

    python langleak.py --html index.html --out DIR [--langs fr,en] [--allow WORD ...] [--seconds 8]

Plays the page in one Chromium per language (browser locale + ?lang=): title, play with taps, pause, game over.
In each scene it keeps the page's visible text and every string drawn on the canvas (fillText/strokeText are
recorded from before the page's own script runs), then flags strings that look like another language: a word
of the game's or shell's English that differs from its French, common English words in French, common French
words or accents in English. It also lists say() keys that fell back to English (a word missing in that
language) and Game.words keys missing from a language. Writes report.json and one screenshot per scene and
language; exits 1 if anything was flagged. Heuristic: LOOK at the screenshots too.
"""
import argparse
import functools
import http.server
import json
import os
import re
import shutil
import sys
import threading

# Words that are English and not also everyday French (so "score", "pause", "record", "bonus" are left out).
EN_WORDS = {
    "the", "and", "you", "your", "tap", "taps", "press", "hold", "release", "to", "of", "with", "best", "level",
    "play", "again", "game", "over", "go", "faster", "before", "they", "away", "are", "is", "it's", "worth",
    "misses", "time", "left", "right", "jump", "start", "win", "lose", "lives", "speed", "back", "title",
    "sound", "off", "resume", "paused", "made", "by", "drag", "swipe", "keep", "don't", "get", "until",
    "when", "while", "each", "every", "out", "up", "down", "new", "next", "ready", "wave", "round",
}
FR_WORDS = {
    "le", "la", "les", "des", "du", "une", "un", "vous", "touchez", "appuyez", "maintenez", "relâchez", "avec",
    "pour", "partie", "jouer", "rejouer", "niveau", "vies", "temps", "et", "est", "pas", "sur", "dans", "chaque",
    "glissez", "terminée", "reprendre", "retour", "titre", "son", "record", "vague", "prêt", "encore", "avant",
}
ACCENTS = re.compile(r"[éèêëàâçùûôîïœ]", re.I)
WORD = re.compile(r"[A-Za-zÀ-ÿœŒ']+")

RECORD_CANVAS = """
window.__texts = new Set();
for (const P of [CanvasRenderingContext2D.prototype, (window.OffscreenCanvasRenderingContext2D || {}).prototype]) {
  if (!P) continue;
  for (const m of ["fillText", "strokeText"]) {
    const orig = P[m];
    P[m] = function (t, ...rest) { try { window.__texts.add(String(t)); } catch (e) {} return orig.call(this, t, ...rest); };
  }
}
"""
WRAP_SAY = """() => {
  window.__fallbacks = new Set();
  try {
    if (typeof say !== "function" || typeof LANGS !== "object") return false;
    const inner = say;
    say = function (key, ...v) {
      if (lang !== "en" && !(LANGS[lang] && key in LANGS[lang])) window.__fallbacks.add(String(key));
      return inner(key, ...v);
    };
    setLang(lang);
    return true;
  } catch (e) { return false; }
}"""
WORDS = """() => {
  const w = (typeof Game === "object" && Game.words) || null;
  return {words: w, offered: typeof offered === "object" ? offered : null, lang: typeof lang === "string" ? lang : null,
          html: document.documentElement.lang, title: document.title,
          name: typeof Game === "object" ? String(Game.name) : "", shellEn: typeof LANGS === "object" ? LANGS.en : {},
          shellFr: typeof LANGS === "object" ? LANGS.fr : {},
          langNames: typeof LANGS === "object" ? Object.values(LANGS).map(d => d.lang).filter(Boolean) : []};
}"""
TAKE = """() => {
  const canvas = Array.from(window.__texts || []); window.__texts = new Set();
  return {dom: document.body.innerText, canvas, fallbacks: Array.from(window.__fallbacks || [])};
}"""


def tokens(text):
    return [w.lower().strip("'") for w in WORD.findall(text)]


def other_language_words(text, lang, en_only=frozenset(), allow=frozenset()):
    """Words in text that look like another language than lang ("fr" or "en")."""
    found = []
    words = [w for w in tokens(text) if w and w not in allow]
    if lang == "fr":
        found += [w for w in words if w in EN_WORDS]
        low = text.lower()
        found += [p for p in en_only if p and re.search(r"(?<![\w'])" + re.escape(p) + r"(?![\w'])", low)]
    elif lang == "en":
        found += [w for w in words if w in FR_WORDS]
        found += [w for w in words if ACCENTS.search(w)]
    return sorted(set(found))


def english_only_phrases(words_en, words_fr):
    """Lowercased English values (shell's and game's) whose French differs: seeing one in French is a leak."""
    out = set()
    for key, value in (words_en or {}).items():
        fr = (words_fr or {}).get(key)
        if key == "lang" or not isinstance(value, str) or fr == value:  # "lang" names the switch button's language
            continue
        plain = re.sub(r"\{\d+\}", "", value).strip(" :.!·").lower()
        if len(plain) >= 4 and not plain.isdigit():
            out.add(plain)
    return out


def missing_keys(words):
    """{lang: [keys present in another language but missing in this one]} for a Game.words object."""
    if not words:
        return {}
    every = set().union(*[set(v) for v in words.values() if isinstance(v, dict)])
    return {L: sorted(every - set(v)) for L, v in words.items() if isinstance(v, dict) and every - set(v)}


def lines(text):
    return [s.strip() for s in str(text).splitlines() if s.strip()]


def serve(root):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def run(html, out, langs, allow, seconds):
    os.makedirs(out, exist_ok=True)
    root = os.path.join(out, "site")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    shutil.copy(html, os.path.join(root, "index.html"))
    open(os.path.join(root, "favicon.ico"), "wb").close()
    srv, base = serve(root)
    report = {"ok": False, "flags": [], "errors": [], "scenes": {}, "missing_words": {}, "files": []}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for L in langs:
            ctx = browser.new_context(locale={"fr": "fr-FR", "en": "en-US"}.get(L, L),
                                      viewport={"width": 450, "height": 800})
            ctx.add_init_script(RECORD_CANVAS)
            page = ctx.new_page()
            page.on("pageerror", lambda e, L=L: report["errors"].append("%s pageerror: %s" % (L, e)))
            page.goto(base + "/index.html?lang=" + L)
            page.wait_for_timeout(800)
            info = page.evaluate(WORDS)
            if not page.evaluate(WRAP_SAY):
                report["errors"].append("%s: not a jamshell 0.5 page (no say/LANGS)" % L)
            page.wait_for_timeout(300)
            if info["lang"] != L or info["html"] != L:
                report["flags"].append("%s: page language is %s (html lang %s)" % (L, info["lang"], info["html"]))
            words = info["words"] or {}
            report["missing_words"] = missing_keys(words)
            en_only = english_only_phrases(dict(info["shellEn"], **(words.get("en") or {})),
                                           dict(info["shellFr"], **(words.get("fr") or {})))
            name_ok = set(tokens(info["name"])) | set(allow)
            scenes = {}

            def take(scene):
                got = page.evaluate(TAKE)
                shot = "%s-%s.png" % (L, scene)
                page.screenshot(path=os.path.join(out, shot))
                report["files"].append(shot)
                texts = lines(got["dom"]) + [t for t in got["canvas"] if t.strip()]
                flagged = {}
                for t in sorted(set(texts) - set(info["langNames"])):  # the switch button names another language
                    bad = other_language_words(t, L, en_only if L == "fr" else frozenset(), frozenset(name_ok))
                    if bad:
                        flagged[t] = bad
                scenes[scene] = {"texts": sorted(set(texts)), "flagged": flagged, "fallbacks": got["fallbacks"]}
                for t, bad in flagged.items():
                    report["flags"].append("%s %s: %r looks like another language (%s)" % (L, scene, t, ", ".join(bad)))
                for k in got["fallbacks"]:
                    report["flags"].append("%s %s: say(%r) has no %s word and fell back" % (L, scene, k, L))

            take("title")
            page.click("#playBtn")
            page.wait_for_timeout(400)
            box = page.locator("canvas").first.bounding_box() or {"x": 0, "y": 0, "width": 450, "height": 800}
            for i in range(max(1, int(seconds * 4))):
                fx_, fy_ = ((i * 37) % 80 + 10) / 100.0, ((i * 53) % 70 + 20) / 100.0
                page.mouse.click(box["x"] + box["width"] * fx_, box["y"] + box["height"] * fy_)
                page.wait_for_timeout(250)
                if page.evaluate("typeof scene === 'string' ? scene : ''") == "over":
                    break
            take("play")
            if page.evaluate("typeof scene === 'string' ? scene : ''") == "play":
                try:
                    page.click("#pauseBtn", timeout=3000)
                    page.wait_for_timeout(300)
                    take("paused")
                    page.click("#resumeBtn", timeout=3000)
                    page.wait_for_timeout(200)
                except Exception as e:  # a game may hide the pause button; the other scenes still count
                    report["errors"].append("%s: pause/resume failed: %s" % (L, str(e).splitlines()[0]))
                page.evaluate("Game.over = true")
                page.wait_for_timeout(800)
            take("over")
            report["scenes"][L] = {"info": {k: info[k] for k in ("lang", "html", "title", "name", "offered")},
                                   **scenes}
            ctx.close()
        browser.close()
    srv.shutdown()
    for L, keys in report["missing_words"].items():
        report["flags"].append("Game.words.%s lacks %s" % (L, ", ".join(keys)))
    report["ok"] = not report["flags"] and not report["errors"]
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--langs", default="fr,en")
    ap.add_argument("--allow", action="append", default=[], help="a word never flagged (a name, say)")
    ap.add_argument("--seconds", type=float, default=8)
    a = ap.parse_args()
    report = run(a.html, a.out, [s.strip() for s in a.langs.split(",") if s.strip()],
                 [w.lower() for w in a.allow], a.seconds)
    print(json.dumps({k: report[k] for k in ("ok", "flags", "errors", "missing_words", "files")},
                     indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
