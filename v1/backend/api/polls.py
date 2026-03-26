"""여론조사 API"""
from fastapi import APIRouter
from data.poll_data import POLL_DATA, get_latest_poll

router = APIRouter(prefix="/api/polls", tags=["polls"])


@router.get("")
def list_polls():
    return {"polls": POLL_DATA}


@router.get("/latest")
def latest_poll():
    return get_latest_poll()
