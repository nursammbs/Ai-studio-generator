# Build Backlog — Long-Form Video Repurposing MVP

Branch: feature/revenue-engine-2027-foundation

## Milestone 0 — Foundation

- [x] Create isolated development branch and product decision record.
- [x] Audit the existing video, API hub and agent foundations.
- [x] Add upload, ffprobe validation, audio extraction, local Whisper transcription, candidate windows, SRT and vertical rendering.
- [x] Add Streamlit upload, review, framing and export interface.
- [x] Add pure-Python tests and a GitHub Actions workflow.
- [x] Review the public feature set and document a review-first differentiation hypothesis.
- [ ] Verify the updated CI result on GitHub.

## Milestone 1 — Local reliability and quality

- [x] Persist job state and transcript paths on disk; reopen jobs after a page refresh.
- [x] Retry analysis and resume failed renders using already validated clips.
- [x] Reject unsupported, silent, overlong or malformed source videos.
- [x] Avoid incomplete transcript tails and continuation-start candidates; suppress overlapping suggestions.
- [x] Group word timestamps into readable multiword SRT captions with adjustable size and position.
- [x] Validate rendered stream presence, 9:16 ratio, dimensions and expected duration through ffprobe.
- [x] Record processing time, source duration, and the share of suggestions selected for export.
- [x] Add a synthetic FFmpeg render smoke test; it skips when FFmpeg/libass/ffprobe are unavailable.
- [ ] Run a real-video upload, transcription, subtitle-sync and MP4 export smoke test on a supported computer.
- [ ] Benchmark CPU throughput, RAM, storage and cost per source hour on target hardware.
- [ ] Measure transcription word error rate against a rights-cleared reference transcript.
- [ ] Add editable transcript corrections and more precise caption timing/style controls.
- [ ] Add speaker-aware reframing only after center-crop and fit baselines are measured.

## Milestone 2 — Pilot and commercial decision

- [ ] Compare output quality and total editing time with current workflows used by five US, UK, Canadian or Australian creators.
- [ ] Record acceptance, boundary edits, caption corrections, failure rate and time saved for each session.
- [ ] Obtain at least two paid pilot commitments before implementing billing.
- [ ] Decide between local desktop, hosted SaaS or managed service from measured user and unit-cost evidence.

## Current verification boundary

The Python tests cover transcript boundaries, subtitle timing, transcript serialization and filesystem job persistence. A synthetic FFmpeg smoke test is included but skips if media dependencies are absent. The current development environment has Python 3.14 but does not have Streamlit, FFmpeg or ffprobe installed. Consequently, the UI has not been launched, no real upload/transcription/render has been verified, CI has not yet been checked, and hardware or operating cost is unknown. The MVP is not yet at its full definition of done.

## MVP definition of done

A user imports an authorized local video, receives a timestamped transcript and explainable clip suggestions, adjusts boundaries, renders valid 9:16 MP4 clips with synchronized captions, and downloads the outputs. Automated tests pass, installation and usage documentation are current, and throughput/hardware cost are measured on target computers. No revenue or virality outcome is assumed.

