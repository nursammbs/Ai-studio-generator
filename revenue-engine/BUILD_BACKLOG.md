# Build Backlog — Long-Form Video Repurposing MVP

Branch: feature/revenue-engine-2027-foundation

## Milestone 0 — Foundation

- [x] Create isolated development branch and product decision record.
- [x] Audit the existing video, API hub and agent foundations.
- [x] Add upload, ffprobe validation, audio extraction, local Whisper transcription, candidate windows, SRT and vertical rendering.
- [x] Add Streamlit upload, review, framing and export interface.
- [x] Add pure-Python tests and a GitHub Actions workflow.
- [x] Review the public feature set and document a review-first differentiation hypothesis.
- [x] Verify the updated CI result on GitHub.

## Milestone 1 — Local reliability and quality

- [x] Persist job state and transcript paths on disk; reopen jobs after a page refresh.
- [x] Retry analysis and resume failed renders using already validated clips.
- [x] Reject unsupported, silent, overlong or malformed source videos.
- [x] Avoid incomplete transcript tails and continuation-start candidates; suppress overlapping suggestions.
- [x] Group word timestamps into readable multiword SRT captions with adjustable size and position.
- [x] Validate rendered stream presence, 9:16 ratio, dimensions and expected duration through ffprobe.
- [x] Record processing time, source duration, and the share of suggestions selected for export.
- [x] Add a synthetic FFmpeg render smoke test.
- [x] Exercise a real NASA interview through transcription, reference-caption WER, candidate selection, SRT generation and 9:16 MP4 rendering in CI.
- [ ] Run the real-video workflow through the upload UI on a supported customer computer.
- [ ] Benchmark CPU throughput, RAM, storage and cost per source hour on target hardware.
- [x] Measure transcription word error rate against a rights-cleared reference transcript (NASA interview CI fixture: 18.3% WER).
- [ ] Add editable transcript corrections and more precise caption timing/style controls.
- [ ] Add speaker-aware reframing only after center-crop and fit baselines are measured.

## Milestone 2 — Pilot and commercial decision

- [ ] Compare output quality and total editing time with current workflows used by five US, UK, Canadian or Australian creators.
- [ ] Record acceptance, boundary edits, caption corrections, failure rate and time saved for each session.
- [ ] Obtain at least two paid pilot commitments before implementing billing.
- [ ] Decide between local desktop, hosted SaaS or managed service from measured user and unit-cost evidence.

## Current verification boundary

GitHub Actions run [42589044858](https://github.com/nursammbs/Ai-studio-generator/actions/runs/42589044858) passed all 16 tests with no skips. The real-media test fetched NASA SVS's Sarah Jones interview (69.03 seconds) into a temporary directory, transcribed 162 words using faster-whisper base, measured 18.3% WER against the NASA caption file, generated clip suggestions and validated an exported 9:16 MP4. Input and output files are discarded when the test ends. The runner reported 4.15 seconds of transcription inference for this source; this is a GitHub-hosted runner measurement and is not a benchmark for a customer's computer.

The CI suite also passes synthetic audio/video and the Streamlit upload-widget smoke test. The upload control has not yet been exercised with a real source through the full UI on a supported customer computer. CPU/RAM/storage costs, real creator acceptance and paid-pilot demand remain unmeasured.

## MVP definition of done

A user imports an authorized local video, receives a timestamped transcript and explainable clip suggestions, adjusts boundaries, renders valid 9:16 MP4 clips with synchronized captions, and downloads the outputs. Automated tests pass, installation and usage documentation are current, and throughput/hardware cost are measured on target computers. No revenue or virality outcome is assumed.
