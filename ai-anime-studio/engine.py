from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass
class ComfyUIClient:
    """Small client for the local ComfyUI HTTP API."""
    base_url: str = "http://127.0.0.1:8188"
    timeout: float = 30.0

    def _request(self, path: str, *, method: str = "GET", payload: Any = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base_url.rstrip("/") + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read()
                if "application/json" in response.headers.get("Content-Type", "") or raw[:1] in (b"{", b"["):
                    return json.loads(raw.decode("utf-8"))
                return raw
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"ComfyUI HTTP {exc.code} at {path}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Tidak bisa terhubung ke ComfyUI di {self.base_url}. "
                "Jalankan ComfyUI dan pastikan alamat/port benar."
            ) from exc

    def health(self) -> dict[str, Any]:
        result = self._request("/system_stats")
        if not isinstance(result, dict):
            raise RuntimeError("Respons /system_stats bukan JSON object.")
        return result

    @staticmethod
    def patch_workflow(workflow: dict[str, Any], positive_node_id: str, negative_node_id: str,
                       seed_node_id: str, positive_prompt: str, negative_prompt: str,
                       seed: int) -> dict[str, Any]:
        """Copy workflow and update chosen CLIP text + sampler seed inputs."""
        patched = json.loads(json.dumps(workflow))
        for node_id, field, value in [
            (str(positive_node_id), "text", positive_prompt),
            (str(negative_node_id), "text", negative_prompt),
            (str(seed_node_id), "seed", int(seed)),
        ]:
            if node_id not in patched:
                raise ValueError(f"Node ID '{node_id}' tidak ditemukan pada workflow API.")
            inputs = patched[node_id].get("inputs", {})
            if field not in inputs:
                raise ValueError(f"Node '{node_id}' tidak memiliki input '{field}'.")
            inputs[field] = value
        return patched

    def submit(self, workflow: dict[str, Any]) -> str:
        result = self._request("/prompt", method="POST", payload={"prompt": workflow})
        prompt_id = result.get("prompt_id") if isinstance(result, dict) else None
        if not prompt_id:
            raise RuntimeError(f"ComfyUI tidak mengembalikan prompt_id: {result}")
        return str(prompt_id)

    def wait_for_outputs(self, prompt_id: str, timeout: float = 600, poll_seconds: float = 2) -> list[dict[str, str]]:
        deadline, last_seen = time.monotonic() + timeout, None
        while time.monotonic() < deadline:
            history = self._request("/history/" + urllib.parse.quote(prompt_id, safe=""))
            record = history.get(prompt_id, {}) if isinstance(history, dict) else {}
            outputs = record.get("outputs", {}) if isinstance(record, dict) else {}
            images: list[dict[str, str]] = []
            for node in outputs.values():
                if not isinstance(node, dict):
                    continue
                for image in node.get("images", []):
                    if image.get("filename"):
                        images.append({
                            "filename": str(image["filename"]),
                            "subfolder": str(image.get("subfolder", "")),
                            "type": str(image.get("type", "output")),
                        })
            if images:
                return images
            last_seen = record or history
            time.sleep(max(0.2, poll_seconds))
        raise TimeoutError(f"ComfyUI belum menghasilkan gambar setelah {timeout}s. Status terakhir: {last_seen}")

    def download_image(self, metadata: dict[str, str], target: str | Path) -> Path:
        query = urllib.parse.urlencode({
            "filename": metadata["filename"],
            "subfolder": metadata.get("subfolder", ""),
            "type": metadata.get("type", "output"),
        })
        raw = self._request("/view?" + query)
        if not isinstance(raw, bytes):
            raise RuntimeError("Endpoint ComfyUI /view tidak mengembalikan data gambar.")
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        with Image.open(target) as image:
            image.verify()
        return target

    def generate_image(self, workflow: dict[str, Any], *, positive_node_id: str, negative_node_id: str,
                       seed_node_id: str, positive_prompt: str, negative_prompt: str, seed: int,
                       output_dir: str | Path, timeout: float = 600) -> Path:
        patched = self.patch_workflow(workflow, positive_node_id, negative_node_id, seed_node_id,
                                      positive_prompt, negative_prompt, seed)
        prompt_id = self.submit(patched)
        images = self.wait_for_outputs(prompt_id, timeout=timeout)
        if not images:
            raise RuntimeError("Workflow selesai tetapi tidak menghasilkan gambar.")
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        return self.download_image(images[0], directory / f"scene_seed_{seed}.png")


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def _draw_cat(d: ImageDraw.ImageDraw, x: float, y: float, t: float, surprised: bool = False) -> None:
    outline, fur = (35, 38, 48), (116, 132, 154)
    tail = 20 * math.sin(t * 5)
    d.line([(x-28,y+12),(x-57,y-2+tail),(x-82,y+tail)], fill=outline, width=10, joint="curve")
    d.ellipse((x-56,y-8,x+27,y+40), fill=fur, outline=outline, width=4)
    d.ellipse((x+1,y-66,x+69,y+3), fill=fur, outline=outline, width=4)
    d.polygon([(x+8,y-52),(x+13,y-84),(x+34,y-59)], fill=fur, outline=outline)
    d.polygon([(x+40,y-58),(x+61,y-83),(x+64,y-47)], fill=fur, outline=outline)
    ey = y-45 if surprised else y-42
    d.ellipse((x+17,ey,x+31,ey+17), fill=(255,222,95), outline=outline, width=2)
    d.ellipse((x+45,ey,x+59,ey+17), fill=(255,222,95), outline=outline, width=2)
    d.ellipse((x+22,ey+4,x+27,ey+13), fill=(20,20,25))
    d.ellipse((x+50,ey+4,x+55,ey+13), fill=(20,20,25))
    d.polygon([(x+34,y-24),(x+43,y-24),(x+38,y-18)], fill=(232,130,150))
    if surprised:
        d.ellipse((x+32,y-15,x+47,y+2), fill=(65,32,38), outline=outline, width=2)
    else:
        d.line([(x+38,y-18),(x+34,y-13)], fill=outline, width=2)
        d.line([(x+38,y-18),(x+43,y-13)], fill=outline, width=2)
    for dy in [-3,5,12]:
        d.line([(x+18,y-23+dy),(x-2,y-28+dy)], fill=(245,245,245), width=2)
    swing = 17 * math.sin(t*11)
    d.line([(x-31,y+28),(x-39+swing,y+48)], fill=outline, width=8)
    d.line([(x+4,y+28),(x+12-swing,y+48)], fill=outline, width=8)


