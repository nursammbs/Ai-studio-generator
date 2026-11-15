# Optional media analysis dependencies

The base clipper remains CPU-first and installs only faster-whisper + Streamlit.

## PySceneDetect

Install from the clipper directory:

    pip install -r requirements-media.txt

Then enable **Detect scene changes (PySceneDetect)** in the sidebar. The detector records scene boundaries and adds an explainable scene-change count to clip suggestions. It does not claim that a cut is interesting or automatically discard any footage.

## Silence analysis

Silence interval detection uses FFmpeg's built-in `silencedetect` filter and is enabled by default. It records intervals for review and annotates suggestions that overlap silence. It does not change the source or automatically trim a candidate's boundaries.

## Auto-Editor

Install Auto-Editor separately:

    pip install auto-editor

Open a saved job and select **Create silence-trimmed review copy with Auto-Editor**. The app creates a separate `auto-editor-review.mp4` in that job's folder. The original recording is never overwritten. This copy is for quick review only; do not use its timestamps as if they still matched the original source.

## WhisperX decision

WhisperX is deliberately not part of the default install. Its forced-alignment and diarization stack adds PyTorch/model dependencies and may be substantially heavier on CPU. The current default faster-whisper pipeline remains the reliable low-resource path. Install and benchmark WhisperX separately on the target computer before making it a default.
