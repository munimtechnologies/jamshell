# Tests for jamshell (no browser needed; playcheck covers the browser). MV2 of Munim, Inc. Apache-2.0.
import json
import os
import re
import shutil
import tempfile
import unittest

import package
import playcheck

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = open(os.path.join(HERE, "shell.html"), encoding="utf-8").read()


def shade(hex_, k):
    """Python twin of paint.shade, so the expected values in steps.json are checked twice."""
    h = hex_.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    t = max(-1.0, min(1.0, k))
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    out = [v * (1 + t) if t < 0 else v + (255 - v) * t for v in rgb]
    # JavaScript's Math.round rounds halves up
    return "#" + "".join("%02x" % max(0, min(255, int(v + 0.5))) for v in out) + (h[6:] if len(h) == 8 else "")


class ShellTests(unittest.TestCase):
    def test_steps_are_valid(self):
        spec = json.load(open(os.path.join(HERE, "steps.json"), encoding="utf-8"))
        self.assertEqual(playcheck.check_steps(spec), [])
        self.assertEqual([v["name"] for v in spec["viewports"]], ["desktop", "phone", "small", "calm"])

    def test_reduced_motion_viewport_option(self):
        calm = playcheck.context_options({"name": "c", "width": 720, "height": 1280, "touch": True,
                                          "reduced_motion": True})
        self.assertEqual(calm["reduced_motion"], "reduce")
        self.assertTrue(calm["has_touch"])
        plain = playcheck.context_options({"name": "d", "width": 1280, "height": 720})
        self.assertEqual(plain["reduced_motion"], "no-preference")
        self.assertFalse(plain["is_mobile"])

    def test_drag_steps_are_checked(self):
        vps = [{"name": "phone", "width": 720, "height": 1280}]
        good = {"viewports": vps, "steps": [{"drag": [0.5, 0.75, 0.75, 0.75], "probe": "stick.x", "expect": 1}]}
        self.assertEqual(playcheck.check_steps(good), [])
        short = {"viewports": vps, "steps": [{"drag": [0.5, 0.75, 0.75]}]}
        self.assertEqual(len(playcheck.check_steps(short)), 1)
        outside = {"viewports": vps, "steps": [{"drag": [0.5, 0.75, 1.5, 0.75]}]}
        self.assertEqual(len(playcheck.check_steps(outside)), 1)
        stray = {"viewports": vps, "steps": [{"eval": "1", "probe": "2"}]}
        self.assertEqual(len(playcheck.check_steps(stray)), 1)
        (x0, y0), (x1, y1) = playcheck.drag_points([0.5, 0.75, 0.75, 0.75], vps[0])
        self.assertEqual((x0, y0, x1, y1), (360, 960, 540, 960))

    def test_steps_exercise_the_action_kit(self):
        spec = json.load(open(os.path.join(HERE, "steps.json"), encoding="utf-8"))
        saves = {s.get("save") for s in spec["steps"]}
        for name in ("stick_full_right", "stick_released", "picked_card", "stick_full_right_letterboxed", "key_picked"):
            self.assertIn(name, saves)
        # the phone drag must be long enough to tilt the stick fully (R = 110 stage px at scale 1)
        drag = next(s for s in spec["steps"] if s.get("save") == "stick_full_right")
        (x0, _), (x1, _) = playcheck.drag_points(drag["drag"], {"width": 720, "height": 1280})
        self.assertGreater(x1 - x0, 110)
        # the desktop drag ends inside the letterboxed stage (1280x720 -> stage from 437.5 to 842.5 px)
        drag = next(s for s in spec["steps"] if s.get("save") == "stick_full_right_letterboxed")
        (x0, _), (x1, _) = playcheck.drag_points(drag["drag"], {"width": 1280, "height": 720})
        self.assertTrue(437.5 < x0 < x1 < 842.5)
        self.assertGreater((x1 - x0) / 0.5625, 110)

    def test_steps_exercise_the_look_kit(self):
        spec = json.load(open(os.path.join(HERE, "steps.json"), encoding="utf-8"))
        by_save = {s.get("save"): s for s in spec["steps"] if s.get("save")}
        for name in ("banner_on_start", "colour_maths", "star_pinned", "banner_gone"):
            self.assertIn(name, by_save)
        self.assertEqual(by_save["colour_maths"]["expect"],
                         " ".join([shade("#808080", -1), shade("#808080", 1), "#808080"]))
        shots = [s["shot"] for s in spec["steps"] if "shot" in s]
        self.assertIn("banner", shots)
        # the banner check comes before the long wait, the "gone" check after it (a banner lasts 1.6 s)
        order = [s.get("save") or ("wait%d" % s["wait"] if "wait" in s else "") for s in spec["steps"]]
        self.assertLess(order.index("banner_on_start"), order.index("wait2500"))
        self.assertLess(order.index("wait2500"), order.index("banner_gone"))

    def test_python_shade_matches_the_selftest_values(self):
        # the same cases the in-page selftest checks, so the two implementations agree
        self.assertEqual(shade("#808080", -1), "#000000")
        self.assertEqual(shade("#808080", 1), "#ffffff")
        self.assertEqual(shade("#4cc9f0", 0), "#4cc9f0")
        self.assertEqual(shade("#fff", -0.5), "#808080")
        self.assertEqual(shade("#ffffff80", -1), "#00000080")
        self.assertEqual(shade("#123456", -5), "#000000")

    def test_look_kit_is_in_the_shell(self):
        start = SHELL.index("// DEMO (replace in a jam game)")
        shell = SHELL[:start]
        for name in ("function hexParts(", "function hexOf(", "function shapePoints(", "function makeBackdrop(",
                     "shade(hex, k) {", "mix(a, b, t) {", "sticker(c, kind,", "backdrop(c, bd,", "vignette(c,",
                     "banner(title,"):
            self.assertIn(name, shell)
        # reduced motion: banners fade in place and the hills stand still
        self.assertIn("const dx = this.calm ? 0 :", shell)
        self.assertIn("const moved = fx.calm ? 0 : scroll;", shell)
        # banners are cleared with everything else and age only while the game runs
        self.assertIn("this.banners = [];", shell)
        self.assertIn("for (const b of this.banners) b.life -= dt;", shell)

    def test_shell_packages_clean(self):
        with tempfile.TemporaryDirectory() as d:
            dist = os.path.join(d, "dist")
            os.makedirs(dist)
            shutil.copy(os.path.join(HERE, "shell.html"), os.path.join(dist, "index.html"))
            problems, files, _ = package.check_dist(dist, "with AI agents")
            self.assertEqual(problems, [])
            self.assertEqual(files, ["index.html"])

    def test_sound_waits_for_a_gesture(self):
        # the only AudioContext is made inside sound.unlock(), which only input handlers and buttons call
        self.assertNotIn("new AudioContext", SHELL)
        self.assertEqual(SHELL.count("new AC()"), 1)
        unlock = SHELL.index("unlock() {")
        self.assertLess(unlock, SHELL.index("new AC()"))
        self.assertLess(SHELL.index("new AC()"), SHELL.index("tone(f,"))

    def test_music_starts_only_from_play(self):
        # music.play is only called inside start(), which only the Play buttons call
        begin, finish = SHELL.index("function start(at) {"), SHELL.index("function pause()")
        calls = [m.start() for m in re.finditer(r"music\.play\(", SHELL)]
        self.assertEqual(len(calls), 1)
        self.assertTrue(begin < calls[0] < finish)
        # and it never makes its own AudioContext
        music = SHELL[SHELL.index("const music = {"):SHELL.index("const ease = {")]
        self.assertIn("const ac = sound.ac", music)
        self.assertNotIn("AudioContext", music)
        self.assertIn('scene === "paused"', music)

    def test_demo_block_is_marked_and_replaceable(self):
        start = SHELL.index("// DEMO (replace in a jam game)")
        end = SHELL.index("end of DEMO")
        demo = SHELL[start:end]
        for member in ("name:", "howTo:", "score:", "over:", "start(", "update(", "draw(", "tests("):
            self.assertIn(member, demo)
        # the shell outside the demo never reaches into the demo's own fields
        outside = SHELL[:start] + SHELL[end:]
        for field in ("bubbles", "misses", "lastTap"):
            self.assertNotIn(field, outside)

    def test_juice_kit_is_in_the_shell(self):
        start = SHELL.index("// DEMO (replace in a jam game)")
        shell = SHELL[:start]
        for name in ("const ease = {", "function tween(", "function stepTweens(", "const fx = {",
                     "const paint = {", "const palettes = {", "const music = {"):
            self.assertIn(name, shell)
        for k in ("linear", "inQuad", "outQuad", "inOutQuad", "outCubic", "outBack", "outElastic", "outBounce"):
            self.assertRegex(shell, r"\b%s: t =>" % k)

    def test_action_kit_is_in_the_shell(self):
        start = SHELL.index("// DEMO (replace in a jam game)")
        shell = SHELL[:start]
        for name in ("const held = new Set()", "const stick = {", "function axis()", "function hit(",
                     "function nearest(", "const clamp =", "function choose(", "function pick("):
            self.assertIn(name, shell)
        # the stick only turns on when the game asks for it, and every way a press can end lets it go
        self.assertIn("if (Game.stick) {", shell)
        self.assertIn("setPointerCapture", shell)
        self.assertRegex(shell, r'addEventListener\("pointerup", e => \{\s*sound\.unlock\(\); stick\.end\(\);')
        self.assertIn('addEventListener("pointercancel", () => { down = null; stick.end(); });', shell)
        self.assertIn('addEventListener("blur", () => { held.clear(); stick.end(); });', shell)
        self.assertIn('addEventListener("keyup"', shell)

    def test_card_screen_freezes_the_game(self):
        self.assertIn('<div id="choose" class="layer hidden"', SHELL)
        self.assertIn('for (const id of ["title", "paused", "over", "choose", "levels"])', SHELL)
        frame = SHELL[SHELL.index("function frame(t) {"):]
        frame = frame[:frame.index("requestAnimationFrame(frame);")]
        # Game.update runs only in play, and tweens and sparks stand still behind the cards
        self.assertIn('if (scene === "play") { Game.update(dt);', frame)
        self.assertIn('scene !== "choose"', frame)
        # card labels are text, never HTML from the game
        choose = SHELL[SHELL.index("function choose("):SHELL.index("function pick(")]
        self.assertNotIn("innerHTML", choose)
        self.assertIn("options.slice(0, 4)", choose)
        card_css = SHELL[SHELL.index(".btn.card {"):]
        self.assertGreaterEqual(int(re.search(r"min-height:\s*(\d+)px", card_css).group(1)), 88)

    def test_reduced_motion_is_respected(self):
        self.assertIn('prefers-reduced-motion: reduce', SHELL)
        self.assertIn("if (!this.calm) this.shakeAmp", SHELL)

    def test_credits_strip(self):
        self.assertIn("const SAFE_BOTTOM = 96;", SHELL)
        css = SHELL[SHELL.index("#credits {"):]
        css = css[:css.index("}")]
        self.assertIn("background:", css)
        self.assertIn("pointer-events: none", css)

    def test_version_is_consistent(self):
        self.assertIn('const VERSION = "0.7.0";', SHELL)
        self.assertIn("jamshell 0.7.0:", SHELL)
        readme = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
        self.assertIn("0.7.0", readme)

    def test_portrait_stage_and_touch(self):
        self.assertIn("{ w: 720, h: 1280, landscape: false }", SHELL)
        self.assertIn("touch-action: none", SHELL)
        self.assertRegex(SHELL, r'name="viewport" content="width=device-width')

    def test_buttons_are_big_enough_to_tap(self):
        # 88 logical px at the smallest scale we test (390 wide: x0.54) is about 48 CSS px, the usual minimum
        sizes = [int(n) for n in re.findall(r"min-height:\s*(\d+)px", SHELL)]
        self.assertTrue(sizes)
        self.assertGreaterEqual(min(sizes), 88)

    def test_credits_and_licence(self):
        self.assertIn("Made by MV2 of Munim, Inc. with AI agents (Anthropic Claude)", SHELL)
        self.assertIn("Apache-2.0", SHELL)
        self.assertNotIn("M" + "IT", SHELL)

    def test_selftest_prints_the_pass_line(self):
        self.assertIn('"No problems found."', SHELL)
        self.assertIn('location.hash === "#selftest"', SHELL)


