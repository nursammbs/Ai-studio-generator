#!/usr/bin/env python3
"""Shot-based cartoon production: ComfyUI image-to-video -> FFmpeg -> final episode."""
from __future__ import annotations
import argparse, copy, hashlib, html, json, shutil, subprocess, sys, time
from PIL import Image, ImageDraw, ImageFont
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
    motion_video: Path | None = None

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

def file_sha256(path: Path) -> str:
    """Hash large media incrementally, so a changed reference invalidates old renders."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shot_fingerprint(shot: Shot, workflow_path: Path, *, style: str, characters: str,
                     negative: str, node_config: dict[str, str]) -> str:
    """Stable cache key covering model workflow, prompt, image/video refs and controls."""
    payload = {
        "shot_id": shot.id, "prompt": shot.prompt, "seed": shot.seed, "speed": shot.speed,
        "style": style, "characters": characters, "negative": negative, "nodes": node_config,
        "workflow_sha256": file_sha256(workflow_path),
        "reference_sha256": file_sha256(shot.reference_image) if shot.reference_image.is_file() else None,
        "motion_sha256": file_sha256(shot.motion_video) if shot.motion_video else None,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def patch_shot_workflow(workflow: dict[str, Any], *, positive_node_id: str,
                        positive_field: str, seed_node_id: str, seed_field: str,
                        image_node_id: str, image_field: str, positive_prompt: str, seed: int,
                        uploaded_image_name: str, negative_node_id: str | None = None,
                        negative_field: str = "text", negative_prompt: str = "",
                        motion_node_id: str | None = None, motion_field: str = "video",
                        motion_filename: str | None = None) -> dict[str, Any]:
    """Patch a fresh API workflow copy; field names are configurable for different ComfyUI nodes."""
    patched = copy.deepcopy(workflow)
    def set_input(node_id: str, field: str, value: Any) -> None:
        node = patched.get(str(node_id))
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            raise ValueError(f"Workflow node '{node_id}' does not exist or has no inputs")
        if field not in node["inputs"]:
            raise ValueError(f"Workflow node '{node_id}' has no input '{field}'")
        node["inputs"][field] = value
    set_input(positive_node_id, positive_field, positive_prompt)
    set_input(seed_node_id, seed_field, int(seed))
    set_input(image_node_id, image_field, uploaded_image_name)
    if negative_node_id:
        set_input(negative_node_id, negative_field, negative_prompt)
    if motion_filename is not None:
        if not motion_node_id:
            raise ValueError("A motion filename requires motion_node_id")
        set_input(motion_node_id, motion_field, motion_filename)
    return patched


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
        motion = Path(str(raw["motion_video"])) if raw.get("motion_video") else None
        if motion and not motion.is_absolute(): motion = root / motion
        prompt = str(raw.get("prompt", "")).strip()
        if not prompt: raise ValueError(f"Empty prompt for {sid}")
        seed, speed = int(raw.get("seed", 1000+i)), float(raw.get("speed", 1.0))
        if not 0.25 <= speed <= 4.0: raise ValueError(f"Speed for {sid} must be 0.25–4.0")
        if src:
            if not src.is_file(): raise FileNotFoundError(f"Source video missing: {src}")
        elif not ref.is_file():
            raise FileNotFoundError(f"Reference image for {sid} missing: {ref}")
        if motion and not motion.is_file(): raise FileNotFoundError(f"Motion video missing: {motion}")
        shots.append(Shot(sid, ref, prompt, seed, speed, src, motion))
    return data, shots

def generate(project: dict[str, Any], shots: list[Shot], workflow_path: Path, base_url: str,
             positive_id: str, seed_id: str, image_id: str, negative_id: str | None,
             output_dir: Path, timeout: int, motion_id: str | None = None,
             motion_field: str = "video", comfy_input_dir: Path | None = None,
             positive_field: str = "text", seed_field: str = "seed",
             image_field: str = "image", negative_field: str = "text",
             force: bool = False) -> list[Path]:
    """Generate resumable shots from a ComfyUI API workflow and approved reference assets."""
    if ComfyUIClient is None:
        raise RuntimeError("engine.py belum tersedia. Jalankan script dari folder ai-anime-studio.")
    workflow_template = json.loads(workflow_path.read_text(encoding="utf-8"))
    style = str(project.get("style_bible", "premium 2D cel animation, consistent ink, expressive readable silhouettes"))
    characters = str(project.get("character_bible", "Preserve identity, colors, proportions and face from each reference image"))
    negative = str(project.get("negative_prompt", "flicker, identity drift, extra limbs, malformed anatomy, duplicate character, text, watermark"))
    uses_motion = any(shot.motion_video for shot in shots)
    if uses_motion and not (motion_id and comfy_input_dir):
        raise ValueError("motion_video requires --motion-video-node and --comfy-input-dir (folder ComfyUI/input on server)")
    if uses_motion:
        assert comfy_input_dir is not None and motion_id is not None
        motion_node = workflow_template.get(str(motion_id))
        if not isinstance(motion_node, dict) or motion_field not in motion_node.get("inputs", {}):
            raise ValueError(f"Motion node {motion_id} does not expose input {motion_field}")
        comfy_input_dir.mkdir(parents=True, exist_ok=True)
    client = ComfyUIClient(base_url=base_url, timeout=60)
    client.health()
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    results: list[Path] = []
    node_config = {"positive_node":str(positive_id),"positive_field":positive_field,
        "seed_node":str(seed_id),"seed_field":seed_field,"image_node":str(image_id),
        "image_field":image_field,"negative_node":str(negative_id or ""),
        "negative_field":negative_field,"motion_node":str(motion_id or ""),
        "motion_field":motion_field}
    for i, shot in enumerate(shots, 1):
        if not shot.reference_image.is_file():
            raise FileNotFoundError(f"Reference image for generated shot '{shot.id}' missing: {shot.reference_image}")
        prompt = (f"{style}. Character continuity: {characters}. Shot action: {shot.prompt}. "
                  "Keep identity stable from first to last frame; clear silhouettes, deliberate anticipation and follow-through, "
                  "smooth animation timing, no camera teleporting.")
        fingerprint = shot_fingerprint(shot, workflow_path, style=style, characters=characters,
                                       negative=negative, node_config=node_config)
        candidates = [raw_dir / f"{i:02d}_{shot.id}.mp4", raw_dir / f"{i:02d}_{shot.id}.gif"]
        if not force:
            for candidate in candidates:
                sidecar = candidate.with_suffix(".json")
                if candidate.is_file() and candidate.stat().st_size > 512 and sidecar.is_file():
                    try:
                        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        metadata = {}
                    if metadata.get("fingerprint") == fingerprint:
                        print(f"[resume] {shot.id}: cache cocok, memakai hasil yang sudah tervalidasi")
                        results.append(candidate)
                        break
            else:
                pass
            if results and results[-1] in candidates:
                continue
        # Stale results cannot silently be reused when prompt, seed, reference, workflow or settings changed.
        for candidate in candidates:
            candidate.unlink(missing_ok=True)
            candidate.with_suffix(".json").unlink(missing_ok=True)
        uploaded_image_name = client.upload_image(shot.reference_image)
        motion_filename = None
        if shot.motion_video:
            assert comfy_input_dir is not None and motion_id is not None
            motion_target = comfy_input_dir / f"{shot.id}{shot.motion_video.suffix.lower()}"
            if shot.motion_video.resolve() != motion_target.resolve():
                shutil.copy2(shot.motion_video, motion_target)
            motion_filename = motion_target.name
        patched = patch_shot_workflow(
            workflow_template, positive_node_id=positive_id, positive_field=positive_field,
            seed_node_id=seed_id, seed_field=seed_field, image_node_id=image_id, image_field=image_field,
            positive_prompt=prompt, seed=shot.seed, uploaded_image_name=uploaded_image_name,
            negative_node_id=negative_id, negative_field=negative_field, negative_prompt=negative,
            motion_node_id=motion_id, motion_field=motion_field, motion_filename=motion_filename,
        )
        print(f"[{i}/{len(shots)}] Generating {shot.id}, seed={shot.seed}")
        prompt_id = client.submit(patched)
        output_metadata = client.wait_for_video(prompt_id, timeout=timeout)
        suffix = ".gif" if output_metadata.get("media_key") == "gifs" else ".mp4"
        target = raw_dir / f"{i:02d}_{shot.id}{suffix}"
        client.download_media(output_metadata, target)
        # Decode the complete returned file before marking it as reusable.
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(target), "-f", "null", "-"])
        target.with_suffix(".json").write_text(json.dumps({
            "id":shot.id,"prompt":prompt,"negative_prompt":negative,"seed":shot.seed,
            "reference_image":str(shot.reference_image),"workflow":str(workflow_path),
            "motion_video":str(shot.motion_video) if shot.motion_video else None,
            "fingerprint":fingerprint,"output_metadata":output_metadata,
            "generated_at_unix":int(time.time())
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        results.append(target)
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

def create_review_bundle(shots: list[Shot], clips: list[Path], review_dir: Path,
                         final_video: Path) -> tuple[Path, Path]:
    """Create an offline HTML review page and three-frame-per-shot contact sheet."""
    if len(shots) != len(clips):
        raise ValueError("QC review requires one normalized clip per shot.")
    review_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = review_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    cell_w, image_h, label_h = 320, 180, 30
    sheet = Image.new("RGB", (cell_w * 3, (image_h + label_h) * len(shots)), (22, 25, 32))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    html_rows: list[str] = []
    summary: list[dict[str, Any]] = []
    labels = (("start", 0.05), ("middle", 0.50), ("end", 0.92))
    for index, (shot, clip) in enumerate(zip(shots, clips)):
        clip_duration = duration(clip)
        row_frames: list[Path] = []
        cards: list[str] = []
        for col, (label, fraction) in enumerate(labels):
            timestamp = min(max(0.0, clip_duration * fraction), max(0.0, clip_duration - 0.08))
            frame_path = frames_dir / f"{index + 1:02d}_{shot.id}_{label}.jpg"
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{timestamp:.3f}",
                 "-i", str(clip), "-frames:v", "1", "-q:v", "3", str(frame_path)])
            if not frame_path.is_file() or frame_path.stat().st_size < 256:
                raise RuntimeError(f"Unable to extract QC frame {label} from {clip}")
            with Image.open(frame_path) as opened:
                thumbnail = opened.convert("RGB")
                thumbnail.thumbnail((cell_w, image_h), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (cell_w, image_h), (0, 0, 0))
                canvas.paste(thumbnail, ((cell_w-thumbnail.width)//2, (image_h-thumbnail.height)//2))
                sheet.paste(canvas, (col*cell_w, index*(image_h+label_h)))
                draw.text((col*cell_w+8, index*(image_h+label_h)+image_h+7),
                          f"{shot.id} | {label} | {timestamp:.2f}s", fill=(235, 238, 245), font=font)
            row_frames.append(frame_path)
            cards.append(f'<figure><img src="frames/{html.escape(frame_path.name)}" alt="{html.escape(shot.id)} {label}"><figcaption>{html.escape(label.title())} · {timestamp:.2f}s</figcaption></figure>')
        html_rows.append(
            f'<section><h2>{index+1:02d}. {html.escape(shot.id)}</h2>'
            f'<p><strong>Prompt:</strong> {html.escape(shot.prompt)}<br>'
            f'<strong>Seed:</strong> {shot.seed} · <strong>Speed:</strong> {shot.speed:g}× · '
            f'<strong>Duration:</strong> {clip_duration:.2f}s · <strong>File:</strong> {html.escape(clip.name)}</p>'
            f'<div class="frames">{"".join(cards)}</div></section>'
        )
        summary.append({"shot_id":shot.id,"clip":str(clip),"duration_seconds":round(clip_duration,3),
                        "file_bytes":clip.stat().st_size,"seed":shot.seed,"speed":shot.speed,
                        "prompt":shot.prompt,"qc_frames":[str(p) for p in row_frames]})
    sheet_path = review_dir / "contact_sheet.jpg"
    sheet.save(sheet_path, quality=88, optimize=True)
    page = """<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Anime Studio — Shot Review</title><style>
