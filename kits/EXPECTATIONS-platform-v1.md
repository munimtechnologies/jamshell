# Expectations for job jamshell-platform-v1 (written 2026-11-17 ~05:00Z, before any run)

Kit: `kits/platform.js` 0.1.0. Tests: `kits/platform.test.cjs` (18), `test_platform_kit.py` (7 static, 1 may skip).
No browser and no network. The code has never been executed; every number was worked out by hand.

Hand-worked numbers (32 px tiles, 120 ticks/s, gravity 2400 -> 20 px/s per tick, jump 760, cut 0.45):
- T2: resting y = 224 - 30 = 194; exactly one "land" event, on tick 1.
- T3: jump fires on tick 2 (tick 1 lands, so there is no coyote time yet); per-tick upward speed 760 - 20k, k = 1..37;
  rise = (37 * 760 - 20 * 703) / 120 = 117 + 1/6 = 117.1667 px; apex y = 76.8333.
- T4: release on tick 3: 740 * 0.45 = 333; rise = (740 + 2608)/120 = 27.9 px; apex y = 166.1.
- T5: wall at x = 224, body w 24 -> x = 200.
- T6: coyote 0.08 s: press on tick 9 (0.08 - 9/120 = 0.005 > 0) jumps; tick 10 (< 0) does not.
- T7: one-way row 4 top y = 128 -> stands at 98; held jump apex bottom 106.83 < 128, so it passes up and lands at 98.
- T10: gravity LEFT -> x = 32; walking "down" stops on row 5 -> y = 130.
- T11: x2 from (40,194,24,30): centred x = 28 hits the column-0 wall, left edge kept -> (40,164,48,60); x0.5 -> (46,209,12,15).
- T17: camera lerp 0.5 from 640 towards 332 -> 486.

Predictions:
- E1: all 18 node tests pass (node_rc=0). If any fail, the cause is a kit bug or a hand-arithmetic slip; the fix is
  decided from the trace, never by editing an expected number to match without re-deriving it.
- E2: python static tests pass (python_rc=0), or python3 is missing in node:24 (then it is recorded, not a failure).
- E3: trace-jump.txt shows "land" on tick 1, "jump" on tick 2, the lowest y 76.8333 around tick 39, and y back to
  194.0000 with a second "land" before tick 80.
- E4: peak memory under 0.3 GB, run under 2 minutes.
