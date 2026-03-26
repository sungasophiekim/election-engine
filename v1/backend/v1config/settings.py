"""V1 설정"""
import os
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # election_engine/
LEGACY_DATA = PROJECT_ROOT / "data"
ENRICHMENT_PATH = LEGACY_DATA / "enrichment_snapshot.json"
INDEX_HISTORY_DIR = LEGACY_DATA / "index_history"

# 디렉토리 자동 생성
os.makedirs(LEGACY_DATA, exist_ok=True)
os.makedirs(INDEX_HISTORY_DIR, exist_ok=True)

CANDIDATE = "김경수"
OPPONENT = "박완수"
ELECTION_DAY = "2026-06-03"
