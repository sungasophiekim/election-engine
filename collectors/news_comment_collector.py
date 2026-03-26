"""
Naver News Comment Collector — 네이버 뉴스 댓글 수집기
뉴스 기사의 댓글 수 + 공감/비공감 + 감성 분석.

여론의 바로미터:
  - 네이버 뉴스 댓글은 한국 온라인 여론의 최전선
  - 기사 댓글 수 = 이슈 관심도, 공감 비율 = 여론 방향
  - Reaction Index Layer 5와 병행하여 직접 반응 측정 강화

수집 방법:
  - 네이버 뉴스 기사 URL에서 oid(언론사 ID), aid(기사 ID) 추출
  - 네이버 댓글 API (commentBox) 호출
  - 댓글 텍스트 + 공감/비공감 수 수집

제한:
  - 기사당 최대 20개 댓글 (최신순)
  - API 호출 간 0.5초 대기 (rate limit)
  - 차단 방지를 위해 과도한 호출 자제
"""
from __future__ import annotations
import re
import time
import httpx
from dataclasses import dataclass, field
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# 데이터 구조
# ═══════════════════════════════════════════════════════════════

@dataclass
class NewsComment:
    """개별 댓글"""
    text: str
    author: str = ""
    likes: int = 0           # 공감 수
    dislikes: int = 0        # 비공감 수
    sentiment: str = "neutral"   # positive | negative | neutral
    is_reply: bool = False


@dataclass
class ArticleCommentSignal:
    """기사 1건의 댓글 분석 결과"""
    article_title: str
    article_url: str
    oid: str = ""
    aid: str = ""

    comment_count: int = 0       # 전체 댓글 수
    fetched_count: int = 0       # 수집한 댓글 수

    # 감성 집계
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    net_sentiment: float = 0.0   # -1.0 ~ +1.0

    # 공감/비공감 집계
    total_likes: int = 0         # 전체 공감 합계
    total_dislikes: int = 0      # 전체 비공감 합계
    like_ratio: float = 0.0      # 공감 / (공감+비공감)

    # 대표 댓글
    top_liked: str = ""          # 공감 최다 댓글
    top_liked_count: int = 0     # 공감 최다 수

    # 동원 신호
    mobilization_detected: bool = False

    comments: list = field(default_factory=list)  # list[NewsComment]


@dataclass
class NewsCommentReport:
    """키워드별 뉴스 댓글 종합 리포트"""
    keyword: str
    articles_analyzed: int = 0
    total_comments: int = 0       # 전체 기사 댓글 합계
    avg_comments: float = 0.0     # 기사당 평균 댓글

    # 종합 감성
    net_sentiment: float = 0.0    # -1.0 ~ +1.0
    positive_ratio: float = 0.0
    negative_ratio: float = 0.0
    dominant_sentiment: str = "neutral"

    # 종합 공감
    total_likes: int = 0
    total_dislikes: int = 0
    like_ratio: float = 0.0       # 공감 비율

    # 동원 신호
    mobilization_detected: bool = False

    # 대표 댓글
    top_positive: str = ""
    top_negative: str = ""
    top_liked: str = ""
    top_liked_count: int = 0

    # 반응 등급
    reaction_grade: str = "LOW"   # EXPLOSIVE | HOT | ACTIVE | LOW

    # 개별 기사 결과
    article_signals: list = field(default_factory=list)  # list[ArticleCommentSignal]

    computed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "articles_analyzed": self.articles_analyzed,
            "total_comments": self.total_comments,
            "avg_comments": round(self.avg_comments, 1),
            "net_sentiment": round(self.net_sentiment, 3),
            "positive_ratio": round(self.positive_ratio, 3),
            "negative_ratio": round(self.negative_ratio, 3),
            "dominant_sentiment": self.dominant_sentiment,
            "total_likes": self.total_likes,
            "total_dislikes": self.total_dislikes,
            "like_ratio": round(self.like_ratio, 3),
            "mobilization_detected": self.mobilization_detected,
            "top_positive": self.top_positive,
            "top_negative": self.top_negative,
            "top_liked": self.top_liked,
            "top_liked_count": self.top_liked_count,
            "reaction_grade": self.reaction_grade,
            "articles": [
                {
                    "title": a.article_title[:50],
                    "comments": a.comment_count,
                    "sentiment": round(a.net_sentiment, 3),
                    "likes": a.total_likes,
                    "dislikes": a.total_dislikes,
                }
                for a in self.article_signals[:10]
            ],
            "computed_at": self.computed_at,
        }


# ═══════════════════════════════════════════════════════════════
# URL 파싱 — 네이버 뉴스 oid/aid 추출
# ═══════════════════════════════════════════════════════════════

