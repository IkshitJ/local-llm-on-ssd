#!/usr/bin/env python3
"""Speed harness: starts llama-server with expert streaming at several cache sizes,
measures tokens/s, time to first token and memory pressure, writes results/speed.json.

Usage: bench.py <model.gguf> [cache_gib ...]      (stdlib only)
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "llama.cpp", "build", "bin", "llama-server")
PORT = 8089
URL = f"http://127.0.0.1:{PORT}"

SHORT = "Write a Python function that merges overlapping intervals in a list of (start, end) tuples. Include a short docstring and two test cases."


def long_prompt():
    # ~2,000 tokens of real code as context, the shape of an IDE request
    src = open(os.path.join(ROOT, "llama.cpp", "common", "sampling.cpp")).read()[:7000]
    return "Review this C++ file excerpt. List the three most likely bugs or risks, each with the line it is on.\n\n```cpp\n" + src + "\n```"


def post(path, body, timeout=1800):
    req = urllib.request.Request(URL + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def swapouts():
    out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    m = re.search(r"Swapouts:\s+(\d+)", out)
    return int(m.group(1)) if m else -1


def free_pct():
    out = subprocess.run(["memory_pressure"], capture_output=True, text=True).stdout
    m = re.search(r"free percentage:\s+(\d+)%", out)
    return int(m.group(1)) if m else -1


def start(model, cache, extra):
    log = open(os.path.join(ROOT, "results", f"server_cache{cache}.log"), "w")
    cmd = [SERVER, "-m", model, "--port", str(PORT), "-c", "8192", "-ngl", "all",
           "--moe-stream-cache", str(cache), "--no-warmup", "-np", "1"] + extra
    p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < 600:
        if p.poll() is not None:
            return None, time.time() - t0
        try:
            if json.load(urllib.request.urlopen(URL + "/health", timeout=2)).get("status") == "ok":
                return p, time.time() - t0
        except Exception:
            time.sleep(1)
    p.kill()
    return None, time.time() - t0


def ask(prompt, n):
    t0 = time.time()
    r = post("/v1/chat/completions", {"messages": [{"role": "user", "content": prompt}],
                                      "max_tokens": n, "temperature": 0.2, "cache_prompt": False})
    t = r["timings"]
    assert t["predicted_n"] > 0, "no tokens generated"
    return {"prompt_tokens": t["prompt_n"], "prompt_tps": round(t["prompt_per_second"], 2),
            "first_token_s": round(t["prompt_ms"] / 1000, 1), "gen_tokens": t["predicted_n"],
            "gen_tps": round(t["predicted_per_second"], 2), "wall_s": round(time.time() - t0, 1)}


def main():
    model = sys.argv[1]
    caches = sys.argv[2:] or ["6"]
    extra = os.environ.get("EXTRA", "").split()
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    results = []
    for cache in caches:
        s0 = swapouts()
        p, load_s = start(model, cache, extra)
        row = {"cache_gib": cache, "extra": extra, "load_s": round(load_s, 1)}
        if p is None:
            row["error"] = "server failed to start; see results/server_cache%s.log" % cache
        else:
            try:
                row["short_cold"] = ask(SHORT, 200)
                row["short_warm"] = ask(SHORT + " Use type hints.", 200)
                row["long"] = ask(long_prompt(), 200)
                row["free_mem_pct"] = free_pct()
                rss = subprocess.run(["ps", "-o", "rss=", "-p", str(p.pid)], capture_output=True, text=True).stdout
                row["server_rss_gib"] = round(int(rss.strip() or 0) / 1048576, 2)
            except Exception as e:  # keep going so one bad config does not lose the rest
                row["error"] = repr(e)
            p.terminate()
            try:
                p.wait(30)
            except subprocess.TimeoutExpired:
                p.kill()
        row["swapouts_during"] = swapouts() - s0
        results.append(row)
        print(json.dumps(row), flush=True)
        json.dump(results, open(os.path.join(ROOT, "results", "speed.json"), "w"), indent=1)
        time.sleep(5)


if __name__ == "__main__":
    main()
