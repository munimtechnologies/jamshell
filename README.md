# jamshell

A starter for touch-first browser games made during game jams (portrait by default, landscape on request), by MV2 of Munim, Inc.
Apache-2.0 (see LICENSE). Version 0.7.0 (0.6.0 added a landscape stage and 0.7.0 a level kit to `shell.html`; see the sections at the end).
Playable demo and downloads: https://munimv2.itch.io/jamshell

Made with AI agents (Anthropic Claude) working for MV2 of Munim, Inc., on 2026-10-16 and 2026-10-17, before
any jam window opened. The code and tests were written by the agents and run in an automated sandbox. It holds
no gameplay of its own beyond a tiny demo, so every jam entry that starts from it says so in its description.

`shell.html` is one offline file:
- a 720x1280 stage scaled to fit any window and centred (phone, tablet, desktop, itch.io's iframe);
- one input path for mouse, touch and keys: `onTap`, `onPress`, `onDrag`, `onSwipe(dir)`, `onKey`, in stage pixels;
- synthesized sound (`sound.tone`) that starts only after the first tap, a remembered sound on/off button;
- title, pause and game-over screens with buttons at least 88 stage pixels tall, best score, pause on tab switch;
- seeded random numbers, storage that never throws, a toast line;
- `#selftest`: shell checks plus the game's own `tests(check)`, ending in "No problems found.";
- the AI-disclosure credits line, on its own strip (`SAFE_BOTTOM`, 96 stage pixels) so game art never hides it.

The juice kit (0.2.0):
- `music`: a synthesized loop (pad, bass, arpeggio, drums). Set `Game.music = { bpm, key, chords, minor, seed }`
  and it starts with the first game, follows the sound switch and stops while paused. `music.notes(song, step)`
  is pure, so a test can check the pattern without audio.
- `fx.burst(x, y, color)` sparks, `fx.text(x, y, "+10")` rising numbers, `fx.shake(px)`, `fx.flash(color)`;
  players whose system asks for reduced motion get no shake and only a faint flash.
- `tween(obj, { x: 300 }, 0.4, ease.outBack, done)` and eight easing curves.
- `paint.sky`, `paint.box`, `paint.glow`, `paint.text` and four palettes (`dusk`, `candy`, `forest`, `neon`).

The action kit (0.3.0), for games where the player moves:
- `Game.stick = true` turns on a floating touch stick: it appears where the finger goes down and tilts toward the
  drag (`stick.x`, `stick.y`, -1 to 1, with a small dead zone); the drag keeps tracking outside the stage.
- `axis()` is where the player wants to go: arrows or WASD (diagonals as fast as straight lines), else the stick.
  `held` is the set of keys held down right now.
- `hit(a, b)` for two circles `{ x, y, r }`, `nearest(list, x, y, maxD)`, `clamp(v, lo, hi)`.
- `choose("Level up!", [{ label: "Faster", detail: "+20% speed" }, ...], i => ...)`: a pick-one card screen for
  level-ups, shops and upgrades. It freezes the game, shows up to four big numbered buttons (tap, click, Enter or
  keys 1-4) and calls back with the index picked.

The look kit (0.4.0), so a 48-hour game can look finished:
- `paint.shade("#4cc9f0", -0.4)` (40% darker; +0.4 is 40% lighter) and `paint.mix(a, b, t)`: pure colour maths
  on `#rgb`, `#rrggbb` and `#rrggbbaa` strings.
- `paint.sticker(c, "star", x, y, r, fill, n, rot)`: a circle, polygon (`"poly"`, n sides) or star (n points)
  with a drop shadow, a lighter top, a dark outline and a shine. `shapePoints(kind, x, y, r, n, rot)` gives the
  corners for hit tests or your own drawing.
- `bd = makeBackdrop(seed, palettes.dusk)` once, then `paint.backdrop(c, bd, scroll, time)` every frame: three
  seeded layers of rolling hills (far ones pale and slow, near ones dark and fast) that tile forever, plus
  twinkles up high. Players who ask for reduced motion get still hills.
- `paint.vignette(c, 0.4)` darkens the edges so the eye goes to the middle.
- `fx.banner("Level 2", "faster bubbles")`: a ribbon that slides across the middle and away (it only fades for
  reduced motion). One at a time; it stands still while the game is paused or the cards are up.

A jam game replaces only the block between `// DEMO (replace in a jam game)` and `end of DEMO` (the demo,
"Pop", exists so the shell can be played and tested) and adds its steps to `steps.json`.

## Files

- `shell.html`: the starter and its demo.
- `steps.json`: the scripted playtest for the demo (viewports, taps, drags, probes).
- `steps-landscape.json` (0.6.0): the playtest for a landscape page.
- `examples/levels.html` and `steps-levels.json` (0.7.0): a three-level example of the level kit and its playtest.
- `playcheck.py`: plays any single-file HTML game in headless Chromium, takes screenshots per viewport and
  records gameplay video. Needs `pip install playwright` and `python -m playwright install chromium`; the tests
  below do not.
- `framewalk.py`: records a gameplay video with the game's own sound one frame at a time on a virtual clock, so
  a slow or busy machine still gives a full-speed video with the sound in sync. It plays each seed first,
  records the one with the shortest stretch without progress, and fails if the recording does not end on the
  frame the probe predicted. Same needs as playcheck, plus ffmpeg; the spec's keys are listed at the top of the
  file. The idea is not new (CCapture.js, timecut and trailer-kit step a page's clock too); this is one file
  sized for jamshell games, first used for the walkthrough video of MV2's jam game Lantern Drift.
- `framewalk.json`: the example spec for the demo. Pop has no player bot, so nobody taps: the demo ends after
  three missed bubbles (about 9 seconds of play) and the video runs about 16 seconds with the title and the
  game-over screen. A real game's spec swaps the probe and `start` for its own demo player.
- `package.py`: zips a build for itch.io and refuses it if it loads anything from the network, lacks the
  credits text, breaks itch.io's limits, or carries any text listed in a private `--forbid` file.
- `langleak.py` (0.5.1): finds words of the wrong language in a translated jamshell game (see below).
- `make_fixtures.py` (0.5.1): builds two test pages for langleak from the demo, one leaky and one clean.
- `test_jamshell.py`, `test_package.py`, `test_framewalk.py`, `test_langleak.py`: unit tests (no browser needed).

```
python -m unittest -v test_jamshell.py test_package.py test_framewalk.py test_langleak.py
python playcheck.py --html dist/index.html --steps steps.json --out out/playcheck
python playcheck.py --url http://127.0.0.1:5099/ --steps steps.json --out out/playcheck --skip-video
python framewalk.py --html dist/index.html --spec framewalk.json --out out/walk
python package.py --dist dist --zip out/game-itch.zip --credits "with AI agents" --forbid private/forbid.txt
python langleak.py --html dist/index.html --out out/langleak --langs fr,en --allow "Pop"
```

The `--forbid` file holds one text per line, optionally `text<TAB>reason`, with lines starting with `#`
skipped. Put your own private strings there (a home address, a personal email) and keep that file outside the
build and out of every download; the report names only the reason, never the text. Set `FORBID_FILE` to the
same file and `test_package.py` also checks that the packager's own files are clean.

A playcheck viewport with `"reduced_motion": true` runs the steps the way a player with that setting would. A
`"drag"` step presses, moves and holds the mouse and checks its `"probe"` before letting go.

itch.io embed for a portrait jam: "This file will be played in the browser", viewport 720 x 1280, tick
"Mobile friendly" (orientation portrait) and "Fullscreen button". For a landscape page use 1280 x 720.

Versions: 0.1.0 (2026-10-16) the shell; 0.2.0 (2026-10-16) music, juice kit, credits strip, reduced motion;
0.3.0 (2026-10-16) action kit: touch stick, keys held, axis, hits, nearest, pick-one card screen; 0.4.0
(2026-10-17) look kit: shade and mix, stickers, parallax backdrop, vignette, banners; the packager reads the
texts it must refuse from a private `--forbid` file; playcheck gained `--url` and `--skip-video` (2026-10-19);
framewalk.py added (2026-10-24), and its example spec for the demo (2026-10-25); 0.5.0 (2026-10-30) language
kit; 0.5.1 (2026-10-31) langleak.py; 0.6.0 (written 2026-11-11) landscape stage; 0.7.0 (written 2026-11-11,
released 2026-11-13 after its sandbox playtest) level kit.

MV2 of Munim, Inc., mv2@munimtech.com. Code Apache-2.0.

## Language kit (0.5.0)

A game can now be played in more than one language. It opts in with `Game.words = { en: { ... }, fr: { ... } }`:
the languages it lists are offered, its words join the shell's own (English and French are built in for every
button, the score lines and the credits) and may replace them, and `say("key", a, b)` shows a word in the current
language with `{0}` and `{1}` filled in (a missing word falls back to English). The language is `?lang=xx` in the
address, else the player's last pick, else the browser's language ("fr-CA" counts as "fr"), else the first one
listed; a button on the title screen switches languages when there is more than one. `Game.name` and `Game.howTo`
are read again on every switch, so a game can make them getters that call `say`. A game without `Game.words` stays
in English, as in 0.4.0.

Saved values (best score, sound, language) are now kept per page path: itch.io serves its HTML games from one
shared origin, so two jamshell games there used to share one best score.

Made by AI agents (Anthropic Claude) working for MV2 of Munim, Inc. on 2026-10-30, before any jam window, and
checked in Chromium with French and English browser languages. Apache-2.0.

## langleak (0.5.1)

Opting in to a second language is easy; forgetting one English string is easier. A how-to line written as a
plain string, or an `fx.banner("Go!", ...)` that never went through `say()`, still shows in English on the French
screen, and a quick look at the title often misses it. `langleak.py` plays the page once per language (browser
locale and `?lang=`): title, a few seconds of taps, pause, game over. In each scene it keeps the page's visible
text and every string drawn on the canvas (it records `fillText` and `strokeText` before the game's own script
runs), then flags strings that look like another language:
- in French: common English words that are not also everyday French (so "score", "pause", "record" and "bonus"
  pass), and any English phrase of the shell's or the game's words whose French differs;
- in English: common French words and accented letters;
- in every language: `say()` keys that fell back to English, and `Game.words` keys missing from one language.

It writes `report.json` and a screenshot per scene and language, and exits 1 if anything was flagged. Names that
stay the same in every language go in `--allow`. It is a word-list heuristic for English and French, not a
language detector: look at the screenshots too.

Checked on 2026-10-31 in a sealed container (Chromium via Playwright 1.47) against two pages made from the 0.5.0
demo by `make_fixtures.py`: the clean page, with every string through `say()`, passed in both languages; the
leaky page, which offers French but keeps the demo's English name, how-to and banners, was flagged on exactly
those three strings in French ("Tap the bubbles ...", "Go!", "pop the bubbles") and on nothing in English, with
no page errors. Made by AI agents (Anthropic Claude) working for MV2 of Munim, Inc. Apache-2.0.

## Landscape stage (0.6.0)

A game can now use a landscape stage. Put this tag in the page's head:

```html
<meta name="jamshell-stage" content="landscape">
```

The stage is then 1280x720 logical pixels instead of 720x1280, and `W` and `H` follow. The title, pause, game-over
and card screens are packed for the wider shape (the four cards sit in two rows of two), and the window still
letterboxes the stage and maps taps and drags onto it. Without the tag, or with any other value, the stage stays
portrait, exactly as in 0.5.x. Landscape suits jams whose players mostly use a desktop browser, such as itch.io
embeds and judged jams; portrait suits phones.

`steps-landscape.json` is the playtest for a landscape page. It plays a desktop window, a phone held sideways and a
phone held upright (letterboxed), and checks that every screen fits inside the stage above the credits strip:

```
python playcheck.py --html dist/index.html --steps steps-landscape.json --out /out --skip-video
```

Made by AI agents (Anthropic Claude) working for MV2 of Munim, Inc. on 2026-11-11, before any jam window, and
checked in Chromium in both orientations before release. Apache-2.0.

## Level kit (0.7.0)

For games made of hand-made levels: puzzles, mazes, platformers. A game opts in by listing its levels:

```js
const Game = {
  levels: [{ name: "Walk", map: ["#######", "#@   *#", "#######"] }, /* ... */],
  load(i, level) {  // set the game up for level i
    this.map = parseLevel(level.map); this.grid = fitGrid(this.map.w, this.map.h); this.me = this.map.find("@");
  },
  snapshot() { return { me: this.me }; },  // optional: plain JSON state, turns on undo
  restore(s) { this.me = s.me; },
  // call levels.remember() before each move and levels.win() when the level is solved
};
```

The shell then adds:

- a **Levels** button and screen: later levels open as earlier ones are cleared (`Game.levelsOpen = true` opens
  them all), cleared levels show green, and progress is saved per page;
- **Play** goes to the first level not cleared yet;
- **Undo** and **Restart** buttons in the HUD, and keys: R restarts, Z, U or Backspace undo;
- a "Level 3" banner as each level opens (`Game.levelBanner = false` turns it off), a "Level clear!" banner and
  sound, then the next level, and an all-clear screen after the last one.

Helpers: `parseLevel` (text maps with `at`, `set`, `find`, `all` and `rows`), `fitGrid` (square cells laid out
between the HUD and the credits strip, with `centre` and `cellAt` for taps), `DIRS` and `keyDir` (arrows and WASD
give the same `"up"`, `"down"`, `"left"` and `"right"` that swipes use) and `moveBox` (moves a box through a tile map
and stops it at solid tiles, in half-tile steps so it never passes through a thin floor, for platformers). A game
without `Game.levels` plays exactly as before. The level words come in English and French like the rest.

`examples/levels.html` is a three-level example of the kit ("Steps": walk, push a crate, undo) and
`steps-levels.json` is its playtest, for a portrait or a landscape page:

```
python playcheck.py --html examples/levels.html --steps steps-levels.json --out /out --skip-video
```

Made by AI agents (Anthropic Claude) working for MV2 of Munim, Inc. on 2026-11-11, before any jam window; the kit
holds no game. Checked in Chromium in portrait and landscape before release. Apache-2.0.

Release check (2026-11-13, sealed container on the Dell, Chromium via Playwright 1.47, built from repo commit
6d7343df): 71 unit tests passed (1 skipped: it needs a private `FORBID_FILE`); the demo played with no errors in
four portrait and three landscape viewports, reaching game over in each; the "Steps" example played with no errors
in three viewports each in portrait and landscape (walk, push, undo by key and button, restart, Levels screen
showing 1 cleared / 2 open / 3 locked, win). An earlier run of the same check on 2026-11-12 failed one landscape
step because a fixed 16-second wait outran a slow sandbox browser; the playtest now waits for the game-over
screen instead of a fixed time.
