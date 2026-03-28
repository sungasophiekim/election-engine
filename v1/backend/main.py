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
from api.strategy import router as strategy_router

app = FastAPI(title="Election Engine v1", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(polls_router)
app.include_router(prediction_router)
app.include_router(indices_router)
app.include_router(enrichment_router)
app.include_router(strategy_router)


@app.on_event("startup")
def on_startup():
    from scheduler import start_scheduler
    start_scheduler()
    try:
        from telegram_bot import start_telegram_bot
        start_telegram_bot()
    except Exception as e:
        print(f"[텔레그램] 봇 시작 실패: {e}", flush=True)


@app.post("/api/admin/collect-now")
def trigger_collect():
    """수동 데이터 수집 트리거"""
    import threading
    from scheduler import _update_all
    threading.Thread(target=_update_all, daemon=True).start()
    return {"status": "수집 시작됨"}


@app.post("/api/admin/reset-history")
def reset_history():
    """히스토리 초기화 — 잘못된 데이터 리셋"""
    import json
    from v1config.settings import LEGACY_DATA
    hist_path = LEGACY_DATA / "indices_history.json"
    with open(hist_path, "w") as f:
        json.dump([], f)
    return {"status": "히스토리 초기화 완료"}


@app.post("/api/admin/fix-side")
def fix_cluster_side(issue: str = "", side: str = "중립"):
    """클러스터 진영 즉시 수정"""
    import json
    from v1config.settings import ENRICHMENT_PATH
    try:
        with open(ENRICHMENT_PATH) as f:
            snap = json.load(f)
        fixed = False
        for c in snap.get("news_clusters", []):
            if issue in c.get("name", ""):
                c["side"] = side
                fixed = True
        if fixed:
            with open(ENRICHMENT_PATH, "w") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2, default=str)
            return {"status": f"'{issue}' → {side} 수정 완료"}
        return {"error": f"'{issue}' 클러스터를 찾을 수 없음"}
    except Exception as e:
        return {"error": str(e)}


# ── Next.js 정적 빌드 서빙 (Render 배포용) ──
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_FRONTEND_OUT = Path(__file__).resolve().parent.parent / "frontend" / "out"

if _FRONTEND_OUT.exists():
    # Next.js static export의 _next 에셋
    _next_dir = _FRONTEND_OUT / "_next"
    if _next_dir.exists():
        app.mount("/_next", StaticFiles(directory=str(_next_dir)), name="next-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Next.js static export fallback. /api/* 는 무시."""
        if full_path.startswith("api/"):
            return {"error": "not found"}
        file_path = _FRONTEND_OUT / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        # SPA fallback → index.html
        index = _FRONTEND_OUT / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"error": "not found"}
else:
    @app.get("/")
    def root():
        return {"service": "Election Engine v1", "status": "ok"}
