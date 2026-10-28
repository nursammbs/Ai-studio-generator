import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import studio_pipeline
import workflow_inspect
import generate_motion_guides
from PIL import Image, ImageDraw


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


    def test_optional_seed_keeps_exported_workflow_value(self):
        patched = studio_pipeline.patch_shot_workflow(
            self.template, positive_node_id="10", positive_field="prompt_text",
            seed_node_id=None, seed_field="seed_value", image_node_id="20", image_field="ref_file",
            positive_prompt="test appearance", seed=99, uploaded_image_name="reference.png",
        )
        self.assertEqual(patched["10"]["inputs"]["seed_value"], 1)
        self.assertEqual(self.template["10"]["inputs"]["seed_value"], 1)

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
class WorkflowInspectorTests(unittest.TestCase):
    def test_reports_api_prompt_fields(self):
        data = {
            "10": {"class_type": "CLIPTextEncode", "inputs": {"text": "cat in kitchen", "clip": ["1", 0]}},
            "20": {"class_type": "LoadImage", "inputs": {"image": "cat.png", "upload": "image"}},
            "30": {"class_type": "SamplerCustom", "inputs": {"noise_seed": 9876}},
        }
        fmt, report = workflow_inspect.inspect_workflow(data)
        self.assertEqual(fmt, "api")
        self.assertIn("noise_seed", report)
        self.assertIn("cat in kitchen", report)
        self.assertIn("Node ID", report)

    def test_warns_when_input_is_ui_graph_not_api_json(self):
        data = {"nodes": [{
            "id": 261, "type": "MotionTransfer", "title": "Motion Transfer",
            "inputs": [{"name": "text"}, {"name": "text_4"}], "widgets_values": []
        }]}
        fmt, report = workflow_inspect.inspect_workflow(data)
        self.assertEqual(fmt, "ui")
        self.assertIn("not the API prompt format", report)
        self.assertIn("text_4", report)


class MotionGuideGeneratorTests(unittest.TestCase):
    def test_crop_pose_extracts_visible_sprite_from_one_quadrant(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sheet.png"
            sheet = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
            draw = ImageDraw.Draw(sheet)
            draw.rectangle((12, 12, 75, 42), fill=(220, 30, 40, 255))
            draw.rectangle((120, 12, 175, 42), fill=(20, 180, 60, 255))
            draw.rectangle((12, 62, 75, 92), fill=(40, 60, 230, 255))
            draw.rectangle((120, 62, 175, 92), fill=(230, 180, 40, 255))
            sheet.save(path)
            pose = generate_motion_guides.crop_pose(path, 0)
            self.assertEqual(pose.mode, "RGBA")
            self.assertIsNotNone(pose.getchannel("A").getbbox())
            self.assertGreater(pose.width, 60)

    def test_scene_frame_is_valid_832_by_480_rgb_image(self):
        cat = Image.new("RGBA", (200, 100), (110, 125, 145, 255))
        mouse = Image.new("RGBA", (120, 70), (170, 120, 90, 255))
        frame = generate_motion_guides.scene_frame(
            "02_chase_start", 1.0, [cat] * 4, [mouse] * 4
        )
        self.assertEqual(frame.size, (832, 480))
        self.assertEqual(frame.mode, "RGB")
        self.assertEqual(frame.getpixel((0, 0)), (228, 231, 230))

    def test_unknown_scene_fails_explicitly(self):
        cat = Image.new("RGBA", (20, 20), (255, 0, 0, 255))
        mouse = Image.new("RGBA", (20, 20), (0, 255, 0, 255))
        with self.assertRaisesRegex(ValueError, "Unknown scene"):
            generate_motion_guides.scene_frame("unused", 0.0, [cat] * 4, [mouse] * 4)


class ShotSelectionTests(unittest.TestCase):
    def setUp(self):
        self.shots = [
            studio_pipeline.Shot("one", Path("one.png"), "first", 1),
            studio_pipeline.Shot("two", Path("two.png"), "second", 2),
            studio_pipeline.Shot("three", Path("three.png"), "third", 3),
        ]

    def test_limit_shots_selects_first_n_in_order(self):
        self.assertEqual([s.id for s in studio_pipeline.select_shots(self.shots, limit_shots=1)], ["one"])
        self.assertEqual([s.id for s in studio_pipeline.select_shots(self.shots, limit_shots=2)], ["one", "two"])

    def test_only_shot_selects_exact_id(self):
        self.assertEqual([s.id for s in studio_pipeline.select_shots(self.shots, only_shot="two")], ["two"])

    def test_invalid_or_empty_selection_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            studio_pipeline.select_shots(self.shots, only_shot="missing")
        with self.assertRaisesRegex(ValueError, "at least 1"):
            studio_pipeline.select_shots(self.shots, limit_shots=0)
        with self.assertRaisesRegex(ValueError, "either"):
            studio_pipeline.select_shots(self.shots, only_shot="one", limit_shots=1)


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
            self.assertEqual(len(list((root / "review" / "frames").glob("*.png"))), 3)
            self.assertTrue((root / "review" / "qc_summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
