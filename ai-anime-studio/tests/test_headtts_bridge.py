from __future__ import annotations

import base64
import io
import json
import wave

import pytest

import headtts_bridge


def tiny_wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * 2400)
    return output.getvalue()


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return self.body


def test_headtts_bridge_saves_wav_and_viseme_timeline(tmp_path, monkeypatch):
    response = {
        "audio": base64.b64encode(tiny_wav()).decode("ascii"),
        "words": ["Hello", "there."],
        "wtimes": [50, 320],
        "wdurations": [220, 310],
        "visemes": ["aa", "E", "O", "sil"],
        "vtimes": [50, 170, 320, 540],
        "vdurations": [120, 150, 180, 100],
    }
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse(json.dumps(response).encode("utf-8"))

    monkeypatch.setattr(headtts_bridge.urllib.request, "urlopen", fake_urlopen)
    audio_path, timeline_path = headtts_bridge.HeadTTSClient().synthesize(
        "Hello there.", tmp_path / "line.wav", tmp_path / "line.visemes.json",
        voice="af_bella", language="en-us", speed=1.05,
    )

    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    assert captured["url"].endswith("/v1/synthesize")
    assert captured["payload"]["language"] == "en-us"
    assert captured["payload"]["audioEncoding"] == "wav"
    assert audio_path.read_bytes() == tiny_wav()
    assert timeline["visemes"][0]["mouth_index"] == 1
    assert timeline["visemes"][1]["mouth_index"] == 2
    assert timeline["visemes"][2]["mouth_index"] == 3
    assert timeline["visemes"][3]["mouth_index"] == 0
    assert timeline["words"][1]["word"] == "there."


def test_headtts_bridge_rejects_more_than_500_characters(tmp_path):
    with pytest.raises(ValueError, match="500 characters"):
        headtts_bridge.HeadTTSClient().synthesize(
            "x" * 501, tmp_path / "line.wav", tmp_path / "line.json"
        )


def test_headtts_bridge_rejects_mismatched_viseme_arrays(tmp_path, monkeypatch):
    response = {
        "audio": base64.b64encode(tiny_wav()).decode("ascii"),
        "visemes": ["aa"], "vtimes": [], "vdurations": [100],
    }
    monkeypatch.setattr(
        headtts_bridge.urllib.request, "urlopen",
        lambda *args, **kwargs: FakeResponse(json.dumps(response).encode("utf-8")),
    )
    with pytest.raises(headtts_bridge.HeadTTSError, match="different lengths"):
        headtts_bridge.HeadTTSClient().synthesize(
            "Hello.", tmp_path / "line.wav", tmp_path / "line.json"
        )
