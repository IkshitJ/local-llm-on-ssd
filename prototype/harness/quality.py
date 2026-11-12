#!/usr/bin/env python3
"""Quality runner: the 34 Python exercises of the Aider Polyglot benchmark, two attempts each
(second attempt sees the failing test output), the same rule Aider uses. Stdlib only.

Usage: quality.py [--selfcheck] [--limit N] [--max-tokens N] [--url http://127.0.0.1:8089]
  --selfcheck  uses each exercise's reference solution instead of the model, to prove the runner works.

Generated code is executed locally with a 60 s timeout inside results/quality/work/.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "polyglot-benchmark", "python", "exercises", "practice")
WORK = os.path.join(ROOT, "results", "quality", "work")


def read(p):
    return open(p).read() if os.path.exists(p) else ""


def chat(url, messages, max_tokens):
    # thinking off: with it on, one answer ran past 4,096 tokens (9 min at ~8 tok/s) without finishing
    body = {"messages": messages, "max_tokens": max_tokens, "temperature": 0.2,
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(url + "/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=3600))
    return r["choices"][0]["message"].get("content") or "", r.get("timings", {})


def code_block(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    return max(blocks, key=len) if blocks else None


def run_tests(d, test):
    try:
        p = subprocess.run([sys.executable, "-m", "unittest", test], cwd=d, capture_output=True, text=True, timeout=60)
        return p.returncode == 0, (p.stdout + p.stderr)[-2500:]
    except subprocess.TimeoutExpired:
        return False, "tests timed out after 60 s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=2500)
    ap.add_argument("--url", default="http://127.0.0.1:8089")
    a = ap.parse_args()
    names = sorted(os.listdir(EX))[: a.limit or None]
    out_path = os.path.join(ROOT, "results", "quality_selfcheck.json" if a.selfcheck else "quality.json")
    # resume: keep finished exercises from an interrupted run
    rows = [r for r in (json.load(open(out_path)) if os.path.exists(out_path) else []) if "error" not in r]
    done = {r["exercise"] for r in rows}
    for n in names:
        if n in done:
            continue
        src = os.path.join(EX, n)
        cfg = json.load(open(os.path.join(src, ".meta", "config.json")))["files"]
        sol, test = cfg["solution"][0], cfg["test"][0]
        d = os.path.join(WORK, n)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        for f in os.listdir(src):  # stub, tests and any helper files; not .meta (holds the answer)
            if os.path.isfile(os.path.join(src, f)):
                shutil.copy(os.path.join(src, f), d)
        row = {"exercise": n, "passed_try": 0, "gen_tokens": 0, "seconds": 0.0}
        t0 = time.time()
        if a.selfcheck:
            shutil.copy(os.path.join(src, cfg["example"][0]), os.path.join(d, sol))
            row["passed_try"] = 1 if run_tests(d, test)[0] else 0
        else:
            instr = read(os.path.join(src, ".docs", "instructions.md")) + "\n" + read(os.path.join(src, ".docs", "instructions.append.md"))
            msgs = [{"role": "user", "content": f"{instr}\n\nImplement the solution in `{sol}`. Keep the existing function and class names; "
                     f"use only the standard library. Current contents of `{sol}`:\n\n```python\n{read(os.path.join(d, sol))}\n```\n\n"
                     f"Reply with the complete new contents of `{sol}` in one ```python block."}]
            for attempt in (1, 2):
                try:
                    text, tm = chat(a.url, msgs, a.max_tokens)
                except Exception as e:
                    row["error"] = repr(e)
                    break
                row["gen_tokens"] += tm.get("predicted_n", 0)
                code = code_block(text)
                if code:
                    open(os.path.join(d, sol), "w").write(code)
                ok, log = run_tests(d, test) if code else (False, "no code block in reply")
                if ok:
                    row["passed_try"] = attempt
                    break
                msgs += [{"role": "assistant", "content": text},
                         {"role": "user", "content": f"The tests failed:\n\n```\n{log}\n```\n\nFix `{sol}` and reply with its complete contents in one ```python block."}]
        row["seconds"] = round(time.time() - t0, 1)
        rows.append(row)
        print(json.dumps(row), flush=True)
        json.dump(rows, open(out_path, "w"), indent=1)
    p1 = sum(r["passed_try"] == 1 for r in rows)
    p2 = sum(r["passed_try"] in (1, 2) for r in rows)
    print(f"\n{len(rows)} exercises: pass on first try {p1} ({100 * p1 / len(rows):.1f}%), within two tries {p2} ({100 * p2 / len(rows):.1f}%)")


if __name__ == "__main__":
    main()
