from __future__ import annotations
import json, re, shutil, subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

@dataclass
class Word:
    text: str
    start: float
    end: float

@dataclass
class Candidate:
    start: float
    end: float
    text: str
    score: float
    reasons: list[str]

def run_checked(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, capture_output=True, text=True)

def probe_media(path: str | Path) -> dict:
    source = Path(path)
    if not source.is_file(): raise FileNotFoundError(source)
    if not shutil.which("ffprobe"): raise RuntimeError("ffprobe was not found on PATH")
    result = run_checked(["ffprobe","-v","error","-show_entries","format=duration:stream=codec_type,width,height,sample_rate","-of","json",str(source)])
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    duration = float(payload.get("format", {}).get("duration", 0))
    if duration <= 0: raise ValueError("Media duration is missing or invalid")
    return {"duration":duration,"has_video":any(s.get("codec_type")=="video" for s in streams),"has_audio":any(s.get("codec_type")=="audio" for s in streams),"streams":streams}

def extract_audio(video_path: str | Path, wav_path: str | Path) -> Path:
    info = probe_media(video_path)
    if not info["has_audio"]: raise ValueError("The input video has no audio stream to transcribe")
    target=Path(wav_path); target.parent.mkdir(parents=True,exist_ok=True)
    run_checked(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(video_path),"-vn","-ac","1","-ar","16000","-c:a","pcm_s16le",str(target)])
    return target

def transcribe(audio_path: str | Path, model_size: str="small", device: str="cpu") -> list[Word]:
    try: from faster_whisper import WhisperModel
    except ImportError as exc: raise RuntimeError("Install faster-whisper to enable transcription") from exc
    model=WhisperModel(model_size,device=device,compute_type="int8" if device=="cpu" else "float16")
    segments,_info=model.transcribe(str(audio_path),word_timestamps=True,vad_filter=True,beam_size=3)
    words=[]
    for segment in segments:
        for item in (getattr(segment,"words",None) or []):
            token=str(item.word).strip(); start,end=float(item.start),float(item.end)
            if token and end>start>=0: words.append(Word(token,start,end))
    return words

def _sentences(words: list[Word]) -> list[tuple[float,float,str]]:
    result=[]; chunk=[]
    for word in words:
        chunk.append(word)
        if re.search(r"""[.!?]["')\]]?$""",word.text):
            result.append((chunk[0].start,chunk[-1].end," ".join(w.text for w in chunk))); chunk=[]
    if chunk: result.append((chunk[0].start,chunk[-1].end," ".join(w.text for w in chunk)))
    return result

def suggest_candidates(words: list[Word], min_duration: float=25.0, max_duration: float=60.0, max_candidates: int=12) -> list[Candidate]:
    if min_duration<=0 or max_duration<=min_duration: raise ValueError("Require 0 < min_duration < max_duration")
    sentences=_sentences(words); candidates=[]
    for left in range(len(sentences)):
        start=sentences[left][0]; pieces=[]
        for right in range(left,len(sentences)):
            end=sentences[right][1]; pieces.append(sentences[right][2]); duration=end-start
            if duration>max_duration: break
            if duration<min_duration: continue
            text=" ".join(pieces).strip(); lower=text.lower(); reasons=[]
            if re.search(r"\b(why|how|what if|here's why|the reason|mistake|secret|lesson)\b",lower): reasons.append("Opens with a question, explanation, or curiosity cue")
            if re.search(r"\b(because|therefore|so that|which means|the result)\b",lower): reasons.append("Contains an explanatory connection")
            if re.search(r"[.!?]$",text): reasons.append("Ends at a sentence boundary")
            density=min(len(text.split())/max(duration,1)*60,220)/220
            score=min(100.0,35.0+density*35.0+len(reasons)*10.0)
            candidates.append(Candidate(round(start,3),round(end,3),text,round(score,1),reasons))
    candidates.sort(key=lambda c:c.score,reverse=True); selected=[]
    for candidate in candidates:
        if any(min(candidate.end,c.end)-max(candidate.start,c.start)>0.5*min(candidate.end-candidate.start,c.end-c.start) for c in selected): continue
        selected.append(candidate)
        if len(selected)>=max_candidates: break
    return sorted(selected,key=lambda c:c.start)

def _srt_time(seconds: float) -> str:
    ms=max(0,round(seconds*1000)); hours,ms=divmod(ms,3600000); minutes,ms=divmod(ms,60000); secs,ms=divmod(ms,1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"

def write_srt(words: Iterable[Word], clip_start: float, clip_end: float, target: str | Path) -> Path:
    selected=[w for w in words if w.end>clip_start and w.start<clip_end]; lines=[]
    for index,word in enumerate(selected,1):
        start=max(0.0,word.start-clip_start); end=min(clip_end,word.end)-clip_start
        if end<=start: continue
        lines.extend([str(index),f"{_srt_time(start)} --> {_srt_time(end)}",word.text,""])
    output=Path(target); output.parent.mkdir(parents=True,exist_ok=True); output.write_text("\n".join(lines),encoding="utf-8")
    return output

def render_clip(video_path: str | Path, candidate: Candidate, subtitle_path: str | Path, output_path: str | Path, width: int=1080, height: int=1920) -> Path:
    if width<=0 or height<=0: raise ValueError("Output dimensions must be positive")
    if not shutil.which("ffmpeg"): raise RuntimeError("ffmpeg was not found on PATH")
    target=Path(output_path); target.parent.mkdir(parents=True,exist_ok=True)
    subtitle=str(Path(subtitle_path).resolve()).replace("\\","/").replace(":","\\:").replace("'","\\'")
    vf=(f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
        f"subtitles='{subtitle}':force_style='FontName=Arial,FontSize=18,Outline=2,Shadow=0,Alignment=2,MarginV=180'")
    run_checked(["ffmpeg","-hide_banner","-loglevel","error","-y","-ss",f"{candidate.start:.3f}","-i",str(video_path),"-t",f"{candidate.end-candidate.start:.3f}","-vf",vf,"-c:v","libx264","-preset","veryfast","-crf","22","-c:a","aac","-b:a","128k","-movflags","+faststart",str(target)])
    return target

def save_transcript(words: list[Word], target: str | Path) -> Path:
    output=Path(target); output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps([asdict(w) for w in words],ensure_ascii=False,indent=2),encoding="utf-8")
    return output
