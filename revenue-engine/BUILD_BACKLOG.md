# Build Backlog — Long-Form Video Repurposing MVP

Branch: `feature/revenue-engine-2027-foundation`

## Milestone 0 — Foundation (current)
- [x] Create isolated development branch.
- [x] Record product decision and scope.
- [x] Audit existing video, API hub and agent foundations.
- [ ] Add reproducible test workflow and dependency lock strategy.

## Milestone 1 — Media ingestion and transcript
- [ ] Create `clipper/` package separate from slideshow engine.
- [ ] Validate input video with ffprobe; record duration, streams, frame size and audio presence.
- [ ] Extract mono 16 kHz WAV via FFmpeg.
- [ ] Add transcription adapter contract.
- [ ] Implement CPU-first faster-whisper adapter with configurable model size and cache directory.
- [ ] Save transcript segments and word timestamps in normalized JSON.
- [ ] Handle missing audio, corrupt media, unsupported codec, long files and cancellation.

## Milestone 2 — Candidate clip detection
- [ ] Build deterministic candidate windows from transcript sentence/paragraph boundaries.
- [ ] Enforce configurable duration range (default 25–60 seconds).
- [ ] Rank candidates using topic continuity, complete thought, opening hook, speech density and ending completeness.
- [ ] Store reasons and transcript excerpts; never expose a fake "virality score".
- [ ] Add overlap suppression and duplicate detection.
- [ ] Keep human selection as mandatory.

## Milestone 3 — Captioned rendering
- [ ] Generate editable SRT and ASS subtitles.
- [ ] Escape ASS text safely and wrap long captions.
- [ ] Render 9:16 crop with safe margins; initial crop is center crop, not claimed face tracking.
- [ ] Add optional landscape 16:9 export.
- [ ] Validate output with ffprobe and verify expected duration/audio.
- [ ] Generate preview contact sheet and metadata JSON.

## Milestone 4 — Review UI and resumability
- [ ] Streamlit upload/import page.
- [ ] Transcript view and candidate list.
- [ ] Approve/reject/trim candidate boundaries.
- [ ] Caption style and export settings.
- [ ] SQLite job state, processing logs, retry/resume.
- [ ] Download all accepted clips as ZIP.

## Milestone 5 — Pilot and commercial decision
- [ ] Prepare rights-cleared sample dataset.
- [ ] Test on at least 5 target users.
- [ ] Track acceptance, edit time, processing time and cost per source hour.
- [ ] Obtain paid pilot commitments before building billing.
- [ ] Decide desktop, hosted SaaS, or managed service based on measured demand.

## Definition of done for MVP
A user can import an authorized local video, receive a transcript and explainable clip suggestions, adjust each segment, render valid 9:16 MP4 clips with synchronized captions, and download a resumable export bundle without requiring a paid video-generation API.
