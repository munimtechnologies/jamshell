/*
 * jamshell platform kit 0.1.0 (kits/platform.js)
 * Tile platformer physics for jam games: fixed-step movement, coyote time, jump buffering,
 * variable jump height, one-way platforms, hazards, gravity in any of the four directions,
 * safe grow/shrink of the player box, input recording for ghosts and replays, snapshots
 * for rewind, a camera follow and a plain tile painter.
 * Works on its own or next to jamshell's shell.html. No network, no dependencies.
 * Made by MV2 of Munim, Inc. with AI agents (Anthropic Claude). Licence: Apache-2.0.
 * https://github.com/munimtechnologies/jamshell
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Platform = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var VERSION = "0.1.0";
  var EPS = 1e-4;
  var DOWN = { x: 0, y: 1 }, UP = { x: 0, y: -1 }, LEFT = { x: -1, y: 0 }, RIGHT = { x: 1, y: 0 };
  var LEGEND = { "#": "solid", "=": "oneway", "^": "hazard" };

  // Defaults tuned for 32 px tiles: a held jump rises about 117 px (3.7 tiles) at 120 ticks/s.
  var DEFAULTS = {
    gravity: 2400, // px/s^2 along the gravity direction
    maxFall: 900, // px/s
    run: 260, // px/s top walking speed
    accel: 2400, // px/s^2 on the ground with input
    decel: 3000, // px/s^2 on the ground without input
    airAccel: 1600, // px/s^2 in the air
    jump: 760, // px/s take-off speed
    cut: 0.45, // rising speed is multiplied by this when jump is released early
    coyote: 0.08, // s after leaving a ledge during which a jump still works
    buffer: 0.1, // s a jump press is remembered before landing
    hurtInset: 4 // px of overlap forgiven before a hazard hurts
  };

  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
  function approach(v, target, delta) {
    if (v < target) return Math.min(v + delta, target);
    if (v > target) return Math.max(v - delta, target);
    return v;
  }

  // ---- world ---------------------------------------------------------------------------
  // rows: array of strings, one char per tile. Legend chars become tile kinds; any other
  // char except " " and "." is a marker (spawn, key, door...) and the cell stays empty.
  function world(rows, tile, legend) {
    tile = tile || 32;
    legend = legend || LEGEND;
    var h = rows.length, w = 0, y, x;
    for (y = 0; y < h; y++) w = Math.max(w, rows[y].length);
    var kinds = new Array(w * h), markers = {};
    for (y = 0; y < h; y++) {
      for (x = 0; x < w; x++) {
        var ch = rows[y].charAt(x) || " ";
        var k = Object.prototype.hasOwnProperty.call(legend, ch) ? legend[ch] : null;
        kinds[y * w + x] = k;
        if (!k && ch !== " " && ch !== ".") (markers[ch] = markers[ch] || []).push({ x: x, y: y });
      }
    }
    var wd = {
      w: w, h: h, tile: tile, pixelW: w * tile, pixelH: h * tile,
      // Outside the map: left and right are walls, above and below are open air.
      kindAt: function (cx, cy) {
        if (cx < 0 || cx >= w) return "solid";
        if (cy < 0 || cy >= h) return null;
        return kinds[cy * w + cx];
      },
      set: function (cx, cy, kind) {
        if (cx >= 0 && cx < w && cy >= 0 && cy < h) kinds[cy * w + cx] = kind || null;
      },
      find: function (ch) {
        return (markers[ch] || []).map(function (c) { return { x: c.x, y: c.y }; });
      },
      centre: function (c) { return { x: (c.x + 0.5) * tile, y: (c.y + 0.5) * tile }; },
      cellAt: function (px, py) { return { x: Math.floor(px / tile), y: Math.floor(py / tile) }; }
    };
    return wd;
  }

  // Does box {x,y,w,h} (shrunk by inset px on every side) overlap a tile of this kind?
  function overlaps(wd, box, kind, inset) {
    inset = inset || 0;
    var t = wd.tile;
    var x0 = Math.floor((box.x + inset) / t), x1 = Math.floor((box.x + box.w - inset - EPS) / t);
    var y0 = Math.floor((box.y + inset) / t), y1 = Math.floor((box.y + box.h - inset - EPS) / t);
    for (var cy = y0; cy <= y1; cy++)
      for (var cx = x0; cx <= x1; cx++)
        if (wd.kindAt(cx, cy) === kind) return true;
    return false;
  }

  // ---- bodies --------------------------------------------------------------------------
  function body(o) {
    o = o || {};
    var p = {}, k;
    for (k in DEFAULTS) p[k] = DEFAULTS[k];
    if (o.p) for (k in o.p) p[k] = o.p[k];
    var w = o.w || 24, h = o.h || 30;
    return {
      x: o.x || 0, y: o.y || 0, w: w, h: h, baseW: w, baseH: h, scale: 1,
      vx: 0, vy: 0, g: o.g || DOWN, p: p,
      grounded: false, coyote: 0, buffer: 0, jumpHeld: false, rising: false, facing: 1
    };
  }

  // Leading-edge sweep along one axis. Returns the pixel edge that stops the box, or null.
  function sweepBlock(wd, b, ax, part, prev, g, drop) {
    var t = wd.tile, sz = ax === "x" ? "w" : "h";
    var lead, prevLead, edge;
    if (part > 0) {
      lead = Math.floor((b[ax] + b[sz] - EPS) / t);
      prevLead = Math.floor((prev + b[sz] - EPS) / t);
      if (lead === prevLead) return null;
      edge = lead * t;
    } else {
      lead = Math.floor(b[ax] / t);
      prevLead = Math.floor(prev / t);
      if (lead === prevLead) return null;
      edge = (lead + 1) * t;
    }
    var o = ax === "x" ? "y" : "x", osz = ax === "x" ? "h" : "w";
    var s0 = Math.floor((b[o] + EPS) / t), s1 = Math.floor((b[o] + b[osz] - EPS) / t);
    // One-way tiles block only movement along gravity, and only if the box started
    // on the near side of the tile's edge.
    var alongGravity = g[ax] !== 0 && (part > 0) === (g[ax] > 0);
    var wasOutside = part > 0 ? prev + b[sz] <= edge + EPS : prev >= edge - EPS;
    for (var s = s0; s <= s1; s++) {
      var kind = ax === "x" ? wd.kindAt(lead, s) : wd.kindAt(s, lead);
      if (kind === "solid") return edge;
      if (kind === "oneway" && alongGravity && wasOutside && !drop) return edge;
    }
    return null;
  }

  // Move a box along one axis, in chunks shorter than half a tile so nothing tunnels.
  // Returns +1 / -1 for the side that hit something, or 0.
  function moveAxis(wd, b, ax, d, g, drop) {
    if (!d) return 0;
    var sz = ax === "x" ? "w" : "h";
    var maxChunk = Math.max(1, Math.min(wd.tile, b.w, b.h) * 0.45);
    var n = Math.ceil(Math.abs(d) / maxChunk), part = d / n;
    for (var i = 0; i < n; i++) {
      var prev = b[ax];
      b[ax] += part;
      var edge = sweepBlock(wd, b, ax, part, prev, g || DOWN, drop);
      if (edge !== null) {
        b[ax] = part > 0 ? edge - b[sz] : edge;
        return part > 0 ? 1 : -1;
      }
    }
    return 0;
  }

  // One fixed tick. input = { move: -1..1, jump: held?, drop: fall through one-ways? }.
  // "move" is screen-right when gravity is vertical and screen-down when it is sideways.
  // Returns a list of events: "jump", "land", "bonk", "wall", "hurt", "out".
  function step(wd, b, input, dt) {
    input = input || {};
    var p = b.p, g = b.g || DOWN, ev = [];
    var gAx = g.x !== 0 ? "x" : "y", mAx = gAx === "x" ? "y" : "x";
    var gs = g[gAx] > 0 ? 1 : -1;
    var vg = gAx === "x" ? "vx" : "vy", vm = mAx === "x" ? "vx" : "vy";

    b.coyote = b.grounded ? p.coyote : Math.max(0, b.coyote - dt);
    var held = !!input.jump, pressed = held && !b.jumpHeld;
    b.jumpHeld = held;
    b.buffer = pressed ? p.buffer : Math.max(0, b.buffer - dt);

    var move = clamp(+input.move || 0, -1, 1);
    var target = move * p.run;
    var a = b.grounded ? (move !== 0 ? p.accel : p.decel) : p.airAccel;
    b[vm] = approach(b[vm], target, a * dt);
    if (move) b.facing = move > 0 ? 1 : -1;

    if (b.buffer > 0 && b.coyote > 0) {
      b[vg] = -gs * p.jump;
      b.buffer = 0; b.coyote = 0; b.grounded = false; b.rising = true;
      ev.push("jump");
    }
    if (b.rising && !held && b[vg] * gs < 0) { b[vg] *= p.cut; b.rising = false; }
    if (b[vg] * gs >= 0) b.rising = false;

    b[vg] += gs * p.gravity * dt;
    if (b[vg] * gs > p.maxFall) b[vg] = gs * p.maxFall;

    if (moveAxis(wd, b, mAx, b[vm] * dt, g, input.drop)) { b[vm] = 0; ev.push("wall"); }
    var was = b.grounded;
    var hit = moveAxis(wd, b, gAx, b[vg] * dt, g, input.drop);
    b.grounded = hit === gs;
    if (hit) {
      if (hit === gs && !was) ev.push("land");
      if (hit === -gs) ev.push("bonk");
      b[vg] = 0;
    }
    if (overlaps(wd, b, "hazard", p.hurtInset)) ev.push("hurt");
    var m = 2 * wd.tile;
    if (b.y > wd.pixelH + m || b.y + b.h < -m) ev.push("out");
    return ev;
  }

  // Change gravity direction (DOWN, UP, LEFT, RIGHT). Velocity is kept; the body is airborne.
  function setGravity(b, g) { b.g = g; b.grounded = false; b.coyote = 0; b.rising = false; }

  // Grow or shrink the box to baseW/baseH * scale, keeping the feet (the side facing gravity)
  // in place. Tries centred, then each edge kept; returns false (no change) if all are blocked.
  function resize(wd, b, scale) {
    var g = b.g || DOWN, nw = b.baseW * scale, nh = b.baseH * scale;
    var vertical = g.x === 0, tries = [], fx, fy;
    if (vertical) {
      fy = g.y > 0 ? b.y + b.h - nh : b.y;
      tries = [b.x + b.w / 2 - nw / 2, b.x, b.x + b.w - nw].map(function (x) { return { x: x, y: fy }; });
    } else {
      fx = g.x > 0 ? b.x + b.w - nw : b.x;
      tries = [b.y + b.h / 2 - nh / 2, b.y, b.y + b.h - nh].map(function (y) { return { x: fx, y: y }; });
    }
    for (var i = 0; i < tries.length; i++) {
      var box = { x: tries[i].x, y: tries[i].y, w: nw, h: nh };
      if (box.x < 0 || box.x + box.w > wd.pixelW) continue;
      if (!overlaps(wd, box, "solid", 0)) {
        b.x = box.x; b.y = box.y; b.w = nw; b.h = nh; b.scale = scale;
        return true;
      }
    }
    return false;
  }

  // ---- time ----------------------------------------------------------------------------
  // Fixed-step ticker: call tick(dt, fn) every frame; fn(stepSec) runs 0..maxSteps times.
  function ticker(stepSec, maxSteps) {
    stepSec = stepSec || 1 / 120;
    maxSteps = maxSteps || 10;
    var acc = 0;
    return function (dt, fn) {
      acc += dt;
      var n = 0;
      while (acc >= stepSec - 1e-9 && n < maxSteps) { acc -= stepSec; fn(stepSec); n++; }
      if (n === maxSteps) acc = 0;
      return n;
    };
  }

  // Input recorder: push one input per tick; frames is a compact list for replays/ghosts.
  function recorder() {
    var frames = [];
    return {
      frames: frames,
      push: function (inp) {
        inp = inp || {};
        frames.push([clamp(+inp.move || 0, -1, 1), inp.jump ? 1 : 0, inp.drop ? 1 : 0]);
      }
    };
  }
  // Replay: next() gives the input for the next tick, or null when the recording ends.
  function replayer(frames) {
    var i = 0;
    return {
      done: function () { return i >= frames.length; },
      next: function () {
        if (i >= frames.length) return null;
        var f = frames[i++];
        return { move: f[0], jump: !!f[1], drop: !!f[2] };
      }
    };
  }

  // Snapshots for rewind/undo: plain JSON, safe to store.
  var SNAP_KEYS = ["x", "y", "w", "h", "scale", "vx", "vy", "grounded", "coyote", "buffer", "jumpHeld", "rising", "facing"];
  function snap(b) {
    var s = { g: { x: b.g.x, y: b.g.y } };
    SNAP_KEYS.forEach(function (k) { s[k] = b[k]; });
    return s;
  }
  function restore(b, s) {
    SNAP_KEYS.forEach(function (k) { b[k] = s[k]; });
    b.g = { x: s.g.x, y: s.g.y };
    return b;
  }
  // Ring buffer of snapshots (e.g. 600 = 5 s at 120 ticks/s).
  function history(size) {
    var buf = [];
    size = size || 600;
    return {
      push: function (s) { buf.push(s); if (buf.length > size) buf.shift(); },
      pop: function () { return buf.length ? buf.pop() : null; },
      get length() { return buf.length; },
      clear: function () { buf.length = 0; }
    };
  }

  // ---- view ----------------------------------------------------------------------------
  // Ease a camera {x,y} towards the body, kept inside the world. lerp 1 = snap.
  function follow(cam, b, viewW, viewH, wd, lerp) {
    lerp = lerp === undefined ? 0.15 : lerp;
    var tx = clamp(b.x + b.w / 2 - viewW / 2, 0, Math.max(0, wd.pixelW - viewW));
    var ty = clamp(b.y + b.h / 2 - viewH / 2, 0, Math.max(0, wd.pixelH - viewH));
    cam.x += (tx - cam.x) * lerp;
    cam.y += (ty - cam.y) * lerp;
    return cam;
  }

  // Paint visible tiles: solid = filled square, oneway = thin bar, hazard = spikes.
  function drawTiles(ctx, wd, cam, viewW, viewH, colors) {
    colors = colors || {};
    var t = wd.tile;
    var x0 = Math.max(0, Math.floor(cam.x / t)), x1 = Math.min(wd.w - 1, Math.floor((cam.x + viewW) / t));
    var y0 = Math.max(0, Math.floor(cam.y / t)), y1 = Math.min(wd.h - 1, Math.floor((cam.y + viewH) / t));
    for (var cy = y0; cy <= y1; cy++) {
      for (var cx = x0; cx <= x1; cx++) {
        var k = wd.kindAt(cx, cy);
        if (!k) continue;
        var px = cx * t - cam.x, py = cy * t - cam.y;
        if (k === "solid") {
          ctx.fillStyle = colors.solid || "#3a3550";
          ctx.fillRect(px, py, t, t);
        } else if (k === "oneway") {
          ctx.fillStyle = colors.oneway || "#8a7fb0";
          ctx.fillRect(px, py, t, Math.max(3, t / 6));
        } else if (k === "hazard") {
          ctx.fillStyle = colors.hazard || "#e05a5a";
          ctx.beginPath();
          for (var i = 0; i < 3; i++) {
            ctx.moveTo(px + (i * t) / 3, py + t);
            ctx.lineTo(px + ((i + 0.5) * t) / 3, py + t * 0.45);
            ctx.lineTo(px + ((i + 1) * t) / 3, py + t);
          }
          ctx.closePath();
          ctx.fill();
        }
      }
    }
  }

  return {
    VERSION: VERSION, DEFAULTS: DEFAULTS, LEGEND: LEGEND,
    DOWN: DOWN, UP: UP, LEFT: LEFT, RIGHT: RIGHT,
    world: world, overlaps: overlaps, body: body, step: step, moveAxis: moveAxis,
    setGravity: setGravity, resize: resize, ticker: ticker,
    recorder: recorder, replayer: replayer, snap: snap, restore: restore, history: history,
    follow: follow, drawTiles: drawTiles, clamp: clamp, approach: approach
  };
});
