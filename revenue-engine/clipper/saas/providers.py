from __future__ import annotations

import os
import uuid
from datetime import timedelta


class StripeBilling:
    """Optional Stripe Checkout and signed-webhook adapter."""

    def __init__(self):
        try:
            import stripe
        except ImportError as exc:
            raise RuntimeError("Install requirements-saas.txt to enable subscription billing") from exc
        key = os.environ.get("STRIPE_SECRET_KEY")
        if not key:
            raise RuntimeError("Set STRIPE_SECRET_KEY before enabling billing")
        self.stripe = stripe
        self.stripe.api_key = key

    def checkout_url(self, user: dict, plan: str) -> str:
        price_id = os.environ.get(f"STRIPE_PRICE_{plan.upper()}")
        success_url = os.environ.get("STRIPE_SUCCESS_URL")
        cancel_url = os.environ.get("STRIPE_CANCEL_URL")
        if not price_id or not success_url or not cancel_url:
            raise RuntimeError("Set the Stripe price ID and success/cancel URLs")
        session = self.stripe.checkout.Session.create(
            mode="subscription", customer_email=user["email"],
            client_reference_id=user["id"],
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"user_id": user["id"], "plan": plan},
            subscription_data={"metadata": {"user_id": user["id"], "plan": plan}},
            subscription_data={"metadata": {"user_id": user["id"], "plan": plan}},
            success_url=success_url, cancel_url=cancel_url,
            idempotency_key=f"{user['id']}:{plan}:{uuid.uuid4().hex}",
        )
        return session.url

    def verify_webhook(self, payload: bytes, signature: str):
        secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
        if not secret:
            raise RuntimeError("Set STRIPE_WEBHOOK_SECRET before accepting billing webhooks")
        return self.stripe.Webhook.construct_event(payload, signature, secret)


class S3MediaStore:
    """Private S3-compatible storage adapter; uses server-side encryption and short-lived links."""

    def __init__(self):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install requirements-saas.txt to enable object storage") from exc
        self.bucket = os.environ.get("CLIPPER_S3_BUCKET")
        if not self.bucket:
            raise RuntimeError("Set CLIPPER_S3_BUCKET before enabling cloud storage")
        self.client = boto3.client(
            "s3", region_name=os.environ.get("AWS_REGION"),
            endpoint_url=os.environ.get("CLIPPER_S3_ENDPOINT_URL") or None,
        )

    def upload(self, owner_id: str, source: str, filename: str) -> str:
        safe_name = filename.replace("/", "_").replace("\\", "_")[:120]
        key = f"users/{owner_id}/media/{uuid.uuid4().hex}/{safe_name}"
        self.client.upload_file(
            source, self.bucket, key,
            ExtraArgs={"ServerSideEncryption": "AES256", "ContentType": "application/octet-stream"},
        )
        return key

    def upload_url(self, owner_id: str, filename: str, content_type: str = "application/octet-stream") -> dict:
        safe_name = filename.replace("/", "_").replace("\\", "_")[:120]
        key = f"users/{owner_id}/media/{uuid.uuid4().hex}/{safe_name}"
        url = self.client.generate_presigned_url(
            "put_object", Params={"Bucket": self.bucket, "Key": key, "ServerSideEncryption": "AES256", "ContentType": content_type},
            ExpiresIn=600,
        )
        return {"key": key, "upload_url": url, "expires_in": 600}

    def upload_url(self, owner_id: str, filename: str, content_type: str = "application/octet-stream") -> dict:
        safe_name = filename.replace("/", "_").replace("\\", "_")[:120]
        key = f"users/{owner_id}/media/{uuid.uuid4().hex}/{safe_name}"
        url = self.client.generate_presigned_url(
            "put_object", Params={"Bucket": self.bucket, "Key": key, "ServerSideEncryption": "AES256", "ContentType": content_type},
            ExpiresIn=600,
        )
        return {"key": key, "upload_url": url, "expires_in": 600}

    def download_url(self, key: str, expires_seconds: int = 600) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=min(max(expires_seconds, 60), int(timedelta(hours=1).total_seconds())),
        )
