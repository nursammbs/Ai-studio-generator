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
        mouth_sheet = resolve_path(manifest_path.parent, raw.get("mouth_sheet"))
        if raw.get("mouth_sheet") and (mouth_sheet is None or not mouth_sheet.is_file()):
            raise FileNotFoundError(f"Mouth sheet missing for '{name}': {mouth_sheet}")
        if mouth_sheet:
            anchor = raw.get("mouth_anchor", [0.5, 0.42])
            if not isinstance(anchor, list) or len(anchor) != 2:
                raise ValueError(f"mouth_anchor for '{name}' must be [x, y] normalized coordinates.")
            anchor = [float(anchor[0]), float(anchor[1])]
            if not all(math.isfinite(v) and 0.0 <= v <= 1.0 for v in anchor):
                raise ValueError(f"mouth_anchor for '{name}' must contain values from 0 to 1.")
            mouth_width = float(raw.get("mouth_width", 0.16))
            if not math.isfinite(mouth_width) or not 0.02 <= mouth_width <= 0.6:
                raise ValueError(f"mouth_width for '{name}' must be from 0.02 to 0.6.")
            raw["_mouth_sheet_path"] = mouth_sheet
            raw["_mouth_anchor"] = anchor
            raw["_mouth_width"] = mouth_width

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
        dialogue = raw_scene.get("dialogue", [])
        if not isinstance(dialogue, list):
            raise ValueError(f"Scene '{sid}' dialogue must be an array.")
        normalized_dialogue: list[dict[str, Any]] = []
        for line_index, line in enumerate(dialogue):
            if not isinstance(line, dict):
                raise ValueError(f"Dialogue {line_index} in '{sid}' must be an object.")
            speaker = str(line.get("character", ""))
            if speaker not in character_poses:
                raise ValueError(f"Dialogue in '{sid}' references unknown character '{speaker}'.")
            if not character_defs[speaker].get("_mouth_sheet_path"):
                raise ValueError(f"Character '{speaker}' needs mouth_sheet to use dialogue lip-sync.")
            audio_path = resolve_path(manifest_path.parent, line.get("audio"))
            viseme_path = resolve_path(manifest_path.parent, line.get("visemes"))
            if audio_path is None or not audio_path.is_file():
                raise FileNotFoundError(f"Dialogue audio missing in '{sid}': {audio_path}")
            if viseme_path is None or not viseme_path.is_file():
                raise FileNotFoundError(f"Dialogue viseme JSON missing in '{sid}': {viseme_path}")
            timeline = json.loads(viseme_path.read_text(encoding="utf-8"))
            events = timeline.get("visemes") if isinstance(timeline, dict) else None
            if not isinstance(events, list):
                raise ValueError(f"Viseme JSON for '{sid}' must contain a visemes array.")
            checked_events: list[dict[str, Any]] = []
            for event in events:
                if not isinstance(event, dict):
                    raise ValueError(f"Malformed viseme event in '{sid}'.")
                start = float(event.get("start", -1))
                event_duration = float(event.get("duration", -1))
                mouth_index = int(event.get("mouth_index", -1))
                if (not math.isfinite(start) or not math.isfinite(event_duration)
                        or start < 0 or event_duration < 0 or mouth_index not in range(4)):
                    raise ValueError(f"Invalid viseme timing or mouth_index in '{sid}'.")
                checked_events.append({**event, "start": start, "duration": event_duration,
                                        "mouth_index": mouth_index})
            line_start = float(line.get("start", 0))
            volume = float(line.get("volume", 1.0))
            if not math.isfinite(line_start) or not 0 <= line_start < duration:
                raise ValueError(f"Dialogue start for '{sid}' must be within the scene.")
            if not math.isfinite(volume) or not 0 <= volume <= 2:
                raise ValueError(f"Dialogue volume for '{sid}' must be from 0 to 2.")
            normalized_dialogue.append({
                **line, "character": speaker, "audio_path": audio_path,
                "visemes_data": checked_events, "start": line_start, "volume": volume,
            })
        normalized_scenes.append({**raw_scene, "id": sid, "duration": duration,
                                  "background_image_path": bg_path, "actors": actors,
                                  "dialogue": normalized_dialogue})
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


def sample_mouth_pose(events: list[dict[str, Any]], local_t: float) -> int:
    """Return the four-shape mouth index active at a local dialogue timestamp."""
    if local_t < 0:
        return 0
    for event in reversed(events):
        start = float(event["start"])
        if start <= local_t < start + float(event["duration"]):
            return int(event["mouth_index"])
    return 0


