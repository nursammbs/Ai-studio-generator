from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlparse

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
DB_PATH = Path(os.getenv("VIDEO_API_HUB_DB", str(ROOT / "data" / "jobs.sqlite3"))).expanduser()

PROVIDER_META: dict[str, dict[str, Any]] = {
    "higgsfield": {"name": "Higgsfield API", "kind": "video",
        "capabilities": ["text_to_video", "image_to_video (model-dependent)", "video_edit (model-dependent)"],
        "docs": "https://docs.higgsfield.ai/", "key_env": "HIGGSFIELD_API_KEY",
        "description": "Video dan image models lewat katalog Higgsfield; harga berbeda per model."},
    "runway": {"name": "Runway Dev", "kind": "video",
        "capabilities": ["text_to_video", "image_to_video", "video_to_video"],
        "docs": "https://docs.dev.runwayml.com/", "key_env": "RUNWAY_API_KEY",
        "description": "Generasi dan edit video; parameter bergantung endpoint dan model."},
    "fal": {"name": "fal.ai", "kind": "video",
        "capabilities": ["model-specific text/image/video workflows"],
        "docs": "https://docs.fal.ai/", "key_env": "FAL_KEY",
        "description": "Model melalui antrean; advanced JSON harus cocok dengan schema model."},
    "openai": {"name": "OpenAI API", "kind": "assistant",
        "capabilities": ["script", "prompt", "storyboard text", "shot list"],
        "docs": "https://developers.openai.com/api/docs", "key_env": "OPENAI_API_KEY",
        "description": "Menyusun naskah/prompt. API billing terpisah dari paket ChatGPT."},
    "comfyui": {"name": "ComfyUI lokal/cloud sendiri", "kind": "local",
        "capabilities": ["custom workflows", "image/video generation"],
        "docs": "https://docs.comfy.org/", "key_env": "COMFYUI_BASE_URL",
        "description": "Didefinisikan sebagai connector berikutnya; gunakan workflow API JSON."},
}

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con

