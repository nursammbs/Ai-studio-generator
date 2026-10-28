# CepatCuan Studio

AI-assisted promotion kits for Indonesian small businesses.

**Live site:** https://cepatcuan-studio.floot.app

## What it sells

- **Starter — Rp29,000:** landing-page copy, 7 social captions, WhatsApp message.
- **Growth — Rp59,000:** Starter plus campaign ideas.
- **Studio — Rp99,000:** Growth plus a 14-day content calendar and FAQs.

These are initial launch prices to validate with real customers, not proven market rates.

## Automation flow

1. A buyer submits a business brief and selects a fixed-price package.
2. The server creates an order using server-side prices.
3. Midtrans Snap hosts the checkout. The browser never receives the merchant Server Key.
4. A signed Midtrans notification is checked server-side, including signature, order ID, amount and currency.
5. After verified payment, the app uses an AI writing model to generate an Indonesian-language kit. If AI is temporarily unavailable, the system has a deterministic fallback.
6. The buyer returns to a token-protected order page to copy or download the kit.

## Merchant setup before accepting real payments

1. Register and complete the required verification with Midtrans.
2. Store `MIDTRANS_SERVER_KEY` and `MIDTRANS_ENV` as secured server-side environment variables. Start with `MIDTRANS_ENV=sandbox`; never commit either value.
3. For production, use the production Server Key only after merchant verification.
4. Configure the settlement bank account in the Midtrans Merchant Administration Portal. Enable **Auto-Withdrawal** and choose its schedule if available for the merchant account.
5. Test a sandbox transaction and a signed callback end-to-end before announcing paid checkout.

The app sends a per-transaction notification override to:

`https://cepatcuan-studio.floot.app/_api/midtrans-notification`

Payment processing and bank settlement depend on the merchant account and provider settings. A website cannot bypass payment-provider onboarding or settlement rules. Follow the current official docs:
- https://docs.midtrans.com/docs/snap-snap-integration-guide
- https://docs.midtrans.com/docs/how-can-i-have-my-money-in-my-account-payout

## Important implementation note

The live implementation uses Floot's page, database, endpoint and AI runtime conventions (including `@floot/ai`). The Floot runtime is required to execute the current application code; this repository is the project documentation and source-export home, not a standalone GitHub Pages deployment. Never publish production secrets, customer data, API keys, or payment tokens in Git.

## Trust and claims

The generator drafts promotional content; it cannot guarantee sales, virality, or factual correctness of details absent from the buyer's brief. Verify claims, pricing, promotions, availability and business details before publication.

## Experimental animation module

The repository also contains an early **AI Anime Studio** prototype in [ai-anime-studio](ai-anime-studio/README.md). It combines a local ComfyUI API integration with a three-scene MP4 animatic renderer. Its offline demo and API mock tests validate the rendering and integration scaffolding; true image generation requires a local ComfyUI installation, models, and an exported API workflow. It is not yet a full frame-by-frame anime generator.


## AI Anime Studio pilot milestone

An AI-assisted cartoon pilot is now rendered: original AI-generated cat/mouse character poses are composited into a 15-second 1280×720, 24 FPS MP4 with moving backgrounds, pose changes and an original synthesized audio cue. The source renderer is in [ai-anime-studio/sprite_animator.py](ai-anime-studio/sprite_animator.py). It is sprite animation, not full generative video; use the accompanying downloadable pilot package for the PNG pose sheet and finished MP4.