def paste_mouth(canvas: Image.Image, mouth: Image.Image, base_sprite: Image.Image,
                x: float, baseline_y: float, desired_height: float, rotation: float,
                anchor: list[float], width_fraction: float) -> None:
    """Overlay one transparent mouth pose at a normalized point on the character."""
    body_ratio = desired_height / max(1, base_sprite.height)
    body_width = base_sprite.width * body_ratio
    center_x = x + (float(anchor[0]) - 0.5) * body_width
    center_y = baseline_y - desired_height + float(anchor[1]) * desired_height
    if abs(rotation) > 0.01:
        pivot_y = baseline_y - desired_height / 2
        dx, dy = center_x - x, center_y - pivot_y
        angle = math.radians(rotation)
        center_x = x + math.cos(angle) * dx + math.sin(angle) * dy
        center_y = pivot_y - math.sin(angle) * dx + math.cos(angle) * dy
    target_width = max(2, int(round(desired_height * width_fraction)))
    target_height = max(2, int(round(target_width * mouth.height / max(1, mouth.width))))
    rendered = mouth.resize((target_width, target_height), Image.Resampling.LANCZOS)
    if abs(rotation) > 0.01:
        rendered = rendered.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=True)
    px, py = int(round(center_x - rendered.width / 2)), int(round(center_y - rendered.height / 2))
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
    character_defs = data["characters"]
    mouth_poses = {
        name: load_pose_sheet(raw["_mouth_sheet_path"])
        for name, raw in character_defs.items() if raw.get("_mouth_sheet_path")
    }
    voice_tracks: list[tuple[Path, float, float]] = []
    scene_offsets: list[float] = []
    running_offset = 0.0
    for scene in scenes:
        scene_offsets.append(running_offset)
        for line in scene["dialogue"]:
            voice_tracks.append((line["audio_path"], running_offset + line["start"], line["volume"]))
        running_offset += scene["duration"]
    total_duration = running_offset

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
                    character = str(actor["character"])
                    transform = sample_actor(actor, local_t)
                    sprite = poses[character][int(transform["pose"])]
                    desired_height = float(actor.get("height", 240)) * transform["scale"]
                    paste_actor(canvas, sprite, transform["x"], transform["y"],
                                desired_height, transform["rotation"])
                    if character in mouth_poses:
                        character_meta = character_defs[character]
                        for line in scene["dialogue"]:
                            if line["character"] != character:
                                continue
                            speaking_t = local_t - line["start"]
                            mouth_index = sample_mouth_pose(line["visemes_data"], speaking_t)
                            mouth = mouth_poses[character][mouth_index]
                            paste_mouth(
                                canvas, mouth, sprite, transform["x"], transform["y"],
                                desired_height, transform["rotation"],
                                character_meta["_mouth_anchor"], character_meta["_mouth_width"],
                            )
                draw_caption(canvas, str(scene.get("caption", "")))
                writer.append_data(np.asarray(canvas))
                frame_count += 1
    finally:
        writer.close()
    if frame_count == 0 or not silent_path.is_file() or silent_path.stat().st_size < 2048:
        raise RuntimeError("No video frames were rendered.")

    if music_path and not music_path.is_file():
        raise FileNotFoundError(f"Music track not found: {music_path}")
    if voice_tracks or music_path:
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent_path)]
        filters: list[str] = []
        audio_labels: list[str] = []
        for index, (audio_path, offset, volume) in enumerate(voice_tracks):
            input_index = index + 1
            cmd += ["-i", str(audio_path)]
            delay_ms = max(0, int(round(offset * 1000)))
            label = f"voice{index}"
            filters.append(f"[{input_index}:a]adelay={delay_ms}|{delay_ms},volume={volume:.3f}[{label}]")
            audio_labels.append(f"[{label}]")
        if music_path:
            music_index = len(voice_tracks) + 1
            cmd += ["-stream_loop", "-1", "-i", str(music_path)]
            filters.append(
                f"[{music_index}:a]atrim=0:{total_duration:.3f},asetpts=PTS-STARTPTS,"
                f"volume={0.16 if voice_tracks else 0.75:.3f}[music]"
            )
            audio_labels.append("[music]")
        filters.append(
            "".join(audio_labels)
            + f"amix=inputs={len(audio_labels)}:duration=longest:dropout_transition=2:normalize=1[aout]"
        )
        cmd += [
            "-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total_duration:.3f}",
            "-movflags", "+faststart", str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"FFmpeg dialogue/music mix failed: {result.stderr[-2500:]}")
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
