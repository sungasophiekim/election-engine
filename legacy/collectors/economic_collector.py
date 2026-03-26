"""
Economic Indicator Collector — 경남 경제 지표 수집
현직 도지사 평가에 직접 영향을 미치는 경제 체감 지표.

수집 방법:
  1. 초기 데이터: KOSIS/통계청 수동 입력 (고용률, 물가, GRDP)
  2. 뉴스 기반: 네이버 검색으로 경제 이슈 감성 파악
  3. 향후: KOSIS OpenAPI 직접 연동

Leading Index에 신규 component로 반영.

경남 경제가 좋으면 → 현직(박완수) 유리
경남 경제가 나쁘면 → 도전자(김경수) 유리
"""
from __future__ import annotations
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EconomicIndicator:
    """경남 경제 지표"""
    date: str = ""
    source: str = ""

    # 고용
    employment_rate: float = 0.0       # 고용률 (%)
    unemployment_rate: float = 0.0     # 실업률 (%)
    employment_change: float = 0.0     # 전년 동기 대비 고용자 수 변화 (천명)

    # 물가
    cpi_change: float = 0.0            # 소비자물가 등락률 (전년 동월 대비 %)

    # 산업
    shipbuilding_orders: str = ""       # 조선업 수주 동향
    manufacturing_index: float = 0.0    # 제조업 생산지수 변화율 (%)

    # 부동산
    housing_price_change: float = 0.0   # 아파트 매매가격 변화율 (%)

    # 종합 경제 체감
    economic_sentiment: float = 0.0     # -50~+50 (나쁨~좋음)
    sentiment_direction: str = ""       # "improving" | "stable" | "declining"

    # 현직 유불리
    incumbent_effect: float = 0.0       # -50~+50 (현직 불리~유리)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "source": self.source,
            "employment_rate": self.employment_rate,
            "unemployment_rate": self.unemployment_rate,
            "cpi_change": self.cpi_change,
            "manufacturing_index": self.manufacturing_index,
            "housing_price_change": self.housing_price_change,
            "shipbuilding_orders": self.shipbuilding_orders,
            "economic_sentiment": round(self.economic_sentiment, 1),
            "sentiment_direction": self.sentiment_direction,
            "incumbent_effect": round(self.incumbent_effect, 1),
        }


# ── 경남 경제 지표 (KOSIS/통계청/뉴스 기반 수동 입력) ──
# 출처: 통계청 KOSIS, 경남도청 경제동향, 뉴스 보도
ECONOMIC_DATA = [
    {
        "date": "2025-12",
        "source": "KOSIS/통계청 2025년 12월",
        "employment_rate": 62.1,
        "unemployment_rate": 2.8,
        "cpi_change": 1.8,
        "manufacturing_index": -1.2,
        "housing_price_change": -0.3,
        "shipbuilding_orders": "한화오션 대형 수주 지속",
    },
    {
        "date": "2026-01",
        "source": "KOSIS/통계청 2026년 1월",
        "employment_rate": 61.5,
        "unemployment_rate": 3.0,
        "cpi_change": 2.1,
        "manufacturing_index": -0.8,
        "housing_price_change": -0.5,
        "shipbuilding_orders": "수주 안정세",
    },
    {
        "date": "2026-02",
        "source": "KOSIS/통계청 2026년 2월",
        "employment_rate": 61.8,
        "unemployment_rate": 2.9,
        "cpi_change": 2.0,
        "manufacturing_index": 0.3,
        "housing_price_change": -0.2,
        "shipbuilding_orders": "조선업 호황, 방산 수출 증가",
    },
]


def _calc_economic_sentiment(data: dict) -> tuple[float, str]:
    """경제 체감 점수 산출 (-50~+50)"""
    score = 0.0

    # 고용률 (62% 기준)
    emp = data.get("employment_rate", 62)
    score += (emp - 62) * 5  # 62% → 0, 63% → +5

    # 실업률 (3% 기준, 낮을수록 좋음)
    unemp = data.get("unemployment_rate", 3)
    score += (3 - unemp) * 8  # 3% → 0, 2% → +8

    # 물가 (2% 기준, 높을수록 나쁨)
    cpi = data.get("cpi_change", 2)
    score += (2 - cpi) * 5  # 2% → 0, 3% → -5

    # 제조업 (0% 기준)
    mfg = data.get("manufacturing_index", 0)
    score += mfg * 3  # +1% → +3

    # 부동산 (0% 기준, 상승=자산효과 좋음)
    housing = data.get("housing_price_change", 0)
    score += housing * 5  # +1% → +5

    score = max(-50, min(50, score))

    if score > 5:
        direction = "improving"
    elif score < -5:
        direction = "declining"
    else:
        direction = "stable"

    return round(score, 1), direction


def _calc_incumbent_effect(sentiment: float) -> float:
    """경제 체감 → 현직 유불리 (-50~+50)
    경제 좋으면 현직 유리(+), 나쁘면 현직 불리(-)
    → 도전자(김경수) 관점에서는 반전: 현직 유리 = 우리 불리
    """
    return -sentiment  # 현직 유리 = 도전자 불리


def get_latest_economic() -> EconomicIndicator:
    """최신 경남 경제 지표 반환"""
    if not ECONOMIC_DATA:
        return EconomicIndicator()

    latest = max(ECONOMIC_DATA, key=lambda x: x["date"])
    sentiment, direction = _calc_economic_sentiment(latest)
    incumbent = _calc_incumbent_effect(sentiment)

    return EconomicIndicator(
        date=latest["date"],
        source=latest["source"],
        employment_rate=latest.get("employment_rate", 0),
        unemployment_rate=latest.get("unemployment_rate", 0),
        cpi_change=latest.get("cpi_change", 0),
        manufacturing_index=latest.get("manufacturing_index", 0),
        housing_price_change=latest.get("housing_price_change", 0),
        shipbuilding_orders=latest.get("shipbuilding_orders", ""),
        economic_sentiment=sentiment,
        sentiment_direction=direction,
        incumbent_effect=incumbent,
    )


def get_economic_trend() -> list[dict]:
    """경제 지표 시계열"""
    result = []
    for d in sorted(ECONOMIC_DATA, key=lambda x: x["date"]):
        sentiment, direction = _calc_economic_sentiment(d)
        result.append({
            "date": d["date"],
            "employment_rate": d.get("employment_rate", 0),
            "cpi_change": d.get("cpi_change", 0),
            "sentiment": sentiment,
            "direction": direction,
        })
    return result


def fetch_economic_news_sentiment() -> float:
    """네이버 뉴스에서 경남 경제 감성 파악 (보조 지표)"""
    try:
        from collectors.naver_news import search_news, NEGATIVE_KEYWORDS, POSITIVE_KEYWORDS

        queries = ["경남 경제", "경남 일자리", "경남 물가", "경남 조선업"]
        total_pos = total_neg = 0

        for q in queries:
            articles = search_news(q, display=10, pages=1)
            for art in articles:
                text = art.get("title", "") + " " + art.get("description", "")
                neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
                pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
                total_pos += pos
                total_neg += neg
            time.sleep(0.3)

        total = total_pos + total_neg
        if total > 0:
            return round((total_pos - total_neg) / total, 2)  # -1~+1
        return 0.0

    except Exception:
        return 0.0
