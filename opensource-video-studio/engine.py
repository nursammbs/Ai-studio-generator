from __future__ import annotations

import asyncio
import json
import re
import subprocess
import time
import textwrap
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
HEADERS = {"User-Agent": "OpenSourceVideoStudio/0.1 (educational local app)"}


def _get(url, params, timeout=30):
    response = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response


def research_topic(topic: str, language: str = "id") -> list[dict[str, str]]:
    lang = "en" if language == "en" else "id"
    params = {
        "action": "query", "generator": "search", "gsrsearch": topic,
        "gsrnamespace": 0, "gsrlimit": 5, "prop": "extracts|info",
        "exintro": 1, "explaintext": 1, "exchars": 1800,
        "inprop": "url", "format": "json", "formatversion": 2,
    }
    try:
        pages = _get(f"https://{lang}.wikipedia.org/w/api.php", params).json().get("query", {}).get("pages", [])
    except (requests.RequestException, ValueError):
        return []
    results = []
    for page in pages:
        extract = re.sub(r"\s+", " ", page.get("extract", "")).strip()
        if extract:
            results.append({
                "title": str(page.get("title", "Wikipedia")),
                "url": str(page.get("fullurl", f"https://{lang}.wikipedia.org/")),
                "extract": extract,
            })
    return results


def _fallback_scenes(topic: str, sources: list[dict[str, str]], count: int, language: str):
    english = language == "en"
    headings = (
        ["Opening question", "Context", "What sources say", "Common misunderstanding", "Conclusion", "Next step", "Recap"]
        if english else
        ["Pertanyaan pembuka", "Konteks utama", "Yang disebut sumber", "Kesalahpahaman umum", "Kesimpulan", "Langkah berikutnya", "Ringkasan"]
    )
    facts = []
    for source in sources:
        facts.extend(re.split(r"(?<=[.!?])\s+", source["extract"]))
    facts = [x.strip() for x in facts if x.strip()]
    scenes = []
    for i in range(count):
        heading = headings[i % len(headings)]
        if i == 0:
            narration = (f"What should we understand about {topic}? This video is a starting point, and its claims should be checked against the linked sources."
                         if english else f"Apa yang perlu kita pahami tentang {topic}? Video ini merupakan titik awal; periksa klaimnya melalui sumber yang dicantumkan.")
        elif facts:
            fact = facts[min(i - 1, len(facts) - 1)]
            narration = (f"A source summary states: {fact} Check the original page and context before treating this as a verified claim."
                         if english else f"Ringkasan sumber menyebutkan: {fact} Periksa halaman asli dan konteksnya sebelum menganggap ini sebagai klaim yang terverifikasi.")
        else:
            narration = (f"To explain {topic} accurately, add a reliable source, date, and specific example before publishing this section."
                         if english else f"Untuk menjelaskan {topic} secara akurat, tambahkan sumber tepercaya, tanggal, dan contoh spesifik sebelum memublikasikan bagian ini.")
        scenes.append({"heading": heading, "narration": narration, "visual_query": topic})
    return scenes


def generate_scenes(topic: str, sources: list[dict[str, str]], count: int, language: str,
                    use_ollama: bool, model: str, style: str):
    if use_ollama:
        context = "\n\n".join(f"SOURCE: {s['title']}\nURL: {s['url']}\nEXTRACT: {s['extract']}" for s in sources)
        prompt = (
            "Output valid JSON only with a top-level 'scenes' array. Write in "
            + ("English" if language == "en" else "Bahasa Indonesia")
            + f". Topic: {topic}. Style: {style}. Make exactly {count} scenes. Every item has string fields "
            "'heading', 'narration', 'visual_query'. Use the source context for factual claims. Do not invent names, dates, "
            "numbers, quotations, or sources. Where evidence is missing, say it needs checking. Write original narration, "
            "not copied paragraphs. Avoid promises of money, views, or guaranteed results.\nSOURCE CONTEXT:\n"
            + (context or "[No source results; keep facts cautious and flag verification.]")
            + '\nExample shape: {"scenes":[{"heading":"...","narration":"...","visual_query":"..."}]}'
        )
        try:
            response = requests.post(
                "http://127.0.0.1:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
                timeout=240,
            )
            response.raise_for_status()
            raw = response.json().get("response", "")
            parsed = json.loads(raw)
            scenes = []
            for item in parsed.get("scenes", []):
                if not isinstance(item, dict):
                    continue
                heading = str(item.get("heading", "")).strip()[:100]
                narration = str(item.get("narration", "")).strip()
                query = str(item.get("visual_query", topic)).strip()[:150] or topic
                if heading and narration:
                    scenes.append({"heading": heading, "narration": narration, "visual_query": query})
            if len(scenes) >= 2:
                return scenes[:count], f"Draf dibantu Ollama ({model}). Verifikasi tetap wajib."
        except (requests.RequestException, ValueError, TypeError, KeyError):
            pass
        return _fallback_scenes(topic, sources, count, language), "Ollama gagal diakses/keluarannya tidak valid; memakai kerangka cadangan."
    return _fallback_scenes(topic, sources, count, language), "Kerangka cadangan dipakai. Untuk naskah yang lebih baik, jalankan Ollama dan edit/verifikasi draf."


