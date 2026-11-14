#!/usr/bin/env python3
"""CPU-first script-to-video renderer. Requires Pillow and FFmpeg/ffprobe."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FPS = 30
PALETTE = ["#101827", "#18243a", "#20213a", "#132c35", "#30213c"]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
        if bold else
        ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/System/Library/Fonts/Supplemental/Arial.ttf"]
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, face: Any, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).splitlines() or [""]:
        words = paragraph.split()
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if current and draw.textbbox((0, 0), trial, font=face)[2] > max_width:
                lines.append(current)
                current = word
            else:
                current = trial
        lines.append(current)
    return lines


def make_card(scene: dict[str, Any], index: int, total: int, destination: Path,
              width: int = W, height: int = H) -> None:
    bg = scene.get("background", PALETTE[(index - 1) % len(PALETTE)])
    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)
    margin = int(width * 0.105)
    accent = "#77E0C3"
    draw.rounded_rectangle((margin, int(height * .12), margin + 92, int(height * .12) + 12),
                           radius=6, fill=accent)
    draw.text((margin, int(height * .16)), f"SCENE {index:02d}  /  {total:02d}",
              font=font(26, True), fill="#B8C5D8")
    title_size = max(42, int(width * .075))
    body_size = max(28, int(width * .042))
    title_font = font(title_size, True)
    body_font = font(body_size)
    title_lines = wrap_text(draw, scene.get("title", "Untitled scene"), title_font, width - 2 * margin)
    y = int(height * .29)
    for line in title_lines[:4]:
        draw.text((margin, y), line, font=title_font, fill="#FFFFFF")
        y += int(title_size * 1.2)
    y += int(height * .055)
    body_lines = wrap_text(draw, scene.get("text", ""), body_font, width - 2 * margin)
    for line in body_lines[:10]:
        draw.text((margin, y), line, font=body_font, fill="#D9E2EF")
        y += int(body_size * 1.55)
    draw.text((margin, int(height * .91)), "MADE WITH CPU-FIRST VIDEO STUDIO",
              font=font(19, True), fill="#8796AA")
    draw.text((width - margin - 80, int(height * .91)), f"{index:02d}",
              font=font(24, True), fill=accent)
    image.save(destination, format="PNG", optimize=True)


def srt_time(seconds: float) -> str:
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def run(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stderr[-4000:]}"
        )


def render(manifest_path: Path, output: Path, narration: Path | None = None,
           width: int = W, height: int = H, fps: int = FPS) -> Path:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and ffprobe must be installed and available on PATH.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scenes = manifest.get("scenes", [])
    if not scenes:
        raise ValueError("Manifest must contain at least one scene.")
    for scene in scenes:
        if float(scene.get("duration", 0)) <= 0:
            raise ValueError("Every scene needs a positive duration.")
    if narration and not narration.is_file():
        raise FileNotFoundError(narration)

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    total_duration = sum(float(s["duration"]) for s in scenes)
    with tempfile.TemporaryDirectory(prefix="quick-video-") as temp:
        work = Path(temp)
        concat_lines: list[str] = []
        captions: list[str] = []
        cursor = 0.0
        for i, scene in enumerate(scenes, start=1):
            png = work / f"scene-{i:03}.png"
            segment = work / f"segment-{i:03}.mp4"
            duration = float(scene["duration"])
            make_card(scene, i, len(scenes), png, width, height)
            run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-loop", "1", "-framerate", str(fps), "-i", str(png),
                "-t", str(duration), "-vf", "format=yuv420p",
                "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "23", "-an", "-movflags", "+faststart", str(segment)
            ])
            concat_lines.append(f"file '{segment.as_posix()}'")
            captions.append(
                f"{i}\n{srt_time(cursor)} --> {srt_time(cursor + duration)}\n"
                f"{scene.get('title', '').strip()}\n{scene.get('text', '').strip()}\n"
            )
            cursor += duration

        concat_file = work / "concat.txt"
        concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
        joined = work / "joined.mp4"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
             "-safe", "0", "-i", str(concat_file), "-c", "copy", str(joined)])

        if narration:
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(joined),
                 "-i", str(narration.resolve()), "-map", "0:v:0", "-map", "1:a:0",
                 "-c:v", "copy", "-c:a", "aac", "-af", "apad", "-t", str(total_duration),
                 "-movflags", "+faststart", str(output)])
        else:
            shutil.copy2(joined, output)

        output.with_suffix(".srt").write_text("\n".join(captions), encoding="utf-8")
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(output)],
            capture_output=True, text=True
        )
        if probe.returncode or not probe.stdout.strip():
            raise RuntimeError("Output validation failed: ffprobe could not read the MP4.")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a simple vertical MP4 from a scene script.")
    parser.add_argument("manifest", type=Path, help="Path to a JSON scene manifest")
    parser.add_argument("-o", "--output", type=Path, default=Path("output.mp4"))
    parser.add_argument("--narration", type=Path, help="Optional narration audio file (WAV/MP3/M4A)")
    parser.add_argument("--width", type=int, default=W)
    parser.add_argument("--height", type=int, default=H)
    parser.add_argument("--fps", type=int, default=FPS)
    args = parser.parse_args()
    result = render(args.manifest, args.output, args.narration, args.width, args.height, args.fps)
    print(f"Created: {result}")
    print(f"Captions: {result.with_suffix('.srt')}")


if __name__ == "__main__":
    main()
