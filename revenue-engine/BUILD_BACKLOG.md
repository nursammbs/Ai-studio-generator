# Build Backlog — Long-Form Video Repurposing MVP

Branch: feature/revenue-engine-2027-foundation

## Milestone 0 — Foundation
- [x] Create isolated development branch.
- [x] Record product decision and scope.
- [x] Audit existing video, API hub and agent foundations.
- [x] Add media core: media probe, audio extraction, transcription adapter, candidate windows, SRT and vertical rendering.
- [x] Add Streamlit upload/review/export interface.
- [x] Add pure-Python unit tests and GitHub Actions workflow.
- [ ] Verify CI result and fix any failures.

## Milestone 1 — Reliability and quality
- [ ] Add robust job persistence, cancellation, retry and resume.
- [ ] Add boundary snapping and overlap suppression tests.
- [ ] Add caption wrapping, safe-area preview and style presets.
- [ ] Add optional face tracking after center-crop baseline is validated.
- [ ] Add optional speaker diarization.
- [ ] Add end-to-end smoke tests with a rights-cleared short fixture.
- [ ] Benchmark CPU throughput, RAM and cost per source hour on target hardware.

## Milestone 2 — Pilot and commercial decision
- [ ] Test with 5 target English-language creators/podcasters.
- [ ] Measure clip acceptance, edit time, processing time and cost per source hour.
- [ ] Obtain paid pilot commitments before billing or public SaaS.
- [ ] Decide desktop, hosted SaaS, or managed service based on measured demand.

## MVP definition of done
A user imports an authorized local video, receives a transcript and explainable clip suggestions, adjusts segment boundaries, renders valid 9:16 MP4 clips with synchronized captions, and downloads the outputs without a paid video-generation API. The current branch is an experimental first implementation and is not yet validated on the user's hardware.
