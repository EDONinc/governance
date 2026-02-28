from fastapi import APIRouter, Request, HTTPException
from typing import Dict
import secrets
import hashlib

from ..persistence import get_db
from ..config import config
from ..tenancy import get_request_tenant_id

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/status")
async def billing_status(request: Request):
    """
    Return billing status for the current tenant.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        if not config.DEMO_MODE:
            raise HTTPException(
                status_code=401,
                detail="No tenant context for billing status"
            )
        tenant_id = config.DEMO_TENANT_ID

    db = get_db()
    tenant = db.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    from .plans import get_plan_limits
    limits = get_plan_limits(tenant["plan"])
    usage_today = db.get_tenant_usage(tenant_id)

    return {
        "tenant_id": tenant_id,
        "status": tenant["status"],
        "plan": tenant["plan"],
        "usage": {
            "today": usage_today
        },
        "limits": {
            "requests_per_month": limits.requests_per_month,
            "requests_per_day": limits.requests_per_day,
            "requests_per_minute": limits.requests_per_minute
        }
    }


@router.post("/api-keys")
async def create_api_key(request: Request, body: Dict = None):
    """Create a new API key for the authenticated tenant."""
    tenant_id = get_request_tenant_id(request)

    if not tenant_id:
        if not config.DEMO_MODE:
            raise HTTPException(status_code=401, detail="Authentication required")
        tenant_id = config.DEMO_TENANT_ID

    name = (body or {}).get("name") or "API Key"

    raw_key = secrets.token_hex(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    db = get_db()
    api_key = db.create_api_key(
        tenant_id=tenant_id,
        name=name,
        key_hash=key_hash,
    )

    return {
        "api_key": raw_key,
        "api_key_id": api_key["id"],
        "tenant_id": tenant_id,
        "warning": "Store this key now. It will not be shown again.",
    }


@router.delete("/api-keys/{key_id}")
async def delete_api_key(request: Request, key_id: str):
    """Delete an API key owned by the authenticated tenant."""
    tenant_id = get_request_tenant_id(request)

    if not tenant_id:
        if not config.DEMO_MODE:
            raise HTTPException(status_code=401, detail="Authentication required")
        tenant_id = config.DEMO_TENANT_ID

    db = get_db()
    keys = db.list_api_keys(tenant_id)
    if not any(str(k.get("id")) == str(key_id) for k in keys):
        raise HTTPException(status_code=404, detail="API key not found")

    deleted = db.delete_api_key(key_id, tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="API key not found")

    return {"deleted": True, "key_id": key_id}


@router.get("/api-keys")
async def list_api_keys(request: Request):
    """
    List API keys for the current tenant.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        if not config.DEMO_MODE:
            raise HTTPException(
                status_code=401,
                detail="No tenant context for API keys"
            )
        tenant_id = config.DEMO_TENANT_ID

    db = get_db()
    keys = db.list_api_keys(tenant_id)
    return {
        "keys": keys,
        "total": len(keys),
    }
