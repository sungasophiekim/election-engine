"""Election Engine v1 — Backend"""
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Legacy 엔진 import 경로 설정
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # election_engine/
sys.path.insert(0, str(PROJECT_ROOT))  # engines/, config/ 등 import 가능
sys.path.insert(0, str(Path(__file__).resolve().parent))  # v1/backend (data/, api/ 등)
print(f"[v1] PROJECT_ROOT: {PROJECT_ROOT}")
print(f"[v1] sys.path[0]: {sys.path[0]}")

from api.auth import router as auth_router
from api.polls import router as polls_router
from api.prediction import router as prediction_router
from api.indices import router as indices_router
from api.enrichment import router as enrichment_router

app = FastAPI(title="Election Engine v1", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(polls_router)
app.include_router(prediction_router)
app.include_router(indices_router)
app.include_router(enrichment_router)


@app.on_event("startup")
def on_startup():
    from scheduler import start_scheduler
    start_scheduler()


@app.get("/")
def root():
    return {"service": "Election Engine v1", "status": "ok"}
