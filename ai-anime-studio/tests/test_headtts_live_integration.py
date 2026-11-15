from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from headtts_bridge import HeadTTSClient
import traditional_2d_pipeline as pipeline


@pytest.mark.skipif(not os.getenv("HEADTTS_URL"), reason="Set HEADTTS_URL to run real Kokoro inference.")
def test_live_headtts_cpu_to_lipsynced_episode() -> None:
    base = Path(os.getenv("HEADTTS_SMOKE_OUTPUT_DIR", "outputs/headtts-cpu-smoke")).resolve()
    base.mkdir(parents=True, exist_ok=True)
    audio_path = base / "hero_line.wav"
    timeline_path = base / "hero_line.visemes.json"
    client = HeadTTSClient(os.environ["HEADTTS_URL"], timeout=300)
    client.synthesize(
        "A little courage can change everything, especially when nobody expects it.",
        audio_path, timeline_path, voice="af_bella", language="en-us", speed=1.0,
    )
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    assert audio_path.stat().st_size > 4096
    assert timeline["duration_seconds"] > 0
    assert len(timeline["visemes"]) > 0

    body_sheet = base / "hero_poses.png"
    mouth_sheet = base / "hero_mouths.png"
    for target, is_mouth in ((body_sheet, False), (mouth_sheet, True)):
        image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        colors = [(235, 90, 70, 255), (70, 175, 100, 255),
                  (80, 120, 225, 255), (235, 185, 60, 255)]
        for index, color in enumerate(colors):
            x0, y0 = (index % 2) * 128, (index // 2) * 128
            if is_mouth:
                draw.ellipse((x0 + 38, y0 + 50, x0 + 90, y0 + 76), fill=color)
            else:
                draw.ellipse((x0 + 20, y0 + 12, x0 + 108, y0 + 116), fill=color)
        image.save(target)

    scene_duration = float(timeline["duration_seconds"]) + 0.8
    manifest = {
        "width": 360, "height": 640, "fps": 12,
        "characters": {
            "hero": {
                "sheet": str(body_sheet), "mouth_sheet": str(mouth_sheet),
                "mouth_anchor": [0.5, 0.68], "mouth_width": 0.2,
            }
        },
        "scenes": [{
            "id": "real_kokoro_dialogue", "duration": scene_duration,
            "background": "#dce8e8",
            "actors": [{
                "character": "hero", "height": 390,
                "keyframes": [{"t": 0, "x": 180, "y": 590, "pose": 0}],
            }],
            "dialogue": [{
                "character": "hero", "audio": str(audio_path),
                "visemes": str(timeline_path), "start": 0.25, "volume": 1.0,
            }],
        }],
    }
    manifest_path = base / "episode.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output_path = base / "english_lipsync_smoke.mp4"
    pipeline.render_manifest(manifest_path, output_path)

    ffprobe = shutil.which("ffprobe")
    assert ffprobe, "ffprobe must be installed in the CPU integration job."
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "json", str(output_path)],
        capture_output=True, text=True, check=True,
    )
    stream_types = {item["codec_type"] for item in json.loads(probe.stdout)["streams"]}
    assert {"video", "audio"} <= stream_types
    assert output_path.stat().st_size > 10_000
    print(f"REAL_HEADTTS_PASS: {output_path} | {len(timeline['visemes'])} visemes | "
          f"{timeline['duration_seconds']:.2f}s speech")