body{font:16px system-ui,sans-serif;background:#151923;color:#e8edf5;max-width:1200px;margin:2rem auto;padding:0 1rem}
a{color:#93c5fd}section{border:1px solid #343b4a;border-radius:12px;margin:1.2rem 0;padding:1rem}
.frames{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.7rem}figure{margin:0}img{width:100%;height:auto;display:block;background:#000}figcaption{font-size:.85rem;color:#b8c1d1}
p{line-height:1.5;overflow-wrap:anywhere}@media(max-width:700px){.frames{grid-template-columns:1fr}}
</style><body><h1>AI Anime Studio — QC Shot Review</h1>
<p>Review the beginning, middle and end of each generated shot before publishing. This report does not automatically judge identity consistency or animation quality.</p>
<p><strong>Final episode:</strong> <code>""" + html.escape(str(final_video.resolve())) + """</code></p>
""" + "\n".join(html_rows) + "</body></html>"
    page_path = review_dir / "index.html"
    page_path.write_text(page, encoding="utf-8")
    (review_dir / "qc_summary.json").write_text(json.dumps({
        "final_video":str(final_video.resolve()),"shot_count":len(shots),
        "contact_sheet":str(sheet_path.resolve()),"shots":summary
    },indent=2,ensure_ascii=False),encoding="utf-8")
    return page_path, sheet_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",type=Path,required=True)
    p.add_argument("--output",type=Path,default=Path("outputs/episode_final.mp4"))
    p.add_argument("--work-dir",type=Path,default=Path("outputs/studio_pipeline"))
    p.add_argument("--workflow",type=Path)
    p.add_argument("--comfy-url",default="http://127.0.0.1:8188")
    p.add_argument("--positive-node"); p.add_argument("--positive-field", default="text")
    p.add_argument("--seed-node"); p.add_argument("--seed-field", default="seed")
    p.add_argument("--image-node"); p.add_argument("--image-field", default="image")
    p.add_argument("--negative-node"); p.add_argument("--negative-field", default="text")
    p.add_argument("--motion-video-node", help="Optional video-loader node ID for a driving motion video")
    p.add_argument("--motion-video-field", default="video", help="Input name on the video-loader node; inspect your API workflow")
    p.add_argument("--force", action="store_true", help="Regenerate all shots even if cache fingerprint matches")
    p.add_argument("--skip-review", action="store_true", help="Do not create the HTML/contact-sheet QC bundle")
    p.add_argument("--comfy-input-dir", type=Path, help="ComfyUI/input directory on the machine running ComfyUI")
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
        raws = generate(project,shots,a.workflow,a.comfy_url,a.positive_node,a.seed_node,a.image_node,a.negative_node,
            a.work_dir,a.timeout,a.motion_video_node,a.motion_video_field,a.comfy_input_dir,
            a.positive_field,a.seed_field,a.image_field,a.negative_field,a.force)
    normalized = []
    for i,(shot,raw) in enumerate(zip(shots,raws),1):
        dst=a.work_dir/"normalized"/f"{i:02d}_{shot.id}.mp4"
        if not dst.exists() or dst.stat().st_mtime < Path(raw).stat().st_mtime:
            normalize(Path(raw),dst,a.width,a.height,a.fps,shot.speed)
        normalized.append(dst)
    final_path = a.output.resolve()
    assemble(normalized,final_path,a.fps,a.transition,a.music.resolve() if a.music else None)
    if not a.skip_review:
        page, sheet = create_review_bundle(shots,normalized,a.work_dir/"review",final_path)
        print(f"QC review: {page}")
        print(f"Contact sheet: {sheet}")
    return 0

if __name__ == "__main__":
    try: raise SystemExit(main())
    except (ValueError,FileNotFoundError,RuntimeError,TimeoutError,json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr); raise SystemExit(2)
