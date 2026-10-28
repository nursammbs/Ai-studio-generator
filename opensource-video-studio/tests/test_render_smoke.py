import shutil
import subprocess
from pathlib import Path

import pytest

import engine


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is not installed")
def test_smoke_renders_video_and_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "OUTPUTS", tmp_path / "outputs")
    monkeypatch.setattr(engine, "_commons_image", lambda query: None)

    def make_test_voice(text, target, language):
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-c:a", "libmp3lame", str(target),
            ],
            check=True,
            capture_output=True,
        )

    monkeypatch.setattr(engine, "_make_voice", make_test_voice)
    scenes = [
        {"heading": "Test scene one", "narration": "Test narration one.", "visual_query": "test"},
        {"heading": "Test scene two", "narration": "Test narration two.", "visual_query": "test"},
    ]
    job = engine.create_video(
        "CI smoke test",
        scenes,
        [{"title": "Example", "url": "https://example.com", "extract": "Test source."}],
        language="en",
        aspect="9:16",
    )

    assert (job / "video.mp4").is_file()
    assert (job / "video.mp4").stat().st_size > 1000
    assert (job / "thumbnail.jpg").is_file()
    assert (job / "script.md").is_file()
    assert (job / "sources.md").is_file()
    assert (job / "description.txt").is_file()
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(job / "video.mp4")],
        check=True, capture_output=True, text=True,
    )
    assert float(probe.stdout.strip()) > 1.0
