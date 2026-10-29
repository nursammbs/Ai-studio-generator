from __future__ import annotations

import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / "video_api_hub_test_jobs.sqlite3"
os.environ["VIDEO_API_HUB_DB"] = str(TEST_DB)
for name in ("HIGGSFIELD_API_KEY", "RUNWAY_API_KEY", "FAL_KEY", "OPENAI_API_KEY"):
    os.environ.pop(name, None)

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
import app as hub


def test_health_and_provider_list_do_not_leak_secrets() -> None:
    with TestClient(hub.app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        providers = client.get("/api/providers")
        assert providers.status_code == 200
        data = providers.json()
        assert {row["id"] for row in data["providers"]} >= {"higgsfield", "runway", "fal", "openai"}
        assert all("api_key" not in row and "secret" not in row for row in data["providers"])


def test_video_generation_requires_cost_confirmation() -> None:
    with TestClient(hub.app) as client:
        response = client.post("/api/jobs", json={
            "providers": ["runway"], "mode": "text_to_video",
            "prompt": "A small orange cat runs past a tree.", "confirm_possible_cost": False
        })
        assert response.status_code == 400
        assert "Konfirmasi biaya" in response.json()["detail"]


def test_arbitrary_provider_or_http_image_url_is_rejected() -> None:
    with TestClient(hub.app) as client:
        bad_provider = client.post("/api/jobs", json={
            "providers": ["attacker"], "prompt": "A cat", "confirm_possible_cost": True
        })
        assert bad_provider.status_code == 422
        bad_url = client.post("/api/jobs", json={
            "providers": ["runway"], "mode": "image_to_video",
            "prompt": "Animate this character", "image_url": "http://127.0.0.1/private.png",
            "confirm_possible_cost": True
        })
        assert bad_url.status_code == 422


def test_missing_provider_key_fails_visibly() -> None:
    with TestClient(hub.app) as client:
        response = client.post("/api/jobs", json={
            "providers": ["runway"], "mode": "text_to_video",
            "prompt": "A cat runs across a quiet garden.", "confirm_possible_cost": True
        })
        assert response.status_code == 200
        jobs = response.json()["jobs"]
        assert len(jobs) == 1
        assert jobs[0]["status"] == "failed"
        assert "belum dikonfigurasi" in jobs[0]["error"]