class LanguageKitTests(unittest.TestCase):
    """jamshell 0.5.0: the language kit and per-page storage."""

    @staticmethod
    def lang_keys(code):
        block = SHELL[SHELL.index("const LANGS = {"):]
        block = block[:block.index("\n};")]
        part = block[block.index("\n  %s: {" % code) + 1:]
        nxt = re.search(r"\n  [a-z]{2}: \{", part)
        return set(re.findall(r'\b([A-Za-z]+): "', part[:nxt.start()] if nxt else part))

    def test_language_kit_is_in_the_shell(self):
        shell = SHELL[:SHELL.index("// DEMO (replace in a jam game)")]
        for name in ("const LANGS = {", "function fmt(", "function say(", "function pickLang(", "function addWords(",
                     "function setLang(", '<button id="langBtn" class="btn small hidden"'):
            self.assertIn(name, shell)
        # the kit is defined before the sound switch first draws its label
        self.assertLess(SHELL.index("const LANGS = {"), SHELL.index("sound.showLabel();"))

    def test_english_and_french_have_the_same_words(self):
        en, fr = self.lang_keys("en"), self.lang_keys("fr")
        self.assertEqual(en, fr)
        self.assertGreaterEqual(len(en), 15)
        # every word the page marks with data-say exists
        self.assertLessEqual(set(re.findall(r'data-say="(\w+)"', SHELL)), en)

    def test_english_reads_as_before(self):
        for line in ('sound: "Sound: {0}"', 'score: "Score {0} · best {1}"', 'best: "Best: {0}"', 'play: "Play"'):
            self.assertIn(line, SHELL)
        credits = re.search(r'<div id="credits" data-say="credits">(.*?)</div>', SHELL).group(1)
        self.assertIn("credits: %s" % json.dumps(credits, ensure_ascii=False), SHELL)

    def test_games_opt_in(self):
        self.assertIn('let lang = "en", offered = ["en"];', SHELL)
        after = SHELL[SHELL.index("end of DEMO"):]
        self.assertIn("addWords(Game.words);", after)
        self.assertIn('setLang(pickLang(new URLSearchParams(location.search).get("lang"), store.get("lang", null),', after)

    def test_storage_is_per_page(self):
        # itch.io serves its HTML games from one shared origin, so keys carry the page's path
        self.assertIn('key(k) { return "jamshell." + location.pathname + "#" + k; },', SHELL)
        self.assertNotIn('localStorage.getItem("jamshell." + k)', SHELL)

    def test_steps_switch_language(self):
        spec = json.load(open(os.path.join(HERE, "steps.json"), encoding="utf-8"))
        saves = {s.get("save") for s in spec["steps"]}
        for name in ("lang_default", "lang_button", "lang_french", "lang_back"):
            self.assertIn(name, saves)


