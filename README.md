# Local LLM on SSD

Prototype for running a large mixture-of-experts LLM on a 16 GB Mac by streaming expert weights from the SSD instead of holding the whole model in RAM.

- `Local-LLM-on-SSD-Pitch.pdf`: pitch deck
- `prototype/harness/`: speed benchmark (`bench.py`), quality runner on the Aider Polyglot Python exercises (`quality.py`), resumable model downloader (`download.sh`)
- `prototype/results/`: measured speed, quality and server logs
- `prototype/Start Local AI.command` / `Stop Local AI.command`: start/stop a local chat server on 127.0.0.1:8089

## Not in this repo (recreate them)

**Model** (22,134,528,992 bytes, ~21 GB): `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf` in `prototype/models/`. SHA-256 is in `prototype/models/expected.txt`.

**llama.cpp with expert streaming** (PR #25294), into `prototype/llama.cpp`:

```sh
cd prototype
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
git fetch origin pull/25294/head:pr-25294 && git checkout pr-25294   # tested at 1248fd8fa
cmake -B build && cmake --build build --config Release -j
```

**Aider Polyglot benchmark**, into `prototype/polyglot-benchmark` (tested at 7e0611e):

```sh
git clone https://github.com/Aider-AI/polyglot-benchmark.git prototype/polyglot-benchmark
```

The harness scripts use only the Python standard library.
