from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import zipfile
from pathlib import Path

import streamlit as st

from core import (
    Candidate,
    SUPPORTED_VIDEO_SUFFIXES,
    align_transcript_correction,
    extract_audio,
    load_transcript,
    render_clip,
    save_transcript,
    suggest_candidates,
    transcribe,
    transcript_excerpt,
    validate_rendered_clip,
    validate_video,
    word_error_rate,
    write_srt,
)
from jobs import JobStore
from semantic_selection import suggest_semantic_candidates
from diarization import attach_speakers, diarize_audio


ROOT = Path(__file__).resolve().parent
WORK = ROOT / "outputs"
STORE = JobStore(WORK)
MAX_UPLOAD_BYTES = int(os.environ.get("CLIPPER_MAX_UPLOAD_BYTES", str(2 * 1024**3)))
MAX_SOURCE_SECONDS = int(os.environ.get("CLIPPER_MAX_SOURCE_SECONDS", str(4 * 60 * 60)))


@st.cache_resource
def _account_store():
    from saas.accounting import SaaSStore
    return SaaSStore()


def _account_gate() -> dict | None:
    if os.environ.get("CLIPPER_REQUIRE_AUTH") != "1":
        return None
    try:
        account_store = _account_store()
        token = st.session_state.get("clipper_session_token")
        account = account_store.verify_token(token) if token else None
    except Exception as exc:
        st.error(f"Account service is not configured: {exc}")
        st.stop()

    if account:
        with st.sidebar:
            st.caption(f"Signed in: {account['email']} · {account['plan']} plan")
            usage = account_store.monthly_usage(account["id"])
            st.progress(
                min(usage["used_seconds"] / max(usage["limit_seconds"], 1), 1.0),
                text=f"Monthly allowance: {usage['used_seconds'] / 3600:.1f} / {usage['limit_seconds'] / 3600:.0f} hours",
            )
            if account["plan"] == "free":
                upgrade_plan = st.selectbox("Upgrade plan", ["starter", "pro"], key="clipper_upgrade_plan")
                if st.button("Open secure checkout", key="clipper_checkout"):
                    try:
                        from saas.providers import StripeBilling
                        checkout_url = StripeBilling().checkout_url(account, upgrade_plan)
                        st.link_button("Continue to Stripe", checkout_url, use_container_width=True)
                    except Exception as exc:
                        st.error(f"Billing is not configured yet: {exc}")
            if st.button("Sign out", key="clipper_sign_out"):
                st.session_state.pop("clipper_session_token", None)
                st.rerun()
        return account

    with st.sidebar:
        st.header("Account")
        mode = st.radio("Choose an action", ["Sign in", "Create account"], horizontal=True)
        email = st.text_input("Email", key="account_email")
        password = st.text_input("Password", type="password", key="account_password")
        if st.button(mode, type="primary", use_container_width=True):
            try:
                account = (
                    account_store.register(email, password)
                    if mode == "Create account"
                    else account_store.authenticate(email, password)
                )
                if account is None:
                    raise ValueError("Email or password is incorrect")
                st.session_state["clipper_session_token"] = account_store.issue_token(account)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    st.info("Sign in to continue. Account mode keeps each user's saved jobs separate.")
    st.stop()


def job_dir(job: dict) -> Path:
    return WORK / job["id"]


def source_path(job: dict) -> Path:
    return Path(job["source_path"])


