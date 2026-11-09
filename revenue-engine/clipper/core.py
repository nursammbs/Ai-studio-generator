from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from difflib import SequenceMatcher
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
DEFAULT_MAX_SOURCE_SECONDS = 4 * 60 * 60
_SENTENCE_END = re.compile(r"[.!?][\"')\]]?$")
_CONTINUATION_STARTS = {"and", "but", "because", "so", "which", "that", "or", "although", "while"}
_HOOK_TERMS = re.compile(r"\b(why|how|what if|here's why|the reason|mistake|secret|lesson|surprising)\b", re.I)
_INSIGHT_TERMS = re.compile(r"\b(because|therefore|which means|the result|learned|lesson|realized|instead)\b", re.I)
_STORY_TERMS = re.compile(r"\b(problem|failed|wrong|changed|challenge|discovered|finally|turned out)\b", re.I)


@dataclass
class Word:
    text: str
    start: float
    end: float
    speaker: str | None = None


@dataclass
class Candidate:
    start: float
    end: float
    text: str
    score: float
    reasons: list[str]


def run_checked(command: list[str], *, timeout: float = 900) -> subprocess.CompletedProcess:
    """Run a media command and surface a useful, bounded error message."""
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Media command exceeded the {timeout:g}s timeout") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        if len(detail) > 2400:
            detail = detail[-2400:]
        raise RuntimeError(detail or f"Media command failed with exit code {exc.returncode}") from exc


def probe_media(path: str | Path) -> dict:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.suffix.lower() not in SUPPORTED_VIDEO_SUFFIXES:
        raise ValueError(f"Unsupported video extension: {source.suffix or '(none)'}")
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe was not found on PATH")

    result = run_checked([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,format_name:stream=codec_type,width,height,sample_rate",
        "-of", "json", str(source),
    ], timeout=60)
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    duration = float(payload.get("format", {}).get("duration", 0))
    if duration <= 0:
        raise ValueError("Media duration is missing or invalid")
    return {
        "duration": duration,
        "format_name": payload.get("format", {}).get("format_name", "unknown"),
        "has_video": any(stream.get("codec_type") == "video" for stream in streams),
        "has_audio": any(stream.get("codec_type") == "audio" for stream in streams),
        "streams": streams,
    }


def validate_video(path: str | Path, max_duration_seconds: float = DEFAULT_MAX_SOURCE_SECONDS) -> dict:
    if max_duration_seconds <= 0:
        raise ValueError("Maximum source duration must be positive")
    media = probe_media(path)
    if not media["has_video"]:
        raise ValueError("The uploaded file has no video stream")
    if not media["has_audio"]:
        raise ValueError("The uploaded video has no audio stream to transcribe")
    if media["duration"] > max_duration_seconds:
        raise ValueError(f"Video is longer than the {max_duration_seconds / 3600:g} hour limit")
    return media


def extract_audio(video_path: str | Path, wav_path: str | Path) -> Path:
    validate_video(video_path)
    target = Path(wav_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    run_checked([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target),
    ])
    return target


def transcribe(audio_path: str | Path, model_size: str = "base", device: str = "cpu") -> list[Word]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Install faster-whisper to enable transcription") from exc
    if not Path(audio_path).is_file():
        raise FileNotFoundError(audio_path)
    if model_size not in {"tiny", "tiny.en", "base", "small", "medium", "large-v3"}:
        raise ValueError("Choose a supported faster-whisper model size")
    if device not in {"cpu", "cuda"}:
        raise ValueError("Transcription device must be cpu or cuda")

    compute_type = "int8" if device == "cpu" else "float16"
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, _info = model.transcribe(
        str(audio_path), word_timestamps=True, vad_filter=True, beam_size=3,
    )
    words: list[Word] = []
    for segment in segments:
        for item in (getattr(segment, "words", None) or []):
            token = str(item.word).strip()
            start, end = float(item.start), float(item.end)
            if token and 0 <= start < end:
                words.append(Word(token, start, end))
    return words


def load_transcript(path: str | Path) -> list[Word]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    words = [
        Word(str(item["text"]), float(item["start"]), float(item["end"]), item.get("speaker"))
        for item in payload
    ]
    _validate_words(words)
    return words


