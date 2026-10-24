"""Frame-stepped gameplay video with the game's own sound, for a single-file canvas game (Apache-2.0).
By MV2 of Munim, Inc., made with AI agents (Anthropic Claude).

playcheck.py records a video in real time. In a busy container that goes wrong two ways: a game that never
moves more than a set step per frame (jamshell's frame() caps it at 0.05 s) runs slow once the page drops
under 20 frames a second, and the sound, rendered on a starved audio thread, falls behind the picture.
framewalk.py takes the clock away from the wall instead:

    python3 framewalk.py --html dist/index.html --spec framewalk.json --out /out/walk

Before the page loads, requestAnimationFrame and performance.now are replaced by a virtual clock, and
AudioContext by an OfflineAudioContext. Then, frame by frame: the clock moves on 1/fps s, the sound is rendered
up to that moment, the game runs and draws one frame, and a screenshot of it goes to ffmpeg. However slow the
machine, every frame is exactly 1/fps s of game time, and the sound lines up with the picture to the sample.

Because each step is exact, the seed can be chosen before anything is recorded: the spec's "probe" plays each
seed with the same fixed step and no drawing, and the seed whose longest stretch without progress is shortest
(among those that finish in time) is the one recorded. The recorded run must then end on the very frame the
probe predicted, which checks that the recording really was deterministic.

framewalk.json:
    {"viewport": {"width": 720, "height": 1280}, "fps": 25, "rate": 48000, "title_seconds": 2.5,
     "click": "#playBtn", "start": "Game.start(rng(SEED)); Game.autoplay = true; true",
     "probe": "(seed, dt) => ({updates: 0, gap: 0})", "seeds": [1, 2, 3], "done": "scene === 'over'",
     "status": "Game.m + ' ' + Game.chorus.length", "tail_seconds": 10, "end_shot_after": 3,
     "shots_every": 30, "max_game_seconds": 260, "min_seconds": 60, "max_seconds": 330}

Writes gameplay.mp4 (H.264 + AAC), audio.wav, shot-<seconds>.png every shots_every s of play, end.png,
last-frame.png and report.json, and exits 1 if anything failed: a page error or console warning, no seed that
finishes, a run that ends off the probe's frame, a video outside its length limits, or silent sound.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys

# Runs before the page's own scripts. The page's frames, its clock and its sound all move only when step() is
# called; t0 is the moment (on the virtual clock) the page made its AudioContext.
VCLOCK = """(() => {
  const STEP = %(step_ms)r, RATE = %(rate)d, FRAMES = %(frames)d;
  const vt = window.__vt = { now: 0, queue: [], ac: null, t0: -1, rendered: 0, started: false, done: null, wav: null };
  let nextId = 1;
  window.requestAnimationFrame = cb => { const id = nextId++; vt.queue.push([id, cb]); return id; };
  window.cancelAnimationFrame = id => { vt.queue = vt.queue.filter(q => q[0] !== id); };
  performance.now = () => vt.now;
  const OAC = window.OfflineAudioContext, P = OAC.prototype;
  window.AudioContext = window.webkitAudioContext = function () {
    if (vt.ac) return vt.ac;
    const ac = new OAC(1, FRAMES, RATE);
    Object.defineProperty(ac, "state", { get: () => "running" });  // the game schedules sound only while running
    ac.resume = ac.suspend = ac.close = () => Promise.resolve();    // and only step() moves its clock
    vt.ac = ac; vt.t0 = vt.now;
    return ac;
  };
  const go = () => { if (vt.started) P.resume.call(vt.ac); else { vt.started = true; vt.done = P.startRendering.call(vt.ac); } };
  vt.audioTo = async seconds => {
    if (!vt.ac) return;
    const t = Math.round(seconds * RATE / 128) * 128 / RATE;
    if (t <= vt.rendered) return;
    if (t * RATE >= FRAMES) throw new Error("framewalk: the sound buffer is full at " + t + " s; raise max_seconds");
    const reached = P.suspend.call(vt.ac, t);
    go(); await reached; vt.rendered = t;
  };
  vt.step = async () => {
    vt.now += STEP;
    if (vt.ac) await vt.audioTo((vt.now - vt.t0) / 1000);
    const due = vt.queue; vt.queue = [];
    for (const [, cb] of due) cb(vt.now);
  };
  // renders the rest of the buffer, keeps what was played as 16-bit mono PCM WAV; returns its size in bytes
  vt.finish = async () => {
    if (!vt.ac) return 0;
    go();
    const buf = await vt.done, n = Math.min(buf.length, Math.round(vt.rendered * RATE)), pcm = buf.getChannelData(0);
    const out = new DataView(new ArrayBuffer(44 + 2 * n)), text = (at, s) => { for (let i = 0; i < 4; i++) out.setUint8(at + i, s.charCodeAt(i)); };
    text(0, "RIFF"); out.setUint32(4, 36 + 2 * n, true); text(8, "WAVE"); text(12, "fmt ");
    out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, 1, true); out.setUint32(24, RATE, true);
    out.setUint32(28, RATE * 2, true); out.setUint16(32, 2, true); out.setUint16(34, 16, true);
    text(36, "data"); out.setUint32(40, 2 * n, true);
    for (let i = 0; i < n; i++) out.setInt16(44 + 2 * i, Math.round(Math.max(-1, Math.min(1, pcm[i])) * 32767), true);
    vt.wav = new Uint8Array(out.buffer);
    return vt.wav.length;
  };
  vt.chunk = (from, size) => {
    const b = vt.wav.subarray(from, from + size);
    let s = "";
    for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
    return btoa(s);
  };
})();"""

CHUNK = 4 << 20  # bytes of WAV handed back from the page per call


def vclock_script(fps, rate, seconds):
    """The init script for one recording: steps of 1000/fps ms, and room for `seconds` of sound."""
    return VCLOCK % {"step_ms": 1000.0 / fps, "rate": rate, "frames": int(rate * seconds)}


def aligned(fps, rate):
    """A frame is a whole number of 128-sample render quanta, so the sound stops exactly on every frame."""
    return rate % fps == 0 and (rate // fps) % 128 == 0


def check_spec(spec):
    """Problems in a framewalk spec, found before any browser starts."""
    problems = []
    for key in ("viewport", "fps", "rate", "click", "start", "probe", "seeds", "done", "max_game_seconds",
                "max_seconds"):
        if key not in spec:
            problems.append("missing " + key)
    if problems:
        return problems
    if not aligned(spec["fps"], spec["rate"]):
        problems.append("rate / fps must be a whole number of 128-sample quanta (48000 Hz: fps 25 or 125)")
    if "SEED" not in spec["start"]:
        problems.append("start must name SEED")
    if not spec["seeds"]:
        problems.append("no seeds")
    if spec.get("title_seconds", 0) + spec["max_game_seconds"] + spec.get("tail_seconds", 0) > spec["max_seconds"]:
        problems.append("title + max_game_seconds + tail is longer than max_seconds")
    return problems


def choose_seed(results, max_game_seconds):
    """The probe result to record: of the seeds that finish within max_game_seconds, the one with the least
    length plus three times its longest stretch without progress (a viewer minds a stall more than a longer
    film); None if no seed finishes."""
    done = [r for r in results if 0 < r["secs"] <= max_game_seconds]
    return min(done, key=lambda r: (r["secs"] + 3 * r["gap"], r["seed"])) if done else None


def shot_times(game_seconds, every):
    """Seconds into play at which a still is kept: every `every` s while the game runs."""
    return list(range(every, int(game_seconds) + 1, every)) if every else []


def encode_cmd(fps, out):
    """ffmpeg reading JPEG frames on stdin and writing silent H.264."""
    return ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", str(fps),
            "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", out]


def mux_cmd(video, wav, offset_s, out):
    """ffmpeg putting the sound under the picture, starting offset_s in, padded with silence to the end."""
    return ["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", wav, "-filter_complex",
            "[1:a]adelay=delays=%d:all=1,apad[a]" % max(0, round(offset_s * 1000)), "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]


def duration(path, stream=None):
    """Seconds of a media file, or of its first audio ("a") or video ("v") stream; 0.0 if unknown."""
    cmd = ["ffprobe", "-v", "error"]
    if stream:
        cmd += ["-select_streams", stream + ":0", "-show_entries", "stream=duration"]
    else:
        cmd += ["-show_entries", "format=duration"]
    probe = subprocess.run(cmd + ["-of", "default=noprint_wrappers=1:nokey=1", path], capture_output=True, text=True)
    try:
        return float(probe.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return 0.0


def loudness(text):
    """mean_volume and max_volume (dB) from ffmpeg's volumedetect output; None where missing."""
    got = {}
    for key in ("mean_volume", "max_volume"):
        m = re.search(key + r":\s*(-?[\d.]+|-inf) dB", text)
        got[key] = None if not m else (-999.0 if m.group(1) == "-inf" else float(m.group(1)))
    return got