class LandscapeTests(unittest.TestCase):
    """jamshell 0.6.0: a page may ask for a landscape stage (1280x720); portrait stays the default."""

    def test_stage_size_is_read_from_the_page(self):
        shell = SHELL[:SHELL.index("// DEMO (replace in a jam game)")]
        self.assertIn("function stageSize(asked) {", shell)
        self.assertIn("document.querySelector('meta[name=\"jamshell-stage\"]')", shell)
        self.assertIn("const W = STAGE.w, H = STAGE.h;", shell)
        self.assertIn("{ w: 720, h: 1280, landscape: false }", shell)
        self.assertIn("{ w: 1280, h: 720, landscape: true }", shell)
        self.assertIn('document.body.classList.toggle("landscape", STAGE.landscape);', shell)

    def test_the_shell_itself_stays_portrait(self):
        head = SHELL[:SHELL.index("</head>")]
        # the head mentions the tag only inside the header comment, so the shell as shipped is portrait
        outside = head[:head.index("<!--")] + head[head.index("-->") + 3:]
        self.assertNotIn("jamshell-stage", outside)

    def test_landscape_css_packs_the_screens(self):
        css = SHELL[SHELL.index("<style>"):SHELL.index("</style>")]
        for rule in ("body.landscape .layer {", "body.landscape .btn.card {", "body.landscape #chooseList {"):
            self.assertIn(rule, css)
        cards = css[css.index("body.landscape #chooseList {"):]
        self.assertIn("flex-wrap: wrap", cards[:cards.index("}")])

    def test_vignette_covers_both_orientations(self):
        self.assertIn("const M = Math.max(W, H), g = c.createRadialGradient(", SHELL)

    def test_landscape_steps_are_valid(self):
        spec = json.load(open(os.path.join(HERE, "steps-landscape.json"), encoding="utf-8"))
        self.assertEqual(playcheck.check_steps(spec), [])
        by_save = {s.get("save"): s for s in spec["steps"] if s.get("save")}
        self.assertEqual(by_save["stage_size"]["expect"], "1280x720 true")
        for name in ("title_fits", "centre_tap", "cards_fit", "picked_card", "paused_fits", "over_fits"):
            self.assertIn(name, by_save)
        # a sideways window and an upright one, so both ways of letterboxing are played
        self.assertEqual({v["width"] > v["height"] for v in spec["viewports"]}, {True, False})

    def test_readme_says_how(self):
        readme = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
        self.assertIn('<meta name="jamshell-stage" content="landscape">', readme)


