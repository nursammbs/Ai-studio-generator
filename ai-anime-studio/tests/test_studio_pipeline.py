import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import studio_pipeline


class ProjectParsingTests(unittest.TestCase):
    def test_loads_source_video_shots_for_assemble_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = root / "clip.mp4"
            clip.write_bytes(b"placeholder video file")
            project = root / "project.json"
            project.write_text(json.dumps({"shots": [{
                "id": "shot_01", "reference_image": "unused.png", "source_video": "clip.mp4",
                "prompt": "cat runs", "seed": 7, "speed": 1.2
            }]}), encoding="utf-8")
            data, shots = studio_pipeline.load_project(project)
            self.assertEqual(len(shots), 1)
            self.assertEqual(shots[0].id, "shot_01")
            self.assertEqual(shots[0].source_video, clip)
            self.assertAlmostEqual(shots[0].speed, 1.2)

    def test_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "ref.png"
            image.write_bytes(b"placeholder")
            project = root / "project.json"
            shot = {"id": "same", "reference_image": "ref.png", "prompt": "run", "seed": 1}
            project.write_text(json.dumps({"shots": [shot, shot]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                studio_pipeline.load_project(project)

    def test_rejects_speed_outside_supported_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "ref.png"
            image.write_bytes(b"placeholder")
            project = root / "project.json"
            shot = {"id": "shot", "reference_image": "ref.png", "prompt": "run", "seed": 1, "speed": 8}
            project.write_text(json.dumps({"shots": [shot]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Speed"):
                studio_pipeline.load_project(project)

    def test_resolves_motion_video_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ref.png").write_bytes(b"placeholder")
            (root / "motion.mp4").write_bytes(b"placeholder")
            project = root / "project.json"
            project.write_text(json.dumps({"shots": [{
                "id": "shot", "reference_image": "ref.png", "motion_video": "motion.mp4",
                "prompt": "animate", "seed": 2
            }]}), encoding="utf-8")
            _, shots = studio_pipeline.load_project(project)
            self.assertEqual(shots[0].motion_video, root / "motion.mp4")


class WorkflowPatchingTests(unittest.TestCase):
    def setUp(self):
        self.template = {
            "10": {"inputs": {"prompt_text": "", "seed_value": 1}},
            "20": {"inputs": {"ref_file": "old.png"}},
            "30": {"inputs": {"driving_clip": "old.mp4"}},
            "40": {"inputs": {"negative": ""}},
        }

    def test_patches_nonstandard_node_field_names(self):
        patched = studio_pipeline.patch_shot_workflow(
            self.template, positive_node_id="10", positive_field="prompt_text",
            seed_node_id="10", seed_field="seed_value", image_node_id="20", image_field="ref_file",
            positive_prompt="cat chases mouse", seed=42, uploaded_image_name="reference.png",
            negative_node_id="40", negative_field="negative", negative_prompt="flicker",
            motion_node_id="30", motion_field="driving_clip", motion_filename="motion.mp4",
        )
        self.assertEqual(patched["10"]["inputs"]["prompt_text"], "cat chases mouse")
        self.assertEqual(patched["10"]["inputs"]["seed_value"], 42)
        self.assertEqual(patched["20"]["inputs"]["ref_file"], "reference.png")
        self.assertEqual(patched["30"]["inputs"]["driving_clip"], "motion.mp4")
        self.assertEqual(patched["40"]["inputs"]["negative"], "flicker")

    def test_patching_isolated_between_shots(self):
        first = studio_pipeline.patch_shot_workflow(
            self.template, positive_node_id="10", positive_field="prompt_text",
            seed_node_id="10", seed_field="seed_value", image_node_id="20", image_field="ref_file",
            positive_prompt="first shot", seed=1, uploaded_image_name="first.png",
            motion_node_id="30", motion_field="driving_clip", motion_filename="first.mp4",
        )
        second = studio_pipeline.patch_shot_workflow(
            self.template, positive_node_id="10", positive_field="prompt_text",
            seed_node_id="10", seed_field="seed_value", image_node_id="20", image_field="ref_file",
            positive_prompt="second shot", seed=2, uploaded_image_name="second.png",
        )
        self.assertEqual(first["30"]["inputs"]["driving_clip"], "first.mp4")
        self.assertEqual(second["30"]["inputs"]["driving_clip"], "old.mp4")
        self.assertEqual(self.template["30"]["inputs"]["driving_clip"], "old.mp4")

    def test_patches_separate_appearance_and_pose_prompts(self):
        self.template["10"]["inputs"]["pose"] = ""
        patched = studio_pipeline.patch_shot_workflow(
            self.template, positive_node_id="10", positive_field="prompt_text",
            seed_node_id="10", seed_field="seed_value", image_node_id="20", image_field="ref_file",
            positive_prompt="character appearance and background", seed=5, uploaded_image_name="cat.png",
            pose_prompt_node_id="10", pose_prompt_field="pose", pose_prompt="follow the driving motion",
        )
        self.assertEqual(patched["10"]["inputs"]["prompt_text"], "character appearance and background")
        self.assertEqual(patched["10"]["inputs"]["pose"], "follow the driving motion")
        self.assertEqual(self.template["10"]["inputs"]["pose"], "")

    def test_rejects_invalid_workflow_field(self):
        with self.assertRaisesRegex(ValueError, "no input"):
            studio_pipeline.patch_shot_workflow(
                self.template, positive_node_id="10", positive_field="missing",
                seed_node_id="10", seed_field="seed_value", image_node_id="20", image_field="ref_file",
                positive_prompt="test", seed=1, uploaded_image_name="ref.png",
            )


class FingerprintTests(unittest.TestCase):
    def test_fingerprint_changes_with_prompt_or_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ref = root / "ref.png"
            ref.write_bytes(b"reference A")
            workflow = root / "workflow.json"
            workflow.write_text('{"node":"A"}', encoding="utf-8")
            shot = studio_pipeline.Shot("one", ref, "walk", 1, 1.0)
            options = {"style": "2D", "characters": "cat", "negative": "flicker",
                       "node_config": {"positive": "10"}}
            first = studio_pipeline.shot_fingerprint(shot, workflow, **options)
            changed_prompt = studio_pipeline.Shot("one", ref, "run", 1, 1.0)
            second = studio_pipeline.shot_fingerprint(changed_prompt, workflow, **options)
            self.assertNotEqual(first, second)
            workflow.write_text('{"node":"B"}', encoding="utf-8")
            third = studio_pipeline.shot_fingerprint(shot, workflow, **options)
            self.assertNotEqual(first, third)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/ffprobe not installed")
class ReviewBundleTests(unittest.TestCase):
    def test_creates_contact_sheet_and_offline_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = root / "tiny.mp4"
            result = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "testsrc=size=160x90:rate=12:duration=1",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)
            ], capture_output=True, text=True)
            if result.returncode != 0:
                self.skipTest("FFmpeg test-source filter is unavailable")
            shot = studio_pipeline.Shot("shot_01", root / "unused.png", "Cat turns to camera", 7)
            page, sheet = studio_pipeline.create_review_bundle([shot], [clip], root / "review", root / "final.mp4")
            self.assertTrue(page.is_file())
            self.assertTrue(sheet.is_file())
            self.assertIn("Cat turns to camera", page.read_text(encoding="utf-8"))
            self.assertEqual(len(list((root / "review" / "frames").glob("*.jpg"))), 3)
            self.assertTrue((root / "review" / "qc_summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
