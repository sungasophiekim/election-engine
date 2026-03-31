"""V1 설정"""
import os
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # election_engine/
# Render Persistent Disk (/data) 우선, 없으면 프로젝트 내 data/
_RENDER_DISK = Path("/data")
LEGACY_DATA = _RENDER_DISK if _RENDER_DISK.exists() and os.environ.get("RENDER") else PROJECT_ROOT / "data"
ENRICHMENT_PATH = LEGACY_DATA / "enrichment_snapshot.json"
INDEX_HISTORY_DIR = LEGACY_DATA / "index_history"

# 디렉토리 자동 생성
os.makedirs(LEGACY_DATA, exist_ok=True)
os.makedirs(INDEX_HISTORY_DIR, exist_ok=True)
os.makedirs(LEGACY_DATA / "daily_reports", exist_ok=True)
os.makedirs(LEGACY_DATA / "training_data", exist_ok=True)

# Render 첫 배포 시: git의 기존 data → Persistent Disk로 복사
if LEGACY_DATA == _RENDER_DISK and os.environ.get("RENDER"):
    _git_data = PROJECT_ROOT / "data"
    if _git_data.exists():
        import shutil
        for src in _git_data.rglob("*"):
            if src.is_file():
                dst = LEGACY_DATA / src.relative_to(_git_data)
                if not dst.exists():
                    os.makedirs(dst.parent, exist_ok=True)
                    shutil.copy2(src, dst)

CANDIDATE = "김경수"
OPPONENT = "박완수"
ELECTION_DAY = "2026-06-03"
