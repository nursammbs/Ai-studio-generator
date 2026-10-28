#!/usr/bin/env python3
"""Shot-based cartoon production: ComfyUI image-to-video -> FFmpeg -> final episode."""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from engine import ComfyUIClient
except ImportError:
    ComfyUIClient = None

@dataclass(frozen=True)
class Shot:
    id: str
    reference_image: Path
    prompt: str
    seed: int
    speed: float = 1.0
    source_video: Path | None = None

def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, check=True, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {cmd[0]}. Install FFmpeg/ffprobe and check PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Command failed ({exc.returncode}): {' '.join(cmd[:8])}\n{(exc.stderr or exc.stdout)[-2500:]}") from exc

def duration(path: Path) -> float:
    result = run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)])
    value = float(result.stdout.strip())
    if value <= 0: raise RuntimeError(f"Invalid duration: {path}")
    return value

def load_project(path: Path) -> tuple[dict[str, Any], list[Shot]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("shots"), list) or not data["shots"]:
        raise ValueError("Project JSON needs a non-empty shots array.")
    root, shots, ids = path.resolve().parent, [], set()
    for i, raw in enumerate(data["shots"], 1):
        if not isinstance(raw, dict): raise ValueError(f"shots[{i-1}] must be an object")
        sid = str(raw.get("id", f"shot_{i:02d}")).strip()
        if not sid or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in sid):
            raise ValueError(f"Unsafe shot id: {sid!r}")
        if sid in ids: raise ValueError(f"Duplicate shot id: {sid}")
        ids.add(sid)
        ref = Path(str(raw.get("reference_image", "")))
        if not ref.is_absolute(): ref = root / ref
        src = Path(str(raw["source_video"])) if raw.get("source_video") else None
        if src and not src.is_absolute(): src = root / src
        prompt = str(raw.get("prompt", "")).strip()
        if not prompt: raise ValueError(f"Empty prompt for {sid}")
        seed, speed = int(raw.get("seed", 1000+i)), float(raw.get("speed", 1.0))
        if not 0.25 <= speed <= 4.0: raise ValueError(f"Speed for {sid} must be 0.25–4.0")
        if src:
            if not src.is_file(): raise FileNotFoundError(f"Source video missing: {src}")
        elif not ref.is_file():
            raise FileNotFoundError(f"Reference image for {sid} missing: {ref}")
        shots.append(Shot(sid, ref, prompt, seed, speed, src))
    return data, shots

def generate(project: dict[str, Any], shots: list[Shot], workflow_path: Path, base_url: str,
             positive_id: str, seed_id: str, image_id: str, negative_id: str | None,
             output_dir: Path, timeout: int) -> list[Path]:
    if ComfyUIClient is None: raise RuntimeError("Run this script beside the project's engine.py.")
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    style = str(project.get("style_bible", "premium 2D cel animation, consistent ink, expressive readable silhouettes"))
    characters = str(project.get("character_bible", "Preserve identity, colors, proportions and face from each reference image"))
    negative = str(project.get("negative_prompt", "flicker, identity drift, extra limbs, malformed anatomy, duplicate character, text, watermark"))
    if negative_id:
        node = workflow.get(str(negative_id))
        if not isinstance(node, dict) or "text" not in node.get("inputs", {}):
            raise ValueError(f"Negative prompt node {negative_id} does not expose text input")
        node["inputs"]["text"] = negative
    client = ComfyUIClient(base_url=base_url, timeout=60)
    client.health()
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for i, shot in enumerate(shots, 1):
        target = raw_dir / f"{i:02d}_{shot.id}.mp4"
        if target.exists() and target.stat().st_size > 2048:
            print(f"[resume] {shot.id}: keeping existing render")
            results.append(target); continue
        prompt = f"{style}. Character continuity: {characters}. Shot action: {shot.prompt}. Keep identity stable, coherent staging, clear silhouettes, natural anticipation and follow-through; no camera teleporting."
        print(f"[{i}/{len(shots)}] Generating {shot.id}, seed={shot.seed}")
        result = client.generate_video_from_image(workflow, positive_node_id=positive_id, seed_node_id=seed_id,
            image_node_id=image_id, positive_prompt=prompt, seed=shot.seed,
            source_image=shot.reference_image, output_path=target, timeout=timeout)
        target.with_suffix(".json").write_text(json.dumps({"id":shot.id,"prompt":prompt,"negative_prompt":negative,
            "seed":shot.seed,"reference_image":str(shot.reference_image),"workflow":str(workflow_path),
            "generated_at_unix":int(time.time())}, indent=2, ensure_ascii=False), encoding="utf-8")
        results.append(result)
    return results

def normalize(src: Path, dst: Path, width: int, height: int, fps: int, speed: float) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = f"setpts=PTS/{speed:.6f},fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(src),"-vf",vf,"-an",
         "-c:v","libx264","-preset","medium","-crf","18","-movflags","+faststart",str(dst)])
    if not dst.is_file() or dst.stat().st_size < 2048: raise RuntimeError(f"Invalid normalized clip: {dst}")
    run(["ffmpeg","-hide_banner","-loglevel","error","-i",str(dst),"-f","null","-"])
    return dst