def init_db() -> None:
    with connect_db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, provider TEXT NOT NULL, mode TEXT NOT NULL,
            prompt TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL,
            external_id TEXT, status_url TEXT, output_url TEXT, error TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, response_json TEXT
        )""")

def provider_key_is_set(provider: str) -> bool:
    if provider == "comfyui":
        return bool(os.getenv("COMFYUI_BASE_URL"))
    return bool(os.getenv(PROVIDER_META[provider]["key_env"], "").strip())

def public_provider_list() -> list[dict[str, Any]]:
    rows = []
    for provider_id, meta in PROVIDER_META.items():
        configured = provider_key_is_set(provider_id)
        rows.append({"id": provider_id, "name": meta["name"], "kind": meta["kind"],
            "capabilities": meta["capabilities"], "docs": meta["docs"],
            "description": meta["description"], "configured": configured,
            "status": "ready" if configured else "needs_setup"})
    return rows

class JobRequest(BaseModel):
    providers: list[Literal["higgsfield", "runway", "fal"]] = Field(min_length=1, max_length=3)
    mode: Literal["text_to_video", "image_to_video", "video_to_video"] = "text_to_video"
    prompt: str = Field(min_length=3, max_length=6000)
    model: str | None = Field(default=None, max_length=180)
    duration: int = Field(default=5, ge=3, le=20)
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    resolution: Literal["480p", "720p", "1080p"] = "720p"
    generate_audio: bool = False
    image_url: str | None = None
    video_url: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    confirm_possible_cost: bool = False

    @field_validator("image_url", "video_url")
    @classmethod
    def validate_https_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        parsed = urlparse(value.strip())
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("URL input harus URL HTTPS yang bisa diakses provider; embedded credential dilarang.")
        return value.strip()

    @field_validator("model")
    @classmethod
    def validate_model_identifier(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if len(value) > 180 or not re.fullmatch(r"[A-Za-z0-9_./:-]+", value) or ".." in value:
            raise ValueError("Model harus berupa ID/path model, bukan URL atau ekspresi.")
        return value

    @field_validator("options")
    @classmethod
    def validate_options_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, ensure_ascii=False)) > 12000:
            raise ValueError("Advanced options maksimal 12 KB.")
        return value

class AssistRequest(BaseModel):
    task: Literal["script", "prompt", "shotlist"] = "prompt"
    brief: str = Field(min_length=3, max_length=12000)
    model: str | None = Field(default=None, max_length=100)

def _json_response(resp: httpx.Response) -> dict[str, Any]:
    try:
        data = resp.json()
    except ValueError:
        data = {"raw_text": resp.text[:2000]}
    if resp.is_error:
        detail = data.get("error", data) if isinstance(data, dict) else data
        raise RuntimeError(f"Provider HTTP {resp.status_code}: {json.dumps(detail, ensure_ascii=False)[:1200]}")
    if not isinstance(data, dict):
        raise RuntimeError("Provider mengembalikan format respons yang tidak didukung.")
    return data

def _extract_url(value: Any) -> str | None:
    wanted = {"url", "video_url", "videoUrl", "output_url", "outputUrl", "download_url", "downloadUrl", "result_url", "resultUrl"}
    if isinstance(value, dict):
        for key, item in value.items():
            if key in wanted and isinstance(item, str) and item.startswith("https://"):
                return item
        for item in value.values():
            found = _extract_url(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _extract_url(item)
            if found:
                return found
    elif isinstance(value, str) and value.startswith("https://") and any(ext in value.lower() for ext in (".mp4", ".webm", ".mov")):
        return value
    return None

def _external_id(data: dict[str, Any]) -> str | None:
    for key in ("request_id", "requestId", "task_id", "taskId", "id", "job_id", "jobId"):
        val = data.get(key)
        if isinstance(val, (str, int)) and str(val).strip():
            return str(val)
    return None

def _status(data: dict[str, Any]) -> str:
    value = str(data.get("status", data.get("state", "submitted"))).lower()
    if value in {"succeeded", "success", "completed", "complete", "done", "finished"}:
        return "completed"
    if value in {"failed", "error", "cancelled", "canceled", "aborted"}:
        return "failed"
    if value in {"running", "processing", "in_progress", "in progress"}:
        return "running"
    return "submitted"

def _provider_base(provider: str) -> str:
    env_name = {"higgsfield": "HIGGSFIELD_API_BASE", "runway": "RUNWAY_API_BASE", "fal": "FAL_API_BASE"}[provider]
    default = {"higgsfield": "https://api.higgsfield.ai", "runway": "https://api.dev.runwayml.com", "fal": "https://queue.fal.run"}[provider]
    return os.getenv(env_name, default).rstrip("/")

async def _submit_provider(provider: str, req: JobRequest) -> tuple[str, str | None, dict[str, Any]]:
    if not provider_key_is_set(provider):
        raise RuntimeError(f"{PROVIDER_META[provider]['name']} belum dikonfigurasi. Tambahkan API key ke .env server.")
    base, timeout = _provider_base(provider), httpx.Timeout(45.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        if provider == "higgsfield":
            endpoint = req.model or os.getenv("HIGGSFIELD_DEFAULT_MODEL", "bytedance/seedance-2.0/text-to-video")
            if endpoint.startswith("/") or not re.fullmatch(r"[A-Za-z0-9_./:-]+", endpoint) or ".." in endpoint:
                raise RuntimeError("Higgsfield model harus berupa path katalog, bukan URL.")
            body: dict[str, Any] = {"prompt": req.prompt, "duration": req.duration,
                "resolution": req.resolution, "aspect_ratio": req.aspect_ratio,
                "generate_audio": req.generate_audio}
            body.update(req.options)
            headers = {"Authorization": "Key " + os.environ["HIGGSFIELD_API_KEY"].strip(), "Content-Type": "application/json"}
            response = await client.post(base + "/" + endpoint, headers=headers, json=body)
        elif provider == "runway":
            model = req.model or ("aleph2" if req.mode == "video_to_video" else "gen4.5")
            headers = {"Authorization": "Bearer " + os.environ["RUNWAY_API_KEY"].strip(),
                "X-Runway-Version": os.getenv("RUNWAY_API_VERSION", "2024-11-06"), "Content-Type": "application/json"}
            ratio = {"16:9": "1280:720", "9:16": "720:1280", "1:1": "1024:1024"}[req.aspect_ratio]
            body: dict[str, Any] = {"model": model, "promptText": req.prompt, "duration": req.duration}
            if req.mode == "text_to_video":
                route = "/v1/text_to_video"; body["ratio"] = ratio
            elif req.mode == "image_to_video":
                if not req.image_url:
                    raise RuntimeError("Runway image-to-video membutuhkan URL gambar HTTPS.")
                route = "/v1/image_to_video"; body.update({"promptImage": req.image_url, "ratio": ratio})
            else:
                if not req.video_url:
                    raise RuntimeError("Runway video-to-video membutuhkan URL video HTTPS.")
                route = "/v1/video_to_video"; body["videoUri"] = req.video_url
            body.update(req.options)
            response = await client.post(base + route, headers=headers, json=body)
        elif provider == "fal":
            model = req.model or os.getenv("FAL_DEFAULT_MODEL", "").strip()
            if not model:
                raise RuntimeError("Pilih model fal.ai endpoint ID di kolom Model/API path.")
            if not re.fullmatch(r"[A-Za-z0-9_./:-]+", model) or model.startswith("/") or ".." in model:
                raise RuntimeError("Model fal.ai harus berupa endpoint ID, bukan URL.")
            body = dict(req.options)
            body.setdefault("prompt", req.prompt)
            body.setdefault("duration", req.duration)
            body.setdefault("aspect_ratio", req.aspect_ratio)
            body.setdefault("resolution", req.resolution)
            if req.mode == "image_to_video" and req.image_url: body.setdefault("image_url", req.image_url)
            if req.mode == "video_to_video" and req.video_url: body.setdefault("video_url", req.video_url)
            headers = {"Authorization": "Key " + os.environ["FAL_KEY"].strip(), "Content-Type": "application/json"}
            response = await client.post(base + "/" + model, headers=headers, json=body)
        else:
            raise RuntimeError("Provider belum didukung.")
        data = _json_response(response)
        ext_id = _external_id(data)
        status_url = data.get("status_url") or data.get("statusUrl")
        if not ext_id and isinstance(status_url, str): ext_id = status_url
        if not ext_id: raise RuntimeError("Provider tidak mengembalikan request/task ID.")
        return ext_id, status_url if isinstance(status_url, str) else None, data

def _insert_job(provider: str, req: JobRequest, ext_id: str | None, status_url: str | None,
                status: str, output_url: str | None, error: str | None, response: dict[str, Any]) -> dict[str, Any]:
    job_id, now = str(uuid.uuid4()), now_iso()
    with connect_db() as con:
        con.execute("""INSERT INTO jobs
        (id, provider, mode, prompt, model, status, external_id, status_url, output_url,
         error, created_at, updated_at, response_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, provider, req.mode, req.prompt, req.model or "", status, ext_id, status_url,
         output_url, error, now, now, json.dumps(response, ensure_ascii=False)[:20000]))
    return get_job(job_id)  # type: ignore[return-value]

