# AI Media Studio

A local-first workspace for creating and reviewing original videos, animations, and media assets. The core direction is **creative production**, not an UMKM promotion or small-business marketing product.

The repository contains separate modules. They are not one monolithic application; each has its own dependencies and maturity level. The preferred low-cost path uses Python, Pillow, and FFmpeg. AI models and cloud APIs are optional and must be evaluated separately for hardware needs, cost, and license.

## Production modules

### Open Source Video Studio

[Open Source Video Studio](opensource-video-studio/README.md) creates a reviewable video draft from a topic:

1. Collects starter references from Wikipedia.
2. Drafts narration with an optional local Ollama model or a deterministic fallback.
3. Generates narration with Edge TTS or system TTS; VoiceStudio is available as an optional OpenAI-compatible local TTS backend.
4. Finds candidate images on Wikimedia Commons and saves attribution details.
5. Renders vertical Shorts or horizontal video with FFmpeg.
6. Saves the MP4, thumbnail, script, sources, and image attribution for manual review.

The app does not automatically upload videos. Source summaries and image-license metadata are not legal or factual verification; check original sources and licenses before publishing.

### AI Anime Studio

[AI Anime Studio](ai-anime-studio/README.md) contains a shot-based animation prototype, including a traditional 2D sprite pipeline and optional ComfyUI integration. The no-GPU sprite path is deterministic animation, not full AI-generated cinematic video. True image generation requires a separately installed ComfyUI setup, compatible model weights, and sufficient compute.

### Video API Hub

[Video API Hub](video-api-hub/README.md) provides a local interface for optional video-generation providers. Real cloud generation requires valid provider accounts, API keys, and may incur usage charges.

### Personal AI Workbench

[Personal AI Workbench](personal-ai-agent/README.md) is a bounded local assistant connected to Ollama. Its tools are deliberately allowlisted; it does not execute arbitrary shell commands or publish content automatically.

## Integration assessment

See [the open-source integration assessment](integrations/OPEN_SOURCE_INTEGRATION_ASSESSMENT.md) for the review of OpenCode, VoiceStudio, OpenSEO, OpenMausBot, and Replica, including why only VoiceStudio is currently wired into the video workflow.

## Hardware and cost boundaries

- FFmpeg/Pillow rendering is the predictable CPU-first foundation.
- Local AI inference speed depends on the selected model, RAM, CPU, and (where used) GPU. “Open source” does not mean lightweight or free to run.
- Cloud video APIs and SEO data services can incur usage-based charges.
- Model weights, voices, fonts, datasets, stock footage, and music may have licenses different from the application's source code.
- No module guarantees views, channel growth, monetization, or income.

## Legacy Floot prototype

`floot-source/` is retained as an older Floot-based promotional-kit and payment-flow prototype. It is not the current product direction and is not part of the active video-production roadmap. Its source is preserved rather than deleted.

## General setup

Start with the README inside the module you intend to run. Most Python modules require Python 3.10+, a virtual environment, and their own `requirements.txt`. Video rendering modules also require FFmpeg and ffprobe on `PATH`.

Do not commit API keys, voice samples, private source media, generated customer data, or paid model weights to Git.
