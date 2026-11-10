---
name: jamshell
description: Build a portrait, touch-first browser game for a game jam as one offline HTML file with jamshell (720x1280 stage, one input path for mouse/touch/keys, title/pause/game-over screens, sound, music, juice, touch stick, self-test, headless playtest and an itch.io packager). Use when an agent must make a small HTML5 jam game fast, test it without a human, and upload it to itch.io.
license: Apache-2.0
---

# jamshell: one-file browser jam games

jamshell (https://github.com/munimtechnologies/jamshell, Apache-2.0, by MV2 of Munim, Inc.) is a
starter kit for portrait, touch-first browser games. `shell.html` is a single offline file with the
plumbing a jam game needs; you replace only its DEMO block with your game object. jamshell itself was
made with AI agents (Anthropic Claude), and its credits strip says so.

## When to use

- A timed jam (itch.io or similar) wants a browser-playable game and you have hours, not weeks.
- The game is 2D, plays in one screen, and should work on phones (touch) and desktops (mouse, keys).
- You need to test it headlessly: a self-test, a scripted playtest with screenshots, and a zip that
  passes itch.io's limits.

Not for: 3D games, multi-scene games with heavy assets, or engines such as Godot, GDevelop or Phaser.

## Workflow

1. Get the kit and check it runs (Python 3.10+):
   ```sh
   git clone --depth 1 https://github.com/munimtechnologies/jamshell
   cd jamshell
   python -m unittest -v test_jamshell.py test_package.py test_framewalk.py test_langleak.py
   ```
2. Copy `shell.html` to `dist/index.html`. In the copy, replace the code from `const Game = {` down
   to (not including) the line `// ------ end of DEMO ------` with your own `const Game = { ... };`.
   Keep everything else.
3. Name the maker in your game object, not in the HTML: give it
   `words: { en: { credits: "Made by <maker> with AI agents (...): ..." } }`. Since jamshell 0.5.0
   every word the shell shows, the credits strip included, comes from its language table, so text
   typed into the `<div id="credits">` element is replaced when the page loads. If your game offers
   more languages (for example `fr`), give each one its own `credits` entry too, or that language
   keeps the shell's own credit line. Keep the words `with AI agents` if AI agents made the game (the
   self-test and `package.py --credits "with AI agents"` both check for them), and answer the jam's
   and itch.io's AI-disclosure questions truthfully.
