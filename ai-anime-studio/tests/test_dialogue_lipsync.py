from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import traditional_2d_pipeline as pipeline


def make_sheet(path: Path, mouth: bool = False) -> None:
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    colors = [(240, 70, 60, 255), (70, 180, 90, 255),
              (70, 100, 230, 255), (240, 190, 40, 255)]
    for index, color in enumerate(colors):
        x0, y0 = (index % 2) * 128, (index // 2) * 128
        if mouth:
            draw.ellipse((x0 + 38, y0 + 52, x0 + 90, y0 + 72), fill=color)
        else:
            draw.ellipse((x0 + 22, y0 + 12, x0 + 106, y0 + 116), fill=color)


def make_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24000)
        output.writeframes(b"\x00\x00" * 24000)


def test_sample_mouth_pose_uses_headtts_event_timing() -> None:
    events = [
        {"start": 0.0, "duration": 0.3, "mouth_index": 1},
        {"start": 0.3, "duration": 0.2, "mouth_index": 2},
        {"start": 0.5, "duration": 0.3, "mouth_index": 3},
    ]
    assert pipeline.sample_mouth_pose(events, -0.1) == 0
    assert pipeline.sample_mouth_pose(events, 0.1) == 1
    assert pipeline.sample_mouth_pose(events, 0.4) == 2
    assert pipeline.sample_mouth_pose(events, 0.6) == 3
    assert pipeline.sample_mouth_pose(events, 0.9) == 0


@pytest.mark.skipif(not shutil.which("ffprobe"), reason="ffprobe is required for audio stream validation")
def test_dialogue_manifest_renders_lipsync_and_mixed_audio(tmp_path: Path) -> None:
    body_sheet = tmp_path / "character.png"
    mouth_sheet = tmp_path / "mouths.png"
    audio_path = tmp_path / "hello.wav"
    viseme_path = tmp_path / "hello.visemes.json"
    make_sheet(body_sheet)
    make_sheet(mouth_sheet, mouth=True)
    make_wav(audio_path)
    viseme_path.write_text(json.dumps({
        "provider": "HeadTTS / Kokoro",
        "visemes": [
            {"start": 0.0, "duration": 0.45, "viseme": "aa", "mouth_index": 1},
            {"start": 0.45, "duration": 0.45, "viseme": "O", "mouth_index": 3},
        ],
    }), encoding="utf-8")
    manifest = {
        "width": 320, "height": 180, "fps": 8,
        "characters": {
            "hero": {
                "sheet": "character.png", "mouth_sheet": "mouths.png",
                "mouth_anchor": [0.5, 0.68], "mouth_width": 0.22,
            }
        },
        "scenes": [{
            "id": "english_dialogue_test", "duration": 1.0,
            "background": "#dce8e8", "actors": [{
                "character": "hero", "height": 110,
                "keyframes": [{"t": 0, "x": 160, "y": 172, "pose": 0}],
            }],
            "dialogue": [{
                "character": "hero", "audio": "hello.wav",
                "visemes": "hello.visemes.json", "start": 0.0,
            }],
        }],
    }
    manifest_path = tmp_path / "episode.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output_path = tmp_path / "episode.mp4"

    rendered = pipeline.render_manifest(manifest_path, output_path)

    assert rendered.is_file() and rendered.stat().st_size > 2048
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
        "-of", "json", str(rendered),
    ], capture_output=True, text=True, check=True)
    stream_types = {item["codec_type"] for item in json.loads(probe.stdout)["streams"]}
    assert {"video", "audio"} <= stream_types
    decoded = subprocess.run(
        [pipeline.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
         "-i", str(rendered), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    assert decoded.returncode == 0, decoded.stderr
