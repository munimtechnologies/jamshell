"""Browser playtest, screenshots and gameplay video for any single-file HTML game (Apache-2.0).
By MV2 of Munim, Inc., made with AI agents (Anthropic Claude).

Built so a game made inside a jam window needs only a steps file to be checked in one compete job:

    python3 playcheck.py --html dist/index.html --steps steps.json --out /out
    python3 playcheck.py --url http://127.0.0.1:5099/ --steps steps.json --out /out --skip-video

--html opens a file on disk (file://), the way the first checks of a jam game run. --url opens a page a server
already offers: the Windows wrapper (winwrap, Neutralinojs) serves the game from its own local http server,
so a check against that server runs the same selftest and steps the way the .exe would show them. --skip-video
runs every step but records no video, so the job needs no ffmpeg. (Added 2026-10-18 for the wrapper check.)

steps.json:
    {"selftest": {"hash": "#selftest", "text": "No problems found.", "timeout_ms": 60000},
     "viewports": [{"name": "desktop", "width": 1280, "height": 720},
                   {"name": "phone", "width": 720, "height": 1280, "touch": true},
                   {"name": "calm", "width": 720, "height": 1280, "touch": true, "reduced_motion": true}],
     "steps": [{"wait": 800}, {"shot": "title"}, {"click": "text=Play"}, {"key": "ArrowLeft", "times": 3},
               {"tap": [0.5, 0.6]}, {"eval": "G.on", "save": "playing", "expect": true}, {"shot": "play"},
               {"drag": [0.5, 0.7, 0.8, 0.7], "probe": "stick.x > 0.9", "save": "stick", "expect": true}],
     "video": {"viewport": "phone", "min_seconds": 20, "max_seconds": 60, "steps": [...]}}

Every step list runs once per viewport (screenshots are named <viewport>-<shot>.png); "video" runs once
more, recorded, with a dot drawn where the mouse is because headless recordings show no cursor. A step
may carry "only": "<viewport name>". A viewport with "reduced_motion": true asks the page for reduced
motion, the way a player's system setting would. A "drag" presses the mouse at the first point (fractions
of the viewport), moves to the second, holds ("hold" ms, default 150), evaluates its "probe" while still
pressed (saved and checked like an eval), then lets go. The run fails on any page error, console error or
warning, a missing self-test text, a step that throws, or a video outside its length limits. A long video
is sped up evenly (at most 1.5x) instead of cut, and its last frame is saved so a person can see how it ends.
Writes report.json, the PNGs, gameplay.mp4 and last-frame.png.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.parse

CURSOR = """()=>{
  const d=document.createElement("div");
  d.style.cssText="position:fixed;left:0;top:0;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;"+
    "background:rgba(255,255,255,.85);box-shadow:0 0 0 2px rgba(0,0,0,.45);pointer-events:none;z-index:99999;"+
    "transition:transform .12s";
  document.body.append(d);
  addEventListener("mousemove",e=>{d.style.left=e.clientX+"px";d.style.top=e.clientY+"px";});
  addEventListener("mousedown",()=>d.style.transform="scale(.6)");
  addEventListener("mouseup",()=>d.style.transform="");
}"""

STEP_KEYS = {"wait", "shot", "click", "key", "tap", "eval", "type", "drag"}


def page_url(html=None, url=None):
    """The address the browser opens: a file on disk (file://), or a page a server already offers, such as the
    Windows wrapper's own http://127.0.0.1:<port>/. Exactly one of the two. A served address ends in a path, so
    the steps file's "#selftest" can be appended to it."""
    if (html is None) == (url is None):
        raise ValueError("give exactly one of html or url")
    if html is not None:
        return "file://" + os.path.abspath(html)
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("url must start with http:// or https:// and name a host: %r" % url)
    if parts.query or parts.fragment:
        raise ValueError("url must carry no query or #hash (the steps file adds the hash): %r" % url)
    return url if parts.path else url + "/"


def check_steps(spec):
    """Problems in a steps file, found before any browser starts."""
    problems = []
    names = {v.get("name") for v in spec.get("viewports", [])}
    if not names:
        problems.append("no viewports")
    lists = [("steps", spec.get("steps", []))]
    if spec.get("video"):
        lists.append(("video.steps", spec["video"].get("steps", [])))
        if spec["video"].get("viewport") not in names:
            problems.append("video.viewport is not one of the viewports")
    for where, steps in lists:
        for i, s in enumerate(steps):
            kinds = STEP_KEYS & set(s)
            if len(kinds) != 1:
                problems.append("%s[%d]: needs exactly one of %s" % (where, i, sorted(STEP_KEYS)))
            if "only" in s and s["only"] not in names:
                problems.append("%s[%d]: only=%r is not a viewport" % (where, i, s["only"]))
            if "tap" in s and not (len(s["tap"]) == 2 and all(0 <= f <= 1 for f in s["tap"])):
                problems.append("%s[%d]: tap takes two fractions of the viewport" % (where, i))
            if "drag" in s and not (len(s["drag"]) == 4 and all(0 <= f <= 1 for f in s["drag"])):
                problems.append("%s[%d]: drag takes four fractions of the viewport (x0, y0, x1, y1)" % (where, i))
            if "probe" in s and "drag" not in s:
                problems.append("%s[%d]: probe belongs to a drag step" % (where, i))
    return problems


def context_options(vp):
    """Playwright new_context() options for one viewport entry."""
    return {"viewport": {"width": vp["width"], "height": vp["height"]},
            "has_touch": bool(vp.get("touch")), "is_mobile": bool(vp.get("touch")),
            "reduced_motion": "reduce" if vp.get("reduced_motion") else "no-preference"}


def drag_points(frac, vp):
    """A drag step's four viewport fractions -> two (x, y) points in CSS pixels."""
    x0, y0, x1, y1 = frac
    return (x0 * vp["width"], y0 * vp["height"]), (x1 * vp["width"], y1 * vp["height"])


def watch(page, report, label):
    page.on("pageerror", lambda e: report["errors"].append("%s pageerror: %s" % (label, e)))
    page.on("console", lambda m: report["errors"].append("%s console %s: %s" % (label, m.type, m.text))
            if m.type in ("error", "warning") else None)


def record(s, value, vp, i, what, report):
    """Save and check one evaluated value the same way for eval and drag probes."""
    if s.get("save"):
        report["values"]["%s.%s" % (vp["name"], s["save"])] = value
    if "expect" in s and value != s["expect"]:
        report["errors"].append("%s step %d: %s gave %r, expected %r" % (vp["name"], i, what, value, s["expect"]))


def run_steps(page, steps, vp, report, out, glide=False):
    for i, s in enumerate(steps):
        if s.get("only") and s["only"] != vp["name"]:
            continue
        try:
            if "wait" in s:
                page.wait_for_timeout(s["wait"])
            elif "shot" in s:
                name = "%s-%s.png" % (vp["name"], s["shot"])
                page.screenshot(path=os.path.join(out, name), full_page=s.get("full", False))
                report["files"].append(name)
            elif "click" in s:
                loc = page.locator(s["click"]).first
                if glide:  # move the mouse there the way a person would, so the video is followable
                    box = loc.bounding_box()
                    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=12)
                    page.wait_for_timeout(200)
                loc.click()
            elif "key" in s:
                for _ in range(s.get("times", 1)):
                    page.keyboard.press(s["key"])
                    page.wait_for_timeout(s.get("gap", 60))
            elif "type" in s:
                page.keyboard.type(s["type"])
            elif "tap" in s:
                x, y = s["tap"][0] * vp["width"], s["tap"][1] * vp["height"]
                if vp.get("touch"):
                    page.touchscreen.tap(x, y)
                else:
                    page.mouse.move(x, y, steps=12 if glide else 1)
                    page.mouse.click(x, y)
            elif "drag" in s:
                (x0, y0), (x1, y1) = drag_points(s["drag"], vp)
                page.mouse.move(x0, y0)
                page.mouse.down()
                try:
                    page.mouse.move(x1, y1, steps=s.get("moves", 10))
                    page.wait_for_timeout(s.get("hold", 150))
                    if s.get("probe"):
                        record(s, page.evaluate(s["probe"]), vp, i, s["probe"], report)
                finally:
                    page.mouse.up()
            elif "eval" in s:
                record(s, page.evaluate(s["eval"]), vp, i, s["eval"], report)
            if s.get("after"):
                page.wait_for_timeout(s["after"])
        except Exception as e:  # report, don't hide
            report["errors"].append("%s step %d %s: %r" % (vp["name"], i, json.dumps(s), e))
            return False
    return True


