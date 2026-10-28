#!/usr/bin/env python3
"""Upload an already-rendered MP4 to YouTube using OAuth 2.0.

Safe defaults: privacy=private; this script never uploads unless explicitly run.
Use --privacy unlisted or --privacy public only when you knowingly want that visibility.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any


YOUTUBE_UPLOAD_SCOPE = ["https://www.googleapis.com/auth/youtube.upload"]


def validate_metadata(title: str, description: str, tags: list[str]) -> tuple[str, str, list[str]]:
    title = " ".join(title.split()).strip()
    description = description.strip()
    tags = [tag.strip() for tag in tags if tag.strip()]
    if not title:
        raise ValueError("Judul video wajib diisi.")
    if len(title) > 100:
        raise ValueError("Judul YouTube maksimal 100 karakter.")
    if len(description) > 5000:
        raise ValueError("Deskripsi terlalu panjang (maksimal 5000 karakter).")
    if any(len(tag) > 100 for tag in tags):
        raise ValueError("Setiap tag maksimal 100 karakter.")
    return title, description, tags


def parse_tags(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def build_video_resource(title: str, description: str, tags: list[str],
                         privacy: str = "private", category_id: str = "1",
                         made_for_kids: bool | None = None) -> dict[str, Any]:
    title, description, tags = validate_metadata(title, description, tags)
    if privacy not in {"private", "unlisted", "public"}:
        raise ValueError("Privacy harus private, unlisted, atau public.")
    if not category_id.isdigit():
        raise ValueError("category_id harus angka.")
    status: dict[str, Any] = {"privacyStatus": privacy}
    if made_for_kids is not None:
        status["selfDeclaredMadeForKids"] = made_for_kids
    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": status,
    }


def _load_google_client(client_secrets: Path, token_file: Path):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Dependensi upload belum terpasang. Jalankan: pip install google-api-python-client google-auth-oauthlib"
        ) from exc

    credentials = None
    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), YOUTUBE_UPLOAD_SCOPE)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not client_secrets.exists():
                raise FileNotFoundError(
                    f"File OAuth tidak ditemukan: {client_secrets}. Buat OAuth Desktop app di Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), YOUTUBE_UPLOAD_SCOPE)
            credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(credentials.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=credentials, cache_discovery=False)


def upload_video(youtube, video_file: Path, resource: dict[str, Any], *,
                 max_retries: int = 5) -> dict[str, str]:
    """Resumable upload with exponential backoff for transient Google API errors."""
    try:
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise RuntimeError("google-api-python-client belum terpasang.") from exc

    if not video_file.exists() or not video_file.is_file():
        raise FileNotFoundError(f"Video tidak ditemukan: {video_file}")
    if video_file.suffix.lower() not in {".mp4", ".mov", ".m4v", ".webm"}:
        raise ValueError("Format video harus MP4, MOV, M4V, atau WebM.")
    if video_file.stat().st_size == 0:
        raise ValueError("File video kosong.")

    media = MediaFileUpload(str(video_file), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=resource, media_body=media)
    response = None
    retry = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"Upload: {int(status.progress() * 100)}%")
        except HttpError as exc:
            code = getattr(exc.resp, "status", None)
            if code not in {500, 502, 503, 504} or retry >= max_retries:
                raise
            retry += 1
            time.sleep(min(60, (2 ** retry) + random.random()))
    video_id = response.get("id")
    if not video_id:
        raise RuntimeError(f"Upload selesai tetapi respons tidak berisi video ID: {response}")
    return {"video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path, help="Video final MP4")
    parser.add_argument("--title", required=True, help="Judul video (maksimal 100 karakter)")
    parser.add_argument("--description", default="", help="Deskripsi video")
    parser.add_argument("--tags", default="", help="Tag dipisahkan koma")
    parser.add_argument("--category-id", default="1", help="1=Film & Animation")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private",
                        help="Default private agar tidak terpublikasi tanpa sengaja")
    parser.add_argument("--client-secrets", type=Path, default=Path("client_secrets.json"))
    parser.add_argument("--token-file", type=Path, default=Path(".youtube_token.json"))
    parser.add_argument("--made-for-kids", choices=["yes", "no"], default=None,
                        help="Nyatakan setting audiens dengan benar; jangan menebak.")
    parser.add_argument("--dry-run", action="store_true", help="Validasi metadata tanpa otorisasi/upload")
    args = parser.parse_args()

    resource = build_video_resource(
        args.title, args.description, parse_tags(args.tags), args.privacy, args.category_id,
        None if args.made_for_kids is None else args.made_for_kids == "yes",
    )
    if not args.file.exists() or not args.file.is_file():
        raise FileNotFoundError(f"Video tidak ditemukan: {args.file}")
    print(json.dumps({"file": str(args.file), "bytes": args.file.stat().st_size,
                      "resource": resource, "dry_run": args.dry_run}, indent=2, ensure_ascii=False))
    if args.dry_run:
        print("DRY RUN: tidak ada autentikasi atau upload dilakukan.")
        return 0

    if args.privacy == "public":
        confirm = input("Ketik PUBLISH-PUBLIC untuk konfirmasi unggah publik: ")
        if confirm != "PUBLISH-PUBLIC":
            print("Dibatalkan. Tidak ada video yang diunggah.")
            return 2

    youtube = _load_google_client(args.client_secrets, args.token_file)
    result = upload_video(youtube, args.file, resource)
    print(json.dumps(result, indent=2))
    print("Catatan: status pemrosesan YouTube dan visibilitas akhir tetap perlu diperiksa di YouTube Studio.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
