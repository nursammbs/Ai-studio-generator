#!/usr/bin/env python3
"""Render deterministic, asset-based 2D limited animation without a generative GPU.

Reuses transparent 2x2 pose sheets, keyframed placement, scale, rotation,
backgrounds and scene timing. It is a no-GPU production path, not a replacement
for drawing, rigging or animator review.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from imageio_ffmpeg import get_ffmpeg_exe

POSES_PER_SHEET = 4
ALLOWED_EASING = {"linear", "smoothstep"}


def load_pose_sheet(path: Path) -> list[Image.Image]:
    """Load a transparent 2x2 pose sheet and trim each pose to its alpha bounds."""
    if not path.is_file():
        raise FileNotFoundError(f"Sprite sheet not found: {path}")
    with Image.open(path) as opened:
        sheet = opened.convert("RGBA")
    if sheet.width < 128 or sheet.height < 128 or sheet.width % 2 or sheet.height % 2:
        raise ValueError(f"Sprite sheet must be an even-sized 2x2 grid at least 128x128: {path}")
    cell_w, cell_h = sheet.width // 2, sheet.height // 2
    poses: list[Image.Image] = []
    for row in range(2):
        for col in range(2):
            cell = sheet.crop((col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h))
            mask = cell.getchannel("A").point(lambda value: 0 if value < 12 else value)
            cell.putalpha(mask)
            bounds = cell.getchannel("A").getbbox()
            if not bounds:
                raise ValueError(f"Pose {row * 2 + col} is fully transparent in {path}")
            poses.append(cell.crop(bounds))
    return poses


def resolve_path(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def load_manifest(path: Path) -> tuple[dict[str, Any], dict[str, list[Image.Image]], list[dict[str, Any]]]:
    manifest_path = path.resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Manifest root must be a JSON object.")
    width, height, fps = int(data.get("width", 1280)), int(data.get("height", 720)), int(data.get("fps", 24))
    if width < 320 or height < 180 or not 8 <= fps <= 60:
        raise ValueError("Use width >=320, height >=180 and FPS from 8 to 60.")
    character_defs, scenes = data.get("characters"), data.get("scenes")
    if not isinstance(character_defs, dict) or not character_defs:
        raise ValueError("Manifest requires a non-empty characters object.")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Manifest requires a non-empty scenes array.")

    character_poses: dict[str, list[Image.Image]] = {}
    for name, raw in character_defs.items():
        if not isinstance(raw, dict) or not raw.get("sheet"):
            raise ValueError(f"Character '{name}' needs a sheet path.")
        sheet_path = resolve_path(manifest_path.parent, str(raw["sheet"]))
        assert sheet_path is not None
        character_poses[str(name)] = load_pose_sheet(sheet_path)

    normalized_scenes: list[dict[str, Any]] = []
    scene_ids: set[str] = set()
    for index, raw_scene in enumerate(scenes):
        if not isinstance(raw_scene, dict):
            raise ValueError(f"scenes[{index}] must be an object.")
        sid = str(raw_scene.get("id", f"scene_{index + 1:02d}")).strip()
        if not sid or sid in scene_ids:
            raise ValueError(f"Missing or duplicate scene ID: {sid!r}")
        scene_ids.add(sid)
        duration = float(raw_scene.get("duration", 0))
        if not math.isfinite(duration) or not 0.1 <= duration <= 600:
            raise ValueError(f"Scene '{sid}' duration must be between 0.1 and 600 seconds.")
        bg_path = resolve_path(manifest_path.parent, raw_scene.get("background_image"))
        if bg_path and not bg_path.is_file():
            raise FileNotFoundError(f"Background image missing for '{sid}': {bg_path}")
        bg_color = str(raw_scene.get("background", "#dce8e8"))
        if not (len(bg_color) == 7 and bg_color.startswith("#")):
            raise ValueError(f"Scene '{sid}' background must be a #RRGGBB color.")
        try:
            tuple(int(bg_color[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError as exc:
            raise ValueError(f"Invalid background color in scene '{sid}': {bg_color}") from exc
        actors = raw_scene.get("actors", [])
        if not isinstance(actors, list):
            raise ValueError(f"Scene '{sid}' actors must be an array.")
        for actor_index, actor in enumerate(actors):
            if not isinstance(actor, dict):
                raise ValueError(f"Actor {actor_index} in '{sid}' must be an object.")
            char = str(actor.get("character", ""))
            if char not in character_poses:
                raise ValueError(f"Scene '{sid}' references unknown character '{char}'.")
            actor_height = float(actor.get("height", 240))
            if not math.isfinite(actor_height) or not 12 <= actor_height <= height * 2:
                raise ValueError(f"Actor height must be 12 to {height * 2} pixels in '{sid}'.")
            frames = actor.get("keyframes")
            if not isinstance(frames, list) or not frames:
                raise ValueError(f"Actor '{char}' in '{sid}' needs keyframes.")
            previous_t = -1.0
            for key in frames:
                if not isinstance(key, dict):
                    raise ValueError(f"Actor keyframes in '{sid}' must be objects.")
                t = float(key.get("t", -1))
                if not math.isfinite(t) or t < 0 or t > duration or t <= previous_t:
                    raise ValueError(f"Actor keyframe times must be ascending and within scene '{sid}'.")
                previous_t = t
                for prop in ("x", "y", "scale", "rotation"):
                    if prop in key and not math.isfinite(float(key[prop])):
                        raise ValueError(f"Invalid {prop} at keyframe in '{sid}'.")
                if float(key.get("scale", 1.0)) <= 0:
                    raise ValueError(f"Actor scale must be positive in '{sid}'.")
                if int(key.get("pose", 0)) not in range(POSES_PER_SHEET):
                    raise ValueError(f"Pose index must be between 0 and 3 in '{sid}'.")
                easing = str(key.get("ease", "linear"))
                if easing not in ALLOWED_EASING:
                    raise ValueError(f"Easing must be one of {sorted(ALLOWED_EASING)}.")
            cycle_fps = float(actor.get("cycle_fps", 0))
            if not math.isfinite(cycle_fps) or not 0 <= cycle_fps <= 30:
                raise ValueError(f"cycle_fps must be 0 to 30 for '{char}'.")
        normalized_scenes.append({**raw_scene, "id": sid, "duration": duration,
                                  "background_image_path": bg_path, "actors": actors})
    data["width"], data["height"], data["fps"] = width, height, fps
    return data, character_poses, normalized_scenes


def _ease(value: float, kind: str) -> float:
    value = min(1.0, max(0.0, value))
    if kind == "smoothstep":
        return value * value * (3.0 - 2.0 * value)
    return value


def sample_actor(actor: dict[str, Any], local_t: float) -> dict[str, float]:
    """Interpolate transforms; the pose holds on the last keyed drawing."""
    keys = actor["keyframes"]
    left = keys[0]
    right = keys[0]
    for key in keys:
        if float(key["t"]) <= local_t:
            left = key
        if float(key["t"]) > local_t:
            right = key
            break
    else:
        right = left
    if right is left or float(right["t"]) <= float(left["t"]):
        amount = 0.0
    else:
        amount = (local_t - float(left["t"])) / (float(right["t"]) - float(left["t"]))
        amount = _ease(amount, str(right.get("ease", "linear")))
    result: dict[str, float] = {}
    for prop, default in (("x", 0.0), ("y", 0.0), ("scale", 1.0), ("rotation", 0.0)):
        a, b = float(left.get(prop, default)), float(right.get(prop, default))
        result[prop] = a + (b - a) * amount
    pose = int(left.get("pose", 0))
    cycle_fps = float(actor.get("cycle_fps", 0))
    if cycle_fps > 0:
        pose = (pose + int(max(0.0, local_t - float(left["t"])) * cycle_fps)) % POSES_PER_SHEET
    result["pose"] = float(pose)
    return result


def _rgb(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def draw_background(scene: dict[str, Any], width: int, height: int) -> Image.Image:
    canvas = Image.new("RGB", (width, height), _rgb(scene["background"]))
    bg_path = scene.get("background_image_path")
    if bg_path:
        with Image.open(bg_path) as opened:
            background = opened.convert("RGB")
        factor = max(width / background.width, height / background.height)
        fitted = background.resize((int(background.width * factor), int(background.height * factor)),
                                   Image.Resampling.LANCZOS)
        left, top = (fitted.width - width) // 2, (fitted.height - height) // 2
        canvas.paste(fitted.crop((left, top, left + width, top + height)), (0, 0))
    ground_y = scene.get("ground_y")
    if ground_y is not None:
        gy = int(float(ground_y))
        ground_color = _rgb(str(scene.get("ground_color", "#b1b8b8")))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, gy, width, height), fill=ground_color)
        draw.line((0, gy, width, gy), fill=tuple(max(0, c - 35) for c in ground_color), width=2)
    return canvas


def paste_actor(canvas: Image.Image, sprite: Image.Image, x: float, baseline_y: float,
                desired_height: float, rotation: float) -> None:
    ratio = desired_height / max(1, sprite.height)
    new_size = (max(1, int(sprite.width * ratio)), max(1, int(sprite.height * ratio)))
    rendered = sprite.resize(new_size, Image.Resampling.LANCZOS)
    if abs(rotation) > 0.01:
        rendered = rendered.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=True)
    px, py = int(round(x - rendered.width / 2)), int(round(baseline_y - rendered.height))
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.alpha_composite(rendered, (px, py))
    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.alpha_composite(layer)
    canvas.paste(canvas_rgba.convert("RGB"))


def draw_caption(canvas: Image.Image, caption: str) -> None:
    if not caption:
        return
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", max(14, canvas.width // 48))
    except OSError:
        font = ImageFont.load_default()
    margin_x, margin_bottom = max(16, canvas.width // 40), max(14, canvas.height // 32)
    bbox = draw.textbbox((0, 0), caption, font=font, stroke_width=1)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    box_w = min(canvas.width - margin_x * 2, text_w + margin_x)
    box_h = text_h + 20
    x0, y0 = (canvas.width - box_w) // 2, canvas.height - margin_bottom - box_h
    draw.rounded_rectangle((x0, y0, x0 + box_w, y0 + box_h), radius=max(6, box_h // 4),
                           fill=(15, 20, 25), outline=(240, 244, 245), width=1)
    draw.text(((canvas.width - text_w) // 2, y0 + 8), caption, font=font,
              fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0))


def render_manifest(manifest_path: Path, output_path: Path, *, music_path: Path | None = None) -> Path:
    data, poses, scenes = load_manifest(manifest_path)
    width, height, fps = data["width"], data["height"], data["fps"]
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = get_ffmpeg_exe()
    silent_path = output_path.with_name(output_path.stem + "_silent.mp4")
    frame_count = 0
    writer = imageio.get_writer(str(silent_path), fps=fps, codec="libx264", quality=8,
                                pixelformat="yuv420p", macro_block_size=1)
    try:
        for scene_index, scene in enumerate(scenes):
            count = max(1, int(round(scene["duration"] * fps)))
            print(f"[{scene_index + 1}/{len(scenes)}] {scene['id']}: {count} frames")
            for frame_index in range(count):
                local_t = frame_index / fps
                canvas = draw_background(scene, width, height)
                for actor in scene["actors"]:
                    transform = sample_actor(actor, local_t)
                    sprite = poses[str(actor["character"])][int(transform["pose"])]
                    desired_height = float(actor.get("height", 240)) * transform["scale"]
                    paste_actor(canvas, sprite, transform["x"], transform["y"],
                                desired_height, transform["rotation"])
                draw_caption(canvas, str(scene.get("caption", "")))
                writer.append_data(np.asarray(canvas))
                frame_count += 1
    finally:
        writer.close()
    if frame_count == 0 or not silent_path.is_file() or silent_path.stat().st_size < 2048:
        raise RuntimeError("No video frames were rendered.")
    if music_path:
        if not music_path.is_file():
            raise FileNotFoundError(f"Music track not found: {music_path}")
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent_path),
             "-stream_loop", "-1", "-i", str(music_path), "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
             "-movflags", "+faststart", str(output_path)],
            capture_output=True, text=True,
        )
        if result.returncode:
            raise RuntimeError(f"FFmpeg audio mux failed: {result.stderr[-2000:]}")
        silent_path.unlink(missing_ok=True)
    else:
        silent_path.replace(output_path)
    check = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(output_path),
                            "-f", "null", "-"], capture_output=True, text=True)
    if check.returncode:
        raise RuntimeError(f"Output MP4 did not decode: {check.stderr[-2000:]}")
    print(f"PASS: {output_path} | {frame_count} frames | {frame_count / fps:.2f}s | {output_path.stat().st_size:,} bytes")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="JSON timeline and character assets")
    parser.add_argument("--output", type=Path, default=Path("outputs/traditional_2d_episode.mp4"))
    parser.add_argument("--music", type=Path, help="Optional audio track; looped and trimmed to video duration")
    parser.add_argument("--validate-only", action="store_true", help="Validate manifest and assets without rendering")
    args = parser.parse_args(argv)
    try:
        if args.validate_only:
            data, poses, scenes = load_manifest(args.manifest)
            print(f"VALID: {len(poses)} characters, {len(scenes)} scenes, {data['fps']} FPS")
            return 0
        render_manifest(args.manifest, args.output, music_path=args.music)
        return 0
    except (ValueError, FileNotFoundError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
