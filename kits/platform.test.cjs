// Behaviour tests for kits/platform.js (jamshell platform kit 0.1.0). Run: node --test kits/platform.test.cjs
// Every expected number below was worked out by hand before the first run (see EXPECTATIONS.md).
// Made by MV2 of Munim, Inc. with AI agents (Anthropic Claude). Licence: Apache-2.0.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const P = require("./platform.js");

const DT = 1 / 120;
const near = (a, b, msg) => assert.ok(Math.abs(a - b) < 1e-6, `${msg}: got ${a}, want ${b}`);

// 8 columns x 8 rows, walls in columns 0 and 7, floor in row 7 (y = 224).
function room(extra) {
  const rows = [];
  for (let y = 0; y < 7; y++) rows.push("#......#");
  rows.push("########");
  if (extra) extra(rows);
  return P.world(rows, 32);
}
function setRow(rows, y, s) { rows[y] = s; }
function run(wd, b, ticks, inputFor) {
  const all = [];
  for (let i = 1; i <= ticks; i++) all.push(...P.step(wd, b, inputFor ? inputFor(i) : {}, DT));
  return all;
}

test("T1 world parsing, edges and markers", () => {
  const wd = P.world(["#....#", "#.P..#", "######"], 32);
  assert.equal(wd.w, 6); assert.equal(wd.h, 3);
  assert.equal(wd.pixelW, 192); assert.equal(wd.pixelH, 96);
  assert.equal(wd.kindAt(0, 0), "solid");
  assert.equal(wd.kindAt(1, 1), null);
  assert.equal(wd.kindAt(2, 1), null, "marker cells are empty");
  assert.equal(wd.kindAt(-1, 1), "solid", "left of map is wall");
  assert.equal(wd.kindAt(6, 1), "solid", "right of map is wall");
  assert.equal(wd.kindAt(2, -1), null, "above map is open");
  assert.equal(wd.kindAt(2, 5), null, "below map is open");
  assert.deepEqual(wd.find("P"), [{ x: 2, y: 1 }]);
  assert.deepEqual(wd.centre({ x: 2, y: 1 }), { x: 80, y: 48 });
  assert.deepEqual(wd.cellAt(80, 48), { x: 2, y: 1 });
  wd.set(2, 1, "solid");
  assert.equal(wd.kindAt(2, 1), "solid");
});

test("T2 standing on the floor: lands once on tick 1 and stays at y = 194", () => {
  const wd = room();
  const b = P.body({ x: 40, y: 194 });
  const ev = run(wd, b, 120);
  assert.equal(ev.filter((e) => e === "land").length, 1);
  assert.equal(b.y, 194);
  assert.equal(b.grounded, true);
  assert.equal(b.vy, 0);
});

test("T3 held jump: apex 117.1667 px above the floor, then lands back", () => {
  const wd = room();
  const b = P.body({ x: 40, y: 194 });
  let minY = Infinity, jumps = 0, lands = 0;
  for (let i = 1; i <= 240; i++) {
    const ev = P.step(wd, b, { jump: true }, DT);
    jumps += ev.filter((e) => e === "jump").length;
    lands += ev.filter((e) => e === "land").length;
    minY = Math.min(minY, b.y);
  }
  // take-off on tick 2 at 760 px/s; per tick v = 760 - 20k; sum k=1..37 of (760-20k)/120 = 117 + 1/6
  near(minY, 194 - (117 + 1 / 6), "apex y");
  assert.equal(jumps, 1, "holding jump does not re-jump");
  assert.equal(lands, 2, "lands on tick 1 and again after the jump");
  assert.equal(b.y, 194);
});

test("T4 short tap: jump cut gives a 27.9 px hop", () => {
  const wd = room();
  const b = P.body({ x: 40, y: 194 });
  let minY = Infinity;
  for (let i = 1; i <= 240; i++) {
    P.step(wd, b, { jump: i <= 2 }, DT);
    minY = Math.min(minY, b.y);
  }
  // tick 2 moves 740/120; tick 3 cuts 740 -> 333; then sum k=1..16 of (333-20k)/120 = 2608/120
  near(minY, 194 - (740 + 2608) / 120, "hop apex y");
  assert.equal(b.y, 194);
});

