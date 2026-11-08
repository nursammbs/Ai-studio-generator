from __future__ import annotations

import json
import tempfile
import uuid
import zipfile
from pathlib import Path

import streamlit as st

from core import Candidate, extract_audio, probe_media, render_clip, save_transcript, suggest_candidates, transcribe, write_srt

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "outputs"
WORK.mkdir(exist_ok=True)

st.set_page_config(page_title="Local Clipper", page_icon="✂️", layout="wide")
st.title("Local Clipper")
st.caption("Long recording → transcript → explainable clip suggestions → reviewed vertical MP4 exports.")
st.warning("Experimental MVP. Review every clip and caption. Candidate scores are heuristic ranking aids, not predictions of virality or income.")

with st.sidebar:
    st.header("Processing")
    model_size = st.selectbox("Whisper model", ["base", "small", "medium"], index=0)
    st.caption("CPU / int8 mode. Larger models need more RAM and run slower on CPU.")
    min_seconds = st.slider("Minimum clip duration (seconds)", 15, 45, 25)
    max_seconds = st.slider("Maximum clip duration (seconds)", 30, 90, 60)
    max_clips = st.slider("Maximum suggestions", 3, 20, 10)

uploaded = st.file_uploader("Upload a video you own or are authorized to process", type=["mp4", "mov", "mkv", "webm", "m4v"])
if uploaded is not None:
    if st.button("Analyze video", type="primary", use_container_width=True):
        job_id = uuid.uuid4().hex[:12]
        job_dir = WORK / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        source = job_dir / Path(uploaded.name).name
        source.write_bytes(uploaded.getvalue())
        try:
            with st.status("Inspecting media and preparing transcript…", expanded=True) as status:
                media = probe_media(source)
                if not media["has_video"]:
                    raise ValueError("The uploaded file has no video stream.")
                st.write(f"Duration: {media['duration']:.1f}s")
                audio = extract_audio(source, job_dir / "audio.wav")
                st.write("Transcribing locally with faster-whisper…")
                words = transcribe(audio, model_size=model_size, device="cpu")
                if not words:
                    raise ValueError("No timestamped words were returned. Try another model or check the audio.")
                save_transcript(words, job_dir / "transcript.json")
                candidates = suggest_candidates(words, min_seconds, max_seconds, max_clips)
                if not candidates:
                    raise ValueError("No candidate segments matched the selected duration range.")
                (job_dir / "media.json").write_text(json.dumps(media, indent=2), encoding="utf-8")
                st.session_state["clipper_job"] = {
                    "id": job_id, "dir": str(job_dir), "source": str(source),
                    "words": [w.__dict__ for w in words],
                    "candidates": [c.__dict__ for c in candidates],
                }
                status.update(label=f"Analysis complete — {len(candidates)} suggestions", state="complete")
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
            st.info("Check FFmpeg/ffprobe, available RAM/disk space, and the selected Whisper model.")

job = st.session_state.get("clipper_job")
if job:
    from core import Word
    st.subheader("Review suggested clips")
    st.caption("Select clips and edit start/end times. Listen to each result before publishing.")
    rows = []
    for index, item in enumerate(job["candidates"]):
        rows.append({
            "Export": index < 5,
            "Start (s)": float(item["start"]),
            "End (s)": float(item["end"]),
            "Score": float(item["score"]),
            "Reason": "; ".join(item["reasons"]),
            "Transcript": item["text"][:500],
        })
    edited = st.data_editor(
        rows, hide_index=True, use_container_width=True,
        column_config={
            "Export": st.column_config.CheckboxColumn("Export", default=False),
            "Start (s)": st.column_config.NumberColumn("Start (s)", min_value=0.0, format="%.2f"),
            "End (s)": st.column_config.NumberColumn("End (s)", min_value=0.1, format="%.2f"),
            "Score": st.column_config.NumberColumn("Heuristic score", disabled=True, format="%.1f"),
            "Reason": st.column_config.TextColumn("Why suggested", disabled=True, width="large"),
            "Transcript": st.column_config.TextColumn("Transcript excerpt", disabled=True, width="large"),
        },
        key=f"clip_editor_{job['id']}",
    )
    if st.button("Render selected clips", type="primary"):
        selected = [row for row in edited if row.get("Export")]
        if not selected:
            st.error("Select at least one clip.")
        else:
            job_dir = Path(job["dir"])
            words = [Word(**item) for item in job["words"]]
            rendered = []
            progress = st.progress(0.0)
            try:
                for index, row in enumerate(selected, 1):
                    start, end = float(row["Start (s)"]), float(row["End (s)"])
                    if start < 0 or end <= start:
                        raise ValueError("Each clip needs a valid start/end range.")
                    candidate = Candidate(start, end, str(row["Transcript"]), float(row["Score"]), [])
                    subtitle = write_srt(words, start, end, job_dir / f"clip_{index:02d}.srt")
                    output = render_clip(job["source"], candidate, subtitle, job_dir / f"clip_{index:02d}.mp4")
                    rendered.append(output)
                    progress.progress(index / len(selected), text=f"Rendered {index}/{len(selected)}")
                bundle = job_dir / "clips-export.zip"
                with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
                    for output in rendered:
                        archive.write(output, output.name)
                        archive.write(output.with_suffix(".srt"), output.with_suffix(".srt").name)
                    archive.write(job_dir / "transcript.json", "transcript.json")
                st.session_state["clipper_export"] = str(bundle)
                st.success(f"Rendered {len(rendered)} clips.")
            except Exception as exc:
                st.error(f"Render failed: {exc}")

export_path = st.session_state.get("clipper_export")
if export_path and Path(export_path).is_file():
    st.download_button("Download clips + subtitles (ZIP)", Path(export_path).read_bytes(),
                       file_name="local-clipper-export.zip", mime="application/zip",
                       use_container_width=True)
