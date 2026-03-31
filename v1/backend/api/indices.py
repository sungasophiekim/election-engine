"""지표 현황 API — enrichment snapshot에서 읽기"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter
from v1config.settings import ENRICHMENT_PATH, LEGACY_DATA, CANDIDATE, OPPONENT

router = APIRouter(prefix="/api/indices", tags=["indices"])


def _load_enrichment() -> dict:
    try:
        with open(ENRICHMENT_PATH) as f:
            return json.load(f)
    except Exception:
        return {}




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
        "server_updated_at": enrichment_ts,
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

    return {
        "trend": [],  # 하위 호환 (프론트에서 미사용)
        "candidate_trend": candidate_history[-168:],  # 최근 168건 (7일 × 24시간)
        "days": 0,
    }


@router.get("/regional")
def regional_reaction():
    """지역별 반응 현황 — 최근 24시간 히스토리에서 집계"""
    hist_path = ENRICHMENT_PATH.parent / "indices_history.json"
    all_hist = []
    try:
        with open(hist_path) as f:
            all_hist = json.load(f)
    except Exception:
        pass

    recent = all_hist[-24:]
    regions = {}
    for h in recent:
        for region, data in h.get("regional", {}).items():
            if region not in regions:
                regions[region] = {"mentions": 0, "sentiments": [], "hourly": []}
            regions[region]["mentions"] += data.get("mentions", 0)
            s = data.get("avg_sentiment", 0)
            if s != 0:
                regions[region]["sentiments"].append(s)
            regions[region]["hourly"].append({
                "time": h.get("date", ""),
                "mentions": data.get("mentions", 0),
                "sentiment": data.get("avg_sentiment", 0),
            })

    items = []
    for region, v in sorted(regions.items(), key=lambda x: -x[1]["mentions"]):
        sents = v["sentiments"]
        avg = sum(sents) / len(sents) if sents else 0
        items.append({
            "region": region,
            "mentions": v["mentions"],
            "avg_sentiment": round(avg, 3),
            "tone": "긍정" if avg > 0.05 else "부정" if avg < -0.05 else "중립",
            "hourly": v["hourly"][-12:],  # 최근 12시간
        })

    return {"regions": items, "hours": len(recent)}


@router.get("/collection-status")
def collection_status():
    """수집 상태 — 최근 7일 수집 건수 + API 상태"""
    hist_path = ENRICHMENT_PATH.parent / "indices_history.json"
    all_hist = []
    try:
        with open(hist_path) as f:
            all_hist = json.load(f)
    except Exception:
        pass

    # 날짜별 수집 건수 집계
    daily_counts = {}
    for h in all_hist:
        ts = h.get("timestamp", "")
        if not ts:
            continue
        day = ts[:10]  # YYYY-MM-DD
        daily_counts[day] = daily_counts.get(day, 0) + 1

    # 최근 7일
    days = []
    for i in range(7):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        count = daily_counts.get(d, 0)
        status = "ok" if count >= 20 else "warning" if count >= 10 else "error" if count > 0 else "missing"
        days.append({"date": d, "count": count, "expected": 24, "status": status})

    today = datetime.now().strftime("%Y-%m-%d")
    today_count = daily_counts.get(today, 0)
    # 오늘 경과 시간 기준 예상 건수
    hours_passed = datetime.now().hour + 1
    expected_so_far = hours_passed  # 1시간당 1건
    today_status = "ok" if today_count >= expected_so_far * 0.8 else "warning" if today_count >= expected_so_far * 0.5 else "error"

    # 최근 7일 수집률
    total_collected = sum(d["count"] for d in days)
    total_expected = sum(d["expected"] for d in days)
    collection_rate = round(total_collected / total_expected * 100, 1) if total_expected > 0 else 0

    # API 상태
    api_status = []
    try:
        from collectors.api_cache import get_all_status
        api_status = get_all_status()
    except Exception:
        pass

    # 마지막 수집 시각
    last_ts = all_hist[-1].get("timestamp", "") if all_hist else ""

    return {
        "today": {"date": today, "count": today_count, "expected": expected_so_far, "status": today_status},
        "days": days,
        "collection_rate_7d": collection_rate,
        "last_collected_at": last_ts,
        "api_status": api_status,
    }
