# Local Clipper — experimental MVP

Local-first software for turning authorized long-form video into reviewed vertical clips. The project is an early product experiment, not a revenue or virality promise.

## Current workflow

- Upload a local MP4, MOV, MKV, WebM or M4V recording.
- Check the source format, audio/video streams and duration with ffprobe.
- Extract mono 16 kHz audio and transcribe locally with faster-whisper on CPU/int8.
- Suggest transcript windows that begin and end on completed sentences, with a short explanation of the heuristic signals used.
- Optionally rerank suggestions with a local sentence-embedding model for semantic editorial intent matching (`pip install -r requirements-ai.txt`).
- Review and trim candidate boundaries in the table.
- Correct transcript text while preserving existing word times where alignment permits.
- Choose caption size, caption position, center-crop, fit or an OpenCV face-focused crop; add optional fade-in/fade-out transitions.
- Optionally identify speakers locally with pyannote and label caption phrases by speaker.
- Render H.264/AAC 1080×1920 MP4, group word timestamps into readable caption phrases, and validate each result with ffprobe.
- Download the clips, SRT files, transcript and processing report as a ZIP.
- Reopen saved jobs after a page refresh. A failed render can be retried; already validated clips are reused when the selection and render settings match.
- Optionally upload a human-checked TXT transcript to calculate word error rate (WER) locally.

Jobs and media are stored under outputs/<job-id>/. Delete a job folder to remove its source, transcript and exports.

## Requirements

- Python 3.10 or newer.
- FFmpeg and ffprobe on PATH; FFmpeg must include the subtitles/libass filter and libx264.
- Enough free disk space for the source, extracted WAV, rendered clips and ZIP. WAV extraction uses about 115 MB per source hour before overhead.
- CPU-only processing is supported. The base Whisper model is the default; larger models use more memory and take longer. First use downloads model weights; inference then runs locally.
- Optional semantic/face/speaker models are in `requirements-ai.txt`; model weights download separately. pyannote requires a Hugging Face token and acceptance of its model conditions.

The current upload limit is 2 GB and the source duration limit is 4 hours. Override with CLIPPER_MAX_UPLOAD_BYTES and CLIPPER_MAX_SOURCE_SECONDS if needed. Streamlit's upload limit must be set to at least the same size when raising the app limit.

## Install and run

From this directory in PowerShell:

    py -3.11 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements-clipper.txt
    streamlit run app.py --server.maxUploadSize 2048

To use the full 2 GB upload allowance, ensure Streamlit's server.maxUploadSize is set to 2048 MB. Install FFmpeg separately and confirm ffmpeg, ffprobe, and the subtitles filter are available.

Run the unit checks and the FFmpeg smoke test with:

    python -m unittest discover -s tests -v

## Measurements and limits

Each job records analysis/render time, source duration, number of suggestions, and the share selected for export. The export report includes processing seconds per source hour. This is a processing-speed measure, not wall-clock editing time or a cost estimate.

The real-media CI smoke test measures WER against a NASA SVS reference transcript, but customer accuracy and device performance still need measurement. Configure `CLIPPER_COST_PER_SOURCE_HOUR_USD` to record a cost estimate; it uses the configured rate and does not infer electricity or cloud cost. The optional face crop estimates a stable face center rather than following a face frame by frame. Candidate reasons and scores are not estimates of views or virality.

## Not implemented

Public hosting and commercial adapters are an early scaffold. Optional accounts, per-account job isolation, quotas, Stripe Checkout, S3 upload URLs, REST endpoints and Prometheus metrics require `requirements-saas.txt` and configuration described in `saas/README.md`. There is no production security review, account recovery, social publishing, or background job queue yet. Do not process media without the rights to do so.

## Privacy and rights

Uploads, transcripts and exports stay on the local machine in outputs/. Only process recordings you own or are authorized to use. Review the cut, framing and captions before publishing.
