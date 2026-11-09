from __future__ import annotations

import os
from pathlib import Path

from core import Word


MODEL_ID = "pyannote/speaker-diarization-community-1"


def diarize_audio(
    audio_path: str | Path, token: str | None = None, device: str = "cpu",
) -> tuple[list[dict], str]:
    """Run the open-source pyannote speaker pipeline locally and return labeled turns."""
    token = token or os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("Set HF_TOKEN and accept the model terms to enable speaker diarization")
    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise RuntimeError("Install requirements-ai.txt to enable speaker diarization") from exc

    pipeline = Pipeline.from_pretrained(MODEL_ID, token=token)
    if pipeline is None:
        raise RuntimeError("Could not load the speaker diarization model")
    pipeline.to(torch.device(device))
    output = pipeline(str(audio_path))
    turns = [
        {"start": float(turn.start), "end": float(turn.end), "speaker": str(speaker)}
        for turn, speaker in output.speaker_diarization
    ]
    return turns, MODEL_ID


def attach_speakers(words: list[Word], turns: list[dict]) -> list[Word]:
    labeled: list[Word] = []
    for word in words:
        midpoint = (word.start + word.end) / 2
        matches = [turn for turn in turns if turn["start"] <= midpoint < turn["end"]]
        speaker = max(matches, key=lambda turn: turn["end"] - turn["start"])["speaker"] if matches else None
        labeled.append(Word(word.text, word.start, word.end, speaker))
    return labeled
