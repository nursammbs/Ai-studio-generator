# Open-source integration assessment

**Scope:** the five requested GitHub projects, assessed against this repository's local-first video workflow.  
**Decision rule:** add a project only when it removes a real bottleneck without silently adding GPU, subscription, API, licensing, or security costs.

## Decision summary

| Project | What it actually does | License observed | Decision for this product |
|---|---|---|---|
| [OpenCode](https://github.com/anomalyco/opencode) | AI coding agent for terminal, desktop, and IDE workflows | MIT | **Do not embed.** Use it as an optional developer tool to maintain this repository. It is not a video generator, renderer, or TTS service. |
| [VoiceStudio](https://github.com/debpalash/VoiceStudio) | Local voice design, TTS, dubbing, transcription and audio workflows; exposes an OpenAI-compatible audio API | AGPL-3.0 | **Integrate as an optional external TTS provider.** The adapter in `opensource-video-studio/engine.py` calls `POST /v1/audio/speech`; VoiceStudio source and weights are not copied into this repository. Model/voice licenses remain separate. |
| [OpenSEO](https://github.com/Softosmith/OpenSEO) | Keyword research, rank tracking, competitor/backlink research, site audits, AI visibility; MCP/agent workflows | MIT | **Defer.** Useful for a separate channel SEO workspace, not video creation. Self-hosting still requires a DataForSEO API key and usage-based charges for SEO data. |
| [OpenMausBot](https://github.com/milind-soni/OpenMausBot) | Desktop team-of-agents app using installed agent CLIs, connected apps and computer/VM control | Apache-2.0 on the author's repository | **Do not embed or grant host control.** It overlaps the personal-agent concept and introduces a large permission surface, external agent credentials, connected apps, and potential compute/provider costs. Keep it separate until a concrete, narrow task justifies it. |
| [Replica](https://github.com/github/replica) | AI-assisted interactive UI prototyping against a design system | MIT | **Do not embed.** It is a design/prototyping environment that uses the GitHub Copilot app for its documented canvas workflow; it does not render videos or supply a production UI runtime. |

## VoiceStudio adapter: implementation notes

- Default endpoint: `http://127.0.0.1:3900/v1/audio/speech`.
- Request format: OpenAI-compatible JSON containing `model`, `voice`, `input`, and `response_format=mp3`.
- Default aliases: `tts-1` and `alloy`; VoiceStudio maps OpenAI voice aliases to the active engine's default voice.
- The adapter is opt-in. The existing automatic mode remains unchanged (Edge TTS, then system TTS).
- A selected VoiceStudio failure stops the render; it does not silently change voice providers.
- Local loopback use needs no API key under VoiceStudio's documented default. Remote use is accepted only over HTTPS with an API key. Credentials are passed in the Authorization header, never in the URL.
- This implementation has mock-based API tests. A real render against an installed VoiceStudio instance, selected model, and the user's target hardware is **not yet verified**.

## Important ownership and licensing observations

There are two separate repositories with the OpenMausBot name: `OpenMausBot/OpenMausBot` reports MIT, while the author's `milind-soni/OpenMausBot` reports Apache-2.0. The organization repository's README refers to the author's project. They are not treated as interchangeable sources; this assessment points to the author's repository and does not copy either codebase.

Open-source application code does not automatically make included or downloaded model weights, voices, fonts, datasets, or media free for every commercial use. Verify each model's own license and acceptable-use terms before distribution or monetization.

## Recommended architecture

1. Keep FFmpeg and the existing local renderer as the deterministic video/export core.
2. Keep Ollama as the optional script-writing backend.
3. Use VoiceStudio only as an optional external narration service through its documented local API.
4. Keep the clipper and Quick Video Studio as separate production paths until their branches are deliberately integrated and tested; do not merge open PRs blindly.
5. Consider OpenSEO later as a post-production metadata tool only after a real channel workflow and an explicit DataForSEO spending limit exist.
6. Keep OpenCode, OpenMausBot, and Replica as external developer/agent/design tools rather than runtime dependencies.

## Not claimed as complete

This assessment and the adapter do not prove that VoiceStudio runs on the user's machine, that every model runs on CPU, that generated narration is natural or rights-cleared, or that a video will gain views or revenue. The GitHub Actions tests validate the adapter contract with mocked HTTP responses; a real VoiceStudio smoke render is still required on the target machine.