class LevelKitTests(unittest.TestCase):
    """jamshell 0.7.0: the level kit (text maps, a fitted grid, saved progress, undo, restart, the Levels screen)."""

    def test_kit_is_in_the_shell(self):
        shell = SHELL[:SHELL.index("// DEMO (replace in a jam game)")]
        for name in ("function parseLevel(", "function fitGrid(", "function keyDir(", "function moveBox(",
                     "const DIRS = {", "const levels = {", "remember() {", "undo() {", "win() {", "menu() {"):
            self.assertIn(name, shell)

    def test_screens_and_buttons(self):
        self.assertIn('<div id="levels" class="layer hidden"', SHELL)
        for button in ("levelsBtn", "undoBtn", "restartBtn"):
            self.assertIn('<button id="%s" class="btn small hidden"' % button, SHELL)
        self.assertIn('for (const id of ["title", "paused", "over", "choose", "levels"])', SHELL)
        self.assertIn('name !== "choose" && name !== "won"', SHELL)

    def test_level_keys_come_before_the_game(self):
        keys = SHELL[SHELL.index('addEventListener("keydown"'):SHELL.index('addEventListener("keyup"')]
        self.assertLess(keys.index("levels.key(e.key)"), keys.index("Game.onKey(e.key)"))
        self.assertIn("levels.count && levels.key(e.key)", keys)

    def test_play_goes_to_the_next_level(self):
        start = SHELL[SHELL.index("function start(at) {"):SHELL.index("function pause()")]
        self.assertIn('levels.go(typeof at === "number" ? at : levels.next())', start)
        self.assertIn("Game.start(rng(Date.now() & 0xffffffff))", start)

    def test_level_list_is_text_not_html(self):
        menu = SHELL[SHELL.index("  menu() {"):SHELL.index("  setup() {")]
        self.assertNotIn("innerHTML", menu)
        self.assertIn("b.disabled = !this.isOpen(i);", menu)

    def test_progress_is_saved_per_page(self):
        self.assertIn('store.get("levels", [])', SHELL)
        self.assertIn('store.set("levels",', SHELL)

    def test_example_keeps_the_shell(self):
        ex = open(os.path.join(HERE, "examples", "levels.html"), encoding="utf-8").read()
        cut, tail = "const Game = {", "// ---------------------------------------- end of DEMO"
        self.assertEqual(ex[:ex.index(cut)], SHELL[:SHELL.index(cut)])
        self.assertEqual(ex[ex.index(tail):], SHELL[SHELL.index(tail):])
        game = ex[ex.index(cut):ex.index(tail)]
        for member in ("levels: [", "load(i, level)", "snapshot()", "restore(s)", "levels.remember()", "levels.win()",
                       "tests(check)"):
            self.assertIn(member, game)
        self.assertNotIn("M" + "IT", ex)

    def test_level_steps_are_valid(self):
        spec = json.load(open(os.path.join(HERE, "steps-levels.json"), encoding="utf-8"))
        self.assertEqual(playcheck.check_steps(spec), [])
        by_save = {s.get("save"): s for s in spec["steps"] if s.get("save")}
        for name in ("levels_button", "title_fits", "first_level", "undo_key", "undo_button", "hud_fits", "hud_order",
                     "restart_button", "won", "next_level", "pushed", "open_levels", "levels_fit", "picked_level",
                     "levels_escape"):
            self.assertIn(name, by_save)
        self.assertEqual(by_save["open_levels"]["expect"], "110")

    def test_readme_says_how(self):
        readme = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
        self.assertIn("## Level kit (0.7.0)", readme)
        self.assertIn("examples/levels.html", readme)


if __name__ == "__main__":
    unittest.main()
