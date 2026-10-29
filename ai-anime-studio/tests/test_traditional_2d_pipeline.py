from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

import traditional_2d_pipeline as pipeline


def create_sheet(path: Path) -> None:
    sheet = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    colors = [(220, 70, 70, 255), (70, 170, 90, 255),
              (70, 100, 220, 255), (220, 180, 40, 255)]
    for row in range(2):
        for col in range(2):
            x0, y0 = col * 128, row * 128
            draw.ellipse((x0 + 24, y0 + 16, x0 + 104, y0 + 112), fill=colors[row * 2 + col])
    sheet.save(path)


def test_sheet_loader_trims_four_poses(tmp_path: Path) -> None:
    path = tmp_path / "sheet.png"
    create_sheet(path)
    poses = pipeline.load_pose_sheet(path)
    assert len(poses) == 4
    assert all(p.width > 0 and p.height > 0 for p in poses)


def test_keyframe_transform_interpolates_and_holds_pose() -> None:
    actor = {
        "cycle_fps": 0,
        "keyframes": [
            {"t": 0, "x": 0, "y": 100, "scale": 1, "rotation": 0, "pose": 1},
            {"t": 2, "x": 200, "y": 200, "scale": 2, "rotation": 30, "pose": 3, "ease": "linear"},
        ],
    }
    mid = pipeline.sample_actor(actor, 1)
    assert mid["x"] == 100
    assert mid["y"] == 150
    assert mid["scale"] == 1.5
    assert mid["rotation"] == 15
    assert mid["pose"] == 1
    end = pipeline.sample_actor(actor, 2)
    assert end["pose"] == 3


def test_render_manifest_outputs_decodable_mp4(tmp_path: Path) -> None:
    sheet = tmp_path / "sheet.png"
    create_sheet(sheet)
    manifest = {
        "width": 320, "height": 180, "fps": 8,
        "characters": {"test": {"sheet": "sheet.png"}},
        "scenes": [{
            "id": "test", "duration": 0.5, "background": "#eeeeee",
            "ground_y": 150, "actors": [{
                "character": "test", "height": 90,
                "keyframes": [
                    {"t": 0, "x": 60, "y": 150, "pose": 0},
                    {"t": 0.5, "x": 260, "y": 150, "pose": 1}
                ]
            }]
        }]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "out.mp4"
    result = pipeline.render_manifest(manifest_path, output)
    assert result.is_file()
    assert result.stat().st_size > 2048