def assemble(clips: list[Path], output: Path, fps: int, transition: float, music: Path | None) -> Path:
    if not clips: raise ValueError("At least one clip is required")
    if not 0 <= transition <= 1.5: raise ValueError("Transition must be in range 0–1.5 seconds")
    lengths = [duration(p) for p in clips]
    if len(clips) > 1 and transition > 0: transition = min(transition, min(lengths)*0.35)
    inputs = []
    for p in clips: inputs += ["-i", str(p)]
    if music:
        if not music.is_file(): raise FileNotFoundError(f"Music file missing: {music}")
        inputs += ["-stream_loop","-1","-i",str(music)]
    filters = []
    if len(clips) == 1:
        video_label, final_length = "[0:v]", lengths[0]
    elif transition == 0:
        filters.append("".join(f"[{i}:v]" for i in range(len(clips)))+f"concat=n={len(clips)}:v=1:a=0[vout]")
        video_label, final_length = "[vout]", sum(lengths)
    else:
        current, elapsed = "[0:v]", lengths[0]
        for i in range(1, len(clips)):
            nxt, offset = f"[xf{i}]", max(0, elapsed-transition)
            filters.append(f"{current}[{i}:v]xfade=transition=fade:duration={transition:.3f}:offset={offset:.3f}{nxt}")
            current, elapsed = nxt, elapsed+lengths[i]-transition
        video_label, final_length = current, elapsed
    if music:
        mi = len(clips)
        filters.append(f"[{mi}:a]atrim=0:{final_length:.3f},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.7,afade=t=out:st={max(0,final_length-1.2):.3f}:d=1.2,volume=0.85[aout]")
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg","-hide_banner","-loglevel","error","-y",*inputs]
    if filters: cmd += ["-filter_complex",";".join(filters)]
    cmd += ["-map",video_label]
    cmd += ["-map","[aout]","-c:a","aac","-b:a","192k"] if music else ["-an"]
    cmd += ["-r",str(fps),"-c:v","libx264","-preset","medium","-crf","18","-pix_fmt","yuv420p","-movflags","+faststart",str(output)]
    run(cmd)
    if not output.is_file() or output.stat().st_size < 4096: raise RuntimeError("Final episode missing or too small")
    run(["ffmpeg","-hide_banner","-loglevel","error","-i",str(output),"-f","null","-"])
    print(f"FINAL: {output} | {duration(output):.2f}s | {output.stat().st_size/1024/1024:.2f} MiB")
    return output

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",type=Path,required=True)
    p.add_argument("--output",type=Path,default=Path("outputs/episode_final.mp4"))
    p.add_argument("--work-dir",type=Path,default=Path("outputs/studio_pipeline"))
    p.add_argument("--workflow",type=Path)
    p.add_argument("--comfy-url",default="http://127.0.0.1:8188")
    p.add_argument("--positive-node"); p.add_argument("--seed-node"); p.add_argument("--image-node"); p.add_argument("--negative-node")
    p.add_argument("--music",type=Path)
    p.add_argument("--width",type=int,default=1280); p.add_argument("--height",type=int,default=720)
    p.add_argument("--fps",type=int,default=24); p.add_argument("--transition",type=float,default=0.25)
    p.add_argument("--timeout",type=int,default=1200); p.add_argument("--assemble-only",action="store_true")
    a = p.parse_args(argv)
    if a.width < 320 or a.height < 180 or not 12 <= a.fps <= 60: p.error("Use at least 320x180 and 12–60 FPS")
    project, shots = load_project(a.project); a.work_dir.mkdir(parents=True,exist_ok=True)
    if a.assemble_only:
        if any(not s.source_video for s in shots): p.error("--assemble-only requires source_video for every shot")
        raws = [s.source_video for s in shots]
    else:
        if not all((a.workflow,a.positive_node,a.seed_node,a.image_node)): p.error("Generation needs --workflow, --positive-node, --seed-node, --image-node")
        raws = generate(project,shots,a.workflow,a.comfy_url,a.positive_node,a.seed_node,a.image_node,a.negative_node,a.work_dir,a.timeout)
    normalized = []
    for i,(shot,raw) in enumerate(zip(shots,raws),1):
        dst=a.work_dir/"normalized"/f"{i:02d}_{shot.id}.mp4"
        if not dst.exists() or dst.stat().st_mtime < Path(raw).stat().st_mtime:
            normalize(Path(raw),dst,a.width,a.height,a.fps,shot.speed)
        normalized.append(dst)
    assemble(normalized,a.output.resolve(),a.fps,a.transition,a.music.resolve() if a.music else None)
    return 0

if __name__ == "__main__":
    try: raise SystemExit(main())
    except (ValueError,FileNotFoundError,RuntimeError,TimeoutError,json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr); raise SystemExit(2)
