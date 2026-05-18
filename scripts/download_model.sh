#!/usr/bin/env bash
# Download a Llama-3-8B-Instruct GGUF for the llama.cpp backend.
#
# Q4_K_M is a good balance: 4.6GB, runs on CPU, quality close to FP16
# for this kind of structured extraction task.
#
# Usage: ./scripts/download_model.sh
set -euo pipefail

MODEL_DIR="${MODEL_DIR:-./models}"
MODEL_FILE="Meta-Llama-3-8B-Instruct.Q4_K_M.gguf"
MODEL_URL="https://huggingface.co/QuantFactory/Meta-Llama-3-8B-Instruct-GGUF/resolve/main/${MODEL_FILE}"

mkdir -p "$MODEL_DIR"
cd "$MODEL_DIR"

if [ -f "$MODEL_FILE" ]; then
    echo "Model already exists at $MODEL_DIR/$MODEL_FILE"
    exit 0
fi

echo "Downloading $MODEL_FILE (~4.6GB)..."
if [ -n "${HF_TOKEN:-}" ]; then
    curl -L -H "Authorization: Bearer $HF_TOKEN" -o "$MODEL_FILE" "$MODEL_URL"
else
    curl -L -o "$MODEL_FILE" "$MODEL_URL"
fi

echo "Done. Model at $MODEL_DIR/$MODEL_FILE"
