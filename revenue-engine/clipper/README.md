# Local Clipper — experimental MVP

Local-first software for turning authorized long-form video into reviewed vertical clips. The project is an early product experiment, not a revenue or virality promise.

## Current workflow

- Upload a local MP4, MOV, MKV, WebM or M4V recording.
- Check the source format, audio/video streams and duration with ffprobe.
- Extract mono 16 kHz audio and transcribe locally with faster-whisper on CPU/int8.
- Suggest transcript windows that begin and end on completed sentences, with a short explanation of the heuristic signals used.
- Review and trim candidate boundaries in the table.
- Choose caption size, caption position and center-crop or fit framing.
- Render H.264/AAC 1080×1920 MP4, group word timestamps into readable caption phrases, and validate each result with ffprobe.
- Download the clips, SRT files, transcript and processing report as a ZIP.
- Reopen saved jobs after a page refresh. A failed render can be retried; already validated clips are reused when the selection and render settings match.

Jobs and media are stored under outputs/<job-id>/. Delete a job folder to remove its source, transcript and exports.

## Requirements

- Python 3.10 or newer.
- FFmpeg and ffprobe on PATH; FFmpeg must include the subtitles/libass filter and libx264.
- Enough free disk space for the source, extracted WAV, rendered clips and ZIP. WAV extraction uses about 115 MB per source hour before overhead.
- CPU-only processing is supported. The base Whisper model is the default; larger models use more memory and take longer. First use downloads model weights; inference then runs locally.

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

Transcription word error rate needs a trusted reference transcript and has not yet been measured. Electricity cost, hardware throughput and real-video export quality have not been benchmarked on a target customer computer. The FFmpeg smoke test generates a synthetic color/audio fixture; it does not replace a real customer-video test. The current framing options are center crop and fit-with-black-bars; no face tracking or speaker diarization is included. Candidate reasons and scores are deterministic heuristics, not estimates of views or virality.

## Not implemented

No user accounts, cloud storage, billing, public deployment, social publishing, analytics, transcript correction editor, multi-user job queue, background worker, GPU path, face tracking, diarization, or guaranteed virality. Do not process media without the rights to do so.

## Privacy and rights

Uploads, transcripts and exports stay on the local machine in outputs/. Only process recordings you own or are authorized to use. Review the cut, framing and captions before publishing.

