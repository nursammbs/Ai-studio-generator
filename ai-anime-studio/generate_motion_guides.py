#!/usr/bin/env python3
"""Generate deterministic cat/mouse 2D blocking guides for Wan Animate 2.

These MP4s are input motion references, NOT neural/video-model outputs.
"""
from __future__ import annotations
import argparse
import math
import subprocess
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
WIDTH, HEIGHT, FPS, FRAME_COUNT = 832, 480, 24, 81
SCENES = (
    ("01_cheese_discovery", "A curious cat spots a mouse beside cheese, with a subtle approach and pause."),
    ("02_chase_start", "The cat and mouse run left-to-right with a short comic skid."),
    ("03_kitchen_chaos", "The cat jumps and lands as the mouse dashes away."),
    ("04_final_gag", "The cat freezes in comic surprise as the mouse guards the cheese."),
)


def crop_pose(sheet_path: Path, index: int) -> Image.Image:
    """Crop one visible quadrant from a transparent 2x2 sprite sheet."""
    with Image.open(sheet_path) as source:
        sheet = source.convert("RGBA")
    if index not in range(4):
        raise ValueError("Sprite quadrant index must be 0, 1, 2 or 3.")
    col, row = index % 2, index // 2
    cell = sheet.crop((col * sheet.width // 2, row * sheet.height // 2,
                       (col + 1) * sheet.width // 2, (row + 1) * sheet.height // 2))
    bbox = cell.getchannel("A").getbbox()
    if not bbox:
        raise ValueError(f"Quadrant {index} of {sheet_path} is fully transparent.")
    sprite = cell.crop(bbox)
    margin = max(8, round(max(sprite.size) * 0.025))
    padded = Image.new("RGBA", (sprite.width + 2 * margin, sprite.height + 2 * margin), (0, 0, 0, 0))
    padded.alpha_composite(sprite, (margin, margin))
    return padded


def draw_background() -> Image.Image:
    canvas = Image.new("RGB", (WIDTH, HEIGHT), (228, 231, 230))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 394, WIDTH, HEIGHT), fill=(208, 213, 212))
    draw.line((0, 393, WIDTH, 393), fill=(167, 174, 174), width=2)
    return canvas


def _paste(canvas: Image.Image, sprite: Image.Image, center_x: float, baseline: float,
           max_width: int, max_height: int, scale: float = 1.0, angle: float = 0.0) -> None:
    factor = min(max_width / sprite.width, max_height / sprite.height) * scale
    rendered = sprite.resize((max(1, int(sprite.width * factor)), max(1, int(sprite.height * factor))),
                             Image.Resampling.LANCZOS)
    if angle:
        rendered = rendered.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    x, y = int(center_x - rendered.width / 2), int(baseline - rendered.height)
    canvas_rgba = canvas.convert("RGBA")
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    shadow_width = max(36, int(rendered.width * .62))
    sd.ellipse((int(center_x - shadow_width / 2), int(baseline - 5),
                int(center_x + shadow_width / 2), int(baseline + 8)), fill=(70, 75, 78, 40))
    canvas_rgba.alpha_composite(shadow)
    canvas_rgba.alpha_composite(rendered, (x, y))
    canvas.paste(canvas_rgba.convert("RGB"))


def _cheese(canvas: Image.Image, x: float, y: float) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.polygon([(x - 22, y + 10), (x + 20, y + 10), (x + 9, y - 13)],
                 fill=(255, 196, 55), outline=(153, 111, 31), width=2)
    for cx, cy, radius in [(x - 5, y + 1, 3), (x + 7, y + 4, 2), (x + 3, y - 7, 2)]:
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(222, 151, 32))


