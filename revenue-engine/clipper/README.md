# Local Clipper — experimental MVP

First implementation slice of Revenue Engine 2027. This package is separate from the existing topic-to-slideshow app.

## Current capabilities
- Inspect local media with ffprobe.
- Extract mono 16 kHz audio with FFmpeg.
- Transcribe using optional faster-whisper (CPU/int8 default).
- Suggest bounded, explainable transcript windows using deterministic heuristics.
- Write word-timestamp SRT subtitles.
- Render a center-cropped vertical clip with burned-in subtitles.

## Not implemented
No face tracking, diarization, browser editing timeline, cloud accounts, payments, auto-upload, or proven virality prediction. Candidate scores are heuristic ranking aids only. Human review is required.

## Install
Python 3.10+, FFmpeg and ffprobe on PATH. Create a virtual environment and install requirements-clipper.txt. Run tests with: python -m unittest discover -s tests -v

Start with the base or small Whisper model on CPU; model download and speed depend on RAM, CPU and disk. No exact hardware profile has been assumed.

## Rights and privacy
Only process media you own or are authorized to use. Do not bypass platform access controls. Review every suggested segment and verify captions before publishing. Keep source files local unless you intentionally configure a cloud service.
