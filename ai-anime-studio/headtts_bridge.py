#!/usr/bin/env python3
"""Generate English dialogue WAV + timecoded mouth cues from a local HeadTTS server.

HeadTTS supplies word and viseme timestamps, so the 2D renderer can animate a
separate four-shape mouth sheet without running a GPU-based video model.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any

VISEME_TO_MOUTH = {
    "sil": 0, "PP": 0,
    "aa": 1, "RR": 1, "DD": 1,
    "E": 2, "I": 2, "SS": 2, "TH": 2, "CH": 2, "FF": 2, "kk": 2, "nn": 2,
    "O": 3, "U": 3,
}


class HeadTTSError(RuntimeError):
    """Raised when the HeadTTS REST server returns an invalid response."""


class HeadTTSClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8882", timeout: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def synthesize(
        self, text: str, audio_path: str | Path, timeline_path: str | Path, *,
        voice: str = "af_bella", language: str = "en-us", speed: float = 1.0,
    ) -> tuple[Path, Path]:
        text = str(text).strip()
        if not text:
            raise ValueError("Dialogue text cannot be empty.")
        if len(text) > 500:
            raise ValueError("HeadTTS REST accepts at most 500 characters per request; split the dialogue into lines.")
        if not math.isfinite(speed) or not 0.25 <= speed <= 4.0:
            raise ValueError("Speed must be between 0.25 and 4.")
        payload = {
            "input": text, "voice": voice, "language": language,
            "speed": speed, "audioEncoding": "wav",
        }
        request = urllib.request.Request(
            f"{self.base_url}/v1/synthesize",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise HeadTTSError(
                f"Cannot reach HeadTTS at {self.base_url}. Start the local Node server first. Details: {exc}"
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HeadTTSError("HeadTTS returned an invalid JSON response.") from exc

        if not isinstance(result, dict):
            raise HeadTTSError("HeadTTS response must be a JSON object.")
        if result.get("error"):
            raise HeadTTSError(str(result["error"]))
        encoded = result.get("audio")
        if not isinstance(encoded, str):
            raise HeadTTSError("HeadTTS response does not contain base64 WAV audio.")
        try:
            audio_bytes = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise HeadTTSError("HeadTTS audio field is not valid base64.") from exc

        audio_target, timeline_target = Path(audio_path), Path(timeline_path)
        audio_target.parent.mkdir(parents=True, exist_ok=True)
        timeline_target.parent.mkdir(parents=True, exist_ok=True)
        audio_target.write_bytes(audio_bytes)
        try:
            with wave.open(str(audio_target), "rb") as wav:
                sample_rate = wav.getframerate()
                duration = wav.getnframes() / float(sample_rate)
                if wav.getnframes() <= 0 or sample_rate <= 0:
                    raise HeadTTSError("HeadTTS returned an empty WAV file.")
        except (wave.Error, EOFError) as exc:
            audio_target.unlink(missing_ok=True)
            raise HeadTTSError("HeadTTS audio is not a valid PCM WAV file.") from exc

        names = result.get("visemes", [])
        starts = result.get("vtimes", [])
        durations = result.get("vdurations", [])
        if not (isinstance(names, list) and isinstance(starts, list) and isinstance(durations, list)):
            raise HeadTTSError("HeadTTS viseme arrays are missing or malformed.")
        if not (len(names) == len(starts) == len(durations)):
            raise HeadTTSError("HeadTTS viseme arrays have different lengths.")

        visemes: list[dict[str, Any]] = []
        for name, start_ms, duration_ms in zip(names, starts, durations):
            try:
                start = float(start_ms) / 1000.0
                length = float(duration_ms) / 1000.0
            except (TypeError, ValueError) as exc:
                raise HeadTTSError("HeadTTS returned a non-numeric viseme timestamp.") from exc
            if not math.isfinite(start) or not math.isfinite(length) or start < 0 or length < 0:
                raise HeadTTSError("HeadTTS returned an invalid viseme timestamp.")
            if start > duration + 0.1 or start + length > duration + 0.15:
                raise HeadTTSError("HeadTTS viseme timing extends beyond the returned WAV duration.")
            key = str(name)
            visemes.append({
                "start": round(start, 4),
                "duration": round(length, 4),
                "viseme": key,
                "mouth_index": VISEME_TO_MOUTH.get(key, 0),
            })

        words: list[dict[str, Any]] = []
        word_items = result.get("words", [])
        word_starts = result.get("wtimes", [])
        word_durations = result.get("wdurations", [])
        if isinstance(word_items, list) and isinstance(word_starts, list) and isinstance(word_durations, list):
            if len(word_items) == len(word_starts) == len(word_durations):
                for word, start_ms, duration_ms in zip(word_items, word_starts, word_durations):
                    words.append({
                        "word": str(word), "start": round(float(start_ms) / 1000.0, 4),
                        "duration": round(float(duration_ms) / 1000.0, 4),
                    })

        timeline = {
            "provider": "HeadTTS / Kokoro",
            "language": language,
            "voice": voice,
            "text": text,
            "sample_rate": sample_rate,
            "duration_seconds": round(duration, 4),
            "words": words,
            "visemes": visemes,
            "mouth_shapes": {"0": "closed/rest", "1": "open", "2": "wide", "3": "round"},
        }
        timeline_target.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
        return audio_target, timeline_target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--text-file", type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8882")
    parser.add_argument("--voice", default="af_bella")
    parser.add_argument("--language", default="en-us")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--audio-out", type=Path, required=True)
    parser.add_argument("--timeline-out", type=Path, required=True)
    args = parser.parse_args(argv)
    text = args.text if args.text is not None else args.text_file.read_text(encoding="utf-8")
    try:
        audio, timeline = HeadTTSClient(args.server).synthesize(
            text, args.audio_out, args.timeline_out,
            voice=args.voice, language=args.language, speed=args.speed,
        )
        print(f"PASS: {audio} + {timeline}")
        return 0
    except (ValueError, OSError, HeadTTSError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
