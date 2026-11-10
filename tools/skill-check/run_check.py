# run_check.py - runs every check of skills/jamshell/SKILL.md against a fresh jamshell clone, in a sandbox.
# Part of jamshell by MV2 of Munim, Inc. (mv2@munimtech.com), made with AI agents. Apache-2.0.
#
#   python run_check.py --repo /work/jamshell --skill /work/skills/jamshell/SKILL.md --out /out
#
# Checks (each recorded with its exit code in <out>/checks.json; the run passes only if all pass):
#   quickstart  the skill's step-1 unit-test command, run inside the clone
#   build       skillcheck.py build: splice the example game into shell.html, write steps.json
#   playcheck   the clone's playcheck.py with the skill's example steps (self-test + both viewports),
#               run with --skip-video exactly as the skill's step 5 says
#   package     the clone's package.py with --credits "with AI agents"
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(name, cmd, cwd, log_dir):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    with open(os.path.join(log_dir, name + ".log"), "w", encoding="utf-8") as f:
        f.write("$ " + " ".join(cmd) + "\n" + p.stdout + "\n--- stderr ---\n" + p.stderr)
    tail = (p.stdout + p.stderr).strip().splitlines()[-8:]
    print("== %s exit=%d\n%s" % (name, p.returncode, "\n".join(tail)), flush=True)
    return {"name": name, "exit": p.returncode}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    logs = os.path.join(a.out, "logs")
    os.makedirs(logs, exist_ok=True)
    build_dir = os.path.join(a.out, "build")
    py = sys.executable
    checks = [
        run("quickstart", [py, "-m", "unittest", "-v", "test_jamshell.py", "test_package.py",
                           "test_framewalk.py", "test_langleak.py"], a.repo, logs),
        run("build", [py, os.path.join(HERE, "skillcheck.py"), "build", "--skill", a.skill,
                      "--shell", os.path.join(a.repo, "shell.html"), "--out", build_dir], a.repo, logs),
    ]
    if checks[-1]["exit"] == 0:
        checks.append(run("playcheck", [py, "playcheck.py", "--html", os.path.join(build_dir, "dist", "index.html"),
                                        "--steps", os.path.join(build_dir, "steps.json"),
                                        "--out", os.path.join(a.out, "playcheck"), "--skip-video"], a.repo, logs))
        os.makedirs(os.path.join(a.out, "package"), exist_ok=True)
        checks.append(run("package", [py, "package.py", "--dist", os.path.join(build_dir, "dist"),
                                      "--zip", os.path.join(a.out, "package", "star-catch-itch.zip"),
                                      "--credits", "with AI agents"], a.repo, logs))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=a.repo, capture_output=True, text=True).stdout.strip()
    result = {"jamshell_commit": commit, "checks": checks,
              "passed": len(checks) == 4 and all(c["exit"] == 0 for c in checks)}
    report = os.path.join(a.out, "playcheck", "report.json")
    if os.path.exists(report):
        with open(report, encoding="utf-8") as f:
            r = json.load(f)
        result["playcheck"] = {"ok": r.get("ok"), "errors": r.get("errors"), "values": r.get("values"),
                               "selftest_text": r.get("selftest_text")}
    build_json = os.path.join(build_dir, "build.json")
    if os.path.exists(build_json):
        with open(build_json, encoding="utf-8") as f:
            result["build"] = json.load(f)
    with open(os.path.join(a.out, "checks.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
