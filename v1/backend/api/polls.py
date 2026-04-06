"""여론조사 API"""
from fastapi import APIRouter
from data.poll_data import POLL_DATA, get_latest_poll, NATIONAL_POLL_TREND

router = APIRouter(prefix="/api/polls", tags=["polls"])


@router.get("")
def list_polls():
    return {"polls": POLL_DATA, "national_trend": NATIONAL_POLL_TREND}


@router.get("/latest")
def latest_poll():
    return get_latest_poll()
