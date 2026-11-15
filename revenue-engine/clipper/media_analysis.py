from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path


def detect_scenes(video_path: str | Path, threshold: float = 27.0, min_scene_seconds: float = 1.0) -> dict:
    """Detect hard cuts with optional PySceneDetect; never block the core clipper."""
    source = Path(video_path)
    if threshold <= 0 or min_scene_seconds < 0:
        raise ValueError("Scene threshold must be positive and minimum scene duration cannot be negative.")
    try:
        from scenedetect import ContentDetector, detect
    except ImportError:
        return {"available": False, "scenes": [], "message": "Install requirements-media.txt to enable PySceneDetect."}

    raw = detect(str(source), ContentDetector(threshold=threshold))
    scenes = []
    for start, end in raw:
        start_s, end_s = float(start.get_seconds()), float(end.get_seconds())
        if end_s - start_s >= min_scene_seconds:
            scenes.append({"start": round(start_s, 3), "end": round(end_s, 3), "duration": round(end_s-start_s, 3)})
    return {"available": True, "scenes": scenes, "count": len(scenes), "threshold": threshold}


def detect_silence(video_path: str | Path, noise_db: float = -35.0, min_silence_seconds: float = 0.45) -> dict:
    """Use FFmpeg's silencedetect filter; no Python audio/ML package is required."""
    if noise_db >= 0 or min_silence_seconds <= 0:
        raise ValueError("Silence threshold must be negative dB and minimum silence must be positive.")
    if not shutil.which("ffmpeg"):
        return {"available": False, "intervals": [], "message": "FFmpeg was not found on PATH."}
    command = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(video_path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_seconds}",
        "-f", "null", "-"
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    log = (result.stderr or "") + "\n" + (result.stdout or "")
    starts = []
    intervals = []
    for line in log.splitlines():
        start_match = re.search(r"silence_start:\s*(-?[0-9.]+)", line)
        end_match = re.search(r"silence_end:\s*(-?[0-9.]+)", line)
        if start_match:
            starts.append(float(start_match.group(1)))
        if end_match:
            end = float(end_match.group(1))
            start = starts.pop(0) if starts else max(0.0, end - min_silence_seconds)
            intervals.append({"start": round(start, 3), "end": round(end, 3), "duration": round(max(0.0, end-start), 3)})
    if starts:
        intervals.append({"start": round(starts.pop(0), 3), "end": None, "duration": None})
    if result.returncode not in (0, 255) and not intervals:
        raise RuntimeError((log[-2000:] or "FFmpeg silence analysis failed."))
    return {"available": True, "intervals": intervals, "noise_db": noise_db, "minimum_seconds": min_silence_seconds}


def enrich_candidates_with_scenes(candidates: list[dict], scenes: list[dict], silence: list[dict]) -> list[dict]:
    """Add explainable visual-cut and silence context without pretending to predict virality."""
    enriched = []
    for original in candidates:
        item = dict(original)
        start, end = float(item["start"]), float(item["end"])
        reasons = list(item.get("reasons", []))
        internal_cuts = [
            scene for scene in scenes
            if start + 0.5 < float(scene["start"]) < end - 0.5
        ]
        if internal_cuts:
            reasons.append(f"Visual scene changes detected: {len(internal_cuts)}")
        overlapping_silence = [
            gap for gap in silence
            if float(gap["start"]) < end and (gap.get("end") is None or float(gap["end"]) > start)
        ]
        if overlapping_silence:
            reasons.append(f"Audio silence intervals to review: {len(overlapping_silence)}")
        item["scene_change_count"] = len(internal_cuts)
        item["silence_interval_count"] = len(overlapping_silence)
        item["reasons"] = reasons
        enriched.append(item)
    return enriched


def create_silence_trimmed_copy(video_path: str | Path, output_path: str | Path,
                                threshold: str = "0.04", margin: str = "0.2s") -> Path:
    """Run Auto-Editor as an optional separate review copy; source is never overwritten."""
    source, target = Path(video_path), Path(output_path)
    if source.resolve() == target.resolve():
        raise ValueError("Auto-Editor output must be a separate file; the original source is protected.")
    executable = shutil.which("auto-editor")
    if not executable:
        raise RuntimeError("Auto-Editor is not installed. Install it separately with: pip install auto-editor")
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        executable, str(source), "--edit", f"audio:threshold={threshold}",
        "--margin", margin, "-o", str(target),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=3600)
    if result.returncode:
        detail = (result.stderr or result.stdout or "Auto-Editor failed.")[-2500:]
        raise RuntimeError(detail)
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError("Auto-Editor did not create a non-empty review copy.")
    return target
