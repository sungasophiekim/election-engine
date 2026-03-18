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
