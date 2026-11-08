import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from core import Candidate, Word, extract_audio, render_clip, validate_rendered_clip, validate_video, write_srt


def _supports_required_ffmpeg() -> bool:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return False
    try:
        filters = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True, text=True, timeout=10,
        ).stdout
        encoders = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10,
        ).stdout
        return " subtitles " in filters and "libx264" in encoders
    except (OSError, subprocess.TimeoutExpired):
        return False


@unittest.skipUnless(_supports_required_ffmpeg(), "FFmpeg with ffprobe, libass and libx264 is not installed")
class MediaSmokeTests(unittest.TestCase):
    def test_synthetic_video_can_be_probed_transcribed_and_rendered(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "fixture.mp4"
            audio = root / "fixture.wav"
            subtitle = root / "clip.srt"
            output = root / "clip.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=blue:s=320x180:d=8",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", str(source),
            ], check=True, capture_output=True, timeout=60)

            media = validate_video(source)
            self.assertTrue(media["has_video"])
            self.assertTrue(media["has_audio"])
            extract_audio(source, audio)
            self.assertTrue(audio.is_file())
            words = [Word("A", 0.2, 0.7), Word("test.", 0.7, 1.2)]
            write_srt(words, 0, 8, subtitle)
            render_clip(source, Candidate(0, 8, "A test.", 50, []), subtitle, output)
            rendered = validate_rendered_clip(output, expected_duration=8)
            self.assertTrue(rendered["has_video"])
            self.assertTrue(rendered["has_audio"])


if __name__ == "__main__":
    unittest.main()