def _clean_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value or "").strip()


def _commons_image(query: str):
    params = {
        "action": "query", "generator": "search", "gsrsearch": f"{query} filetype:bitmap",
        "gsrnamespace": 6, "gsrlimit": 8, "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiurlwidth": 1280, "format": "json", "formatversion": 2,
    }
    try:
        pages = _get("https://commons.wikimedia.org/w/api.php", params).json().get("query", {}).get("pages", [])
    except (requests.RequestException, ValueError):
        return None
    for page in pages:
        infos = page.get("imageinfo", [])
        if not infos:
            continue
        info = infos[0]
        meta = info.get("extmetadata", {})
        license_name = _clean_html(meta.get("LicenseShortName", {}).get("value", ""))
        normalized = license_name.lower()
        allowed = any(k in normalized for k in ("cc by", "cc0", "public domain", "pd"))
        excluded = any(k in normalized for k in ("noncommercial", "non-commercial", " cc nc", "cc by-nd", "cc by nd"))
        if not allowed or excluded:
            continue
        title = str(page.get("title", "Wikimedia image"))
        return {
            "title": title,
            "url": str(info.get("thumburl") or info.get("url") or ""),
            "page_url": "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_"),
            "artist": _clean_html(meta.get("Artist", {}).get("value", "Unknown author")) or "Unknown author",
            "license": license_name,
            "license_url": str(meta.get("LicenseUrl", {}).get("value", "")),
        }
    return None


def _font(size: int, bold: bool = False):
    paths = (
        ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold else
        ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _make_card(image_path: Path | None, heading: str, index: int, total: int, size: tuple[int, int], target: Path):
    width, height = size
    if image_path and image_path.exists():
        try:
            with Image.open(image_path) as opened:
                base = ImageOps.fit(opened.convert("RGB"), size, method=Image.Resampling.LANCZOS)
        except OSError:
            base = Image.new("RGB", size, (22, 34, 63))
    else:
        base = Image.new("RGB", size, (22, 34, 63))
    panel = Image.new("RGBA", size, (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    for y in range(int(height * .43), height):
        alpha = int(45 + 190 * (y - int(height * .43)) / max(1, int(height * .57)))
        pdraw.line((0, y, width, y), fill=(4, 8, 18, alpha))
    base = Image.alpha_composite(base.convert("RGBA"), panel)
    draw = ImageDraw.Draw(base)
    margin = int(width * .075)
    draw.text((margin, int(height * .06)), "OPEN SOURCE VIDEO STUDIO", font=_font(max(16, int(width * .025)), True), fill="white")
    draw.text((margin, int(height * .12)), f"SCENE {index + 1}/{total}", font=_font(max(15, int(width * .02))), fill=(226, 233, 250, 255))
    font = _font(max(28, int(width * (.058 if width < height else .045))), True)
    max_chars = 23 if width < height else 42
    lines = textwrap.wrap(heading, width=max_chars)[:4 if width < height else 3]
    line_height = int(font.size * 1.2) if hasattr(font, "size") else 42
    y = max(int(height * .6), height - margin - len(lines) * line_height - int(height * .12))
    for line in lines:
        draw.text((margin, y), line, font=font, fill="white", stroke_width=2, stroke_fill=(0, 0, 0, 190))
        y += line_height
    bar_y = height - int(height * .05)
    draw.rectangle((margin, bar_y, width - margin, bar_y + max(4, int(height * .006))), fill=(200, 210, 225, 110))
    draw.rectangle((margin, bar_y, margin + int((width - margin * 2) * ((index + 1) / total)), bar_y + max(4, int(height * .006))), fill="white")
    base.convert("RGB").save(target, quality=92)


def _download_image(url: str, target: Path) -> bool:
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        target.write_bytes(response.content)
        with Image.open(target) as img:
            img.verify()
        return True
    except (requests.RequestException, OSError, ValueError):
        target.unlink(missing_ok=True)
        return False


def _make_voice(text: str, target: Path, language: str):
    import edge_tts
    voice = "id-ID-GadisNeural" if language == "id" else "en-US-AriaNeural"

    async def create():
        await edge_tts.Communicate(text, voice).save(str(target))

    try:
        asyncio.run(create())
        return
    except Exception as original_error:
        try:
            import pyttsx3
            wav = target.with_suffix(".wav")
            engine = pyttsx3.init()
            engine.save_to_file(text, str(wav))
            engine.runAndWait()
            engine.stop()
            if not wav.exists() or wav.stat().st_size == 0:
                raise RuntimeError("System TTS did not create audio")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), str(target)],
                           check=True, capture_output=True, text=True)
            wav.unlink(missing_ok=True)
        except Exception as fallback_error:
            raise RuntimeError("TTS failed. Check internet/Edge TTS or install pyttsx3 and a system voice.") from original_error


