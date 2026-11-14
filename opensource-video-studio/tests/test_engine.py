import pytest

import engine
from engine import fallback_scenes_for_test


def test_fallback_scene_count_and_shape():
    sources = [{"title": "Example", "url": "https://example.com", "extract": "Fact one. Fact two. Fact three."}]
    scenes = fallback_scenes_for_test("Solar panels", sources, 4, "en")
    assert len(scenes) == 4
    assert all(scene["heading"] and scene["narration"] and scene["visual_query"] for scene in scenes)


def test_empty_sources_flags_verification():
    scenes = fallback_scenes_for_test("Unknown topic", [], 3, "id")
    assert len(scenes) == 3
    assert any("sumber tepercaya" in scene["narration"].lower() for scene in scenes)


def test_smoke_renders_real_mp4_with_ffmpeg(tmp_path, monkeypatch):
    import shutil
    import subprocess
    from pathlib import Path
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        import pytest
        pytest.skip("FFmpeg/ffprobe are required for the rendering smoke test")

    monkeypatch.setattr(engine, "OUTPUTS", tmp_path / "outputs")
    monkeypatch.setattr(engine, "_commons_image", lambda query: None)

    def fake_voice(text, target, language, *args, **kwargs):
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=0.7",
             "-q:a", "9", "-ac", "1", str(target)],
            check=True, capture_output=True, text=True,
        )

    monkeypatch.setattr(engine, "_make_voice", fake_voice)
    scenes = [
        {"heading": "Ide dimulai dari masalah", "narration": "Ini adalah uji render.", "visual_query": "test"},
        {"heading": "Uji MP4 sungguhan", "narration": "Bukan sekadar cek sintaks.", "visual_query": "test"},
    ]
    job = engine.create_video("Smoke Test Video", scenes, [], language="id", aspect="9:16")
    video = job / "video.mp4"

    assert video.exists() and video.stat().st_size > 10_000
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height",
         "-of", "json", str(video)],
        check=True, capture_output=True, text=True,
    )
    import json
    streams = json.loads(probe.stdout)["streams"]
    video_stream = next(stream for stream in streams if stream["codec_type"] == "video")
    assert video_stream["width"] == 720
    assert video_stream["height"] == 1280
    assert (job / "thumbnail.jpg").exists()
    assert (job / "script.md").exists()
    assert (job / "sources.md").exists()

    # Keep a downloadable example as a CI artifact, not a committed binary.
    artifact_dir = Path("test-artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video, artifact_dir / "smoke-video.mp4")
    shutil.copy2(job / "thumbnail.jpg", artifact_dir / "smoke-thumbnail.jpg")



def test_voicestudio_tts_uses_openai_compatible_local_api(tmp_path, monkeypatch):
    captured = {}

    class FakeResponse:
        headers = {"Content-Type": "audio/mpeg"}
        content = b"ID3" + (b"voice-audio" * 20)

        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(engine.requests, "post", fake_post)
    target = tmp_path / "voice.mp3"
    engine._make_voice(
        "Contoh narasi Bahasa Indonesia.",
        target,
        "id",
        "voicestudio",
        base_url="http://127.0.0.1:3900",
        model="tts-1",
        voice="alloy",
        api_key="local-test-key",
    )

    assert captured["url"] == "http://127.0.0.1:3900/v1/audio/speech"
    assert captured["json"] == {
        "model": "tts-1",
        "voice": "alloy",
        "input": "Contoh narasi Bahasa Indonesia.",
        "response_format": "mp3",
    }
    assert captured["headers"]["Authorization"] == "Bearer local-test-key"
    assert target.read_bytes().startswith(b"ID3")


def test_voicestudio_rejects_remote_http_and_missing_key(tmp_path):
    with pytest.raises(ValueError, match="HTTPS and an API key"):
        engine._voicestudio_speech(
            "private narration",
            tmp_path / "voice.mp3",
            base_url="http://voice.example.com/v1",
        )


def test_voicestudio_rejects_non_audio_response(tmp_path, monkeypatch):
    class FakeResponse:
        headers = {"Content-Type": "application/json"}
        content = b'{"detail":"model not ready"}'

        def raise_for_status(self):
            return None

    monkeypatch.setattr(engine.requests, "post", lambda *args, **kwargs: FakeResponse())
    target = tmp_path / "voice.mp3"
    with pytest.raises(RuntimeError, match="non-audio response"):
        engine._voicestudio_speech("Hello", target, base_url="http://localhost:3900/v1")
    assert not target.exists()
