"""
Election Strategy Engine — Google Trends 수집기
검색어 트렌드로 유권자 관심도를 추적합니다.

API 키 불필요 — pytrends 라이브러리 사용.
제한: 너무 빈번하면 429 에러 (분당 ~10회)
"""
import time
from dataclasses import dataclass, field


@dataclass
class TrendSignal:
    """검색어 트렌드 시그널"""
    keyword: str
    interest_now: int           # 현재 관심도 (0~100)
    interest_7d_avg: int        # 7일 평균
    interest_30d_avg: int       # 30일 평균
    change_7d: float            # 7일 대비 변화율 (%)
    trend_direction: str        # "↑급상승" | "↑상승" | "→유지" | "↓하락"
    related_queries: list[str]  # 연관 검색어 (상승)
    related_topics: list[str]   # 연관 주제
    timeline: list[dict]        # [{"date": "2026-03-01", "value": 45}]


def get_search_trend(
    keyword: str,
    timeframe: str = "today 1-m",  # 최근 1개월
    geo: str = "KR",
) -> TrendSignal:
    """
    Google Trends에서 키워드 검색 관심도 조회.
    """
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="ko", tz=540)  # KST
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)

        # 시계열 데이터
        df = pytrends.interest_over_time()
        if df.empty:
            return TrendSignal(
                keyword=keyword, interest_now=0, interest_7d_avg=0,
                interest_30d_avg=0, change_7d=0, trend_direction="데이터 없음",
                related_queries=[], related_topics=[], timeline=[],
            )

        values = df[keyword].tolist()
        dates = [d.strftime("%Y-%m-%d") for d in df.index]

        interest_now = values[-1] if values else 0
        interest_7d = values[-7:] if len(values) >= 7 else values
        interest_30d = values

        avg_7d = sum(interest_7d) // max(len(interest_7d), 1)
        avg_30d = sum(interest_30d) // max(len(interest_30d), 1)

        # 변화율
        if avg_7d > 0 and len(values) > 7:
            prev_7d = values[-14:-7] if len(values) >= 14 else values[:7]
            prev_avg = sum(prev_7d) // max(len(prev_7d), 1)
            change = ((avg_7d - prev_avg) / max(prev_avg, 1)) * 100
        else:
            change = 0

        # 방향
        if change > 30:
            direction = "↑급상승"
        elif change > 10:
            direction = "↑상승"
        elif change < -10:
            direction = "↓하락"
        else:
            direction = "→유지"

        timeline = [{"date": d, "value": int(v)} for d, v in zip(dates, values)]

        # 연관 검색어
        related_queries = []
        related_topics = []
        try:
            rq = pytrends.related_queries()
            if keyword in rq and rq[keyword].get("rising") is not None:
                rising = rq[keyword]["rising"]
                if rising is not None and not rising.empty:
                    related_queries = rising["query"].tolist()[:10]
        except Exception:
            pass

        try:
            rt = pytrends.related_topics()
            if keyword in rt and rt[keyword].get("rising") is not None:
                rising = rt[keyword]["rising"]
                if rising is not None and not rising.empty:
                    related_topics = rising["topic_title"].tolist()[:10]
        except Exception:
            pass

        return TrendSignal(
            keyword=keyword,
            interest_now=interest_now,
            interest_7d_avg=avg_7d,
            interest_30d_avg=avg_30d,
            change_7d=round(change, 1),
            trend_direction=direction,
            related_queries=related_queries,
            related_topics=related_topics,
            timeline=timeline,
        )

    except Exception as e:
        print(f"  [Trends] '{keyword}' 실패: {e}")
        return TrendSignal(
            keyword=keyword, interest_now=0, interest_7d_avg=0,
            interest_30d_avg=0, change_7d=0, trend_direction="수집 실패",
            related_queries=[], related_topics=[], timeline=[],
        )


# ═══════════════════════════════════════════════════════════════
# 네이버 데이터랩 — 검색어 트렌드 (성별/연령별 분석 가능)
# API: https://openapi.naver.com/v1/datalab/search
# 인증: NAVER_CLIENT_ID + NAVER_CLIENT_SECRET (기존 .env 재사용)
# ═══════════════════════════════════════════════════════════════

import os
import json
import httpx
from datetime import datetime, timedelta


@dataclass
class NaverTrendSignal:
    """네이버 데이터랩 검색어 트렌드"""
    keyword: str
    period: str = ""                # "2026-02-20 ~ 2026-03-20"
    interest_now: float = 0.0       # 최근 값 (0~100)
    interest_avg: float = 0.0       # 기간 평균
    change_7d: float = 0.0          # 7일 변화율 (%)
    trend_direction: str = ""       # "↑급상승" | "↑상승" | "→유지" | "↓하락"
    timeline: list[dict] = field(default_factory=list)  # [{"date": str, "value": float}]

    # 성별 분석
    male_interest: float = 0.0      # 남성 관심도
    female_interest: float = 0.0    # 여성 관심도
    gender_skew: str = ""           # "male" | "female" | "balanced"

    # 연령별 분석
    age_breakdown: dict = field(default_factory=dict)  # {"20s": 45.2, "30s": 62.1, ...}
    peak_age: str = ""              # 가장 관심 높은 연령대

    # 디바이스
    mobile_ratio: float = 0.0       # 모바일 비중 (0~1)

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "period": self.period,
            "interest_now": round(self.interest_now, 1),
            "interest_avg": round(self.interest_avg, 1),
            "change_7d": round(self.change_7d, 1),
            "trend_direction": self.trend_direction,
            "male_interest": round(self.male_interest, 1),
            "female_interest": round(self.female_interest, 1),
            "gender_skew": self.gender_skew,
            "age_breakdown": {k: round(v, 1) for k, v in self.age_breakdown.items()},
            "peak_age": self.peak_age,
            "mobile_ratio": round(self.mobile_ratio, 2),
            "timeline": self.timeline[-14:],  # 최근 14일만
        }


