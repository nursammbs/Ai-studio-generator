# Local Clipper — experimental MVP

A local-first first release for repurposing authorized long-form video into reviewed vertical clips.

## Capabilities
- Streamlit upload and local processing interface.
- Inspect media with ffprobe and extract mono 16 kHz audio with FFmpeg.
- Transcribe with faster-whisper on CPU/int8 by default.
- Suggest bounded transcript windows with explainable heuristic reasons.
- Select/edit clip boundaries in a review table.
- Generate word-timestamp SRT subtitles and burn them into vertical 9:16 MP4.
- Download clips and subtitles in a ZIP.

## Not implemented
No face tracking, diarization, browser timeline, resumable background jobs, cloud accounts, payments, auto-upload, or proven virality prediction. The initial crop is a center crop. Candidate scores are heuristic ranking aids only. Human review is required.

## Install
Python 3.10+, FFmpeg and ffprobe on PATH. FFmpeg must include the subtitles/libass filter. Create a virtual environment, then install requirements-clipper.txt and run: streamlit run app.py.

Run pure-Python tests with: python -m unittest discover -s tests -v.

Start with the base Whisper model on CPU; model download, RAM use and speed depend on hardware. No exact hardware profile has been assumed. The first model download requires internet; subsequent inference is local.

## Rights and privacy
Only process media you own or are authorized to use. Do not bypass platform access controls. Review every suggested segment and verify captions before publishing. Files are stored locally under outputs/; delete the job folder when no longer needed.
