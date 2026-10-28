import json
import tempfile
import unittest
from pathlib import Path
import studio_pipeline

class ProjectParsingTests(unittest.TestCase):
    def test_loads_source_video_shot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "clip.mp4").write_bytes(b"placeholder")
            project = root / "project.json"
            project.write_text(json.dumps({"shots": [{
                "id":"shot_01", "reference_image":"unused.png", "source_video":"clip.mp4",
                "prompt":"cat runs", "seed":7, "speed":1.2
            }]}), encoding="utf-8")
            _, shots = studio_pipeline.load_project(project)
            self.assertEqual(len(shots), 1)
            self.assertEqual(shots[0].id, "shot_01")
            self.assertEqual(shots[0].source_video, root / "clip.mp4")
            self.assertAlmostEqual(shots[0].speed, 1.2)

    def test_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ref.png").write_bytes(b"placeholder")
            project = root / "project.json"
            shot = {"id":"same", "reference_image":"ref.png", "prompt":"run", "seed":1}
            project.write_text(json.dumps({"shots":[shot,shot]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                studio_pipeline.load_project(project)

    def test_rejects_speed_outside_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ref.png").write_bytes(b"placeholder")
            project = root / "project.json"
            project.write_text(json.dumps({"shots":[{
                "id":"shot", "reference_image":"ref.png", "prompt":"run", "seed":1, "speed":8
            }]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Speed"):
                studio_pipeline.load_project(project)

if __name__ == "__main__":
    unittest.main()
