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

    # 이슈지수: 후보별 언급량 비교
    kim_buzz = {k: v for k, v in buzz.items() if CANDIDATE in k}
    park_buzz = {k: v for k, v in buzz.items() if OPPONENT in k}
    kim_mentions = sum(v.get("mention_count", 0) for v in kim_buzz.values())
    park_mentions = sum(v.get("mention_count", 0) for v in park_buzz.values())

    # 반응지수: 후보별 감성 비교
    kim_sents = [v.get("ai_sentiment", {}).get("net_sentiment", 0) for v in kim_buzz.values()]
    park_sents = [v.get("ai_sentiment", {}).get("net_sentiment", 0) for v in park_buzz.values()]
    kim_sent_avg = sum(kim_sents) / len(kim_sents) if kim_sents else 0
    park_sent_avg = sum(park_sents) / len(park_sents) if park_sents else 0

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
            "kim": {"mentions": kim_mentions, "keywords": len(kim_buzz)},
            "park": {"mentions": park_mentions, "keywords": len(park_buzz)},
            "gap": kim_mentions - park_mentions,
            "grade": "우세" if kim_mentions - park_mentions > 20 else "열세" if kim_mentions - park_mentions < -20 else "접전",
            "updated_at": enrichment_ts,
            "sources": {
                "news_updated_at": src_ts.get("news_updated_at"),
                "blog_updated_at": src_ts.get("blog_updated_at"),
                "cafe_updated_at": src_ts.get("cafe_updated_at"),
                "youtube_updated_at": src_ts.get("youtube_updated_at"),
                "trends_updated_at": src_ts.get("trends_updated_at"),
                "community_updated_at": src_ts.get("community_updated_at"),
                "datalab_updated_at": src_ts.get("datalab_updated_at"),
            },
        },
        "reaction": {
            "kim": {"sentiment": round(kim_sent_avg, 3), "pct": round(kim_sent_avg * 100), "keywords": len(kim_buzz)},
            "park": {"sentiment": round(park_sent_avg, 3), "pct": round(park_sent_avg * 100), "keywords": len(park_buzz)},
            "gap": round((kim_sent_avg - park_sent_avg) * 100),
            "grade": "우세" if (kim_sent_avg - park_sent_avg) * 100 > 15 else "열세" if (kim_sent_avg - park_sent_avg) * 100 < -15 else "접전",
            "updated_at": enrichment_ts,
            "sources": {
                "community_updated_at": src_ts.get("community_updated_at"),
                "social_updated_at": src_ts.get("blog_updated_at"),
                "youtube_updated_at": src_ts.get("youtube_updated_at"),
                "comments_updated_at": src_ts.get("news_updated_at"),
                "trends_updated_at": src_ts.get("trends_updated_at"),
                "sentiment_updated_at": src_ts.get("sentiment_updated_at"),
            },
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
        "pandse_alert": snap.get("pandse_alert"),
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
        "candidate_trend": candidate_history[-48:],  # 최근 48건 (8시간분)
        "days": len(daily),
    }