def _extract_naver_ids(url: str) -> tuple:
    """네이버 뉴스 URL에서 oid, aid 추출."""
    # 패턴 1: news.naver.com/main/read.naver?oid=XXX&aid=XXX
    m = re.search(r'oid=(\d+).*?aid=(\d+)', url)
    if m:
        return m.group(1), m.group(2)

    # 패턴 2: n.news.naver.com/article/XXX/XXX
    m = re.search(r'article/(\d+)/(\d+)', url)
    if m:
        return m.group(1), m.group(2)

    # 패턴 3: news.naver.com/article/XXX/XXX
    m = re.search(r'news\.naver\.com/.*?/(\d{3})/(\d{10})', url)
    if m:
        return m.group(1), m.group(2)

    return "", ""


def _get_naver_news_url(article: dict) -> str:
    """검색 결과에서 네이버 뉴스 URL 추출 (link 또는 originallink)."""
    link = article.get("link", "")
    if "news.naver.com" in link or "n.news.naver.com" in link:
        return link
    # originallink는 원본 언론사 URL → 네이버 댓글 없음
    return ""


# ═══════════════════════════════════════════════════════════════
# 감성 분석
# ═══════════════════════════════════════════════════════════════

COMMENT_POSITIVE = [
    "지지", "응원", "기대", "좋아", "훌륭", "최고", "파이팅", "감사",
    "찬성", "성공", "대박", "잘한다", "멋지", "화이팅", "힘내",
    "존경", "실력", "능력", "도민",
]

COMMENT_NEGATIVE = [
    "실망", "최악", "거짓", "사기", "반대", "쓰레기", "싫", "비판",
    "논란", "허위", "무능", "구속", "수사", "탄핵", "퇴진", "내로남불",
    "범죄", "부패", "거부", "반발", "후회", "망", "끝",
]

MOBILIZATION_KEYWORDS = [
    "투표", "심판", "국민의 선택", "이번엔", "꼭 가자", "사전투표",
    "반드시", "찍자", "찍어야", "한 표", "선택",
]


def _analyze_comment_sentiment(text: str) -> str:
    """댓글 감성 판정."""
    pos = sum(1 for kw in COMMENT_POSITIVE if kw in text)
    neg = sum(1 for kw in COMMENT_NEGATIVE if kw in text)
    if neg > pos:
        return "negative"
    elif pos > neg:
        return "positive"
    return "neutral"


def _has_mobilization(text: str) -> bool:
    """동원 키워드 감지."""
    return any(kw in text for kw in MOBILIZATION_KEYWORDS)


# ═══════════════════════════════════════════════════════════════
# 댓글 수집
# ═══════════════════════════════════════════════════════════════

COMMENT_API_URL = "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json"

# 네이버 댓글 API 기본 파라미터
COMMENT_PARAMS = {
    "ticket": "news",
    "templateId": "default_nation",
    "pool": "cbox5",
    "lang": "ko",
    "country": "KR",
    "pageSize": 20,
    "page": 1,
    "sort": "FAVORITE",  # 공감 순
    "initialize": "true",
}

COMMENT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://news.naver.com/",
}


def fetch_article_comments(
    oid: str,
    aid: str,
    article_title: str = "",
    article_url: str = "",
    max_comments: int = 20,
) -> ArticleCommentSignal:
    """단일 기사의 댓글 수집 + 분석."""
    signal = ArticleCommentSignal(
        article_title=article_title,
        article_url=article_url,
        oid=oid,
        aid=aid,
    )

    if not oid or not aid:
        return signal

    try:
        object_id = f"news{oid},{aid}"
        params = dict(COMMENT_PARAMS)
        params["objectId"] = object_id
        params["pageSize"] = min(max_comments, 20)

        with httpx.Client(timeout=10) as client:
            resp = client.get(
                COMMENT_API_URL,
                params=params,
                headers=COMMENT_HEADERS,
            )

        # JSONP 응답 파싱: _callback({"result": {...}})
        text = resp.text
        # JSONP wrapper 제거
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if not json_match:
            return signal

        import json
        data = json.loads(json_match.group())
        result = data.get("result", {})

        # 전체 댓글 수
        count_info = result.get("count", {})
        signal.comment_count = count_info.get("comment", 0) + count_info.get("reply", 0)

        # 댓글 목록
        comment_list = result.get("commentList", [])
        for c in comment_list[:max_comments]:
            text_content = c.get("contents", "")
            likes = c.get("sympathyCount", 0)
            dislikes = c.get("antipathyCount", 0)
            author = c.get("userName", "")
            is_reply = c.get("parentCommentNo", 0) > 0

            sentiment = _analyze_comment_sentiment(text_content)

            comment = NewsComment(
                text=text_content,
                author=author,
                likes=likes,
                dislikes=dislikes,
                sentiment=sentiment,
                is_reply=is_reply,
            )
            signal.comments.append(comment)

            # 집계
            if sentiment == "positive":
                signal.positive_count += 1
            elif sentiment == "negative":
                signal.negative_count += 1
            else:
                signal.neutral_count += 1

            signal.total_likes += likes
            signal.total_dislikes += dislikes

            # 공감 최다 댓글
            if likes > signal.top_liked_count:
                signal.top_liked = text_content[:100]
                signal.top_liked_count = likes

            # 동원 키워드
            if _has_mobilization(text_content):
                signal.mobilization_detected = True

        signal.fetched_count = len(signal.comments)

        # 감성 계산
        total = signal.positive_count + signal.negative_count + signal.neutral_count
        if total > 0:
            signal.net_sentiment = (signal.positive_count - signal.negative_count) / total

        # 공감 비율
        total_reactions = signal.total_likes + signal.total_dislikes
        if total_reactions > 0:
            signal.like_ratio = signal.total_likes / total_reactions

    except Exception:
        pass

    return signal


