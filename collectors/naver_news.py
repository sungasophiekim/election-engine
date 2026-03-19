"""
Election Strategy Engine — 네이버 뉴스 실시간 수집기
네이버 검색 API를 사용하여 실제 뉴스 데이터를 수집합니다.

API 키 발급: https://developers.naver.com/apps/#/register
  → 애플리케이션 등록 → 검색 API 선택
"""
import os
import re
import httpx
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from models.schemas import IssueSignal


NAVER_SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"


def _get_headers() -> dict:
    client_id = os.getenv("NAVER_CLIENT_ID", "")
    client_secret = os.getenv("NAVER_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ValueError(
            "네이버 API 키가 설정되지 않았습니다.\n"
            "1. https://developers.naver.com/apps/#/register 에서 앱 등록\n"
            "2. .env 파일에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 입력"
        )
    return {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).replace("&quot;", '"').replace("&amp;", "&")


def search_news(query: str, display: int = 100, sort: str = "date", pages: int = 1) -> list[dict]:
    """
    네이버 뉴스 검색.
    pages=1: 100건 (기본), pages=3: 300건 (정확도 향상)
    네이버 API 제한: display 최대 100, start 최대 1000
    """
    headers = _get_headers()
    articles = []

    for page in range(pages):
        start = page * 100 + 1
        if start > 1000:
            break
        params = {"query": query, "display": min(display, 100), "sort": sort, "start": start}
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(NAVER_SEARCH_URL, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()

            for item in data.get("items", []):
                articles.append({
                    "title": _strip_html(item.get("title", "")),
                    "description": _strip_html(item.get("description", "")),
                    "link": item.get("originallink", item.get("link", "")),
                    "source": item.get("originallink", "").split("/")[2] if "://" in item.get("originallink", "") else "",
                    "pub_date": item.get("pubDate", ""),
                })

            # 반환 건수가 요청보다 적으면 더 이상 없음
            if len(data.get("items", [])) < display:
                break
        except Exception:
            break

    return articles


def count_mentions(query: str) -> int:
    """검색 결과 총 건수 반환"""
    headers = _get_headers()
    params = {"query": query, "display": 1, "sort": "date"}

    with httpx.Client(timeout=10) as client:
        resp = client.get(NAVER_SEARCH_URL, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json().get("total", 0)


NEGATIVE_KEYWORDS = [
    "논란", "비판", "의혹", "반발", "파문", "문제", "사퇴", "고발",
    "수사", "폭로", "거짓", "실패", "위기", "충격", "갈등", "부실",
    "피해", "불만", "특혜", "비리", "부패", "탈세", "위반", "물의",
    "막말", "실언", "경질", "해임", "퇴진",
]

POSITIVE_KEYWORDS = [
    "지지", "환영", "성과", "약속", "비전", "혁신", "발전", "성장",
    "지원", "투자", "확대", "신설", "개선", "강화", "협력", "상생",
    "호평", "기대", "공약", "계획", "추진", "실행",
]

DEFENSE_PATTERNS = [
    "반박", "해명", "설명", "강조", "일축", "부인", "반론",
]


def analyze_sentiment_simple(articles: list[dict]) -> float:
    """
    간이 부정 감성 비율 (0.0 ~ 1.0). 하위 호환용 래퍼.
    부정 키워드 매칭 기반 — 실제 서비스에서는 NLP 모델로 교체 필요.
    """
    if not articles:
        return 0.0

    neg_count = 0
    for art in articles:
        text = art["title"] + " " + art["description"]
        if any(kw in text for kw in NEGATIVE_KEYWORDS):
            neg_count += 1
    return round(neg_count / len(articles), 3)


def analyze_sentiment(
    articles: list[dict],
    candidate_name: str = "",
    opponents: list[str] = None,
) -> dict:
    """
    컨텍스트 인식 감성 분석.

    - candidate_name 이 포함된 기사에서 긍정/부정/중립 분류
    - opponents 가 포함된 기사에서 긍정/부정 분류
    - 방어 패턴(반박, 해명 등)이 있으면 부정이 아닌 중립으로 처리
    - net_sentiment: -1.0(최악) ~ 1.0(최선) 우리 후보 관점 종합 점수

    Returns:
        {
            "negative_ratio": float,         # 0.0~1.0 전체 부정 비율 (하위 호환)
            "about_us_negative": int,
            "about_us_positive": int,
            "about_us_neutral": int,
            "about_opponent_negative": int,
            "about_opponent_positive": int,
            "net_sentiment": float,          # -1.0 ~ 1.0
        }
    """
    opponents = opponents or []

    result = {
        "negative_ratio": 0.0,
        "about_us_negative": 0,
        "about_us_positive": 0,
        "about_us_neutral": 0,
        "about_opponent_negative": 0,
        "about_opponent_positive": 0,
        "net_sentiment": 0.0,
    }

    if not articles:
        return result

    total_neg = 0
    score_sum = 0.0

    for art in articles:
        text = art["title"] + " " + art["description"]

        neg_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
        pos_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
        has_defense = any(p in text for p in DEFENSE_PATTERNS)

        mentions_us = bool(candidate_name and candidate_name in text)
        mentions_opponent = any(opp in text for opp in opponents)

        # Determine article-level polarity
        if neg_count > pos_count:
            polarity = "negative"
        elif pos_count > neg_count:
            polarity = "positive"
        else:
            polarity = "neutral"

        # Defense pattern override: if article mentions our candidate AND has
        # defense keywords alongside negative keywords, treat as neutral
        if mentions_us and polarity == "negative" and has_defense:
            polarity = "neutral"

        # Track overall negative ratio (backward compat)
        if polarity == "negative":
            total_neg += 1

        # Classify per subject
        if mentions_us:
            if polarity == "negative":
                result["about_us_negative"] += 1
                score_sum -= 1.0
            elif polarity == "positive":
                result["about_us_positive"] += 1
                score_sum += 1.0
            else:
                result["about_us_neutral"] += 1
                # neutral about us contributes 0

        if mentions_opponent:
            if polarity == "negative":
                result["about_opponent_negative"] += 1
                score_sum += 0.5  # bad for opponent = good for us
            elif polarity == "positive":
                result["about_opponent_positive"] += 1
                score_sum -= 0.5  # good for opponent = bad for us

    result["negative_ratio"] = round(total_neg / len(articles), 3)

    # Clamp net_sentiment to [-1, 1]
    raw = score_sum / len(articles)
    result["net_sentiment"] = round(max(-1.0, min(1.0, raw)), 3)

    return result


def classify_media_tier(source_url: str) -> int:
    """미디어 티어 분류: 1=방송/메이저, 2=인터넷뉴스, 3=블로그/카페"""
    major = ["kbs.co.kr", "sbs.co.kr", "mbc.co.kr", "jtbc.co.kr",
             "ytn.co.kr", "chosun.com", "donga.com", "joongang.co.kr",
             "hani.co.kr", "khan.co.kr", "yna.co.kr", "newsis.com"]
    internet = ["news.naver.com", "daum.net", "ohmynews", "newstapa",
                "mt.co.kr", "edaily.co.kr", "mk.co.kr", "hankyung.com"]

    for m in major:
        if m in source_url:
            return 1
    for i in internet:
        if i in source_url:
            return 2
    return 3


def _count_recent_articles(articles: list[dict], hours: int = 24) -> int:
    """최근 N시간 내 발행된 기사 수를 카운트"""
    cutoff = datetime.now() - timedelta(hours=hours)
    count = 0
    for art in articles:
        try:
            pub = parsedate_to_datetime(art.get("pub_date", ""))
            pub = pub.replace(tzinfo=None)
            if pub >= cutoff:
                count += 1
        except Exception:
            continue
    return count


def collect_issue_signals(
    keywords: list[str],
    candidate_name: str = "",
    opponents: list[str] = None,
) -> list[IssueSignal]:
    """
    키워드 리스트로 실제 뉴스를 검색하여 IssueSignal 생성.
    최근 100건 중 24시간 내 기사 수를 기준으로 실시간 활성도를 판단합니다.
    """
    signals = []
    for kw in keywords:
        try:
            # 3페이지 수집 (최대 300건) — 정확도 향상
            articles = search_news(kw, display=100, pages=3)
            total = count_mentions(kw)
        except Exception as e:
            print(f"  [경고] '{kw}' 검색 실패: {e}")
            continue

        if not articles:
            continue

        # 최근 24시간 내 기사 수 = 실질적 mention_count
        recent_24h = _count_recent_articles(articles, hours=24)
        recent_6h = _count_recent_articles(articles, hours=6)

        sentiment = analyze_sentiment(articles, candidate_name, opponents)
        neg_ratio = sentiment["negative_ratio"]

        # 미디어 티어: 최고 티어 기준
        tiers = [classify_media_tier(a.get("link", "")) for a in articles]
        best_tier = min(tiers) if tiers else 3

        # 후보 연결 여부
        candidate_linked = False
        if candidate_name:
            candidate_linked = any(
                candidate_name in (a["title"] + a["description"])
                for a in articles
            )

        # 정확도: 수집 건수 < 샘플이면 정확, 아니면 추정
        sampled = len(articles)
        is_exact = recent_24h < sampled  # 24h건수가 샘플보다 작으면 정확

        # 포털 트렌딩 추정: 300건 샘플에서 150건 이상이면 활발
        portal_trending = recent_24h >= 150

        # TV 보도 여부: 방송사(티어1) 기사가 3건 이상
        tier1_count = sum(1 for t in tiers if t == 1)
        tv_reported = tier1_count >= 3

        # 속도(velocity): 최근 6h / 과거 18h 비율로 가속도 추정
        older_18h = max(recent_24h - recent_6h, 1)
        velocity = (recent_6h / older_18h) * 3.0 if older_18h > 0 else 1.0
        velocity = max(velocity, recent_24h / 10.0)  # baseline 10건/일 대비

        signals.append(IssueSignal(
            keyword=kw,
            mention_count=recent_24h,
            velocity=round(velocity, 2),
            negative_ratio=neg_ratio,
            media_tier=best_tier,
            candidate_linked=candidate_linked,
            portal_trending=portal_trending,
            tv_reported=tv_reported,
        ))

    return signals


def collect_opponent_data(
    opponent_names: list[str],
    region: str = "",
) -> list[dict]:
    """
    경쟁 후보 실시간 뉴스 데이터 수집.
    Engine 4에 전달할 opponent_data 형식으로 반환.
    """
    results = []
    for name in opponent_names:
        query = f"{name} {region}".strip() if region else name
        try:
            articles = search_news(query, display=100)
        except Exception as e:
            print(f"  [경고] '{name}' 수집 실패: {e}")
            results.append({
                "name": name,
                "recent_mentions": 0,
                "message_shift": "",
            })
            continue

        # 최근 24시간 기사 수를 실질적 언급량으로 사용
        recent_24h = _count_recent_articles(articles, hours=24)

        # 메시지 전환 감지: 최근 기사 제목에서 반복 키워드 추출
        message_shift = _detect_message_shift(articles)

        # 상대 후보 기사에 대한 감성 분석
        opp_sentiment = analyze_sentiment(articles, candidate_name=name)

        results.append({
            "name": name,
            "recent_mentions": recent_24h,
            "message_shift": message_shift,
            "articles_sample": articles[:5],  # 상위 5건 샘플
            "sentiment": opp_sentiment,
        })

    return results


def _detect_message_shift(articles: list[dict]) -> str:
    """
    최근 기사 제목에서 반복 등장하는 키워드로 메시지 전환 감지.
    간이 구현 — 실서비스에서는 시계열 비교 필요.
    """
    if not articles:
        return ""

    policy_keywords = {
        "경제": 0, "일자리": 0, "복지": 0, "안보": 0, "교육": 0,
        "부동산": 0, "세금": 0, "환경": 0, "교통": 0, "의료": 0,
        "청년": 0, "노인": 0, "안전": 0, "국방": 0, "외교": 0,
    }

    for art in articles[:20]:
        text = art["title"] + " " + art["description"]
        for kw in policy_keywords:
            if kw in text:
                policy_keywords[kw] += 1

    # 상위 키워드 추출
    sorted_kw = sorted(policy_keywords.items(), key=lambda x: x[1], reverse=True)
    top = [k for k, v in sorted_kw[:3] if v >= 2]

    if top:
        return f"주요 메시지: {', '.join(top)}"
    return ""
