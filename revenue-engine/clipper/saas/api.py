from __future__ import annotations

import os
import hmac

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from starlette.responses import Response

from saas.accounting import SaaSStore
from saas.providers import S3MediaStore, StripeBilling


REQUESTS = Counter("clipper_api_requests_total", "API requests", ["method", "route", "status"])
AUTH = HTTPBearer(auto_error=False)
store = SaaSStore()
app = FastAPI(title="Revenue Engine API", version="0.1.0")


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)


class UsageReservation(BaseModel):
    job_id: str = Field(min_length=1, max_length=128)
    source_seconds: float = Field(gt=0, le=4 * 3600)


class CheckoutRequest(BaseModel):
    plan: str = Field(pattern="^(starter|pro)$")


class UploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content_type: str = Field(default="application/octet-stream", max_length=120)


class ProductEvent(BaseModel):
    properties: dict = Field(default_factory=dict)


@app.middleware("http")
async def count_requests(request: Request, call_next):
    response = await call_next(request)
    route = request.scope.get("route")
    route_name = getattr(route, "path", "unmatched")
    REQUESTS.labels(request.method, route_name, str(response.status_code)).inc()
    return response


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(AUTH)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Bearer token required")
    user = store.verify_token(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Session is invalid or expired")
    return user


@app.get("/health")
def health():
    return {"status": "ok", "service": "revenue-engine-api"}


@app.post("/v1/auth/register")
def register(payload: Credentials):
    try:
        user = store.register(payload.email, payload.password)
        return {"user": user, "access_token": store.issue_token(user), "token_type": "bearer"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/auth/login")
def login(payload: Credentials):
    user = store.authenticate(payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    return {"user": user, "access_token": store.issue_token(user), "token_type": "bearer"}


@app.get("/v1/me")
def me(user: dict = Depends(current_user)):
    return user


@app.get("/v1/usage")
def usage(user: dict = Depends(current_user)):
    return store.monthly_usage(user["id"])


@app.get("/v1/analytics/summary")
def analytics_summary(user: dict = Depends(current_user)):
    return store.analytics_summary(user["id"])


@app.post("/v1/usage/reservations")
def reserve_usage(payload: UsageReservation, user: dict = Depends(current_user)):
    try:
        return store.consume_usage(user["id"], payload.job_id, payload.source_seconds)
    except PermissionError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/billing/checkout")
def checkout(payload: CheckoutRequest, user: dict = Depends(current_user)):
    try:
        return {"checkout_url": StripeBilling().checkout_url(user, payload.plan)}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/billing/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(default="")):
    try:
        event = StripeBilling().verify_webhook(await request.body(), stripe_signature)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid billing webhook") from exc
    payload = event["data"]["object"]
    if event["type"] == "checkout.session.completed":
        user_id = payload.get("metadata", {}).get("user_id")
        plan = payload.get("metadata", {}).get("plan")
        if user_id and plan in {"starter", "pro"}:
            store.set_plan(user_id, plan)
    elif event["type"] in {"customer.subscription.deleted", "customer.subscription.paused"}:
        user_id = payload.get("metadata", {}).get("user_id")
        if user_id:
            store.set_plan(user_id, "free")
    return {"received": True}


@app.post("/v1/storage/upload-url")
def storage_upload_url(payload: UploadUrlRequest, user: dict = Depends(current_user)):
    try:
        return S3MediaStore().upload_url(user["id"], payload.filename, payload.content_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/events/{event_name}")
def record_event(event_name: str, payload: ProductEvent, user: dict = Depends(current_user)):
    try:
        store.record_event(user["id"], event_name, payload.properties)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"recorded": True}


@app.get("/metrics")
def metrics(metrics_token: str = Header(default="", alias="X-Metrics-Token")):
    expected = os.environ.get("CLIPPER_METRICS_TOKEN", "")
    if not expected or not hmac.compare_digest(metrics_token, expected):
        raise HTTPException(status_code=401, detail="Metrics access is restricted")
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
