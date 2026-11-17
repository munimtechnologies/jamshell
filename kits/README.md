# jamshell kits

Optional add-ons for jamshell games. Each kit is one plain JavaScript file with no dependencies and no network use.
Paste it into a `<script>` in your game page before your `Game` object, or ship it next to the page and load it with
`<script src="platform.js"></script>`. Made by MV2 of Munim, Inc. with AI agents (Anthropic Claude). Licence: Apache-2.0.

## platform.js (0.1.0): tile platformer physics

Status, 17 November 2026: the static checks (`test_platform_kit.py`) run before this commit. The 18 behaviour tests
were written with their expected numbers worked out by hand, but have **not run yet**. They are queued as a sealed
Node 24 job, and the kit is only listed as a jamshell release once they pass. Until then, treat it as a preview.

Fixed-step platformer movement on a tile map, written so jam games can bend the usual rules without rewriting physics.

- **Map**: `Platform.world(rows, tile)`. `#` solid, `=` one-way (blocks only along gravity), `^` hazard. Any other
  character except `.` and space is a marker: `world.find("P")` returns its cells and the cell stays empty.
  Left and right of the map are walls; above and below are open.
- **Body**: `Platform.body({x, y, w, h, g, p})`. `p` overrides the tuning in `Platform.DEFAULTS` (gravity 2400,
  run 260, jump 760, coyote 0.08 s, jump buffer 0.1 s, jump cut 0.45).
- **Step**: `Platform.step(world, body, {move, jump, drop}, dt)` returns events: `jump`, `land`, `bonk`, `wall`,
  `hurt`, `out`. `move` is screen-right when gravity is vertical and screen-down when it is sideways; `jump` is the held
  state (the kit detects the press); `drop` falls through one-way tiles.
- **Fixed ticks**: `var tick = Platform.ticker(1/120); tick(dt, function (s) { Platform.step(world, me, input(), s); });`
  Same inputs give the same run, which is what ghosts and replays need.
- **Gravity**: `Platform.setGravity(body, Platform.UP)` (also `DOWN`, `LEFT`, `RIGHT`).
- **Size**: `Platform.resize(world, body, 2)` grows or shrinks around the feet and returns `false` (no change) when
  the new size would not fit.
- **Ghosts and rewind**: `Platform.recorder()` / `Platform.replayer(frames)`; `Platform.snap(body)`,
  `Platform.restore(body, snap)` and `Platform.history(600)` (a ring buffer, 5 s at 120 ticks per second).
- **View**: `Platform.follow(cam, body, viewW, viewH, world, lerp)` and `Platform.drawTiles(ctx, world, cam, viewW, viewH, colors)`.

Demo: `examples/platform.html` (open `#selftest` for a scripted check). Tests: `node --test kits/platform.test.cjs` (18
behaviour tests with hand-worked numbers) and `python test_platform_kit.py` (static checks).

With 32 px tiles and the default tuning, a held jump rises 117.17 px (117 + 1/6 at 120 ticks per second), and letting
go of jump right after take-off gives a 27.9 px hop.
