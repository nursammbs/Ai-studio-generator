import json
import shutil
import subprocess
import unittest
from pathlib import Path

from core import Candidate, Word, render_clip, validate_rendered_clip, write_srt

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "outputs" / "ci-quality"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools required")
class RenderedOutputQualityTests(unittest.TestCase):
    def test_synthetic_source_renders_valid_vertical_clip_and_review_frames(self):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        source = ARTIFACTS / "qa-source.mp4"
        output = ARTIFACTS / "qa-vertical-clip.mp4"
        subtitle = ARTIFACTS / "qa-vertical-clip.srt"
        frame = ARTIFACTS / "qa-frame.jpg"

        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=12",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=12",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", str(source),
        ], check=True, capture_output=True)

        words = [
            Word("This", 1.0, 1.3), Word("is", 1.3, 1.5),
            Word("a", 1.5, 1.6), Word("quality", 1.6, 2.0),
            Word("check.", 2.0, 2.5),
            Word("The", 3.0, 3.2), Word("video", 3.2, 3.6),
            Word("and", 3.6, 3.8), Word("audio", 3.8, 4.2),
            Word("must", 4.2, 4.5), Word("remain", 4.5, 4.9),
            Word("clear.", 4.9, 5.3),
        ]
        write_srt(words, 1.0, 9.0, subtitle)
        render_clip(
            source, Candidate(1.0, 9.0, "Synthetic QA clip.", 80.0, ["CI render"]),
            subtitle, output, width=720, height=1280,
            caption_font_size=30, caption_margin_v=80,
            framing="center_crop", transition="fade",
        )

        media = validate_rendered_clip(output, 8.0)
        video = next(s for s in media["streams"] if s["codec_type"] == "video")
        audio = next(s for s in media["streams"] if s["codec_type"] == "audio")
        self.assertEqual((video["width"], video["height"]), (720, 1280))
        self.assertTrue(audio.get("codec_name") in {"aac", "mp3", "opus"})
        self.assertGreater(output.stat().st_size, 10_000)
        srt = subtitle.read_text(encoding="utf-8")
        self.assertIn("This is a quality", srt)
        self.assertIn("-->", srt)

        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", "3", "-i", str(output), "-frames:v", "1", str(frame),
        ], check=True, capture_output=True)
        self.assertGreater(frame.stat().st_size, 1_000)
        (ARTIFACTS / "qa-report.json").write_text(json.dumps({
            "status": "PASS",
            "video": output.name,
            "frame": frame.name,
            "width": video["width"],
            "height": video["height"],
            "duration_seconds": media["duration"],
            "video_codec": video.get("codec_name"),
            "audio_codec": audio.get("codec_name"),
            "subtitle_file": subtitle.name,
            "note": "Synthetic fixture validates rendering and technical output only; it does not establish editorial quality on real footage."
        }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