def get_job(job_id: str) -> dict[str, Any] | None:
    with connect_db() as con: row = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None: return None
    data = dict(row); data.pop("response_json", None)
    return data

def list_jobs(limit: int = 30) -> list[dict[str, Any]]:
    with connect_db() as con: rows = con.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    result = []
    for row in rows:
        data = dict(row); data.pop("response_json", None); result.append(data)
    return result

def update_job(job_id: str, *, status: str | None = None, output_url: str | None = None,
               error: str | None = None, response: dict[str, Any] | None = None) -> None:
    fields, values = [], []
    if status is not None: fields.append("status = ?"); values.append(status)
    if output_url is not None: fields.append("output_url = ?"); values.append(output_url)
    if error is not None: fields.append("error = ?"); values.append(error[:1500])
    if response is not None: fields.append("response_json = ?"); values.append(json.dumps(response, ensure_ascii=False)[:20000])
    fields.append("updated_at = ?"); values.append(now_iso()); values.append(job_id)
    with connect_db() as con: con.execute("UPDATE jobs SET " + ", ".join(fields) + " WHERE id = ?", values)

async def _refresh_job(job: dict[str, Any]) -> dict[str, Any]:
    provider, ext_id = job["provider"], job["external_id"]
    if not ext_id or job["status"] in {"completed", "failed"}: return job
    if provider == "higgsfield":
        headers = {"Authorization": "Key " + os.environ["HIGGSFIELD_API_KEY"].strip()}
        # Use a fixed origin and URL-encode the ID to avoid arbitrary status URL fetches.
        url = _provider_base(provider) + "/requests/" + quote(ext_id, safe="") + "/status"
    elif provider == "runway":
        headers = {"Authorization": "Bearer " + os.environ["RUNWAY_API_KEY"].strip(),
                   "X-Runway-Version": os.getenv("RUNWAY_API_VERSION", "2024-11-06")}
        url = _provider_base(provider) + "/v1/tasks/" + quote(ext_id, safe="")
    elif provider == "fal":
        headers = {"Authorization": "Key " + os.environ["FAL_KEY"].strip()}
        status_url = job.get("status_url") or ""
        parsed = urlparse(status_url)
        trusted_host = parsed.hostname == "queue.fal.run" or parsed.hostname == "fal.run" or (parsed.hostname or "").endswith(".fal.run")
        if parsed.scheme != "https" or not trusted_host:
            raise RuntimeError("Respons fal.ai tidak memiliki status_url HTTPS dari host fal.ai yang tepercaya.")
        url = status_url
    else:
        return job
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
        data = _json_response(await client.get(url, headers=headers))
    new_status, output_url = _status(data), _extract_url(data)
    error_detail = data.get("error") or data.get("failure") or data.get("message")
    update_job(job["id"], status=new_status, output_url=output_url,
               error=str(error_detail)[:1500] if new_status == "failed" and error_detail else None, response=data)
    return get_job(job["id"]) or job

