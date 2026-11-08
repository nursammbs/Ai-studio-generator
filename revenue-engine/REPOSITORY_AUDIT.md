# Existing Repository Audit — 2026-11-09

Repository: `nursammbs/Ai-studio-generator`  
Audit scope: README and primary source files in `opensource-video-studio`, plus README-level review of `video-api-hub` and `personal-ai-agent`.

## Findings

### 1. opensource-video-studio
**Working foundation:** Streamlit UI, Wikipedia research starter, optional Ollama script drafting, Edge TTS / pyttsx3 fallback, Wikimedia Commons image lookup with basic license metadata filtering, FFmpeg MP4 renderer, output bundle (video, thumbnail, script, sources, attribution).

**Critical gap:** This is a topic-to-slideshow draft generator, not a long-form clip repurposing system. It does not currently ingest a long source recording, transcribe it, propose timestamped highlights, produce word-level captions, track speakers, or provide a clip-review editor.

**Implication:** Reuse FFmpeg/rendering conventions and Streamlit patterns, but add a separate pipeline rather than bending the scene/slideshow abstraction into a clip editor.

### 2. video-api-hub
**Working foundation:** FastAPI workbench, provider adapters (Higgsfield, Runway, fal.ai and OpenAI text assistance), SQLite job persistence, server-side environment secrets, cost confirmation, optional local MCP bridge.

**Critical gap:** It is a single-user local MVP. It is not public SaaS-ready. ComfyUI direct execution is not implemented according to its README. Video generation APIs are not necessary for the core clipping workflow.

**Implication:** Reuse job-state and credential-handling patterns only where useful. Do not route basic clipping through paid video-generation APIs.

### 3. personal-ai-agent
**Working foundation:** Local Ollama assistant with a small allowlisted toolset and note context.

**Critical gap:** It is not a production orchestration engine; no arbitrary shell access is intentionally allowed. Local model quality and speed depend on hardware, and exact CPU/RAM/GPU specifications have not been recorded in available project context.

**Implication:** Do not make the product dependent on a local LLM agent. Use deterministic code for media operations; treat LLMs as optional helpers.

### 4. AI Creative Studio (private repository, README-level context)
The current milestone is image generation/comic pages. Video rendering is deferred. ComfyUI/FastSD workflows have not yet been confirmed end-to-end. It should remain separate from the first clipping MVP unless a concrete reusable module is found.

### 5. Floot and Replit
The public repo README references a Floot deployment for CepatCuan Studio. This is a different product direction (Indonesian small-business promo kits) and is not the target market for this project. A Replit project has not yet been technically inspected in this audit.

## Main risks
- Hardware capacity unknown; CPU throughput must be benchmarked before choosing transcription model defaults.
- "Viral" scoring is not a reliable promise and should not be the core value proposition.
- Source video rights and platform download rules must be respected.
- Open-source dependencies have different licenses; each dependency must be checked before commercial redistribution.
- The market is crowded; product differentiation and paid validation are required.

## Conclusion
The repository contains useful components but no complete product matching the chosen target workflow. The highest-leverage next build is a separate, testable long-form clipping pipeline inside this repository.