def scene_frame(scene: str, seconds: float, cat_poses: list[Image.Image],
                mouse_poses: list[Image.Image]) -> Image.Image:
    canvas = draw_background()
    cat = cat_poses[int(seconds * 8) % 4]
    mouse = mouse_poses[int(seconds * 10 + .5) % 4]
    cat_x, mouse_x, cat_y, mouse_y = 210.0, 550.0, 392.0, 392.0
    cat_scale, mouse_scale, cat_angle = 1.0, .56, 0.0
    total = FRAME_COUNT / FPS
    if scene == "01_cheese_discovery":
        cat_x = 160 + 22 * min(1, seconds / 1.7) + 4 * math.sin(seconds * 2)
        mouse_x = 500 + 7 * math.sin(seconds * 1.5)
        cat_scale = .93 + .02 * math.sin(seconds * 2.5)
        mouse_scale = .54 + .008 * math.sin(seconds * 3)
        _cheese(canvas, 660, 375)
    elif scene == "02_chase_start":
        progress = seconds / total
        cat_x, mouse_x = 135 + 315 * progress, 510 + 150 * progress
        cat_scale = 1 + .055 * math.sin(seconds * 13)
        mouse_scale = .55 + .025 * math.sin(seconds * 15)
        cat_y = 392 + 5 * math.sin(seconds * 15)
        mouse_y = 392 + 5 * math.sin(seconds * 16 + .5)
        if progress > .79:
            cat_angle = -4 + 2 * math.sin(seconds * 8)
        _cheese(canvas, min(790, mouse_x + 75), 377)
    elif scene == "03_kitchen_chaos":
        progress = seconds / total
        cat_x = 165 + 300 * progress
        cat_y = 392 - 115 * math.sin(math.pi * progress)
        cat_scale = .92 + .14 * math.sin(math.pi * progress)
        cat_angle = -7 * math.sin(math.pi * progress)
        mouse_x, mouse_y = 575 + 85 * progress, 392 - 15 * max(0, math.sin(math.pi * progress))
        mouse_scale = .54 + .04 * math.sin(math.pi * progress)
        _cheese(canvas, 770, 376)
    elif scene == "04_final_gag":
        cat_x = 370 + 3 * math.sin(seconds * 2.7)
        cat_y = 392 - 6 * abs(math.sin(seconds * 5))
        cat_scale = .98 + .06 * abs(math.sin(seconds * 5))
        mouse_x = 625 - 16 * math.sin(seconds * 1.7)
        mouse_scale = .54 + .015 * math.sin(seconds * 2.8)
        _cheese(canvas, 700, 375)
    else:
        raise ValueError(f"Unknown scene name: {scene}")
    _paste(canvas, mouse, mouse_x, mouse_y, 220, 170, mouse_scale)
    _paste(canvas, cat, cat_x, cat_y, 360, 270, cat_scale, cat_angle)
    return canvas


def generate_assets(source_dir: Path, output_dir: Path, *, fps: int = FPS, frame_count: int = FRAME_COUNT) -> list[Path]:
    if fps <= 0 or frame_count < 2:
        raise ValueError("FPS must be positive and frame_count must be at least 2.")
    cat_sheet, mouse_sheet = source_dir / "cat_running_sheet_clean.png", source_dir / "mouse_running_sheet_clean.png"
    if not cat_sheet.is_file() or not mouse_sheet.is_file():
        raise FileNotFoundError(f"Expected cat_running_sheet_clean.png and mouse_running_sheet_clean.png in {source_dir}")
    cat_poses = [crop_pose(cat_sheet, i) for i in range(4)]
    mouse_poses = [crop_pose(mouse_sheet, i) for i in range(4)]
    references, motion = output_dir / "assets" / "refs", output_dir / "assets" / "motion"
    references.mkdir(parents=True, exist_ok=True)
    motion.mkdir(parents=True, exist_ok=True)
    created = []
    for scene, _description in SCENES:
        reference = scene_frame(scene, 0, cat_poses, mouse_poses)
        image_path, video_path = references / f"{scene}.png", motion / f"{scene}.mp4"
        reference.save(image_path, optimize=True)
        with imageio.get_writer(str(video_path), fps=fps, codec="libx264", quality=8,
                                pixelformat="yuv420p", macro_block_size=1) as writer:
            for frame_idx in range(frame_count):
                writer.append_data(np.asarray(scene_frame(scene, frame_idx / fps, cat_poses, mouse_poses)))
        if __import__("shutil").which("ffmpeg"):
            checked = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i",
                                      str(video_path), "-f", "null", "-"],
                                     capture_output=True, text=True)
            if checked.returncode:
                raise RuntimeError(f"Video validation failed for {video_path}: {checked.stderr[-1000:]}")
        created.extend([image_path, video_path])
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-dir", type=Path, default=HERE / "assets" / "source")
    parser.add_argument("--output-dir", type=Path, default=HERE)
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--frames", type=int, default=FRAME_COUNT)
    args = parser.parse_args()
    for path in generate_assets(args.assets_dir, args.output_dir, fps=args.fps, frame_count=args.frames):
        print(path)
    print("Done. These are 2D blocking guides, not Wan-generated animation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
