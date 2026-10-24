"""Tests for framewalk's pure helpers (no browser needed). Apache-2.0. MV2 of Munim, Inc., made with AI agents."""
import json
import os
import unittest

import framewalk

HERE = os.path.dirname(os.path.abspath(__file__))


class Helpers(unittest.TestCase):
    def test_frames_line_up_with_render_quanta(self):
        self.assertTrue(framewalk.aligned(25, 48000))   # 1920 samples = 15 quanta
        self.assertTrue(framewalk.aligned(125, 48000))
        self.assertFalse(framewalk.aligned(30, 48000))  # 1600 samples
        self.assertFalse(framewalk.aligned(25, 44100))

    def test_choose_seed_prefers_no_stalls_then_short(self):
        results = [{"seed": 1, "updates": 5000, "secs": 200.0, "gap": 70.0},
                   {"seed": 2, "updates": 5500, "secs": 220.0, "gap": 20.0},
                   {"seed": 3, "updates": 4500, "secs": 180.0, "gap": 25.0},
                   {"seed": 4, "updates": 9000, "secs": -1, "gap": 5.0},
                   {"seed": 5, "updates": 8000, "secs": 320.0, "gap": 10.0}]
        self.assertEqual(framewalk.choose_seed(results, 300)["seed"], 3)   # 255 beats 280, 410; 4 never ends
        self.assertEqual(framewalk.choose_seed(results[:2], 300)["seed"], 2)
        self.assertIsNone(framewalk.choose_seed(results[3:], 300))

    def test_shot_times(self):
        self.assertEqual(framewalk.shot_times(100, 30), [30, 60, 90])
        self.assertEqual(framewalk.shot_times(100, 0), [])

    def test_ffmpeg_commands(self):
        enc = framewalk.encode_cmd(25, "/out/p.mp4")
        self.assertEqual(enc[enc.index("-framerate") + 1], "25")
        self.assertIn("image2pipe", enc)
        mux = framewalk.mux_cmd("v.mp4", "a.wav", 2.5004, "o.mp4")
        self.assertIn("[1:a]adelay=delays=2500:all=1,apad[a]", mux)
        self.assertIn("-shortest", mux)
        self.assertIn("[1:a]adelay=delays=0:all=1,apad[a]", framewalk.mux_cmd("v", "a", -0.04, "o"))

    def test_loudness(self):
        text = "[Parsed_volumedetect_0 @ 0x1] mean_volume: -31.4 dB\n[Parsed_volumedetect_0 @ 0x1] max_volume: -9.0 dB\n"
        self.assertEqual(framewalk.loudness(text), {"mean_volume": -31.4, "max_volume": -9.0})
        self.assertEqual(framewalk.loudness("max_volume: -inf dB"), {"mean_volume": None, "max_volume": -999.0})

    def test_clock_script_takes_over_frames_time_and_sound(self):
        js = framewalk.vclock_script(25, 48000, 360)
        self.assertIn("STEP = 40.0, RATE = 48000, FRAMES = 17280000;", js)
        for hook in ("window.requestAnimationFrame =", "performance.now =", "window.AudioContext =",
                     "OfflineAudioContext", "P.suspend.call", "P.startRendering.call", "btoa"):
            self.assertIn(hook, js)
        self.assertNotIn("%(", js)

    def test_spec_checks(self):
        spec = {"viewport": {"width": 720, "height": 1280}, "fps": 25, "rate": 48000, "title_seconds": 2.5,
                "click": "#playBtn", "start": "Game.start(rng(SEED)); true",
                "probe": "(seed, dt) => ({updates: 0, finished: false, gap: 0})", "seeds": [1, 2, 3],
                "done": "scene === 'over'", "tail_seconds": 5, "max_game_seconds": 200, "max_seconds": 230}
        self.assertEqual(framewalk.check_spec(spec), [])
        self.assertTrue(framewalk.check_spec(dict(spec, fps=30)))
        self.assertTrue(framewalk.check_spec(dict(spec, start="Game.start(rng(1))")))
        self.assertTrue(framewalk.check_spec(dict(spec, max_game_seconds=400)))
        self.assertTrue(framewalk.check_spec(dict(spec, seeds=[])))
        self.assertEqual(framewalk.check_spec({"fps": 25})[0], "missing viewport")

    def test_example_spec_for_the_demo(self):
        path = os.path.join(HERE, "framewalk.json")
        if not os.path.exists(path):
            self.skipTest("no framewalk.json next to the tests")
        spec = json.load(open(path, encoding="utf-8"))
        self.assertEqual(framewalk.check_spec(spec), [])
        for word in ("updates", "finished", "gap"):
            self.assertIn(word, spec["probe"])


if __name__ == "__main__":
    unittest.main()