_NAVER_AGE_MAP = {
    "1": "0-12", "2": "13-18", "3": "19-24",
    "4": "25-29", "5": "30-34", "6": "35-39",
    "7": "40-44", "8": "45-49", "9": "50-54",
    "10": "55-59", "11": "60+",
}

_AGE_GROUP_MAP = {
    "3": "20s", "4": "20s", "5": "30s", "6": "30s",
    "7": "40s", "8": "40s", "9": "50+", "10": "50+", "11": "50+",
}


def _naver_datalab_request(body: dict) -> dict:
    """네이버 데이터랩 API 호출"""
    client_id = os.getenv("NAVER_CLIENT_ID", "")
    client_secret = os.getenv("NAVER_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return {}

    try:
        resp = httpx.post(
            "https://openapi.naver.com/v1/datalab/search",
            headers={
                "X-Naver-Client-Id": client_id,
                "X-Naver-Client-Secret": client_secret,
                "Content-Type": "application/json",
            },
            content=json.dumps(body),
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"  [NaverDataLab] API error: {resp.status_code}")
            return {}
    except Exception as e:
        print(f"  [NaverDataLab] Request failed: {e}")
        return {}


def get_naver_trend(
    keyword: str,
    days: int = 30,
) -> NaverTrendSignal:
    """
    네이버 데이터랩에서 키워드 검색 트렌드 조회.
    성별/연령별 분석 포함.
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    result = NaverTrendSignal(
        keyword=keyword,
        period=f"{start_date} ~ {end_date}",
    )

    # ── 전체 트렌드 제거 — Google Trends와 중복.
    # 데이터랩은 인구통계(성별/연령)만 활용. 검색 관심도는 Google Trends에서 가져옴.

    # ── 1. 성별 분석 ──
    time.sleep(0.3)  # rate limit
    for gender, field_name in [("m", "male_interest"), ("f", "female_interest")]:
        body_g = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": "date",
            "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}],
            "gender": gender,
        }
        data_g = _naver_datalab_request(body_g)
        if data_g and "results" in data_g:
            points_g = data_g["results"][0].get("data", [])
            vals_g = [p["ratio"] for p in points_g]
            if vals_g:
                setattr(result, field_name, sum(vals_g) / len(vals_g))
        time.sleep(0.3)

    # 성별 편향 판정
    if result.male_interest > 0 and result.female_interest > 0:
        ratio = result.male_interest / max(result.female_interest, 0.01)
        if ratio > 1.3:
            result.gender_skew = "male"
        elif ratio < 0.7:
            result.gender_skew = "female"
        else:
            result.gender_skew = "balanced"

    # ── 3. 연령별 분석 ──
    age_groups = {"20s": [], "30s": [], "40s": [], "50+": []}
    for age_code in ["3", "4", "5", "6", "7", "8", "9", "10", "11"]:
        body_a = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": "date",
            "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}],
            "ages": [age_code],
        }
        data_a = _naver_datalab_request(body_a)
        if data_a and "results" in data_a:
            points_a = data_a["results"][0].get("data", [])
            vals_a = [p["ratio"] for p in points_a]
            if vals_a:
                avg_a = sum(vals_a) / len(vals_a)
                group = _AGE_GROUP_MAP.get(age_code, "")
                if group:
                    age_groups[group].append(avg_a)
        time.sleep(0.2)

    for group, vals in age_groups.items():
        if vals:
            result.age_breakdown[group] = sum(vals) / len(vals)

    if result.age_breakdown:
        result.peak_age = max(result.age_breakdown, key=result.age_breakdown.get)

    # 디바이스 분석 제거 — mobile_ratio 어떤 엔진에도 미사용, 2콜 절약

    return result


def get_naver_trend_compare(
    keyword1: str,
    keyword2: str,
    days: int = 30,
) -> dict:
    """두 후보 검색 트렌드 직접 비교"""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    body = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": "date",
        "keywordGroups": [
            {"groupName": keyword1, "keywords": [keyword1]},
            {"groupName": keyword2, "keywords": [keyword2]},
        ],
    }
    data = _naver_datalab_request(body)
    if not data or "results" not in data:
        return {}

    result = {}
    for r in data["results"]:
        name = r["title"]
        points = r.get("data", [])
        values = [p["ratio"] for p in points]
        result[name] = {
            "avg": round(sum(values) / len(values), 1) if values else 0,
            "latest": round(values[-1], 1) if values else 0,
            "timeline": [{"date": p["period"], "value": round(p["ratio"], 1)} for p in points[-14:]],
        }

    return result


def compare_trends(keywords: list[str], geo: str = "KR") -> dict:
    """
    여러 키워드 비교. Google Trends는 최대 5개 비교 가능.
    Returns: {keyword: TrendSignal}
    """
    results = {}
    # 5개씩 나눠서 처리
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i+5]
        for kw in batch:
            results[kw] = get_search_trend(kw)
            time.sleep(1)  # rate limit 방지
    return results