test("T5 running into the right wall stops at x = 200", () => {
  const wd = room();
  const b = P.body({ x: 40, y: 194 });
  const ev = run(wd, b, 240, () => ({ move: 1 }));
  assert.equal(b.x, 200);
  assert.equal(b.vx, 0);
  assert.ok(ev.includes("wall"));
  assert.equal(b.y, 194, "running does not sink into the floor");
  assert.equal(b.facing, 1);
});

test("T6 coyote time: a press on tick 9 after the ledge jumps, tick 10 does not", () => {
  const wd = P.world(["........", "........", "........"], 32);
  function trial(pressTick) {
    const b = P.body({ x: 40, y: 0 });
    b.coyote = 0.08; // as if it walked off a ledge on the previous tick
    let jumped = false;
    for (let i = 1; i <= 12; i++) {
      const ev = P.step(wd, b, { jump: i === pressTick }, DT);
      if (ev.includes("jump")) jumped = true;
    }
    return jumped;
  }
  assert.equal(trial(9), true);
  assert.equal(trial(10), false);
});

test("T7 one-way platform: fall onto it, and jump up through it", () => {
  const wd = room((rows) => setRow(rows, 4, "#==....#"));
  const a = P.body({ x: 40, y: 0 });
  run(wd, a, 240);
  assert.equal(a.y, 98, "lands on top of the one-way row (128 - 30)");
  assert.equal(a.grounded, true);

  const b = P.body({ x: 40, y: 194 });
  const ev = run(wd, b, 240, () => ({ jump: true }));
  assert.ok(!ev.includes("bonk"), "no bonk from below");
  assert.equal(b.y, 98, "ends standing on the one-way platform");

  // drop: holding drop falls through again to the floor
  run(wd, b, 120, () => ({ drop: true }));
  assert.equal(b.y, 194);
});

test("T8 solid ceiling bonks a jump", () => {
  const wd = room((rows) => setRow(rows, 5, "#......#".replace("..", "##")));
  // row 5 = "###....#" spans y 160..192 above columns 1-2; head starts at 194
  const b = P.body({ x: 40, y: 194 });
  const ev = run(wd, b, 60, () => ({ jump: true }));
  assert.ok(ev.includes("bonk"));
  assert.equal(b.y, 194, "back on the floor after the bonk");
});

test("T9 gravity UP: falls onto the ceiling at y = 32", () => {
  const wd = P.world(["########", "#......#", "#......#", "#......#", "#......#"], 32);
  const b = P.body({ x: 40, y: 100, g: P.UP });
  const ev = run(wd, b, 120);
  assert.equal(b.y, 32);
  assert.equal(b.grounded, true);
  assert.equal(ev.filter((e) => e === "land").length, 1);
  // jumping with UP gravity moves down the screen
  const y0 = b.y;
  P.step(wd, b, { jump: true }, DT);
  P.step(wd, b, { jump: true }, DT);
  assert.ok(b.y > y0);
});

test("T10 gravity LEFT: rests against the left wall at x = 32, move walks along y", () => {
  const wd = P.world(["########", "#......#", "#......#", "#......#", "#......#", "########"], 32);
  const b = P.body({ x: 150, y: 80 });
  P.setGravity(b, P.LEFT);
  run(wd, b, 120);
  assert.equal(b.x, 32);
  assert.equal(b.grounded, true);
  run(wd, b, 120, () => ({ move: 1 }));
  assert.equal(b.y, 160 - 30, "walked down the screen until the floor row 5 (y = 160)");
});

test("T11 resize: grows feet-first beside a wall, refuses under a low ceiling, shrinks", () => {
  const wd = room();
  const b = P.body({ x: 40, y: 194 });
  run(wd, b, 2);
  assert.equal(P.resize(wd, b, 2), true);
  assert.deepEqual([b.x, b.y, b.w, b.h, b.scale], [40, 164, 48, 60, 2], "centred try hits the wall, left edge kept");

  const low = room((rows) => setRow(rows, 5, "#####..#"));
  const c = P.body({ x: 40, y: 194 });
  run(low, c, 2);
  assert.equal(P.resize(low, c, 2), false);
  assert.deepEqual([c.x, c.y, c.w, c.h, c.scale], [40, 194, 24, 30, 1], "unchanged when blocked");

  assert.equal(P.resize(wd, c, 0.5), true);
  assert.deepEqual([c.x, c.y, c.w, c.h], [46, 209, 12, 15]);
  run(wd, c, 30);
  assert.equal(c.y, 209, "small body stands on the floor");
});

