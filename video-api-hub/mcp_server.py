"""Optional MCP stdio bridge to the Video API Hub.

Run the FastAPI web app separately. This process exposes approved Hub operations
as MCP tools; provider API keys remain in the Hub server's .env file.
"""
from __future__ import annotations

import json
import os
from typing import Any, Literal
from urllib.parse import quote, urlparse

import httpx
from mcp.server.fastmcp import FastMCP

HUB_URL = os.getenv("VIDEO_API_HUB_URL", "http://127.0.0.1:8090").rstrip("/")
parsed_hub = urlparse(HUB_URL)
if parsed_hub.scheme not in {"http", "https"} or not parsed_hub.hostname:
    raise RuntimeError("VIDEO_API_HUB_URL must be an HTTP(S) URL.")
mcp = FastMCP("Video API Hub")


def _hub_request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        response = httpx.request(method, HUB_URL + path, json=payload, timeout=30.0, follow_redirects=False)
        try:
            data = response.json()
        except ValueError:
            data = {"detail": response.text[:1000]}
        if response.is_error:
            detail = data.get("detail", data) if isinstance(data, dict) else data
            raise RuntimeError("Video API Hub returned HTTP " + str(response.status_code) + ": " +
                               json.dumps(detail, ensure_ascii=False)[:1200])
        if not isinstance(data, dict):
            raise RuntimeError("Video API Hub returned a non-object response.")
        return data
    except httpx.RequestError as exc:
        raise RuntimeError(
            "Cannot reach Video API Hub at " + HUB_URL +
            ". Start the FastAPI app first, and check VIDEO_API_HUB_URL."
        ) from exc


@mcp.tool()
def list_video_providers() -> dict[str, Any]:
    """List configured providers and capabilities without returning key values."""
    return _hub_request("GET", "/api/providers")


@mcp.tool()
def get_video_hub_health() -> dict[str, Any]:
    """Check whether the Video API Hub backend is running."""
    return _hub_request("GET", "/api/health")


@mcp.tool()
def create_video_job(
    providers: list[Literal["higgsfield", "runway", "fal"]],
    mode: Literal["text_to_video", "image_to_video", "video_to_video"],
    prompt: str,
    confirm_possible_cost: bool,
    model: str | None = None,
    duration: int = 5,
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9",
    resolution: Literal["480p", "720p", "1080p"] = "720p",
    image_url: str | None = None,
    video_url: str | None = None,
    generate_audio: bool = False,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Submit a video job to one or more providers through the Hub.

    IMPORTANT: this can spend API balance/credits. The calling agent must show
    the user the selected provider(s), model, mode and potential provider cost,
    then obtain the user's explicit approval before setting confirm_possible_cost
    to true. There is no free-generation guarantee. Input media must be hosted
    at HTTPS URLs the chosen provider is authorized to access.
    """
    if not confirm_possible_cost:
        raise ValueError("Generation not submitted. Obtain user approval for possible provider charges first.")
    if not providers:
        raise ValueError("Select at least one provider.")
    if mode == "image_to_video" and not image_url:
        raise ValueError("image_to_video requires an HTTPS image_url.")
    if mode == "video_to_video" and not video_url:
        raise ValueError("video_to_video requires an HTTPS video_url.")
    payload = {
        "providers": providers, "mode": mode, "prompt": prompt, "model": model,
        "duration": duration, "aspect_ratio": aspect_ratio, "resolution": resolution,
        "image_url": image_url, "video_url": video_url, "generate_audio": generate_audio,
        "options": options or {}, "confirm_possible_cost": True,
    }
    return _hub_request("POST", "/api/jobs", payload)


@mcp.tool()
def get_video_job_status(job_id: str) -> dict[str, Any]:
    """Get a submitted job's latest status and output link, when available."""
    if not job_id or len(job_id) > 100:
        raise ValueError("Invalid job_id.")
    return _hub_request("GET", "/api/jobs/" + quote(job_id, safe=""))


@mcp.tool()
def draft_video_script_or_prompt(
    task: Literal["script", "prompt", "shotlist"],
    brief: str,
    model: str | None = None,
) -> dict[str, str]:
    """Draft a script, video prompt, or shot list using the Hub OpenAI API bridge.

    Requires OPENAI_API_KEY on the Hub server. This is OpenAI API usage and
    billing, not a ChatGPT consumer-session/subscription bypass.
    """
    return _hub_request("POST", "/api/assist", {"task": task, "brief": brief, "model": model})


if __name__ == "__main__":
    # Standard input/output transport is suitable for local MCP hosts.
    # It does not create a public internet endpoint.
    mcp.run(transport="stdio")
