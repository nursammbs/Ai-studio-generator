#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "Install FFmpeg first."; exit 1; }
command -v ffprobe >/dev/null || { echo "Install ffprobe first (usually included with FFmpeg)."; exit 1; }
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