def _validate_words(words: list[Word]) -> None:
    previous_start = -1.0
    for word in words:
        if not word.text.strip() or word.start < 0 or word.end <= word.start:
            raise ValueError("Transcript contains an invalid word or timestamp")
        if word.start < previous_start:
            raise ValueError("Transcript timestamps must be ordered")
        previous_start = word.start


def _sentences(words: list[Word]) -> list[tuple[float, float, str]]:
    """Return complete sentence spans; an unfinished transcript tail is excluded."""
    _validate_words(words)
    result: list[tuple[float, float, str]] = []
    chunk: list[Word] = []
    for word in words:
        chunk.append(word)
        if _SENTENCE_END.search(word.text):
            result.append((chunk[0].start, chunk[-1].end, " ".join(item.text for item in chunk)))
            chunk = []
    return result


def suggest_candidates(
    words: list[Word], min_duration: float = 25.0, max_duration: float = 60.0,
    max_candidates: int = 12,
) -> list[Candidate]:
    if min_duration <= 0 or max_duration <= min_duration:
        raise ValueError("Require 0 < min_duration < max_duration")
    if max_candidates <= 0:
        return []
    sentences = _sentences(words)
    candidates: list[Candidate] = []

    for left, (start, _sentence_end, _text) in enumerate(sentences):
        if sentences[left][2].split()[0].lower().strip("\"'(") in _CONTINUATION_STARTS:
            continue
        pieces: list[str] = []
        for right in range(left, len(sentences)):
            end = sentences[right][1]
            pieces.append(sentences[right][2])
            duration = end - start
            if duration > max_duration:
                break
            if duration < min_duration:
                continue

            excerpt = " ".join(pieces).strip()
            reasons: list[str] = ["Starts and ends on complete transcript sentences"]
            if _HOOK_TERMS.search(excerpt):
                reasons.append("Has a question, curiosity cue, or explicit lesson")
            if _INSIGHT_TERMS.search(excerpt):
                reasons.append("Contains an explanation or takeaway")
            if _STORY_TERMS.search(excerpt):
                reasons.append("Includes a problem, change, or discovery cue")
            words_per_minute = len(excerpt.split()) / max(duration, 1) * 60
            pace_score = max(0.0, 1.0 - abs(words_per_minute - 145) / 145)
            score = min(100.0, 35.0 + pace_score * 25.0 + (len(reasons) - 1) * 10.0)
            candidates.append(Candidate(
                round(start, 3), round(end, 3), excerpt, round(score, 1), reasons,
            ))

    candidates.sort(key=lambda candidate: (-candidate.score, candidate.start))
    selected: list[Candidate] = []
    for candidate in candidates:
        duration = candidate.end - candidate.start
        duplicate = any(
            max(0.0, min(candidate.end, item.end) - max(candidate.start, item.start))
            >= 0.4 * min(duration, item.end - item.start)
            for item in selected
        )
        if duplicate:
            continue
        selected.append(candidate)
        if len(selected) >= max_candidates:
            break
    return sorted(selected, key=lambda candidate: candidate.start)


