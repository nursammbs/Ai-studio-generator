from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PLAN_LIMITS = {"free": 2 * 3600, "starter": 10 * 3600, "pro": 100 * 3600}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


class SaaSStore:
    """SQLite account, quota, event and processing-cost store for a single app instance."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.environ.get("CLIPPER_SAAS_DB", "data/clipper-platform.sqlite3"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    plan TEXT NOT NULL DEFAULT 'free',
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS usage_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    job_id TEXT NOT NULL,
                    source_seconds REAL NOT NULL,
                    cost_usd REAL NOT NULL,
                    created_at INTEGER NOT NULL,
                    UNIQUE(user_id, job_id)
                );
                CREATE INDEX IF NOT EXISTS usage_user_time ON usage_events(user_id, created_at);
                CREATE TABLE IF NOT EXISTS product_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    event_name TEXT NOT NULL,
                    properties_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                """
            )

    @staticmethod
    def _password_digest(password: str, salt: bytes) -> bytes:
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)

    def register(self, email: str, password: str) -> dict:
        email = email.strip().casefold()
        if not _EMAIL.fullmatch(email):
            raise ValueError("Enter a valid email address")
        if len(password) < 12:
            raise ValueError("Use a password with at least 12 characters")
        salt = secrets.token_bytes(16)
        user = {"id": uuid.uuid4().hex, "email": email, "plan": "free", "created_at": int(time.time())}
        with self._connect() as db:
            try:
                db.execute(
                    "INSERT INTO users(id,email,password_salt,password_hash,plan,created_at) VALUES(?,?,?,?,?,?)",
                    (user["id"], email, salt, self._password_digest(password, salt), "free", user["created_at"]),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("An account with that email already exists") from exc
        return user

    def authenticate(self, email: str, password: str) -> dict | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT id,email,password_salt,password_hash,plan,created_at FROM users WHERE email=?",
                (email.strip().casefold(),),
            ).fetchone()
        if row is None or not hmac.compare_digest(self._password_digest(password, row["password_salt"]), row["password_hash"]):
            return None
        return {key: row[key] for key in ("id", "email", "plan", "created_at")}

    @staticmethod
    def _secret() -> bytes:
        secret = os.environ.get("CLIPPER_SESSION_SECRET", "")
        if len(secret) < 32 or "CHANGE_ME" in secret:
            raise RuntimeError("Set CLIPPER_SESSION_SECRET to a random value of at least 32 characters")
        return secret.encode("utf-8")

    def issue_token(self, user: dict, ttl_seconds: int = 12 * 3600) -> str:
        payload = {"sub": user["id"], "exp": int(time.time()) + ttl_seconds}
        body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = _b64(hmac.new(self._secret(), body.encode("ascii"), hashlib.sha256).digest())
        return f"{body}.{signature}"

    def verify_token(self, token: str) -> dict | None:
        try:
            body, signature = token.split(".", 1)
            expected = _b64(hmac.new(self._secret(), body.encode("ascii"), hashlib.sha256).digest())
            if not hmac.compare_digest(signature, expected):
                return None
            payload = json.loads(_unb64(body))
            if int(payload["exp"]) <= int(time.time()):
                return None
        except (ValueError, KeyError, TypeError, RuntimeError, json.JSONDecodeError):
            return None
        with self._connect() as db:
            row = db.execute("SELECT id,email,plan,created_at FROM users WHERE id=?", (payload["sub"],)).fetchone()
        return {key: row[key] for key in ("id", "email", "plan", "created_at")} if row else None

    def monthly_usage(self, user_id: str) -> dict:
        now = datetime.now(timezone.utc)
        month_start = int(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
        with self._connect() as db:
            user = db.execute("SELECT plan FROM users WHERE id=?", (user_id,)).fetchone()
            if user is None:
                raise ValueError("Account was not found")
            usage = db.execute(
                "SELECT COALESCE(SUM(source_seconds),0) seconds, COALESCE(SUM(cost_usd),0) cost "
                "FROM usage_events WHERE user_id=? AND created_at>=?",
                (user_id, month_start),
            ).fetchone()
        limit = _PLAN_LIMITS.get(user["plan"], _PLAN_LIMITS["free"])
        return {
            "plan": user["plan"], "used_seconds": float(usage["seconds"]),
            "limit_seconds": limit, "remaining_seconds": max(0.0, limit - float(usage["seconds"])),
            "estimated_cost_usd": float(usage["cost"]),
        }

    def consume_usage(self, user_id: str, job_id: str, source_seconds: float) -> dict:
        if not job_id or not 0 < source_seconds <= 4 * 3600:
            raise ValueError("Usage reservation requires a job id and a source duration up to four hours")
        now = int(time.time())
        month_start = int(
            datetime.fromtimestamp(now, timezone.utc)
            .replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
        )
        cost_rate = max(0.0, float(os.environ.get("CLIPPER_COST_PER_SOURCE_HOUR_USD", "0")))
        estimated_cost = source_seconds / 3600 * cost_rate
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            user = db.execute("SELECT plan FROM users WHERE id=?", (user_id,)).fetchone()
            if user is None:
                db.rollback()
                raise ValueError("Account was not found")
            prior = db.execute(
                "SELECT source_seconds FROM usage_events WHERE user_id=? AND job_id=?", (user_id, job_id),
            ).fetchone()
            if prior:
                db.commit()
                return self.monthly_usage(user_id)
            used = db.execute(
                "SELECT COALESCE(SUM(source_seconds),0) FROM usage_events WHERE user_id=? AND created_at>=?",
                (user_id, month_start),
            ).fetchone()[0]
            limit = _PLAN_LIMITS.get(user["plan"], _PLAN_LIMITS["free"])
            if float(used) + source_seconds > limit:
                db.rollback()
                raise PermissionError("Monthly video-processing allowance exceeded")
            db.execute(
                "INSERT INTO usage_events(id,user_id,job_id,source_seconds,cost_usd,created_at) VALUES(?,?,?,?,?,?)",
                (uuid.uuid4().hex, user_id, job_id, source_seconds, estimated_cost, now),
            )
            db.commit()
        return self.monthly_usage(user_id)

    def record_event(self, user_id: str, event_name: str, properties: dict | None = None) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", event_name):
            raise ValueError("Event name is invalid")
        safe = {key: value for key, value in (properties or {}).items() if key in {"duration_seconds", "clip_count", "success"}}
        with self._connect() as db:
            db.execute(
                "INSERT INTO product_events(id,user_id,event_name,properties_json,created_at) VALUES(?,?,?,?,?)",
                (uuid.uuid4().hex, user_id, event_name, json.dumps(safe), int(time.time())),
            )

    def analytics_summary(self, user_id: str) -> dict:
        since = int(time.time()) - 30 * 24 * 3600
        with self._connect() as db:
            rows = db.execute(
                "SELECT event_name,COUNT(*) count FROM product_events "
                "WHERE user_id=? AND created_at>=? GROUP BY event_name ORDER BY count DESC",
                (user_id, since),
            ).fetchall()
        return {"window_days": 30, "events": {row["event_name"]: row["count"] for row in rows}}

    def set_plan(self, user_id: str, plan: str) -> None:
        if plan not in _PLAN_LIMITS:
            raise ValueError("Unknown subscription plan")
        with self._connect() as db:
            db.execute("UPDATE users SET plan=? WHERE id=?", (plan, user_id))
