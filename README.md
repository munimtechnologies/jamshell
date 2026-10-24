# jamshell

A starter for portrait, touch-first browser games made during game jams, by MV2 of Munim, Inc.
Apache-2.0 (see LICENSE). Version 0.4.0. Playable demo and downloads: https://munimv2.itch.io/jamshell

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
- `playcheck.py`: plays any single-file HTML game in headless Chromium, takes screenshots per viewport and
  records gameplay video. Needs `pip install playwright` and `python -m playwright install chromium`; the tests
  below do not.
- `framewalk.py`: records a gameplay video with the game's own sound one frame at a time on a virtual clock, so
  a slow or busy machine still gives a full-speed video with the sound in sync. It plays each seed first,
  records the one with the shortest stretch without progress, and fails if the recording does not end on the
  frame the probe predicted. Same needs as playcheck, plus ffmpeg; the spec's keys are listed at the top of the
  file. The idea is not new (CCapture.js, timecut and trailer-kit step a page's clock too); this is one file
  sized for jamshell games, first used for the walkthrough video of MV2's jam game Lantern Drift.
- `package.py`: zips a build for itch.io and refuses it if it loads anything from the network, lacks the
  credits text, breaks itch.io's limits, or carries any text listed in a private `--forbid` file.
- `test_jamshell.py`, `test_package.py`, `test_framewalk.py`: unit tests (no browser needed).

```
python -m unittest -v test_jamshell.py test_package.py test_framewalk.py
python playcheck.py --html dist/index.html --steps steps.json --out out/playcheck
python playcheck.py --url http://127.0.0.1:5099/ --steps steps.json --out out/playcheck --skip-video
python framewalk.py --html dist/index.html --spec framewalk.json --out out/walk
python package.py --dist dist --zip out/game-itch.zip --credits "with AI agents" --forbid private/forbid.txt
```

The `--forbid` file holds one text per line, optionally `text<TAB>reason`, with lines starting with `#`
skipped. Put your own private strings there (a home address, a personal email) and keep that file outside the
build and out of every download; the report names only the reason, never the text. Set `FORBID_FILE` to the
same file and `test_package.py` also checks that the packager's own files are clean.

A playcheck viewport with `"reduced_motion": true` runs the steps the way a player with that setting would. A
`"drag"` step presses, moves and holds the mouse and checks its `"probe"` before letting go.

itch.io embed for a portrait jam: "This file will be played in the browser", viewport 720 x 1280, tick
"Mobile friendly" (orientation portrait) and "Fullscreen button".

Versions: 0.1.0 (2026-10-16) the shell; 0.2.0 (2026-10-16) music, juice kit, credits strip, reduced motion;
0.3.0 (2026-10-16) action kit: touch stick, keys held, axis, hits, nearest, pick-one card screen; 0.4.0
(2026-10-17) look kit: shade and mix, stickers, parallax backdrop, vignette, banners; the packager reads the
texts it must refuse from a private `--forbid` file; playcheck gained `--url` and `--skip-video` (2026-10-19);
framewalk.py added (2026-10-24).

MV2 of Munim, Inc., mv2@munimtech.com. Code Apache-2.0.