def run_analysis(
    job: dict, model_size: str, min_seconds: int, max_seconds: int, max_clips: int,
    selection_strategy: str = "Heuristic", enable_diarization: bool = False,
) -> dict:
    directory = job_dir(job)
    source = source_path(job)
    started = time.perf_counter()
    job.update(status="analyzing", stage="media_validation", error=None, model_size=model_size)
    STORE.save(job)

    media = validate_video(source, MAX_SOURCE_SECONDS)
    if os.environ.get("CLIPPER_REQUIRE_AUTH") == "1" and job.get("owner_id"):
        usage = _account_store().consume_usage(job["owner_id"], job["id"], media["duration"])
        job["metrics"]["monthly_usage_seconds"] = usage["used_seconds"]
    job["media"] = media
    job["metrics"].update({
        "source_duration_seconds": round(media["duration"], 3),
        "source_size_bytes": source.stat().st_size,
    })
    job["stage"] = "audio_extraction"
    STORE.save(job)

    audio = extract_audio(source, directory / "audio.wav")
    job["stage"] = "transcription"
    STORE.save(job)
    words = transcribe(audio, model_size=model_size, device="cpu")
    if not words:
        raise ValueError("No timestamped words were returned. Check the audio or try a larger Whisper model.")
    if enable_diarization:
        turns, diarization_model = diarize_audio(audio, device="cpu")
        words = attach_speakers(words, turns)
        job["diarization_model"] = diarization_model
    else:
        job.pop("diarization_model", None)

    transcript_file = save_transcript(words, directory / "transcript.json")
    job["transcript_path"] = str(transcript_file)
    reference_path = job.get("reference_transcript_path")
    if reference_path and Path(reference_path).is_file():
        reference_text = Path(reference_path).read_text(encoding="utf-8-sig")
        job["metrics"]["transcript_wer"] = round(
            word_error_rate(reference_text, " ".join(word.text for word in words)), 4,
        )
    else:
        job["metrics"].pop("transcript_wer", None)
    job["stage"] = "candidate_selection"
    STORE.save(job)
    if selection_strategy == "Local semantic model":
        candidates = suggest_semantic_candidates(words, min_seconds, max_seconds, max_clips)
    else:
        candidates = suggest_candidates(words, min_seconds, max_seconds, max_clips)
    if not candidates:
        raise ValueError("No complete transcript segments matched the selected duration range.")
    job["candidates"] = [candidate.__dict__ for candidate in candidates]
    job["selection_strategy"] = selection_strategy
    job["status"] = "ready_for_review"
    job["stage"] = "review"
    job["error"] = None
    job["metrics"]["analysis_seconds"] = round(time.perf_counter() - started, 2)
    STORE.save(job)
    if os.environ.get("CLIPPER_REQUIRE_AUTH") == "1":
        try:
            _account_store().record_event(
                job["owner_id"], "video_analyzed",
                {"duration_seconds": round(media["duration"], 2), "success": True},
            )
        except Exception as exc:
            job["metrics"]["analytics_warning"] = str(exc)[:240]
            STORE.save(job)
    return job


