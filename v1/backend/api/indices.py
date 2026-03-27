"""지표 현황 API — enrichment snapshot에서 읽기"""
import json
from pathlib import Path
from fastapi import APIRouter
from v1config.settings import ENRICHMENT_PATH, INDEX_HISTORY_DIR, CANDIDATE, OPPONENT

router = APIRouter(prefix="/api/indices", tags=["indices"])


def _load_enrichment() -> dict:
    try:
        with open(ENRICHMENT_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _load_index_history() -> list:
    """index_history/*.json 파일들을 날짜순으로 로드"""
    history = []
    if not INDEX_HISTORY_DIR.exists():
        return history
    for fp in sorted(INDEX_HISTORY_DIR.glob("snapshot_*.json")):
        try:
            with open(fp) as f:
                history.append(json.load(f))
        except Exception:
            pass
    return history


@router.get("/current")
def current_indices():
    snap = _load_enrichment()
    buzz = snap.get("candidate_buzz", {})

    # 이슈지수: 클러스터 기반 (AI가 사건별 진영 판단 → 우리/상대 건수) 우선
    cluster_issue = snap.get("cluster_issue", {})
    kim_buzz = {k: v for k, v in buzz.items() if CANDIDATE in k}
    park_buzz = {k: v for k, v in buzz.items() if OPPONENT in k}
    if cluster_issue.get("total", 0) > 0:
        kim_mentions = cluster_issue["kim_count"]
        park_mentions = cluster_issue["park_count"]
    else:
        # 폴백: candidate_buzz 중복할인
        kim_sorted = sorted(kim_buzz.values(), key=lambda v: v.get("mention_count", 0), reverse=True)
        park_sorted = sorted(park_buzz.values(), key=lambda v: v.get("mention_count", 0), reverse=True)
        kim_mentions = sum(v.get("mention_count", 0) if i == 0 else int(v.get("mention_count", 0) * 0.5) for i, v in enumerate(kim_sorted))
        park_mentions = sum(v.get("mention_count", 0) if i == 0 else int(v.get("mention_count", 0) * 0.5) for i, v in enumerate(park_sorted))

    # 반응지수: 50pt 스케일 (cluster_reaction에서)
    cluster_rx = snap.get("cluster_reaction", {})
    reaction_index = cluster_rx.get("reaction_index", 50.0)

    # 판세지수: correction에서
    corr = snap.get("turnout", {}).get("correction", {})

    # 타임스탬프: enrichment 갱신 시점
    enrichment_ts = snap.get("timestamp", "")
    # 판세지수는 turnout 계산 시점
    turnout_ts = snap.get("turnout", {}).get("computed_at", enrichment_ts)
    # 뉴스 클러스터 시점
    cluster_ts = snap.get("news_clusters_timestamp", enrichment_ts)
    # collector별 타임스탬프
    src_ts = snap.get("source_timestamps", {})

    return {
        "issue": {
            "index": cluster_issue.get("issue_index", 50),
            "kim": {"mentions": kim_mentions, "score": cluster_issue.get("kim_score", 0), "keywords": len(kim_buzz)},
            "park": {"mentions": park_mentions, "score": cluster_issue.get("park_score", 0), "keywords": len(park_buzz)},
            "gap": round(cluster_issue.get("issue_index", 50) - 50, 1),
            "grade": "우세" if cluster_issue.get("issue_index", 50) > 55 else "열세" if cluster_issue.get("issue_index", 50) < 45 else "접전",
            "updated_at": enrichment_ts,
            "sources": {
                "news_updated_at": src_ts.get("news_updated_at"),
            },
        },
        "reaction": {
            "index": reaction_index,
            "gap": round(reaction_index - 50, 1),
            "grade": "우세" if reaction_index > 55 else "열세" if reaction_index < 45 else "접전",
            "updated_at": cluster_rx.get("updated_at", enrichment_ts),
            "total_mentions": cluster_rx.get("total_mentions", 0),
            "sources_collected": cluster_rx.get("sources_collected", []),
            "keywords_analyzed": cluster_rx.get("keywords_analyzed", 0),
        },
        "pandse": {
            "index": corr.get("pandse_index", 50),
            "gap": corr.get("pandse_gap", 0),
            "grade": "우세" if corr.get("pandse_index", 50) > 55 else "열세" if corr.get("pandse_index", 50) < 45 else "접전",
            "factors_count": len(corr.get("factors", [])),
            "d_day": corr.get("d_day", 0),
            "updated_at": turnout_ts,
            "sources": {
                "issue_updated_at": enrichment_ts,
                "reaction_updated_at": enrichment_ts,
                "poll_updated_at": src_ts.get("news_updated_at"),
                "national_poll_updated_at": src_ts.get("national_poll_updated_at"),
                "economic_updated_at": src_ts.get("economic_updated_at"),
                "pandse_updated_at": src_ts.get("pandse_updated_at"),
            },
        },
        "cluster_updated_at": cluster_ts,
        "issue_alert": snap.get("issue_alert"),
        "reaction_alert": snap.get("reaction_alert"),
        "pandse_alert": snap.get("pandse_alert"),
        "ai_issue_summary": snap.get("ai_issue_summary", ""),
        "ai_reaction_summary": snap.get("ai_reaction_summary", ""),
    }


@router.get("/history")
def index_history():
    # 후보별 지표 히스토리 (indices_history.json)
    hist_path = ENRICHMENT_PATH.parent / "indices_history.json"
    candidate_history = []
    try:
        with open(hist_path) as f:
            candidate_history = json.load(f)
    except Exception:
        pass

    # 일일 스냅샷 (기존)
    daily = _load_index_history()

    return {
        "trend": [
            {
                "date": h.get("date", ""),
                "issue_avg": h.get("issue_index_avg", 0),
                "reaction_avg": h.get("reaction_index_avg", 0),
                "leading_index": h.get("leading_index", 50),
                "poll_kim": h.get("poll_actual_kim", 0),
                "poll_park": h.get("poll_actual_park", 0),
            }
            for h in daily
        ],
        "candidate_trend": candidate_history[-168:],  # 최근 168건 (7일 × 24시간)
        "days": len(daily),
    }