test("T12 hazards hurt after the inset", () => {
  const wd = room((rows) => setRow(rows, 6, "#^^^^^^#"));
  const b = P.body({ x: 40, y: 0 });
  const ev = run(wd, b, 240);
  assert.ok(ev.includes("hurt"));
  assert.equal(b.y, 194, "spikes are not solid; the floor below is");
});

test("T13 falling out of the map reports out", () => {
  const wd = P.world(["#......#", "#......#"], 32);
  const b = P.body({ x: 40, y: 0 });
  const ev = run(wd, b, 240);
  assert.ok(ev.includes("out"));
});

test("T14 recorder + replayer reproduce a run exactly", () => {
  const wd = room((rows) => setRow(rows, 4, "#==....#"));
  const a = P.body({ x: 40, y: 194 });
  const rec = P.recorder();
  for (let i = 1; i <= 300; i++) {
    const inp = { move: i < 90 ? 1 : i < 200 ? -0.5 : 0, jump: (i % 70) < 20, drop: i > 280 };
    rec.push(inp);
    P.step(wd, a, inp, DT);
  }
  const b = P.body({ x: 40, y: 194 });
  const rp = P.replayer(rec.frames);
  let inp;
  while ((inp = rp.next())) P.step(wd, b, inp, DT);
  assert.equal(rp.done(), true);
  assert.equal(rec.frames.length, 300);
  assert.deepEqual([b.x, b.y, b.vx, b.vy], [a.x, a.y, a.vx, a.vy]);
});

test("T15 snapshots and history rewind exactly", () => {
  const wd = room();
  const b = P.body({ x: 40, y: 194 });
  const h = P.history(3);
  run(wd, b, 5);
  const s = P.snap(b);
  h.push(s);
  run(wd, b, 40, () => ({ move: 1, jump: true }));
  assert.notEqual(b.x, s.x);
  P.restore(b, h.pop());
  assert.deepEqual(P.snap(b), s);
  assert.equal(JSON.stringify(JSON.parse(JSON.stringify(s))), JSON.stringify(s), "snapshots are plain JSON");
  for (let i = 0; i < 5; i++) h.push({ i });
  assert.equal(h.length, 3);
  assert.deepEqual(h.pop(), { i: 4 });
  h.clear();
  assert.equal(h.pop(), null);
});

test("T16 ticker runs fixed steps", () => {
  const tick = P.ticker(1 / 120);
  let n = 0;
  assert.equal(tick(0.05, () => n++), 6);
  const t2 = P.ticker(1 / 120);
  let m = 0;
  t2(0.004, () => m++); t2(0.004, () => m++);
  assert.equal(m, 0);
  t2(0.004, () => m++);
  assert.equal(m, 1);
  const t3 = P.ticker(1 / 120, 10);
  assert.equal(t3(1.0, () => {}), 10, "a long stall is capped");
  assert.equal(t3(0, () => {}), 0, "and the backlog is dropped");
});

test("T17 follow keeps the camera inside the world", () => {
  const wd = P.world(Array(10).fill("#".repeat(60)), 32); // 1920 x 320
  const cam = { x: 0, y: 0 };
  P.follow(cam, { x: 1900, y: 10, w: 24, h: 30 }, 1280, 720, wd, 1);
  assert.deepEqual(cam, { x: 640, y: 0 });
  P.follow(cam, { x: 960, y: 10, w: 24, h: 30 }, 1280, 720, wd, 0.5);
  assert.deepEqual(cam, { x: 486, y: 0 }); // target 960 + 12 - 640 = 332; 640 + (332 - 640) * 0.5 = 486
});

test("T18 drawTiles paints one rect per visible solid tile", () => {
  const wd = P.world(["#..", ".#.", "..#"], 32);
  let rects = 0;
  const ctx = { fillRect: () => rects++, beginPath() {}, moveTo() {}, lineTo() {}, closePath() {}, fill() {} };
  P.drawTiles(ctx, wd, { x: 0, y: 0 }, 96, 96);
  assert.equal(rects, 3);
});
