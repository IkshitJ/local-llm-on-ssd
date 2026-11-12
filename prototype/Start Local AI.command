#!/bin/zsh
# Starts the local 35B model with expert streaming and opens the chat page.
# Listens on this Mac only (127.0.0.1). Close with "Stop Local AI.command".
cd "$(dirname "$0")"
if curl -s --max-time 2 http://127.0.0.1:8089/health | grep -q ok; then
  echo "Already running."; open http://127.0.0.1:8089; exit 0
fi
mkdir -p results
# 3 GiB expert cache: fastest setting that did not swap in testing. Thinking off: too slow at ~9 tokens/s.
nohup ./llama.cpp/build/bin/llama-server -m models/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf \
  --host 127.0.0.1 --port 8089 -c 16384 -ngl all --moe-stream-cache 3 --no-warmup -np 1 \
  --reasoning off -a qwen3.6-35b-local > results/server_app.log 2>&1 &
disown
echo "Loading model..."
for i in {1..60}; do
  curl -s --max-time 2 http://127.0.0.1:8089/health | grep -q ok && break; sleep 1
done
if curl -s --max-time 2 http://127.0.0.1:8089/health | grep -q ok; then
  echo "Ready: http://127.0.0.1:8089"; open http://127.0.0.1:8089
else
  echo "Did not start. See results/server_app.log"; tail -5 results/server_app.log; exit 1
fi
