# Video API Hub

Video API Hub is a local-first web workbench that routes creative work to one or more provider APIs. It is separate from the existing AI Anime Studio renderer, but can later orchestrate it in the same workflow.

## What this MVP contains

- Provider cards show available connectors, capabilities, documentation links, and whether a server-side credential is set.
- Multi-provider video submit sends one prompt to Higgsfield, Runway and/or a model-specific fal.ai queue endpoint.
- Job monitor persists provider jobs in SQLite and queries status on demand.
- OpenAI script/prompt assistant uses the official OpenAI Responses API to create scripts, prompts and structured shot lists.
- API secrets are read from .env, never sent to the browser, and no endpoint returns their values.
- Explicit cost confirmation is required before a generation request is submitted.

This MVP performs actual API calls when an API key is configured. It does not fake a successful generation or ship demo credentials. Missing keys produce visible setup/error states.

## Run locally

Python 3.10+ recommended. From this directory:

~~~bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env on your own machine; never commit real keys.
uvicorn app:app --reload --host 127.0.0.1 --port 8090
~~~

Open http://127.0.0.1:8090. Interactive API schema: http://127.0.0.1:8090/docs.

The page runs in local mode by default. Only configure providers you intend to use. Start with a short generation and check the provider's per-model price, duration and output constraints before submitting.

## Current connectors

| Connector | Actions | Configuration |
|---|---|---|
| Higgsfield API | Video generation using a catalog endpoint path | HIGGSFIELD_API_KEY; optional HIGGSFIELD_DEFAULT_MODEL |
| Runway Dev | Text-to-video, image-to-video, video-to-video | RUNWAY_API_KEY |
| fal.ai | Queue-submit adapter with model-specific JSON options | FAL_KEY plus endpoint ID |
| OpenAI API | Script, prompt and shot-list assistance | OPENAI_API_KEY, optional OPENAI_TEXT_MODEL |
| ComfyUI | Listed for the connector design; direct execution adapter is a follow-up | COMFYUI_BASE_URL |

Each model has its own request schema, costs, limits and output format. The "options" object is passed to the selected provider; use current provider docs rather than assuming identical parameters across all adapters. New bridges can be added without rewriting the UI.

## API routes

- GET /api/health
- GET /api/providers
- GET /api/jobs
- POST /api/jobs
- GET /api/jobs/{id}
- POST /api/assist

## MCP vs API

An API adapter lets the website call a vendor REST/queue API. An MCP server exposes tools using the Model Context Protocol so an AI client/agent can discover and invoke operations. They are compatible layers, not synonyms: this MVP starts with provider APIs. A separate MCP server can expose vetted Hub actions such as list_providers, create_video_job and get_job_status to approved AI clients.

OpenAI API credentials and billing are separate from a ChatGPT subscription; this app does not control or scrape the ChatGPT website UI.

## Before public deployment

This is a single-user local MVP, not a hardened SaaS. Do not expose it to the public internet as-is. Before multi-user use, add authentication, account-scoped job data, encrypted secret storage, HTTPS, CSRF/rate limits, provider spend budgets, quota-aware retries, audit events, upload policy, and server-side access controls. The app currently stores prompts and provider job IDs in SQLite. Keep the host private.

## Source documentation

- https://docs.higgsfield.ai/
- https://docs.dev.runwayml.com/
- https://docs.fal.ai/
- https://developers.openai.com/api/docs
- https://modelcontextprotocol.io/