def transcript_excerpt(words: Iterable[Word], start: float, end: float) -> str:
    return " ".join(word.text for word in words if word.end > start and word.start < end).strip()


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Return normalized word-level Levenshtein distance for a reference transcript."""
    tokenize = lambda value: re.findall(r"[\w']+", value.casefold())
    expected, actual = tokenize(reference), tokenize(hypothesis)
    if not expected:
        return 0.0 if not actual else 1.0
    previous = list(range(len(actual) + 1))
    for row, expected_word in enumerate(expected, start=1):
        current = [row]
        for column, actual_word in enumerate(actual, start=1):
            substitution = previous[column - 1] + (expected_word != actual_word)
            insertion = current[column - 1] + 1
            deletion = previous[column] + 1
            current.append(min(substitution, insertion, deletion))
        previous = current
    return previous[-1] / len(expected)


def align_transcript_correction(words: list[Word], corrected_text: str) -> list[Word]:
    """Apply edited words while retaining Whisper times wherever alignment permits."""
    _validate_words(words)
    new_tokens = corrected_text.split()
    if not new_tokens:
        raise ValueError("Corrected transcript must contain at least one word")
    normalize = lambda value: re.sub(r"[^\w']+", "", value.casefold())
    matcher = SequenceMatcher(
        a=[normalize(word.text) for word in words],
        b=[normalize(token) for token in new_tokens],
        autojunk=False,
    )
    aligned: list[Word | None] = [None] * len(new_tokens)
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        count = new_end - new_start
        if count <= 0:
            continue
        if tag == "equal":
            for offset in range(count):
                source = words[old_start + offset]
                aligned[new_start + offset] = Word(
                    new_tokens[new_start + offset], source.start, source.end, source.speaker,
                )
            continue

        if old_end > old_start:
            start = words[old_start].start
            end = words[old_end - 1].end
            speaker = words[old_start].speaker
        else:
            start = words[old_start - 1].end if old_start else 0.0
            end = words[old_start].start if old_start < len(words) else start
            speaker = words[old_start - 1].speaker if old_start else None
            if end <= start:
                end = start + count * 0.22

        span = max(end - start, count * 0.08)
        step = span / count
        for offset in range(count):
            token_start = start + step * offset
            token_end = start + step * (offset + 1)
            aligned[new_start + offset] = Word(new_tokens[new_start + offset], token_start, token_end, speaker)

    result = [word for word in aligned if word is not None]
    _validate_words(result)
    return result


def _srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds_part, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds_part:02},{milliseconds:03}"


def _wrap_caption(words: list[str], max_chars: int = 34) -> str:
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars and len(lines) < 1:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines)


def _caption_cues(
    words: list[Word], clip_start: float, clip_end: float, include_speaker_labels: bool = False,
) -> list[tuple[float, float, str]]:
    if clip_start < 0 or clip_end <= clip_start:
        raise ValueError("Clip start/end range is invalid")
    selected = [
        Word(word.text, max(word.start, clip_start), min(word.end, clip_end))
        for word in words if word.end > clip_start and word.start < clip_end
    ]
    cues: list[tuple[float, float, str]] = []
    group: list[Word] = []

    def flush() -> None:
        if group:
            text = _wrap_caption([word.text for word in group])
            if include_speaker_labels and group[0].speaker:
                text = f"{group[0].speaker}: {text}"
            cues.append((group[0].start - clip_start, group[-1].end - clip_start, text))
            group.clear()

    for word in selected:
        tentative = group + [word]
        text = " ".join(item.text for item in tentative)
        pause = word.start - group[-1].end if group else 0.0
        terminal = bool(_SENTENCE_END.search(group[-1].text)) if group else False
        elapsed = word.end - group[0].start if group else 0.0
        if group and (
            len(tentative) > 7 or len(text) > 64 or pause > 0.65
            or elapsed > 3.2 or terminal
            or word.speaker != group[0].speaker
        ):
            flush()
        group.append(word)
    flush()
    return cues


def write_srt(
    words: Iterable[Word], clip_start: float, clip_end: float, target: str | Path,
    include_speaker_labels: bool = False,
) -> Path:
    cue_lines: list[str] = []
    for index, (start, end, text) in enumerate(
        _caption_cues(list(words), clip_start, clip_end, include_speaker_labels), 1,
    ):
        if end <= start:
            continue
        cue_lines.extend([str(index), f"{_srt_time(start)} --> {_srt_time(end)}", text, ""])
    output = Path(target)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(cue_lines), encoding="utf-8")
    return output


def validate_rendered_clip(path: str | Path, expected_duration: float | None = None) -> dict:
    media = probe_media(path)
    if not media["has_video"]:
        raise ValueError("Rendered file has no video stream")
    if not media["has_audio"]:
        raise ValueError("Rendered file has no audio stream")
    if expected_duration is not None and abs(media["duration"] - expected_duration) > 1.5:
        raise ValueError(
            f"Rendered duration {media['duration']:.2f}s differs from expected "
            f"{expected_duration:.2f}s by more than 1.5s"
        )
    video_streams = [stream for stream in media["streams"] if stream.get("codec_type") == "video"]
    if not video_streams or video_streams[0].get("width", 0) <= 0 or video_streams[0].get("height", 0) <= 0:
        raise ValueError("Rendered video dimensions are invalid")
    ratio = video_streams[0]["width"] / video_streams[0]["height"]
    if abs(ratio - (9 / 16)) > 0.01:
        raise ValueError("Rendered video is not in vertical 9:16 format")
    return media


def render_clip(
    video_path: str | Path, candidate: Candidate, subtitle_path: str | Path,
    output_path: str | Path, width: int = 1080, height: int = 1920,
    caption_font_size: int = 46, caption_margin_v: int = 250,
    framing: str = "center_crop", transition: str = "none",
    subject_center: tuple[float, float] | None = None,
) -> Path:
    if width <= 0 or height <= 0:
        raise ValueError("Output dimensions must be positive")
    if candidate.start < 0 or candidate.end <= candidate.start:
        raise ValueError("Clip start/end range is invalid")
    if not 24 <= caption_font_size <= 96 or not 80 <= caption_margin_v <= 500:
        raise ValueError("Caption size or position is outside the supported range")
    if framing not in {"center_crop", "fit", "subject_focus"}:
        raise ValueError("Framing must be center_crop, fit or subject_focus")
    if transition not in {"none", "fade"}:
        raise ValueError("Transition must be none or fade")
    if Path(output_path).suffix.lower() != ".mp4":
        raise ValueError("Rendered clips must use the .mp4 extension")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg was not found on PATH")
    video = Path(video_path)
    media = validate_video(video)
    if candidate.end > media["duration"] + 0.05:
        raise ValueError("Clip ends after the source video")
    subtitle_file = Path(subtitle_path)
    if not subtitle_file.is_file():
        raise FileNotFoundError(subtitle_file)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.stem}.partial{target.suffix or '.mp4'}")
    subtitle = str(subtitle_file.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    if framing == "fit":
        framing_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
    elif framing == "subject_focus":
        if subject_center is None:
            from reframing import detect_subject_center
            subject_center = detect_subject_center(video, candidate.start, candidate.end)
        if subject_center is None:
            framing_filter = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
        else:
            center_x, center_y = (min(max(float(value), 0.0), 1.0) for value in subject_center)
            framing_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}:min(max(iw*{center_x:.5f}-{width}/2,0),iw-{width}):"
                f"min(max(ih*{center_y:.5f}-{height}/2,0),ih-{height})"
            )
    else:
        framing_filter = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    video_filter = (
        f"{framing_filter},subtitles='{subtitle}':force_style='FontName=Arial,"
        f"FontSize={caption_font_size},Outline=4,Shadow=1,Alignment=2,MarginV={caption_margin_v}'"
    )
    clip_duration = candidate.end - candidate.start
    fade_duration = min(0.35, clip_duration / 6)
    audio_filter = None
    if transition == "fade":
        video_filter += (
            f",fade=t=in:st=0:d={fade_duration:.3f}"
            f",fade=t=out:st={clip_duration - fade_duration:.3f}:d={fade_duration:.3f}"
        )
        audio_filter = (
            f"afade=t=in:st=0:d={fade_duration:.3f},"
            f"afade=t=out:st={clip_duration - fade_duration:.3f}:d={fade_duration:.3f}"
        )
    try:
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{candidate.start:.3f}", "-i", str(video),
            "-t", f"{candidate.end - candidate.start:.3f}",
            "-map", "0:v:0", "-map", "0:a?", "-vf", video_filter,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        ]
        if audio_filter:
            command += ["-af", audio_filter]
        command += ["-movflags", "+faststart", str(temporary)]
        run_checked(command)
        validate_rendered_clip(temporary, candidate.end - candidate.start)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def save_transcript(words: list[Word], target: str | Path) -> Path:
    _validate_words(words)
    output = Path(target)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps([asdict(word) for word in words], ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def save_json_atomic(payload: dict, target: str | Path) -> Path:
    output = Path(target)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=output.parent, prefix=f".{output.name}.",
            suffix=".tmp", delete=False,
        ) as temporary:
            temporary_name = temporary.name
            json.dump(payload, temporary, ensure_ascii=False, indent=2)
            temporary.flush()
        Path(temporary_name).replace(output)
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
    return output
