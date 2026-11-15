import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import media_analysis


class MediaAnalysisTests(unittest.TestCase):
    def test_enrich_candidates_adds_scene_and_silence_reasons_without_changing_ranges(self):
        candidates = [{"start": 5.0, "end": 35.0, "score": 70, "reasons": ["Complete sentences"]}]
        scenes = [{"start": 15.0, "end": 25.0, "duration": 10.0}]
        silence = [{"start": 20.0, "end": 21.0, "duration": 1.0}]
        result = media_analysis.enrich_candidates_with_scenes(candidates, scenes, silence)
        self.assertEqual(result[0]["start"], 5.0)
        self.assertEqual(result[0]["end"], 35.0)
        self.assertEqual(result[0]["scene_change_count"], 1)
        self.assertEqual(result[0]["silence_interval_count"], 1)
        self.assertIn("Visual scene changes detected: 1", result[0]["reasons"])
        self.assertIn("Audio silence intervals to review: 1", result[0]["reasons"])

    def test_enrich_does_not_flag_scene_cut_outside_candidate(self):
        result = media_analysis.enrich_candidates_with_scenes(
            [{"start": 10.0, "end": 20.0, "reasons": []}],
            [{"start": 30.0, "end": 40.0}],
            [],
        )
        self.assertEqual(result[0]["scene_change_count"], 0)
        self.assertEqual(result[0]["silence_interval_count"], 0)

    def test_detect_silence_parses_ffmpeg_output(self):
        completed = types.SimpleNamespace(
            returncode=0,
            stderr="[silencedetect @ 0x1] silence_start: 1.25\n[silencedetect @ 0x1] silence_end: 2.75 | silence_duration: 1.50",
            stdout="",
        )
        with patch.object(media_analysis.shutil, "which", return_value="/usr/bin/ffmpeg"), \
             patch.object(media_analysis.subprocess, "run", return_value=completed):
            result = media_analysis.detect_silence("video.mp4")
        self.assertEqual(result["intervals"], [{"start": 1.25, "end": 2.75, "duration": 1.5}])

    def test_detect_scenes_uses_optional_pyscenedetect_api(self):
        class Timecode:
            def __init__(self, seconds):
                self.seconds = seconds
            def get_seconds(self):
                return self.seconds

        fake = types.ModuleType("scenedetect")
        fake.ContentDetector = lambda threshold: ("content", threshold)
        fake.detect = lambda path, detector, show_progress: [
            (Timecode(0), Timecode(3)), (Timecode(3), Timecode(8))
        ]
        with patch.dict(sys.modules, {"scenedetect": fake}):
            result = media_analysis.detect_scenes("video.mp4", min_scene_seconds=2)
        self.assertTrue(result["available"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["scenes"][1]["start"], 3.0)

    def test_auto_editor_never_overwrites_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.mp4"
            source.write_bytes(b"original")
            with self.assertRaises(ValueError):
                media_analysis.create_silence_trimmed_copy(source, source)


if __name__ == "__main__":
    unittest.main()
