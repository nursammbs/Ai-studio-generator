# Hosted product layer (early scaffold)

This optional layer adds account registration, signed sessions, per-account job isolation in Streamlit, monthly source-video quotas, usage and configured cost records, a versioned REST API, Stripe Checkout/webhooks, S3-compatible private media upload URLs, and Prometheus request metrics.

## Local versus hosted mode

The local clipper stays local-first by default. To enable account login, set `CLIPPER_REQUIRE_AUTH=1`, configure a random `CLIPPER_SESSION_SECRET` of at least 32 characters, and set a writable `CLIPPER_SAAS_DB` location. The API and account store can be run with `uvicorn saas.api:app`. Run the Streamlit interface and API behind the included Caddy reverse proxy in `docker-compose.commercial.yml`.

Copy `.env.example` to `.env` for the compose deployment. The example contains placeholders only. Do not commit the real `.env` file. Caddy terminates HTTPS for a public domain; local `localhost` mode is for development only. The Prometheus endpoint requires `CLIPPER_METRICS_TOKEN` and should stay on an internal network.

## Optional providers and models

- Stripe checkout requires account-owned price IDs, API credentials and a configured webhook endpoint. Subscription entitlements are updated from verified Stripe events.
- S3 storage requires a private bucket and server credentials supplied by the host. Upload URLs expire after ten minutes; media objects use server-side encryption.
- Local semantic selection and face-focused framing are available through `requirements-ai.txt`.
- Speaker diarization uses pyannote's community pipeline, a Hugging Face token and acceptance of the model's access terms. Audio is processed locally after weights are downloaded.

## API surface

- `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/me`
- `GET /api/v1/usage`, `POST /api/v1/usage/reservations`
- `GET /api/v1/analytics/summary`, `POST /api/v1/events/{event_name}`
- `POST /api/v1/billing/checkout`, `POST /api/v1/billing/webhook`
- `POST /api/v1/storage/upload-url`
- `GET /health`
- `GET /metrics` with the configured `X-Metrics-Token`

## Remaining release work

This is an implementation scaffold, not a public production service. Before serving customers, provision Stripe and cloud accounts, configure domains and backups, add rate limits and abuse controls, complete a security review, add database migrations and account recovery, and validate quota behavior under concurrent workers. The default quotas and cost rates are starting values; product pricing must be based on measured hardware/cloud costs and pilot evidence.
