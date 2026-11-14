# Quick Video Studio — CPU-first MVP

A minimal local script-to-MP4 path. It turns a JSON scene list into a vertical H.264 video and a companion SRT subtitle file. It does not require a GPU, cloud account, paid API, LLM, or diffusion model.

## What it does

- Creates clean 9:16 scene cards from titles and narration text.
- Renders each scene with Pillow and encodes MP4 segments with FFmpeg.
- Concatenates scenes into one MP4.
- Accepts optional narration audio (WAV/MP3/M4A).
- Exports a companion SRT file.
- Validates the final MP4 with ffprobe.

This is deliberately a deterministic first milestone, not AI-generated cinematic footage. It proves the production/export path before expensive models are added.

## Requirements

- Python 3.10+
- FFmpeg and ffprobe available on PATH, with H.264/libx264 support
- Pillow

## Install

### Windows PowerShell

```powershell
cd quick-video-studio
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install Pillow
ffmpeg -version
ffprobe -version
```

### macOS

```bash
brew install ffmpeg
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip Pillow
```

### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg python3-venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip Pillow
```

## Generate the sample

```bash
python render.py example.json --output output.mp4
```

With a narration file:

```bash
python render.py example.json --narration narration.wav --output output.mp4
```

Outputs:
- `output.mp4` — vertical 1080×1920 H.264 video
- `output.srt` — scene-level subtitle timing

You can change the scene text, duration (seconds), and background color in the JSON manifest. Keep each scene short and the copy concise.

## Current limits

- Text is displayed as designed scene cards; SRT is scene-level, not word-synchronized.
- Narration is supplied by the user; this MVP does not synthesize speech.
- No stock-footage search, AI image generation, character consistency, face tracking, or timeline editor yet.
- Output quality and render speed depend on the computer and installed FFmpeg build.
- Do not use copyrighted footage, voices, music, or images without the necessary rights.

## Next integration points

1. Add an optional local/cloud LLM script adapter behind an explicit provider setting.
2. Add optional TTS providers without making them mandatory.
3. Reuse the existing Revenue Engine clipper for repurposing long videos into Shorts.
4. Add ComfyUI/Wan only when GPU availability and model licensing are verified.