def fetch_keyword_comments(
    keyword: str,
    max_articles: int = 5,
    max_comments_per_article: int = 20,
) -> NewsCommentReport:
    """
    키워드로 뉴스 검색 → 상위 기사의 댓글 수집 + 종합 분석.
    네이버 뉴스 URL이 있는 기사만 대상.
    """
    report = NewsCommentReport(
        keyword=keyword,
        computed_at=datetime.now().isoformat(),
    )

    try:
        from collectors.naver_news import search_news
        articles = search_news(keyword, display=20, pages=1)
    except Exception:
        return report

    # 네이버 뉴스 URL이 있는 기사만 필터
    naver_articles = []
    for art in articles:
        naver_url = _get_naver_news_url(art)
        if naver_url:
            oid, aid = _extract_naver_ids(naver_url)
            if oid and aid:
                naver_articles.append((art, oid, aid, naver_url))

    naver_articles = naver_articles[:max_articles]

    total_pos = total_neg = total_neu = 0
    all_likes = all_dislikes = 0
    mobilization = False
    best_positive = ""
    best_negative = ""
    best_liked = ""
    best_liked_count = 0

    for art, oid, aid, url in naver_articles:
        signal = fetch_article_comments(
            oid=oid,
            aid=aid,
            article_title=art.get("title", ""),
            article_url=url,
            max_comments=max_comments_per_article,
        )
        report.article_signals.append(signal)
        report.total_comments += signal.comment_count

        total_pos += signal.positive_count
        total_neg += signal.negative_count
        total_neu += signal.neutral_count
        all_likes += signal.total_likes
        all_dislikes += signal.total_dislikes

        if signal.mobilization_detected:
            mobilization = True

        # 대표 댓글 업데이트
        for c in signal.comments:
            if c.sentiment == "positive" and c.likes > 0 and not best_positive:
                best_positive = c.text[:100]
            if c.sentiment == "negative" and c.likes > 0 and not best_negative:
                best_negative = c.text[:100]
        if signal.top_liked_count > best_liked_count:
            best_liked = signal.top_liked
            best_liked_count = signal.top_liked_count

        time.sleep(0.5)  # rate limit

    report.articles_analyzed = len(naver_articles)
    if report.articles_analyzed > 0:
        report.avg_comments = report.total_comments / report.articles_analyzed

    # 종합 감성
    total_sent = total_pos + total_neg + total_neu
    if total_sent > 0:
        report.positive_ratio = total_pos / total_sent
        report.negative_ratio = total_neg / total_sent
        report.net_sentiment = (total_pos - total_neg) / total_sent

    if report.net_sentiment > 0.15:
        report.dominant_sentiment = "positive"
    elif report.net_sentiment < -0.15:
        report.dominant_sentiment = "negative"
    else:
        report.dominant_sentiment = "neutral"

    # 공감
    report.total_likes = all_likes
    report.total_dislikes = all_dislikes
    total_r = all_likes + all_dislikes
    if total_r > 0:
        report.like_ratio = all_likes / total_r

    report.mobilization_detected = mobilization
    report.top_positive = best_positive
    report.top_negative = best_negative
    report.top_liked = best_liked
    report.top_liked_count = best_liked_count

    # 반응 등급
    if report.total_comments >= 500:
        report.reaction_grade = "EXPLOSIVE"
    elif report.total_comments >= 200:
        report.reaction_grade = "HOT"
    elif report.total_comments >= 50:
        report.reaction_grade = "ACTIVE"
    else:
        report.reaction_grade = "LOW"

    return report
