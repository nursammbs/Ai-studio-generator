from __future__ import annotations

import importlib.util
import os
import re
import shutil
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

from core import (
    extract_audio,
    render_clip,
    suggest_candidates,
    transcribe,
    validate_rendered_clip,
    validate_video,
    write_srt,
)


_VIDEO_URL = "https://svs.gsfc.nasa.gov/vis/a010000/a012800/a012825/Sarah_Jones.webm"
_CAPTIONS_URL = "https://svs.gsfc.nasa.gov/vis/a010000/a012800/a012825/SarahJones.en_US.srt"
_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
_READY = (
    os.environ.get("RUN_VIDEO_E2E") == "1"
    and all(shutil.which(name) for name in ("ffmpeg", "ffprobe"))
    and importlib.util.find_spec("faster_whisper") is not None
)


def _download(url: str, destination: Path, minimum_bytes: int) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "RevenueEngineClipper-CI/1.0"})
    total = 0
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
        if response.status != 200:
            raise AssertionError(f"NASA fixture download returned HTTP {response.status}")
        while chunk := response.read(64 * 1024):
            total += len(chunk)
            if total > _MAX_DOWNLOAD_BYTES:
                raise AssertionError("NASA video fixture exceeded the 20 MiB test limit")
            output.write(chunk)
    if total < minimum_bytes:
        raise AssertionError(f"NASA fixture download was unexpectedly small ({total} bytes)")


def _srt_text(path: Path) -> str:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    text_lines = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().isdigit() and "-->" not in line
    ]
    return " ".join(text_lines)


def _word_error_rate(reference: str, hypothesis: str) -> float:
    expected = re.findall(r"[\w']+", reference.casefold())
    actual = re.findall(r"[\w']+", hypothesis.casefold())
    if not expected:
        return 0.0 if not actual else 1.0
    previous = list(range(len(actual) + 1))
    for row, expected_word in enumerate(expected, start=1):
        current = [row]
        for column, actual_word in enumerate(actual, start=1):
            current.append(min(
                previous[column - 1] + (expected_word != actual_word),
                current[column - 1] + 1,
                previous[column] + 1,
            ))
        previous = current
    return previous[-1] / len(expected)


@unittest.skipUnless(_READY, "CI installs FFmpeg and faster-whisper for the real-video smoke test")
class RealVideoSmokeTests(unittest.TestCase):
    def test_nasa_interview_runs_through_transcription_selection_and_render(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "nasa-gold-interview.webm"
            reference = root / "nasa-gold-interview.srt"
            audio = root / "extracted.wav"
            subtitle = root / "clip.srt"
            output = root / "clip.mp4"

            _download(_VIDEO_URL, source, minimum_bytes=1_000_000)
            _download(_CAPTIONS_URL, reference, minimum_bytes=500)

            source_media = validate_video(source, max_duration_seconds=180)
            self.assertTrue(source_media["has_video"])
            self.assertTrue(source_media["has_audio"])
            self.assertGreater(source_media["duration"], 60)
            self.assertLess(source_media["duration"], 90)

            extract_audio(source, audio)
            started = time.perf_counter()
            words = transcribe(audio, model_size="base", device="cpu")
            inference_seconds = time.perf_counter() - started
            hypothesis = " ".join(word.text for word in words)
            self.assertGreater(len(words), 100, "Real interview speech should produce a substantial transcript")

            wer = _word_error_rate(_srt_text(reference), hypothesis)
            self.assertLessEqual(wer, 0.40, f"Real-video transcription WER was too high: {wer:.3f}")
            print(
                f"REAL_VIDEO_METRICS source=nasa-gold-interview "
                f"source_seconds={source_media['duration']:.2f} words={len(words)} "
                f"inference_seconds={inference_seconds:.2f} wer={wer:.3f}"
            )

            candidates = suggest_candidates(words, min_duration=10, max_duration=35, max_candidates=3)
            self.assertTrue(candidates, "Real speech should produce complete, reviewable clip candidates")
            chosen = candidates[0]
            write_srt(words, chosen.start, chosen.end, subtitle)
            self.assertTrue(subtitle.read_text(encoding="utf-8").strip())
            render_clip(source, chosen, subtitle, output)
            rendered = validate_rendered_clip(output, chosen.end - chosen.start)
            self.assertTrue(rendered["has_video"] and rendered["has_audio"])
            video_stream = next(stream for stream in rendered["streams"] if stream["codec_type"] == "video")
            self.assertAlmostEqual(video_stream["width"] / video_stream["height"], 9 / 16, delta=0.01)


if __name__ == "__main__":
    unittest.main()