def duration(path):
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", path], capture_output=True, text=True)
    try:
        return float(probe.stdout.strip())
    except ValueError:
        return 0.0


def fit_speed(raw, max_seconds):
    """Even speed-up that fits a recording into max_seconds (never below 1x)."""
    return max(1.0, raw / (max_seconds - 1)) if raw else 1.0


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--html", help="a game file on disk, opened as file://")
    src.add_argument("--url", help="a page a server already offers, such as the wrapper's http://127.0.0.1:5099/")
    ap.add_argument("--steps", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-video", action="store_true", help="run the steps but record no video (no ffmpeg needed)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    spec = json.load(open(a.steps, encoding="utf-8"))
    report = {"ok": False, "errors": [], "files": [], "values": {}, "spec_problems": check_steps(spec)}
    if report["spec_problems"]:
        print(json.dumps(report, indent=2))
        sys.exit(1)
    try:
        url = page_url(a.html, a.url)
    except ValueError as e:
        report["spec_problems"].append(str(e))
        print(json.dumps(report, indent=2))
        sys.exit(1)
    report["url"] = url
    report["video_skipped"] = bool(a.skip_video)
    vps = {v["name"]: v for v in spec["viewports"]}
    video = None if a.skip_video else spec.get("video")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()

        st = spec.get("selftest")
        if st:
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            watch(page, report, "selftest")
            page.goto(url + st.get("hash", "#selftest"))
            try:
                page.wait_for_selector("text=" + st["text"], timeout=st.get("timeout_ms", 60000))
                report["selftest"] = "found: " + st["text"]
            except Exception as e:
                report["errors"].append("selftest text not found: %r" % e)
            try:
                report["selftest_text"] = page.inner_text("#selftest", timeout=2000)
            except Exception:
                pass
            page.screenshot(path=os.path.join(a.out, "selftest.png"))
            report["files"].append("selftest.png")
            page.close()

        for vp in spec["viewports"]:
            ctx = browser.new_context(**context_options(vp))
            page = ctx.new_page()
            watch(page, report, vp["name"])
            page.goto(url)
            run_steps(page, spec.get("steps", []), vp, report, a.out)
            ctx.close()

        if video:
            vp = vps[video["viewport"]]
            raw_dir = os.path.join(a.out, "raw")
            size = {"width": vp["width"], "height": vp["height"]}
            ctx = browser.new_context(viewport=size, record_video_dir=raw_dir, record_video_size=size,
                                      has_touch=bool(vp.get("touch")))
            page = ctx.new_page()
            watch(page, report, "video")
            page.goto(url)
            page.evaluate(CURSOR)
            page.mouse.move(vp["width"] / 2, vp["height"] / 2)
            run_steps(page, video.get("steps", []), dict(vp, touch=False), report, a.out, glide=True)
            rec = page.video
            page.close()
            ctx.close()
            webm = os.path.join(a.out, "gameplay.webm")
            shutil.move(rec.path(), webm)
            shutil.rmtree(raw_dir, ignore_errors=True)
        browser.close()

    if video:
        raw = duration(webm)
        speed = fit_speed(raw, video["max_seconds"])
        mp4 = os.path.join(a.out, "gameplay.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", webm, "-vf", "setpts=PTS/%.5f" % speed,
                        "-t", str(video["max_seconds"]), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                        "-movflags", "+faststart", "-an", mp4], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.5", "-i", mp4, "-frames:v", "1",
                        os.path.join(a.out, "last-frame.png")])
        report["video"] = {"raw_seconds": round(raw, 1), "speed": round(speed, 3),
                           "mp4_seconds": round(duration(mp4), 1)}
        v = report["video"]
        if not (video.get("min_seconds", 0) <= v["mp4_seconds"] <= video["max_seconds"] and speed <= 1.5):
            report["errors"].append("video length %s s at speed %s is outside the limits" % (v["mp4_seconds"], speed))

    report["ok"] = not report["errors"]
    with open(os.path.join(a.out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
