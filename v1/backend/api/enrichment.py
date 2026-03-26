"""Enrichment API — 뉴스 클러스터, 이슈/리액션 레이더"""
import json
from fastapi import APIRouter
from v1config.settings import ENRICHMENT_PATH

router = APIRouter(prefix="/api/enrichment", tags=["enrichment"])


def _load() -> dict:
    try:
        with open(ENRICHMENT_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


@router.get("/news-clusters")
def news_clusters():
    snap = _load()
    return {
        "clusters": snap.get("news_clusters", []),
        "timestamp": snap.get("news_clusters_timestamp", ""),
    }


@router.get("/issue-radar")
def issue_radar():
    snap = _load()
    ii = snap.get("issue_indices", {})
    items = sorted(
        [{"keyword": k, **v} for k, v in ii.items()],
        key=lambda x: x.get("index", 0),
        reverse=True,
    )
    return {"items": items[:15], "total": len(ii)}


@router.get("/reaction-radar")
def reaction_radar():
    snap = _load()
    ri = snap.get("reaction_indices", {})
    items = sorted(
        [{"keyword": k, **v} for k, v in ri.items()],
        key=lambda x: x.get("final_score", x.get("index", 0)),
        reverse=True,
    )
    return {"items": items[:15], "total": len(ri)}
