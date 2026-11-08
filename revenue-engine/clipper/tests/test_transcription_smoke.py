import importlib.util
import os
import shutil
import subprocess
import tempfile
import time
import unittest
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


_READY = (
    os.environ.get("RUN_VIDEO_E2E") == "1"
    and all(shutil.which(name) for name in ("ffmpeg", "ffprobe", "espeak-ng"))
    and importlib.util.find_spec("faster_whisper") is not None
)


@unittest.skipUnless(_READY, "CI installs FFmpeg, espeak-ng and faster-whisper for this smoke test")
class TranscriptionSmokeTests(unittest.TestCase):
    def test_synthetic_speech_runs_through_transcription_selection_and_render(self):
        sentences = [
            "Why does reliability matter?",
            "Every clip should preserve a complete idea.",
            "We measure each word and timestamp carefully.",
            "Clear captions help creators save editing time.",
            "That is the reason for this test.",
        ] * 3
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            speech = root / "speech.wav"
            source = root / "source.mp4"
            audio = root / "extracted.wav"
            subtitle = root / "clip.srt"
            output = root / "clip.mp4"

            subprocess.run([
                "espeak-ng", "-v", "en-us", "-s", "150", "-w", str(speech), " ".join(sentences),
            ], check=True, capture_output=True, timeout=30)
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=navy:s=320x180:r=24",
                "-i", str(speech), "-shortest", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
            ], check=True, capture_output=True, timeout=60)

            source_media = validate_video(source)
            extract_audio(source, audio)
            started = time.perf_counter()
            words = transcribe(audio, model_size="base", device="cpu")
            inference_seconds = time.perf_counter() - started
            self.assertGreater(len(words), 20)
            print(
                f"TRANSCRIPTION_METRICS model=base "
                f"source_seconds={source_media['duration']:.2f} "
                f"inference_seconds={inference_seconds:.2f} "
                f"realtime_factor={inference_seconds / source_media['duration']:.3f}"
            )

            candidates = suggest_candidates(words, min_duration=5, max_duration=20, max_candidates=3)
            self.assertTrue(candidates, "Transcription should produce complete, reviewable clip candidates")
            chosen = candidates[0]
            write_srt(words, chosen.start, chosen.end, subtitle)
            render_clip(source, chosen, subtitle, output)
            rendered = validate_rendered_clip(output, chosen.end - chosen.start)
            self.assertTrue(rendered["has_video"] and rendered["has_audio"])


if __name__ == "__main__":
    unittest.main()

