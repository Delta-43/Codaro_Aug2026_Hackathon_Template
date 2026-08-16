"""Demo controls — the vertical switch + reset behind the Account page.

`GET /demo/vertical` is public (the app reads it at boot); switching/resetting
is destructive (it wipes and reseeds all catalog + booking data), so it requires
an authenticated user. Not part of the core booking domain — purely the demo's
pivot switch, backed by `seed.seed_vertical`.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

import seed
from app.auth import AuthUser, require_user
from app.errors import INVALID_RANGE, api_error

router = APIRouter(prefix="/demo", tags=["demo"])


class VerticalReq(BaseModel):
    id: str


@router.get("/vertical")
def get_vertical():
    return {"verticalId": seed.active_vertical()}


@router.post("/vertical")
def set_vertical(payload: VerticalReq, _user: AuthUser = Depends(require_user)):
    if payload.id not in seed.VERTICALS:
        raise api_error(INVALID_RANGE, f"Unknown vertical '{payload.id}'.")
    seed.seed_vertical(payload.id)
    return {"verticalId": payload.id}


@router.post("/reset")
def reset(_user: AuthUser = Depends(require_user)):
    vid = seed.active_vertical()
    seed.seed_vertical(vid)
    return {"verticalId": vid}