4. Open `dist/index.html#selftest`: it must end with `No problems found.` (shell checks plus your
   game's own `tests`).
5. Write a playtest spec (`steps.json`, format below) and run it headlessly:
   ```sh
   pip install playwright && python -m playwright install chromium
   python playcheck.py --html dist/index.html --steps steps.json --out out/playcheck --skip-video
   ```
   It exits 0 only if the self-test text appears, every `expect` holds and the page logs no errors.
   Look at the screenshots in `out/playcheck/`.
6. Package for itch.io (refuses network loads, missing credits text and builds over itch's limits):
   ```sh
   python package.py --dist dist --zip out/game-itch.zip --credits "with AI agents"
   ```
   On itch.io: Kind of project "HTML", upload the zip, tick "This file will be played in the
   browser", viewport 720 x 1280, "Mobile friendly" (portrait), "Fullscreen button".

## The game object

The shell calls these; everything is in stage pixels (`W` = 720, `H` = 1280, origin top-left):

| Member | Required | Meaning |
|---|---|---|
| `name`, `howTo` | yes | Title and one-line instructions on the title screen |
| `score`, `over` | yes | The HUD shows `score`; setting `over = true` ends the run |
| `start(rand)` | yes | New run; `rand()` is a seeded random in [0, 1) |
| `update(dt)` | yes | Called every frame during play; `dt` in seconds, capped at 0.05 |
| `draw(ctx, scene)` | yes | Draw everything; `scene` is `"title"`, `"play"`, `"paused"`, `"choose"` or `"over"` |
| `onTap(x, y)`, `onPress(x, y)`, `onDrag(x, y)`, `onSwipe(dir)`, `onKey(key)` | no | Input during play; `dir` is `"up"`, `"down"`, `"left"` or `"right"` |
| `tests(check)` | no | Your own self-test: call `check(condition, "what")` |
| `music` | no | `{ bpm, key, chords, minor, seed }`, e.g. `{ bpm: 104, key: 57, chords: [0, 5, 3, 4], minor: true, seed: 3 }` |
| `stick` | no | `true` shows a floating touch stick; read it through `axis()` |
| `words` | no | `{ en: { credits: "...", hint: "Tap {0} times" }, fr: { ... } }`; the languages listed are offered, `say("hint", 3)` shows a word, and `credits` replaces the shell's credit line |

Keep anything the player must see or tap above `H - SAFE_BOTTOM` (the credits strip, 96 px).

## Helpers the shell gives you

- Sound: `sound.tone(hz, seconds, wave, volume, slideToHz)` (silent until the first tap).
- Juice: `fx.burst(x, y, color, n)`, `fx.text(x, y, "+10", color)`, `fx.shake(px)`,
  `fx.flash(color, alpha)`, `fx.banner(title, subtitle)`. `fx.calm` is true under reduced motion.
- Tweens: `tween(obj, { x: 300 }, seconds, ease.outBack, done)`.
- Paint: `paint.sky(c, top, bottom)`, `paint.box(c, x, y, w, h, radius, fill, stroke)`,
  `paint.glow(c, x, y, r, color)`, `paint.text(c, s, x, y, px, color)`,
  `paint.sticker(c, "star" | "poly" | "circle", x, y, r, fill, n, rot)`, `paint.vignette(c, 0.4)`,
  `paint.shade(hex, k)`, `paint.mix(a, b, t)`; backdrops: `bd = makeBackdrop(seed, palette)` once, then
  `paint.backdrop(c, bd, scroll, time)` per frame.
- Palettes: `palettes.dusk`, `.candy`, `.forest`, `.neon`, each `{ top, bottom, a, b, c, ink }`.
- Action: `axis()` (arrows/WASD, else the stick, as `{ x, y }` in -1..1), `held` (keys down),
  `hit(a, b)` for circles `{ x, y, r }`, `nearest(list, x, y, maxD)`, `clamp(v, lo, hi)`,
  `choose(title, [{ label, detail }], i => ...)` for a pick-one card screen (opens only during play).
- Other: `rng(seed)`, `store.get(key, fallback)` / `store.set(key, value)`, `toast(text)`.

## Example game

"Star Catch": move a basket with the keys or the touch stick, catch stars, avoid rocks. Paste it in
place of the DEMO game object and put your own name in its `credits`. This exact block is spliced into
jamshell 0.5.1 and checked by the self-test, the playtest below and the packager before each release of
this skill.

```js example-game
const Game = {
  name: "Star Catch",
  howTo: "Move the basket with the arrow keys, WASD or the touch stick. Catch the stars and dodge the red rocks. Three rocks and it's over.",
  words: { en: { credits: "Made by Your Name with AI agents (Anthropic Claude): the code, art and sound are AI-made." } },
  music: { bpm: 112, key: 60, chords: [0, 4, 5, 3], seed: 5 },
  stick: true,
  look: palettes.forest,
  score: 0, over: false, rand: Math.random, t: 0, spawn: 0, hits: 0, items: [], bd: null, speed: 620,
  basket: { x: W / 2, y: H - SAFE_BOTTOM - 120, r: 60 },
  start(rand) {
    Object.assign(this, { score: 0, over: false, rand, t: 0, spawn: 0, hits: 0, items: [], speed: 620 });
    this.basket.x = W / 2;
    fx.banner("Go!", "catch the stars");
  },
  update(dt) {
    this.t += dt; this.spawn -= dt;
    this.basket.x = clamp(this.basket.x + axis().x * this.speed * dt, 70, W - 70);
    if (this.spawn <= 0) {
      this.spawn = Math.max(0.3, 0.9 - this.score * 0.01);
      const rock = this.rand() < 0.3;
      const it = { x: 60 + this.rand() * (W - 120), y: -40, r: rock ? 34 : 30, v: 260 + this.score * 4, rock, s: 0 };
      this.items.push(it);
      tween(it, { s: 1 }, 0.3, ease.outBack);
    }
    for (const it of this.items) {
      it.y += it.v * dt;
      if (!it.gone && hit(it, this.basket)) { it.gone = true; this.take(it); }
    }
    this.items = this.items.filter(it => !it.gone && it.y - it.r < H);
    if (this.hits >= 3) this.over = true;
  },
  take(it) {
    if (it.rock) {
      this.hits++;
      fx.shake(18); fx.flash(this.look.b, 0.3); sound.tone(130, 0.25, "sawtooth", 0.12, 60);
      return;
    }
    const level = Math.floor(this.score / 10);
    this.score++;
    fx.burst(it.x, it.y, this.look.a, 20); fx.text(it.x, it.y - 30, "+1", this.look.ink);
    sound.tone(600 + this.score * 6, 0.1, "sine", 0.2, 900);
    if (Math.floor(this.score / 10) > level) { this.speed *= 1.1; fx.banner("Level " + (level + 2), "faster basket"); }
  },
  draw(c, scene) {
    if (!this.bd) this.bd = makeBackdrop(4, this.look);
    paint.sky(c, this.look.top, this.look.bottom);
    paint.backdrop(c, this.bd, this.t * 30, this.t);
    for (const it of this.items) {
      const r = it.r * (it.s === undefined ? 1 : it.s);
      if (it.rock) paint.sticker(c, "poly", it.x, it.y, r, this.look.b, 6, fx.calm ? 0 : this.t);
      else paint.sticker(c, "star", it.x, it.y, r, this.look.a, 5, fx.calm ? 0 : this.t * 2);
    }
    const b = this.basket;
    paint.box(c, b.x - 70, b.y - 24, 140, 48, 18, this.look.c, this.look.ink);
    if (scene === "play") for (let i = 0; i < 3 - this.hits; i++) paint.glow(c, W / 2 - 50 + i * 50, 70, 14, this.look.b, 18);
    paint.vignette(c, 0.35);
  },
  tests(check) {
    const b = this.basket;
    this.start(rng(3)); this.spawn = 99;
    check(fx.banners.length === 1 && fx.banners[0].title === "Go!", "a new game opens with a banner");
    this.items = [{ x: b.x, y: b.y, r: 30, v: 0 }]; this.update(0.016);
    check(this.score === 1 && this.items.length === 0, "a star in the basket scores 1");
    this.items = [{ x: 40, y: 200, r: 30, v: 0 }]; this.update(0.016);
    check(this.score === 1 && this.items.length === 1, "a star far from the basket is not caught");
    this.items = [{ x: b.x, y: b.y, r: 34, v: 0, rock: true }]; this.update(0.016);
    check(this.hits === 1 && !this.over, "one rock costs a life");
    this.items = [0, 1].map(() => ({ x: b.x, y: b.y, r: 34, v: 0, rock: true })); this.update(0.016);
    check(this.hits === 3 && this.over, "three rocks end the game");
    this.start(rng(3)); this.spawn = 99; held.clear(); held.add("ArrowRight"); this.update(0.5); held.clear();
    check(b.x > W / 2 + 200, "the right arrow moves the basket right");
    for (let i = 0; i < 40; i++) { held.add("ArrowLeft"); this.update(0.05); }
    held.clear();
    check(b.x === 70, "the basket stops at the left wall");
    this.score = 9; fx.clear(); this.items = [{ x: b.x, y: b.y, r: 30, v: 0 }]; this.update(0.016);
    check(fx.banners.length === 1 && fx.banners[0].title === "Level 2", "reaching 10 shows a level banner");
    this.start(rng(1)); tweens = []; fx.clear(); held.clear();
  },
};
```

## Playtest spec

`playcheck.py` runs `selftest` once, then every step in every viewport (`only` limits a step to one
viewport). Steps: `wait` ms, `shot` name, `click` selector, `key` name (with `times`), `tap` [fx, fy],
`drag` [fx0, fy0, fx1, fy1] with `hold` ms and a `probe` read while still held, `eval` expression;
`save` records the value in `report.json`, `expect` fails the run on a mismatch, `after` waits ms.
Points are fractions of the viewport. The shell's globals (`Game`, `scene`, `fx`, `stick`, ...) can be
read in `eval`. Buttons: `#playBtn`, `#pauseBtn`, `#resumeBtn`, `#againBtn`, `#menuBtn`, `#quitBtn`.
A `video` section (see the repo's `steps.json`) also records a clip and needs ffmpeg; `--skip-video`
runs the steps without it.

```json example-steps
{
  "selftest": {"hash": "#selftest", "text": "No problems found.", "timeout_ms": 30000},
  "viewports": [
    {"name": "desktop", "width": 1280, "height": 720},
    {"name": "phone", "width": 720, "height": 1280, "touch": true}
  ],
  "steps": [
    {"wait": 600},
    {"shot": "title"},
    {"eval": "document.title", "expect": "Star Catch"},
    {"eval": "document.getElementById('credits').textContent", "save": "credits", "expect": "Made by Your Name with AI agents (Anthropic Claude): the code, art and sound are AI-made."},
    {"click": "#playBtn", "after": 300},
    {"eval": "scene", "expect": "play"},
    {"eval": "(Game.spawn = 99, Game.items = [], Game.basket.x)", "save": "basket_start", "expect": 360},
    {"drag": [0.5, 0.75, 0.62, 0.75], "hold": 900, "probe": "Game.basket.x > 450", "save": "stick_moves_basket", "expect": true},
    {"eval": "Game.items.push({x: Game.basket.x, y: Game.basket.y, r: 30, v: 0}) > 0", "expect": true},
    {"wait": 400},
    {"eval": "Game.score", "save": "score_after_star", "expect": 1},
    {"shot": "play"},
    {"click": "#pauseBtn", "after": 200},
    {"eval": "scene", "expect": "paused"},
    {"click": "#resumeBtn", "after": 200},
    {"eval": "scene", "expect": "play"},
    {"eval": "(() => { for (let i = 0; i < 3; i++) Game.items.push({x: Game.basket.x, y: Game.basket.y, r: 34, v: 0, rock: true}); return Game.items.length >= 3; })()", "expect": true},
    {"wait": 600},
    {"eval": "scene", "save": "scene_after_three_rocks", "expect": "over"},
    {"shot": "over"},
    {"click": "#menuBtn", "after": 300},
    {"eval": "scene", "expect": "title"}
  ]
}
```

## Pitfalls

- Never load fonts, scripts or images from the network: `package.py` refuses the build, and itch.io
  pages may be played offline. Draw with the canvas or embed data URLs.
- Credits typed into the HTML are overwritten on load: name the maker in `Game.words`, as in step 3.
- `choose()` freezes play until a card is picked; a playtest that waits for game over while idle will
  hang if a level-up card opens. Push state with `eval` instead, as above.
- Saved values (`store`) are kept per page path, because all itch.io games share one origin.
- Read the jam's rules before building: many jams ban or limit AI-made art, audio or code, and
  itch.io asks for an AI-generation disclosure on the game page.

Skill by MV2 of Munim, Inc. (mv2@munimtech.com), made with AI agents. Apache-2.0.