def watch(page, report, label):
    page.on("pageerror", lambda e: report["errors"].append("%s pageerror: %s" % (label, e)))
    page.on("console", lambda m: report["errors"].append("%s console %s: %s" % (label, m.type, m.text))
            if m.type in ("error", "warning") else None)


def probe_seeds(browser, url, spec, report):
    """Plays every seed once with the spec's probe (normal clock, nothing drawn) and returns the results."""
    ctx = browser.new_context(viewport=spec["viewport"])
    page = ctx.new_page()
    watch(page, report, "probe")
    page.goto(url)
    page.wait_for_timeout(500)
    dt = 1.0 / spec["fps"]
    results = []
    for seed in spec["seeds"]:
        r = page.evaluate("([seed, dt]) => (%s)(seed, dt)" % spec["probe"], [seed, dt])
        results.append({"seed": seed, "updates": r["updates"], "secs": round(r["updates"] * dt, 2) if r["finished"] else -1,
                        "gap": round(r["gap"], 2)})
    ctx.close()
    return results


def record(browser, url, spec, seed, out, report):
    """The recording itself; returns the silent video's path, the WAV's path (or None) and the sound's offset."""
    fps, vp = spec["fps"], spec["viewport"]
    ctx = browser.new_context(viewport=vp)
    ctx.add_init_script(vclock_script(fps, spec["rate"], spec["max_seconds"] + 30))
    page = ctx.new_page()
    watch(page, report, "video")
    page.goto(url)
    video = os.path.join(out, "picture.mp4")
    enc = subprocess.Popen(encode_cmd(fps, video), stdin=subprocess.PIPE)
    values = report["values"]
    frames = 0

    def step(done=None):
        nonlocal frames
        got = page.evaluate("async () => { await __vt.step(); return %s; }" % (done or "false"))
        enc.stdin.write(page.screenshot(type="jpeg", quality=90))
        frames += 1
        return got

    def still(name):
        page.screenshot(path=os.path.join(out, name))
        report["files"].append(name)

    try:
        for _ in range(round(spec.get("title_seconds", 2) * fps)):
            step()
        box = page.locator(spec["click"]).first.bounding_box()
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        values["started"] = page.evaluate(spec["start"].replace("SEED", str(seed)))
        shots = shot_times(spec["max_game_seconds"], spec.get("shots_every", 0))
        played = 0
        while True:
            over = step(spec["done"])
            played += 1
            if played % fps == 0 and played // fps in shots:
                still("shot-%03d.png" % (played // fps))
                if spec.get("status"):
                    values["status_%03d" % (played // fps)] = page.evaluate(spec["status"])
            if over:
                break
            if played > (spec["max_game_seconds"] + 30) * fps:
                report["errors"].append("the game did not end within %d s of play" % (spec["max_game_seconds"] + 30))
                break
        values["game_frames"] = played
        tail = round(spec.get("tail_seconds", 0) * fps)
        for i in range(tail):
            step()
            if i + 1 == round(spec.get("end_shot_after", 0) * fps):
                still("end.png")
        values["video_frames"] = frames
        size = page.evaluate("__vt.finish()")
        t0 = page.evaluate("__vt.t0")
        wav = None
        if size:
            wav = os.path.join(out, "audio.wav")
            with open(wav, "wb") as f:
                for at in range(0, size, CHUNK):
                    f.write(base64.b64decode(page.evaluate("([a, n]) => __vt.chunk(a, n)", [at, CHUNK])))
        else:
            report["errors"].append("the game made no sound")
    finally:
        enc.stdin.close()
        enc.wait()
        ctx.close()
    # frame k (from 0) is the page at virtual time (k + 1) step, shown at k step in the video; the sound's own
    # clock started at t0 on the page's clock
    return video, wav, (t0 - 1000.0 / fps) / 1000.0 if wav else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True, help="the game file on disk, opened as file://")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    spec = json.load(open(a.spec, encoding="utf-8"))
    report = {"ok": False, "errors": [], "files": [], "values": {}, "spec_problems": check_spec(spec)}
    if report["spec_problems"]:
        print(json.dumps(report, indent=2))
        sys.exit(1)
    url = "file://" + os.path.abspath(a.html)
    fps = spec["fps"]

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        report["probe"] = probe_seeds(browser, url, spec, report)
        chosen = choose_seed(report["probe"], spec["max_game_seconds"])
        report["chosen"] = chosen
        recorded = False
        if not chosen:
            report["errors"].append("no seed finished within %s s" % spec["max_game_seconds"])
        else:
            try:
                video, wav, offset = record(browser, url, spec, chosen["seed"], a.out, report)
                recorded = True
            except Exception as e:  # report, don't hide
                report["errors"].append("recording failed: %r" % e)
        browser.close()

    if recorded:
        v = report["values"]
        if v.get("game_frames") != chosen["updates"]:
            report["errors"].append("the recording ended on frame %s of play, the probe on %s: not deterministic"
                                    % (v.get("game_frames"), chosen["updates"]))
        mp4 = os.path.join(a.out, "gameplay.mp4")
        if wav:
            subprocess.run(mux_cmd(video, wav, offset, mp4), check=True)
            os.remove(video)
        else:
            os.replace(video, mp4)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.5", "-i", mp4, "-frames:v", "1",
                        os.path.join(a.out, "last-frame.png")])
        report["video"] = {"fps": fps, "frames": v.get("video_frames"), "mp4_seconds": round(duration(mp4), 2),
                           "game_seconds": round(v.get("game_frames", 0) / fps, 2)}
        if not spec.get("min_seconds", 0) <= report["video"]["mp4_seconds"] <= spec["max_seconds"]:
            report["errors"].append("video length %s s is outside the limits" % report["video"]["mp4_seconds"])
        if wav:
            vol = subprocess.run(["ffmpeg", "-hide_banner", "-i", mp4, "-map", "0:a:0", "-af", "volumedetect",
                                  "-f", "null", "-"], capture_output=True, text=True)
            au = report["video"]["audio"] = dict(loudness(vol.stderr), offset_seconds=round(offset, 3),
                                                 wav_seconds=round(duration(wav), 2),
                                                 mp4_audio_seconds=round(duration(mp4, "a"), 2))
            if au["max_volume"] is None or au["max_volume"] < -50:
                report["errors"].append("the video's sound is silent or missing: %r" % au)
            if abs(au["mp4_audio_seconds"] - report["video"]["mp4_seconds"]) > 0.5:
                report["errors"].append("the sound does not run the whole video: %r" % au)

    report["ok"] = not report["errors"]
    with open(os.path.join(a.out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
