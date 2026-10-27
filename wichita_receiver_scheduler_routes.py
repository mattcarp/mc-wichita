"""Read-only API surface for the receiver scheduler (flag-gated)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from wichita_receiver_scheduler import (
    build_plan_from_env,
    default_config_path,
    plan_to_public_dict,
    scheduler_enabled,
)

router = APIRouter(prefix="/api/receiver-scheduler", tags=["receiver-scheduler"])


@router.get("/health")
def receiver_scheduler_health():
    return {
        "enabled": scheduler_enabled(),
        "receive_only": True,
        "config_path": str(default_config_path()),
    }


@router.get("/plan")
def receiver_scheduler_plan():
    if not scheduler_enabled():
        raise HTTPException(status_code=404, detail="receiver scheduler disabled")
    plan = build_plan_from_env()
    if plan is None:
        raise HTTPException(status_code=503, detail="scheduler enabled but plan unavailable")
    return plan_to_public_dict(plan)
