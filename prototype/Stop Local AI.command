#!/bin/zsh
pkill -f "llama-server -m models/Qwen3.6-35B-A3B" && echo "Stopped." || echo "Was not running."
