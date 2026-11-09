from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core import save_json_atomic


_JOB_ID = re.compile(r"^[a-f0-9]{12}$")
_SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStore:
    """Small filesystem-backed job store for the single-user local MVP."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _job_dir(self, job_id: str) -> Path:
        if not _JOB_ID.fullmatch(job_id):
            raise ValueError("Invalid job id")
        target = (self.root / job_id).resolve()
        if target.parent != self.root:
            raise ValueError("Job path escapes the storage root")
        return target

    def create(self, source_name: str, source_path: str | Path, owner_id: str = "local") -> dict:
        job_id = uuid.uuid4().hex[:12]
        directory = self._job_dir(job_id)
        directory.mkdir(parents=True, exist_ok=False)
        timestamp = utc_now()
        job = {
            "schema_version": _SCHEMA_VERSION,
            "id": job_id,
            "created_at": timestamp,
            "updated_at": timestamp,
            "status": "created",
            "stage": "upload",
            "source_name": source_name,
            "owner_id": owner_id,
            "source_path": str(Path(source_path).resolve()),
            "media": None,
            "model_size": "base",
            "words": None,
            "candidates": [],
            "selected_clips": None,
            "rendered": [],
            "metrics": {},
            "error": None,
        }
        self.save(job)
        return job

    def save(self, job: dict) -> Path:
        job_id = str(job.get("id", ""))
        directory = self._job_dir(job_id)
        if not directory.is_dir():
            raise FileNotFoundError(f"Unknown job: {job_id}")
        if job.get("schema_version") != _SCHEMA_VERSION:
            raise ValueError("Unsupported job manifest version")
        updated = dict(job)
        updated["updated_at"] = utc_now()
        return save_json_atomic(updated, directory / "job.json")

    def load(self, job_id: str, owner_id: str | None = None) -> dict:
        manifest = self._job_dir(job_id) / "job.json"
        if not manifest.is_file():
            raise FileNotFoundError(f"Saved job not found: {job_id}")
        job = json.loads(manifest.read_text(encoding="utf-8"))
        if job.get("id") != job_id or job.get("schema_version") != _SCHEMA_VERSION:
            raise ValueError("Saved job manifest is invalid or unsupported")
        if owner_id is not None and job.get("owner_id", "local") != owner_id:
            raise PermissionError("This job belongs to another account")
        return job

    def list(self, limit: int = 30, owner_id: str | None = None) -> list[dict]:
        if limit < 0:
            raise ValueError("Job limit must not be negative")
        jobs: list[dict] = []
        for path in self.root.glob("*/job.json"):
            try:
                job = self.load(path.parent.name)
                if owner_id is None or job.get("owner_id", "local") == owner_id:
                    jobs.append(job)
            except (OSError, ValueError, TypeError):
                continue
        jobs.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return jobs[:limit]