def _duration(audio: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio)],
        check=True, capture_output=True, text=True,
    )
    return max(1.0, float(result.stdout.strip()))


def _render_scene(card: Path, audio: Path, target: Path, size: tuple[int, int]):
    w, h = size
    duration = _duration(audio)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(card), "-i", str(audio),
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30,format=yuv420p",
        "-t", f"{duration:.3f}", "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", str(target),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def create_video(topic: str, scenes: list[dict[str, str]], sources: list[dict[str, str]],
                 language: str = "id", aspect: str = "9:16", progress=None) -> Path:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", topic.lower()).strip("-")[:40] or "video"
    job = OUTPUTS / f"{safe}-{int(time.time())}"
    assets = job / "assets"
    assets.mkdir(parents=True)
    size = (720, 1280) if aspect == "9:16" else (1280, 720)
    segments, credits = [], []
    for i, scene in enumerate(scenes):
        if progress:
            progress(i / max(len(scenes), 1), f"Rendering scene {i + 1}/{len(scenes)}")
        asset = _commons_image(scene.get("visual_query", topic))
        picture = None
        if asset and _download_image(asset["url"], assets / f"image-{i + 1}.jpg"):
            picture = assets / f"image-{i + 1}.jpg"
            credits.append({"scene": i + 1, **asset})
        card = assets / f"card-{i + 1:02d}.jpg"
        _make_card(picture, scene["heading"], i, len(scenes), size, card)
        audio = assets / f"voice-{i + 1:02d}.mp3"
        _make_voice(scene["narration"], audio, language)
        segment = assets / f"segment-{i + 1:02d}.mp4"
        _render_scene(card, audio, segment, size)
        segments.append(segment)
    concat = job / "concat.txt"
    def quoted(path: Path):
        return str(path.resolve()).replace(chr(92), "/")
    concat.write_text("\\n".join("file '" + quoted(p) + "'" for p in segments) + "\\n", encoding="utf-8")
    video = job / "video.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-movflags", "+faststart", str(video),
    ], check=True, capture_output=True, text=True)
    with Image.open(assets / "card-01.jpg") as opened:
        ImageOps.fit(opened.convert("RGB"), (1280, 720), method=Image.Resampling.LANCZOS).save(job / "thumbnail.jpg", quality=92)
    script_lines = [f"# {topic}", "", "Draft otomasi — verifikasi sebelum publikasi.", ""]
    for i, scene in enumerate(scenes, 1):
        script_lines += [f"## Scene {i}: {scene['heading']}", "", scene["narration"], ""]
    (job / "script.md").write_text("\\n".join(script_lines), encoding="utf-8")
    src_lines = ["# Sumber riset awal", ""]
    for source in sources:
        src_lines += [f"## {source['title']}", source["url"], source["extract"], ""]
    if not sources:
        src_lines.append("Tidak ada hasil otomatis. Tambahkan sumber tepercaya secara manual.")
    (job / "sources.md").write_text("\\n".join(src_lines), encoding="utf-8")
    (job / "image_attribution.json").write_text(json.dumps(credits, ensure_ascii=False, indent=2), encoding="utf-8")
    description = topic + "\\n\\nVideo dibantu Open Source Video Studio. Periksa fakta dan lisensi sebelum publikasi.\\n\\nSumber riset:\\n"
    description += "\\n".join(f"- {s['title']}: {s['url']}" for s in sources)
    if credits:
        description += "\\n\\nAtribusi gambar:\\n" + "\\n".join(
            f"- Scene {c['scene']}: {c['title']} — {c['artist']}; lisensi {c['license']}; {c['page_url']}" for c in credits
        )
    (job / "description.txt").write_text(description + "\\n", encoding="utf-8")
    if progress:
        progress(1.0, "Selesai — tinjau naskah, sumber, lisensi, suara, dan video.")
    return job


def fallback_scenes_for_test(topic, sources, count=3, language="id"):
    return _fallback_scenes(topic, sources, count, language)
