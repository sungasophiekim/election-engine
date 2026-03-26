"""V1 설정"""
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # election_engine/
LEGACY_DATA = PROJECT_ROOT / "data"  # 원본 데이터 (legacy가 아닌 실제 경로)
ENRICHMENT_PATH = LEGACY_DATA / "enrichment_snapshot.json"
INDEX_HISTORY_DIR = LEGACY_DATA / "index_history"

CANDIDATE = "김경수"
OPPONENT = "박완수"
ELECTION_DAY = "2026-06-03"
