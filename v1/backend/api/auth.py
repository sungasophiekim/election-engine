"""인증 API — 티어 기반 접근 제어"""
import hashlib
import secrets
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 계정 목록: tier 0 = 상황실만, tier 1 = 상황실 + 시스템
USERS = {
    "warroom": {
        "password_hash": hashlib.sha256("election2026!".encode()).hexdigest(),
        "tier": 0,
        "label": "상황실 운영",
    },
    "admin": {
        "password_hash": hashlib.sha256("admin2026!".encode()).hexdigest(),
        "tier": 1,
        "label": "시스템 관리자",
    },
}

# 세션 저장소 (메모리)
_sessions: dict[str, dict] = {}


class LoginReq(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginReq):
    user = USERS.get(req.username)
    if not user:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    pw_hash = hashlib.sha256(req.password.encode()).hexdigest()
    if pw_hash != user["password_hash"]:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    token = secrets.token_hex(32)
    _sessions[token] = {
        "username": req.username,
        "tier": user["tier"],
        "label": user["label"],
        "created_at": time.time(),
    }

    return {
        "token": token,
        "username": req.username,
        "tier": user["tier"],
        "label": user["label"],
    }


@router.get("/me")
def me(token: str = ""):
    session = _sessions.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    return {
        "username": session["username"],
        "tier": session["tier"],
        "label": session["label"],
    }


@router.post("/logout")
def logout(token: str = ""):
    _sessions.pop(token, None)
    return {"ok": True}