def _draw_mouse(d: ImageDraw.ImageDraw, x: float, y: float, t: float) -> None:
    outline, gray = (45,40,42), (158,151,151)
    d.line([(x-27,y+2),(x-43,y+12+4*math.sin(t*6)),(x-56,y+4)], fill=(183,110,120), width=4)
    d.ellipse((x-30,y-10,x+22,y+19), fill=gray, outline=outline, width=3)
    d.ellipse((x+5,y-33,x+42,y+4), fill=(175,166,165), outline=outline, width=3)
    d.ellipse((x+4,y-48,x+23,y-28), fill=(222,173,182), outline=outline, width=3)
    d.ellipse((x+25,y-45,x+44,y-26), fill=(222,173,182), outline=outline, width=3)
    d.ellipse((x+29,y-25,x+34,y-19), fill=(20,20,20))
    d.ellipse((x+39,y-16,x+45,y-10), fill=(80,50,50))


def render_offline_animatic(output_path: str | Path, *, width: int = 960, height: int = 540,
                            fps: int = 24, seconds_per_scene: int = 4) -> Path:
    """Render a deterministic 3-scene vector cartoon without downloading assets/models."""
    if width < 320 or height < 180 or fps < 1 or seconds_per_scene < 1:
        raise ValueError("Ukuran, FPS, atau durasi tidak valid.")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    total = fps * seconds_per_scene * 3
    title_font, caption_font = _font(26, True), _font(19)
    for index in range(total):
        t = index / fps
        scene = min(2, int(t // seconds_per_scene))
        local = t - scene * seconds_per_scene
        image = Image.new("RGB", (width,height), (178,220,246))
        d = ImageDraw.Draw(image)
        d.rectangle((0,int(height*.67),width,height), fill=(109,171,101))
        d.rectangle((0,int(height*.74),width,height), fill=(91,150,83))
        for cx,cy in [(120,84),(650,105),(830,67)]:
            for ox,oy,r in [(-24,4,20),(0,-8,25),(25,5,19)]:
                d.ellipse((cx+ox-r,cy+oy-r,cx+ox+r,cy+oy+r),fill=(248,251,255))
        d.line([(0,int(height*.67)),(width,int(height*.67))], fill=(67,130,68), width=3)
        if scene == 0:
            cat_x, mouse_x = 150+30*math.sin(local*1.5), 690+8*math.sin(local*3)
            cat_y, caption, surprised = 346+4*math.sin(local*4), "SCENE 1 — A curious cat spots a mouse", False
        elif scene == 1:
            progress = local / seconds_per_scene
            cat_x, mouse_x = 180+progress*345, 580+80*math.sin(local*4)
            cat_y, caption, surprised = 342+10*math.sin(local*11), "SCENE 2 — The chase is on!", False
            for k in range(4):
                sx = cat_x-72-k*21
                d.line([(sx,cat_y-4-k*5),(sx-24,cat_y-4-k*5)], fill=(255,255,255), width=3)
        else:
            cat_x, mouse_x = 500+18*math.sin(local*6), 660-min(60,local*14)
            cat_y, caption, surprised = 342+4*math.sin(local*7), "SCENE 3 — BONK! A comic ending", True
        _draw_cat(d,cat_x,cat_y,t,surprised)
        _draw_mouse(d,mouse_x,344+5*math.sin(t*8),t)
        if scene == 2 and 1.0 < local < 2.5:
            d.rounded_rectangle((width//2-94,98,width//2+94,155),radius=14,
                                fill=(255,248,196),outline=(55,45,40),width=3)
            d.text((width//2-77,105),"BONK!",font=_font(40,True),fill=(237,70,47),
                   stroke_width=1,stroke_fill=(255,255,255))
            for angle in range(0,360,45):
                rad = math.radians(angle)
                p0=(width//2+math.cos(rad)*104,126+math.sin(rad)*35)
                p1=(width//2+math.cos(rad)*125,126+math.sin(rad)*47)
                d.line([p0,p1],fill=(237,70,47),width=4)
        d.rounded_rectangle((18,16,390,59),radius=11,fill=(255,255,255),outline=(45,65,80),width=2)
        d.text((31,24),"OPEN-SOURCE ANIMATIC LAB",font=title_font,fill=(35,50,70))
        d.rounded_rectangle((width//2-300,height-58,width//2+300,height-18),radius=10,
                            fill=(255,255,255),outline=(45,65,80),width=2)
        bounds=d.textbbox((0,0),caption,font=caption_font)
        d.text((width//2-(bounds[2]-bounds[0])/2,height-50),caption,font=caption_font,fill=(35,50,70))
        frames.append(np.asarray(image))
    writer=imageio.get_writer(str(output_path),fps=fps,codec="libx264",quality=8,macro_block_size=1)
    try:
        for frame in frames:
            writer.append_data(frame)
    finally:
        writer.close()
    reader=imageio.get_reader(str(output_path))
    try:
        if reader.get_data(0).shape[:2] != (height,width):
            raise RuntimeError("Dimensi video keluaran tidak sesuai.")
        reader.get_data(total-1)
    finally:
        reader.close()
    return output_path


def _fit_canvas(image: Image.Image, width: int, height: int) -> Image.Image:
    scale=min(width/image.width,height/image.height)
    size=(max(1,round(image.width*scale)),max(1,round(image.height*scale)))
    resized=image.resize(size,Image.Resampling.LANCZOS)
    canvas=Image.new("RGB",(width,height),(14,18,28))
    canvas.paste(resized,((width-resized.width)//2,(height-resized.height)//2))
    return canvas


def render_image_animatic(image_paths: Iterable[str | Path], output_path: str | Path, *,
                           width: int=960, height: int=540, fps: int=24,
                           seconds_per_image: int=3) -> Path:
    """Render generated scene stills as a camera push-in animatic MP4."""
    paths=[Path(p) for p in image_paths]
    if not paths:
        raise ValueError("Minimal satu gambar adegan diperlukan.")
    if fps < 1 or seconds_per_image < 1:
        raise ValueError("FPS dan durasi gambar harus positif.")
    output_path=Path(output_path)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    frames=[]
    for scene_idx,path in enumerate(paths):
        with Image.open(path) as source:
            base=source.convert("RGB")
        for k in range(fps*seconds_per_image):
            progress=k/max(1,fps*seconds_per_image-1)
            scale=1+0.08*progress
            fitted=_fit_canvas(base,round(width*scale),round(height*scale))
            left=max(0,(fitted.width-width)//2+int((scene_idx%2)*progress*8))
            top=max(0,(fitted.height-height)//2)
            crop=fitted.crop((left,top,left+width,top+height))
            frames.append(np.asarray(crop))
    writer=imageio.get_writer(str(output_path),fps=fps,codec="libx264",quality=8,macro_block_size=1)
    try:
        for frame in frames:
            writer.append_data(frame)
    finally:
        writer.close()
    reader=imageio.get_reader(str(output_path))
    try:
        reader.get_data(0)
        reader.get_data(len(frames)-1)
    finally:
        reader.close()
    return output_path
