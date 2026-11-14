# Open Source Video Studio

A local-first starter app for creating review-ready YouTube video drafts from a topic. It uses open-source Python libraries, Wikipedia as a starting point for research, Wikimedia Commons images when reuse-friendly license metadata is available, and FFmpeg for rendering.

## Features

- Research starter sources and retain source URLs.
- Optional local script drafting with Ollama; no paid LLM API key is required.
- Create narration with Edge TTS; fall back to system TTS through pyttsx3 in automatic mode.
- Optionally use VoiceStudio through its OpenAI-compatible local TTS API; no VoiceStudio source code or model weights are bundled.
- Search Wikimedia Commons for images whose metadata suggests a reuse-friendly license.
- Render vertical 9:16 Shorts or horizontal 16:9 video.
- Save MP4, thumbnail, script, research sources, and image attribution.
- No automatic upload, so you can review the result before publishing.

## Requirements

- Python 3.10+
- FFmpeg and ffprobe available on PATH
- Internet for Wikipedia and Wikimedia Commons; Edge TTS needs internet.
- Optional: a running VoiceStudio backend with a configured TTS engine/model. Its compute needs depend on the selected engine; this integration does not make GPU-heavy models CPU-friendly.
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

### Optional VoiceStudio narration

1. Install and start [VoiceStudio](https://github.com/debpalash/VoiceStudio) separately.
2. In VoiceStudio, configure and load a TTS engine/model that supports speech generation.
3. Keep the VoiceStudio backend on the local computer. Its default local API is `http://127.0.0.1:3900`.
4. In this app, choose **VoiceStudio local (OpenAI-compatible API)** under **Mesin narasi**. The default API base is `http://127.0.0.1:3900/v1`, model alias `tts-1`, and voice alias `alloy` (VoiceStudio maps the OpenAI aliases to its active engine's default voice).
5. For a custom local setup, set `VOICESTUDIO_BASE_URL`, `VOICESTUDIO_MODEL`, and `VOICESTUDIO_VOICE` in the environment or edit the values in the form.

The adapter sends text to `POST /v1/audio/speech` and expects MP3 audio. It uses an optional `VOICESTUDIO_API_KEY` from the environment or the password field. Remote endpoints are refused unless they use HTTPS **and** an API key. Never expose an unauthenticated VoiceStudio server to the public internet. VoiceStudio application code is AGPL-3.0; this project only calls its HTTP API and does not bundle its source code. Each installed model/voice may have its own license and usage restrictions—check those before commercial use.

The existing automatic voice mode remains the default and continues to use Edge TTS followed by system TTS. Choosing VoiceStudio is explicit: if its endpoint or model is unavailable, the render stops with an error instead of silently switching to a different voice.

## Responsible publishing

Generated text is a draft, not a fact-check. Verify dates, names, statistics, and claims against reliable sources. Wikipedia is a starting point, not proof of every claim. Check the license on each image's original file page; the automatic filter is not a legal guarantee. Keep author, source, and license attribution. Do not use copyrighted music or clips without permission. Review YouTube's rules on repetitive content and synthetic media. This project does not promise views, monetization, or income.

## Current limitations

This is an MVP, not a finished content factory. Script quality varies; Commons may return no suitable images; subtitle generation, upload scheduling, analytics, and automatic fact-checking are not implemented. Computer rendering is required; this is not a mobile-only app.

## License

MIT for this project's code. External services, models, voices, fonts, and media remain subject to their own terms and licenses.
