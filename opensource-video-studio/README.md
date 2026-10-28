# Open Source Video Studio

A local-first starter app for creating review-ready YouTube video drafts from a topic. It uses open-source Python libraries, Wikipedia as a starting point for research, Wikimedia Commons images when reuse-friendly license metadata is available, and FFmpeg for rendering.

## Features

- Research starter sources and retain source URLs.
- Optional local script drafting with Ollama; no paid LLM API key is required.
- Create narration with Edge TTS; try system TTS through pyttsx3 if Edge TTS fails.
- Search Wikimedia Commons for images whose metadata suggests a reuse-friendly license.
- Render vertical 9:16 Shorts or horizontal 16:9 video.
- Save MP4, thumbnail, script, research sources, and image attribution.
- No automatic upload, so you can review the result before publishing.

## Requirements

- Python 3.10+
- FFmpeg and ffprobe available on PATH
- Internet for Wikipedia, Wikimedia Commons, and Edge TTS
- Optional: Ollama plus a local model such as qwen2.5:3b

## Install

Windows: install Python and FFmpeg, and add FFmpeg's bin folder to PATH. macOS users can install Python and FFmpeg with Homebrew. Ubuntu/Debian users can run: sudo apt install python3 python3-venv ffmpeg.

Optional local model: install Ollama, then run: ollama pull qwen2.5:3b

Quick launch: Windows users can double-click run_windows.bat after Python and FFmpeg are installed. macOS/Linux users can run bash run_unix.sh. To install manually, from this folder create a virtual environment, activate it, then run:

    python -m venv .venv
    # Windows PowerShell: .venv\Scripts\Activate.ps1
    # macOS/Linux: source .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    streamlit run app.py

If Ollama mode is enabled, ensure the local Ollama service is running and the selected model is downloaded.

## Responsible publishing

Generated text is a draft, not a fact-check. Verify dates, names, statistics, and claims against reliable sources. Wikipedia is a starting point, not proof of every claim. Check the license on each image's original file page; the automatic filter is not a legal guarantee. Keep author, source, and license attribution. Do not use copyrighted music or clips without permission. Review YouTube's rules on repetitive content and synthetic media. This project does not promise views, monetization, or income.

## Current limitations

This is an MVP, not a finished content factory. Script quality varies; Commons may return no suitable images; subtitle generation, upload scheduling, analytics, and automatic fact-checking are not implemented. Computer rendering is required; this is not a mobile-only app.

## License

MIT for this project's code. External services, models, voices, fonts, and media remain subject to their own terms and licenses.