def _safe_stem(text: str, fallback: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()[:48]
    return value or fallback


def render_batch(
    job: dict, selected: list[dict], caption_font_size: int,
    caption_margin_v: int, framing: str, transition: str = "none",
    include_speaker_labels: bool = False,
) -> tuple[dict, Path]:
    directory = job_dir(job)
    settings = {
        "caption_font_size": caption_font_size,
        "caption_margin_v": caption_margin_v,
        "framing": framing,
        "transition": transition,
        "include_speaker_labels": include_speaker_labels,
    }
    fingerprint_source = json.dumps(
        {"clips": selected, "settings": settings},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:12]
    batch_dir = directory / "renders" / fingerprint
    batch_dir.mkdir(parents=True, exist_ok=True)

    previous = job.get("rendered", []) if job.get("render_batch_fingerprint") == fingerprint else []
    rendered_by_index = {int(item["index"]): item for item in previous if "index" in item}
    job.update(
        status="rendering", stage="render", error=None,
        render_batch_fingerprint=fingerprint,
        selected_clips=selected,
        caption_settings=settings,
        rendered=previous,
    )
    STORE.save(job)
    started = time.perf_counter()
    progress = st.progress(0.0, text="Preparing clips")
    transcript_words = load_transcript(job["transcript_path"])

    for index, item in enumerate(selected, 1):
        title = item["title"]
        stem = _safe_stem(title, f"clip-{index:02d}")
        output = batch_dir / f"{index:02d}-{stem}.mp4"
        subtitle = output.with_suffix(".srt")
        expected_duration = float(item["end"]) - float(item["start"])
        existing = rendered_by_index.get(index)
        if (
            existing
            and Path(existing.get("path", "")).is_file()
            and Path(existing.get("subtitle_path", "")).is_file()
        ):
            try:
                validate_rendered_clip(existing["path"], expected_duration)
                progress.progress(index / len(selected), text=f"Reused clip {index}/{len(selected)}")
                continue
            except (OSError, RuntimeError, ValueError):
                pass

        write_srt(
            transcript_words, float(item["start"]), float(item["end"]), subtitle,
            include_speaker_labels=include_speaker_labels,
        )
        candidate = Candidate(
            start=float(item["start"]), end=float(item["end"]),
            text=transcript_excerpt(transcript_words, float(item["start"]), float(item["end"])),
            score=float(item.get("score", 0)), reasons=list(item.get("reasons", [])),
        )
        output = render_clip(
            source_path(job), candidate, subtitle, output,
            caption_font_size=caption_font_size,
            caption_margin_v=caption_margin_v,
            framing=framing,
            transition=transition,
        )
        media = validate_rendered_clip(output, expected_duration)
        record = {
            "index": index,
            "title": title,
            "path": str(output),
            "subtitle_path": str(subtitle),
            "start": candidate.start,
            "end": candidate.end,
            "score": candidate.score,
            "reasons": candidate.reasons,
            "duration": media["duration"],
        }
        rendered_by_index[index] = record
        job["rendered"] = list(rendered_by_index.values())
        job["stage"] = f"rendered_{index}_of_{len(selected)}"
        STORE.save(job)
        progress.progress(index / len(selected), text=f"Rendered {index}/{len(selected)}")

    rendered = [rendered_by_index[index] for index in range(1, len(selected) + 1)]
    source_hours = max(float(job["media"]["duration"]) / 3600, 1 / 3600)
    analysis_seconds = float(job["metrics"].get("analysis_seconds") or 0)
    render_seconds = round(time.perf_counter() - started, 2)
    selection_rate = len(selected) / max(len(job.get("candidates", [])), 1)
    cost_per_source_hour = max(0.0, float(os.environ.get("CLIPPER_COST_PER_SOURCE_HOUR_USD", "0")))
    estimated_cost = round(source_hours * cost_per_source_hour, 4) if cost_per_source_hour else None
    job["metrics"].update({
        "candidate_count": len(job.get("candidates", [])),
        "exported_clip_count": len(selected),
        "export_selection_rate": round(selection_rate, 4),
        "processing_seconds_per_source_hour": round((analysis_seconds + render_seconds) / source_hours, 2),
        "estimated_processing_cost_usd": estimated_cost,
    })
    report = {
        "job_id": job["id"],
        "source_name": job["source_name"],
        "model": job["model_size"],
        "source_duration_seconds": job["media"]["duration"],
        "analysis_seconds": analysis_seconds,
        "render_seconds": render_seconds,
        "transcript_wer": job["metrics"].get("transcript_wer"),
        "export_selection_rate": job["metrics"]["export_selection_rate"],
        "processing_seconds_per_source_hour": job["metrics"]["processing_seconds_per_source_hour"],
        "estimated_processing_cost_usd": estimated_cost,
        "caption_settings": settings,
        "framing": framing,
        "clips": [
            {key: record[key] for key in ("title", "start", "end", "score", "reasons", "duration")}
            for record in rendered
        ],
    }
    report_path = batch_dir / "processing-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    archive_path = batch_dir / "clips-export.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for record in rendered:
            archive.write(record["path"], Path(record["path"]).name)
            archive.write(record["subtitle_path"], Path(record["subtitle_path"]).name)
        archive.write(job["transcript_path"], "transcript.json")
        archive.write(report_path, report_path.name)

    job["rendered"] = rendered
    job["status"] = "complete"
    job["stage"] = "complete"
    job["error"] = None
    job["metrics"]["render_seconds"] = report["render_seconds"]
    STORE.save(job)
    if os.environ.get("CLIPPER_REQUIRE_AUTH") == "1":
        try:
            _account_store().record_event(
                job["owner_id"], "clips_exported",
                {"duration_seconds": round(float(job["media"]["duration"]), 2),
                 "clip_count": len(rendered), "success": True},
            )
        except Exception as exc:
            job["metrics"]["analytics_warning"] = str(exc)[:240]
            STORE.save(job)
    return job, archive_path


st.set_page_config(page_title="Local Clipper", page_icon="✂️", layout="wide")
account = _account_gate()
owner_id = account["id"] if account else "local"
st.markdown(
    "<style>.block-container{max-width:1320px;padding-top:2rem}.stCaption{opacity:.78}</style>",
    unsafe_allow_html=True,
)
st.title("Local Clipper")
st.caption("Turn an authorized long recording into reviewed, captioned vertical clips.")
st.info("Local experimental MVP. Review every suggestion and caption before publishing. Optional AI features need additional local models.")

with st.sidebar:
    st.header("Processing")
    model_size = st.selectbox("Whisper model", ["base", "small", "medium"], index=0)
    min_seconds = st.slider("Suggested clip minimum", 15, 45, 25)
    max_seconds = st.slider("Suggested clip maximum", 30, 90, 60)
    max_clips = st.slider("Maximum suggestions", 3, 20, 10)
    caption_font_size = st.slider("Caption size", 32, 62, 46)
    caption_position = st.selectbox("Caption position", ["Lower", "Middle", "Higher"], index=0)
    caption_margin_v = {"Lower": 160, "Middle": 250, "Higher": 360}[caption_position]
    framing_label = st.selectbox(
        "Vertical framing", ["Center crop", "Fit with black bars", "Subject-focused crop (OpenCV)"], index=0,
    )
    framing = {
        "Center crop": "center_crop",
        "Fit with black bars": "fit",
        "Subject-focused crop (OpenCV)": "subject_focus",
    }[framing_label]
    transition_label = st.selectbox("Clip transitions", ["None", "Fade in and out"], index=0)
    transition = "fade" if transition_label == "Fade in and out" else "none"
    selection_strategy = st.selectbox("Clip selection", ["Heuristic", "Local semantic model"], index=0)
    enable_diarization = st.checkbox(
        "Identify speakers (pyannote)", value=False,
        help="Optional local model. Install requirements-ai.txt and accept pyannote model terms; HF_TOKEN is required.",
    )
    include_speaker_labels = st.checkbox("Label speakers in captions", value=False)
    st.caption("Transcription uses CPU / int8. Model speed and memory use depend on your computer.")

    saved_jobs = STORE.list(owner_id=owner_id)
    if saved_jobs:
        labels = {
            item["id"]: f"{item.get('source_name', 'Video')} · {item.get('status', 'unknown')} · {item['id']}"
            for item in saved_jobs
        }
        ids = [item["id"] for item in saved_jobs]
        current_id = st.session_state.get("clipper_job_id")
        default_index = ids.index(current_id) if current_id in ids else 0
        selected_id = st.selectbox(
            "Saved jobs", ids, index=default_index, format_func=lambda value: labels[value],
            key="clipper_saved_job_selector",
        )
        if st.button("Open saved job", use_container_width=True):
            st.session_state["clipper_job_id"] = selected_id

uploaded = st.file_uploader(
    "Upload a video you own or are authorized to process",
    type=sorted(suffix.lstrip(".") for suffix in SUPPORTED_VIDEO_SUFFIXES),
    help=f"Maximum {MAX_UPLOAD_BYTES / 1024**3:.1f} GB and {MAX_SOURCE_SECONDS / 3600:g} hours.",
)
reference_upload = st.file_uploader(
    "Optional reference transcript for WER measurement",
    type=["txt"],
    help="Provide a human-checked UTF-8 text transcript to calculate word error rate locally.",
    key="reference_transcript_upload",
)

if uploaded is not None and st.button("Analyze video", type="primary", use_container_width=True):
    suffix = Path(uploaded.name).suffix.lower()
    if suffix not in SUPPORTED_VIDEO_SUFFIXES:
        st.error("This file extension is not supported.")
    elif uploaded.size > MAX_UPLOAD_BYTES:
        st.error(f"This upload exceeds the {MAX_UPLOAD_BYTES / 1024**3:.1f} GB local limit.")
    elif reference_upload is not None and reference_upload.size > 5 * 1024 * 1024:
        st.error("The reference transcript exceeds the 5 MB limit.")
    else:
        job = STORE.create(uploaded.name, WORK / "pending", owner_id=owner_id)
        target = job_dir(job) / f"source{suffix}"
        try:
            uploaded.seek(0)
            with target.open("wb") as destination:
                shutil.copyfileobj(uploaded, destination, length=1024 * 1024)
            if os.environ.get("CLIPPER_S3_BUCKET"):
                from saas.providers import S3MediaStore
                job["storage_key"] = S3MediaStore().upload(owner_id, str(target), uploaded.name)
                job["storage_backend"] = "s3"
            else:
                job["storage_backend"] = "local"
            job["source_path"] = str(target.resolve())
            if reference_upload is not None:
                reference_text = reference_upload.getvalue().decode("utf-8-sig").strip()
                if not reference_text:
                    raise ValueError("The reference transcript is empty.")
                reference_path = job_dir(job) / "reference.txt"
                reference_path.write_text(reference_text, encoding="utf-8")
                job["reference_transcript_path"] = str(reference_path.resolve())
            job["status"] = "uploaded"
            STORE.save(job)
            st.session_state["clipper_job_id"] = job["id"]
            with st.status("Analyzing the recording…", expanded=True) as status:
                status.write("Checking format, audio/video streams and duration")
                job = run_analysis(
                    job, model_size, min_seconds, max_seconds, max_clips,
                    selection_strategy=selection_strategy,
                    enable_diarization=enable_diarization,
                )
                status.update(label="Transcript and clip suggestions are ready", state="complete")
            st.success(f"Analysis complete: {len(job['candidates'])} suggestions.")
        except Exception as exc:
            job["status"] = "failed"
            job["error"] = str(exc)[:1600]
            job["stage"] = job.get("stage", "analysis")
            STORE.save(job)
            st.error(f"Analysis failed: {exc}")
            st.caption("The uploaded file and job state are saved locally. Open the saved job to retry analysis.")

active_id = st.session_state.get("clipper_job_id")
active_job = None
if active_id:
    try:
        active_job = STORE.load(active_id, owner_id=owner_id)
    except (OSError, ValueError, PermissionError) as exc:
        st.error(f"Could not open saved job: {exc}")

if active_job:
    job = active_job
    st.divider()
    st.subheader(job.get("source_name", "Saved video"))
    st.caption(f"Job {job['id']} · Status: {job['status'].replace('_', ' ').title()}")

    if job["status"] == "failed" and job.get("stage") == "render" and job.get("selected_clips"):
        st.warning(job.get("error") or "The last render step failed.")
        if st.button("Retry failed render", type="primary"):
            try:
                job, archive = render_batch(
                    job, job["selected_clips"], caption_font_size, caption_margin_v, framing,
                    transition, include_speaker_labels,
                )
                st.session_state["clipper_export"] = str(archive)
                st.success(f"Rendered and validated {len(job['rendered'])} clips.")
            except Exception as exc:
                job.update(status="failed", stage="render", error=str(exc)[:1600])
                STORE.save(job)
                st.error(f"Render retry failed: {exc}")

    elif job["status"] == "failed":
        st.warning(job.get("error") or "The last step failed.")
        if st.button("Retry analysis", type="primary"):
            try:
                with st.status("Retrying analysis…", expanded=True) as status:
                    job = run_analysis(
                        job, model_size, min_seconds, max_seconds, max_clips,
                        selection_strategy=selection_strategy,
                        enable_diarization=enable_diarization,
                    )
                    status.update(label="Analysis complete", state="complete")
                st.rerun()
            except Exception as exc:
                job.update(status="failed", error=str(exc)[:1600])
                STORE.save(job)
                st.error(f"Retry failed: {exc}")

    if job.get("media") and Path(job.get("source_path", "")).is_file():
        with st.expander("Source video preview", expanded=False):
            st.video(job["source_path"])
            st.caption(f"{job['media']['duration']:.1f}s · {job['media'].get('format_name', 'video')}")

    if job.get("transcript_path") and Path(job["transcript_path"]).is_file():
        transcript_words = load_transcript(job["transcript_path"])
        with st.expander("Edit transcript text", expanded=False):
            edited_transcript = st.text_area(
                "Correct words while preserving existing timestamps where possible",
                value=" ".join(word.text for word in transcript_words),
                height=220,
                key=f"transcript_editor_{job['id']}",
            )
            if st.button("Save transcript corrections", key=f"save_transcript_{job['id']}"):
                try:
                    corrected = align_transcript_correction(transcript_words, edited_transcript)
                    save_transcript(corrected, job["transcript_path"])
                    if job.get("selection_strategy") == "Local semantic model":
                        refreshed = suggest_semantic_candidates(
                            corrected, min_seconds, max_seconds, max_clips,
                        )
                    else:
                        refreshed = suggest_candidates(corrected, min_seconds, max_seconds, max_clips)
                    job["candidates"] = [candidate.__dict__ for candidate in refreshed]
                    job["selected_clips"] = None
                    job["rendered"] = []
                    job.update(status="ready_for_review", stage="review", error=None)
                    STORE.save(job)
                    st.success("Transcript corrections saved. Clip suggestions were refreshed.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not save the transcript corrections: {exc}")

    if job.get("candidates") and job.get("transcript_path") and Path(job["transcript_path"]).is_file():
        st.subheader("Review suggested clips")
        st.caption("Edit the start and end times, rename clips, and select the clips to export.")
        rows = []
        resume_clips = (
            job.get("selected_clips")
            if job.get("selected_clips") and (
                job.get("status") == "complete"
                or job.get("stage", "").startswith("render")
            )
            else None
        )
        if resume_clips:
            for item in resume_clips:
                rows.append({
                    "Export": True, "Title": item["title"],
                    "Start (s)": float(item["start"]), "End (s)": float(item["end"]),
                "Score": float(item.get("score", 0)),
                    "Why suggested": "; ".join(item.get("reasons", [])),
                    "Transcript excerpt": transcript_excerpt(
                        load_transcript(job["transcript_path"]), float(item["start"]), float(item["end"]),
                    )[:360],
                })
        for index, item in enumerate(job["candidates"]):
            if resume_clips and any(abs(float(saved["start"]) - float(item["start"])) < 0.01 for saved in resume_clips):
                continue
            rows.append({
                "Export": not resume_clips and index < 5,
                "Title": f"Clip {index + 1:02d}",
                "Start (s)": float(item["start"]),
                "End (s)": float(item["end"]),
                "Score": float(item["score"]),
                "Why suggested": "; ".join(item["reasons"]),
                "Transcript excerpt": item["text"][:360],
            })
        edited = st.data_editor(
            rows, hide_index=True, use_container_width=True,
            column_config={
                "Export": st.column_config.CheckboxColumn("Export", default=False),
                "Title": st.column_config.TextColumn("Clip title", max_chars=64),
                "Start (s)": st.column_config.NumberColumn("Start (s)", min_value=0.0, format="%.2f"),
                "End (s)": st.column_config.NumberColumn("End (s)", min_value=0.1, format="%.2f"),
                "Score": st.column_config.NumberColumn("Selection score", disabled=True, format="%.1f"),
                "Why suggested": st.column_config.TextColumn(disabled=True, width="large"),
                "Transcript excerpt": st.column_config.TextColumn(disabled=True, width="large"),
            },
            key=f"clip_editor_{job['id']}",
        )

        if st.button("Render selected clips", type="primary"):
            selected: list[dict] = []
            duration = float(job["media"]["duration"])
            errors: list[str] = []
            for row in edited:
                if not row.get("Export"):
                    continue
                start, end = float(row["Start (s)"]), float(row["End (s)"])
                title = str(row.get("Title", "")).strip() or f"Clip {len(selected) + 1:02d}"
                if start < 0 or end <= start or end > duration + 0.05:
                    errors.append(f"{title}: choose a valid range within the source video.")
                elif end - start < 5:
                    errors.append(f"{title}: clips must be at least 5 seconds long.")
                else:
                    selected.append({
                        "title": title,
                        "start": round(start, 3),
                        "end": round(end, 3),
                        "score": float(row["Score"]),
                        "reasons": next((item["reasons"] for item in job["candidates"]
                                         if abs(float(item["start"]) - start) < 0.01), []),
                    })
            if errors:
                for message in errors:
                    st.error(message)
            elif not selected:
                st.error("Select at least one clip to render.")
            elif len({item["title"].casefold() for item in selected}) != len(selected):
                st.error("Clip titles must be unique within one export batch.")
            else:
                try:
                    job, archive = render_batch(
                        job, selected, caption_font_size, caption_margin_v, framing,
                        transition, include_speaker_labels,
                    )
                    st.session_state["clipper_export"] = str(archive)
                    st.success(f"Rendered and validated {len(job['rendered'])} clips.")
                except Exception as exc:
                    job.update(status="failed", stage="render", error=str(exc)[:1600])
                    STORE.save(job)
                    st.error(f"Rendering failed: {exc}")
                    st.caption("Completed clips are retained locally. Reopen the job and retry after fixing the issue.")

    export = st.session_state.get("clipper_export")
    if job.get("render_batch_fingerprint"):
        export = str(job_dir(job) / "renders" / job["render_batch_fingerprint"] / "clips-export.zip")
        if Path(export).is_file():
            st.download_button(
                "Download clips, subtitles and processing report",
                Path(export).read_bytes(), file_name=f"{job['id']}-clips.zip",
                mime="application/zip", use_container_width=True,
            )

    if job.get("rendered"):
        with st.expander("Rendered clip previews", expanded=job.get("status") == "complete"):
            for record in job["rendered"]:
                path = Path(record["path"])
                if path.is_file():
                    st.markdown(f"**{record['title']}** · {record['start']:.1f}–{record['end']:.1f}s")
                    st.video(str(path))
        if job.get("metrics"):
            metrics = job["metrics"]
            cols = st.columns(5)
            if metrics.get("analysis_seconds") is not None:
                cols[0].metric("Analysis time", f"{metrics['analysis_seconds']:.1f}s")
            if metrics.get("render_seconds") is not None:
                cols[1].metric("Render time", f"{metrics['render_seconds']:.1f}s")
            if metrics.get("source_duration_seconds") is not None:
                cols[2].metric("Source duration", f"{metrics['source_duration_seconds'] / 60:.1f} min")
            if metrics.get("export_selection_rate") is not None:
                cols[3].metric("Suggestions exported", f"{metrics['export_selection_rate']:.0%}")
            if metrics.get("transcript_wer") is not None:
                cols[4].metric("Transcript WER", f"{metrics['transcript_wer']:.1%}")
            if metrics.get("estimated_processing_cost_usd") is not None:
                st.metric("Estimated configured processing cost", f"${metrics['estimated_processing_cost_usd']:.4f}")
