# Revenue Engine 2027 — Product and Technical Decision Record

**Status:** Foundation / decision record  
**Target market:** English-speaking creators, podcasters, educators and small media teams in the US, UK, Canada and Australia.  
**Primary product direction:** A reliable long-form video repurposing workflow that turns a customer's own video or authorized media into reviewed, editable short clips.

## Executive decision

Do not build a broad autonomous-agent platform first. Build one narrow workflow that solves a recurring, measurable problem: reduce the time required to turn one long recording into several publishable short clips.

The first product is an internal tool and a candidate paid product, not an income promise. Revenue is not validated until real target users complete a paid pilot.

## Why this direction

The existing repository already contains:
- a Python/Streamlit video draft renderer using FFmpeg;
- a Video API Hub with provider adapters, SQLite jobs and cost confirmation;
- a local AI agent foundation;
- an AI Creative Studio with image/comic capabilities.

The current video studio creates topic-led slideshow videos. It does **not** yet provide a production-grade long-video-to-shorts pipeline, word-level subtitles, reliable speaker-aware reframing, editing review, customer accounts, billing, or publishing analytics. Reuse the working foundations; do not pretend those features already exist.

The open-source clipping space is crowded. Competing on "AI makes viral clips" is weak positioning. The product must win on controllability, transparent costs, repeatable output quality, editing speed, and a focused customer workflow.

## Initial customer and job-to-be-done

**Customer:** Independent English-language podcasters and expert-led creators publishing long interviews, explainers or webinars at least weekly.

**Job:** "I have a long recording and need several accurate, well-framed, captioned short clips without manually reviewing the entire recording."

Avoid targeting all creators at once. Start with talking-head/interview footage because transcription, segment boundaries, and speaker framing are measurable.

## MVP boundary

### Must ship
1. Import a local video file. URL ingestion is deferred until platform terms and download rights are handled correctly.
2. Extract audio and generate a timestamped transcript.
3. Propose candidate segments with start/end times and a reason/evidence excerpt.
4. Let a human approve, reject, trim, and rename each segment.
5. Render vertical 9:16 MP4 clips with burned-in captions and safe margins.
6. Export a batch plus transcript, SRT, metadata and a processing report.
7. Persist jobs locally and allow resume after failure.
8. Provide a clear cost/compute mode: CPU/local first; optional API provider only after explicit configuration and budget checks.

### Explicitly out of scope for MVP
- Fully autonomous posting to social networks.
- Guaranteed virality, views, leads or income.
- Training custom foundation models.
- Expensive text-to-video generation.
- Multi-agent orchestration for its own sake.
- Multi-tenant SaaS, payments and public deployment before the workflow is stable.
- Scraping or republishing media without rights.

## Technical decisions

| Area | Decision | Reason |
|---|---|---|
| Language/runtime | Python 3.10+ | Existing code and broad media ecosystem |
| UI | Keep Streamlit for internal MVP | Fast iteration; no premature frontend rewrite |
| Media processing | FFmpeg/ffprobe | Deterministic, mature, low-cost |
| Transcription | Adapter interface; start with faster-whisper CPU/small model, benchmark before selecting default | Avoid hard dependency on GPU or paid API |
| Segment ranking | Deterministic transcript heuristics first; optional LLM reranking behind adapter | Auditable and cheap; small local models are not trusted for precise timing |
| Captions | SRT/VTT source plus FFmpeg ASS burn-in | Editable text and predictable rendering |
| Storage | SQLite + filesystem artifacts | Simple local persistence and resumability |
| Provider APIs | Reuse Video API Hub patterns, but do not require generation APIs for clipping | Keep variable spend out of core path |
| Agent layer | Add only after the deterministic pipeline works | Agents cannot compensate for unreliable media primitives |
| Deployment | Local/private first | Existing app is not hardened for public multi-user exposure |

## Quality gates

A clip is not accepted solely because an LLM labels it "viral". Every candidate must:
- map to a valid transcript time range;
- preserve enough context to be understood without misleading edits;
- avoid cutting mid-word where possible;
- keep captions synchronized and within platform safe areas;
- render with valid audio/video streams;
- be reviewable before export.

Measure:
- transcription word error rate on a small consented sample;
- candidate acceptance rate;
- human edit time per accepted clip;
- render failure rate;
- cost per source hour;
- percentage of clips needing manual timing correction.

## Business validation gates

Do not build billing or scale infrastructure until:
1. 5 target users test the workflow with their own rights-cleared recordings.
2. At least 3 use it twice within two weeks.
3. At least 2 agree to pay for a pilot or provide a concrete paid commitment.
4. Time saved and acceptable output quality are measured, not assumed.

Initial monetization hypothesis: paid monthly creator workflow or per-hour processing credits. Pricing is not decided until processing cost and willingness-to-pay are measured.

## Security and rights

- Never commit API keys, cookies, OAuth tokens, or customer media.
- Keep uploads local by default; disclose any cloud processing before use.
- Treat source media as user-owned/authorized only.
- Do not bypass platform access controls or download restrictions.
- Do not auto-publish without explicit customer authorization and platform-compliant OAuth.
- Add retention/deletion controls before public customer onboarding.

## Execution sequence

1. Audit current code and tests; identify reusable components and missing modules.
2. Build the local file → transcript → candidate segments → human review → captioned clips path.
3. Add fixtures and tests for timestamp conversion, clip boundaries, subtitle timing, and FFmpeg failures.
4. Benchmark CPU-first configuration on available hardware; keep exact hardware requirements unknown until measured.
5. Run a small rights-cleared pilot and measure time saved, acceptance, cost and willingness to pay.
6. Only then decide whether to turn it into hosted SaaS, a paid desktop tool, or a managed service.

## Non-negotiable product principle

Reliability and user control before autonomy. A system that produces 8 accurate, editable clips is more valuable than an agent that claims to produce 30 viral clips but cannot prove quality.