async def _submit_one(provider: str, req: JobRequest) -> dict[str, Any]:
    try:
        ext_id, status_url, data = await _submit_provider(provider, req)
        status = _status(data)
        return _insert_job(provider, req, ext_id, status_url, status,
                           _extract_url(data) if status == "completed" else None, None, data)
    except Exception as exc:
        return _insert_job(provider, req, None, None, "failed", None, str(exc), {"error": str(exc)})

def _extract_openai_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str): return data["output_text"]
    parts: list[str] = []
    for item in data.get("output", []):
        if isinstance(item, dict):
            for content in item.get("content", []):
                if isinstance(content, dict) and isinstance(content.get("text"), str): parts.append(content["text"])
    return "\n".join(parts).strip()

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Video API Hub", version="0.1.0",
    description="Local-first dashboard for modular video API connectors and production workflows.", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

@app.get("/")
async def home() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": "Video API Hub", "version": "0.1.0"}

@app.get("/api/providers")
async def providers() -> dict[str, Any]:
    return {"providers": public_provider_list(),
            "notice": "Status hanya mengecek apakah env key tersedia; belum menguji saldo atau izin API."}

@app.get("/api/jobs")
async def recent_jobs() -> dict[str, Any]:
    return {"jobs": list_jobs()}

@app.post("/api/jobs")
async def create_jobs(req: JobRequest) -> dict[str, Any]:
    if not req.confirm_possible_cost:
        raise HTTPException(status_code=400, detail="Konfirmasi biaya/kuota diperlukan sebelum submit generasi.")
    if len(set(req.providers)) != len(req.providers):
        raise HTTPException(status_code=400, detail="Provider yang sama tidak boleh dipilih dua kali.")
    if req.mode == "image_to_video" and "runway" in req.providers and not req.image_url:
        raise HTTPException(status_code=400, detail="Runway image-to-video memerlukan URL gambar HTTPS.")
    if req.mode == "video_to_video" and "runway" in req.providers and not req.video_url:
        raise HTTPException(status_code=400, detail="Runway video-to-video memerlukan URL video HTTPS.")
    results = await asyncio.gather(*[_submit_one(provider, req) for provider in req.providers])
    return {"jobs": results}

@app.get("/api/jobs/{job_id}")
async def job_detail(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job tidak ditemukan.")
    if job["status"] not in {"completed", "failed"}:
        try: job = await _refresh_job(job)
        except Exception as exc: job["poll_error"] = str(exc)[:500]
    return {"job": job}

@app.post("/api/assist")
async def assist(req: AssistRequest) -> dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key: raise HTTPException(status_code=400, detail="OPENAI_API_KEY belum dikonfigurasi dalam .env server.")
    task_instructions = {
        "script": "Write an original short-video script with scenes, dialogue, timing and audio notes. Do not claim to generate video.",
        "prompt": "Turn the brief into a production-ready video prompt. Specify subject, action, camera, lighting, timing, visual continuity and avoid ambiguous multi-action instructions.",
        "shotlist": "Turn the brief into a structured shot list with shot_id, duration_seconds, visuals, camera, sound, asset needs and generation/edit suggestions.",
    }
    base, model = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/"), req.model or os.getenv("OPENAI_TEXT_MODEL", "gpt-5.4")
    async with httpx.AsyncClient(timeout=90.0, follow_redirects=False) as client:
        data = _json_response(await client.post(base + "/responses",
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json={"model": model, "instructions": task_instructions[req.task], "input": req.brief}))
    text = _extract_openai_text(data)
    if not text: raise HTTPException(status_code=502, detail="OpenAI API tidak mengembalikan teks yang dapat dibaca.")
    return {"text": text, "model": model}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8090, reload=True)
