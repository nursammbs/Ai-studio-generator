# Build Backlog — Long-Form Video Repurposing MVP

Branch: feature/revenue-engine-2027-foundation

## Milestone 0 — Foundation
- [x] Create isolated development branch.
- [x] Record product decision and scope.
- [x] Audit existing video, API hub and agent foundations.
- [x] Add first media-processing core (probe, audio extraction, transcription adapter, candidate windows, SRT and vertical render).
- [x] Add pure-Python unit tests and GitHub Actions workflow.
- [ ] Verify CI result and fix any failures.

## Milestone 1 — Usable local workflow
- [ ] Streamlit upload/import page for local video files.
- [ ] Run ffprobe validation and show media metadata.
- [ ] Transcribe and persist word timestamps.
- [ ] Show explainable candidate list with transcript excerpts.
- [ ] Human approve/reject and trim controls.
- [ ] Render selected clips and provide ZIP download.
- [ ] Add progress, cancellation, retry and resumable job state.

## Milestone 2 — Quality
- [ ] Boundary snapping and overlap suppression tests.
- [ ] Caption wrapping, safe-area preview and ASS styling.
- [ ] Optional face tracking after baseline center crop works.
- [ ] Benchmark CPU throughput and memory on real target hardware.
- [ ] Add consented sample fixtures and end-to-end smoke tests.

## Milestone 3 — Pilot and commercial decision
- [ ] Test with 5 target English-language creators/podcasters.
- [ ] Measure clip acceptance, edit time, processing time and cost per source hour.
- [ ] Obtain paid pilot commitments before billing or public SaaS.
- [ ] Decide desktop, hosted SaaS, or managed service based on measured demand.

## MVP definition of done
A user imports an authorized local video, receives a transcript and explainable clip suggestions, adjusts segment boundaries, renders valid 9:16 MP4 clips with synchronized captions, and downloads the outputs without a paid video-generation API.
