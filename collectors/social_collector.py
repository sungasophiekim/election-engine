"""
Election Strategy Engine — 소셜/커뮤니티 데이터 수집기
네이버 블로그/카페/동영상 검색 API로 유튜브, 커뮤니티 여론을 수집합니다.
별도 API 키 없이 기존 네이버 키로 동작합니다.
"""
import os
import re
import time
import threading
import httpx
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from dataclasses import dataclass, field

# 네이버 API 글로벌 rate limiter (초당 10건 제한 → 0.12초 간격)
_naver_lock = threading.Lock()
_naver_last_call = 0.0
_NAVER_MIN_INTERVAL = 0.12


@dataclass
class SocialSignal:
    """소셜/커뮤니티 시그널"""
    keyword: str
    source_type: str           # "blog" | "cafe" | "video"
    total_count: int           # 검색 총 건수
    recent_24h: int            # 최근 24시간 건수
    negative_ratio: float      # 부정 비율
    positive_ratio: float      # 긍정 비율
    top_items: list[dict]      # 상위 항목
    engagement_score: float    # 참여도 (0~1)

    # v2: reaction intelligence
    theme_tags: list[str] = field(default_factory=list)  # 감지된 메시지 테마
    net_sentiment: float = 0.0      # positive - negative (요약 지표)


# ── Naver Search API Endpoints ──────────────────────────────────────
NAVER_BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"
NAVER_CAFE_URL = "https://openapi.naver.com/v1/search/cafearticle.json"
# 네이버 동영상 API — 앱 권한 미등록으로 404. 권한 추가 후 활성화.
NAVER_VIDEO_URL = ""  # "https://openapi.naver.com/v1/search/vclip"

# ── Sentiment Keywords ──────────────────────────────────────────────
NEGATIVE_KEYWORDS = [
    "논란", "비판", "의혹", "반발", "파문", "문제", "사퇴", "고발",
    "수사", "폭로", "거짓", "실패", "위기", "충격", "갈등", "부실",
    "피해", "불만", "특혜", "비리", "부패", "막말", "실언",
]

POSITIVE_KEYWORDS = [
    "지지", "환영", "성과", "약속", "비전", "혁신", "발전", "성장",
    "지원", "투자", "확대", "신설", "개선", "강화", "협력", "상생",
    "호평", "기대", "공약", "추진", "실행",
]


# ── Internal Helpers ────────────────────────────────────────────────

def _get_headers() -> dict:
    """네이버 API 인증 헤더 반환"""
    client_id = os.getenv("NAVER_CLIENT_ID", "")
    client_secret = os.getenv("NAVER_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ValueError("네이버 API 키가 설정되지 않았습니다.")
    return {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }


def _strip_html(text: str) -> str:
    """HTML 태그 및 엔티티 제거"""
    return re.sub(r"<[^>]+>", "", text).replace("&quot;", '"').replace("&amp;", "&")


def _naver_rate_limit():
    """글로벌 rate limiter — 병렬 호출에서도 초당 10건 미만 보장"""
    global _naver_last_call
    with _naver_lock:
        now = time.time()
        elapsed = now - _naver_last_call
        if elapsed < _NAVER_MIN_INTERVAL:
            time.sleep(_NAVER_MIN_INTERVAL - elapsed)
        _naver_last_call = time.time()


def _search(url: str, query: str, display: int = 100, sort: str = "date") -> tuple[list[dict], int]:
    """
    네이버 검색 API 범용 호출.
    Returns: (items, total_count)
    """
    _naver_rate_limit()
    headers = _get_headers()
    params = {"query": query, "display": min(display, 100), "sort": sort}
    with httpx.Client(timeout=10) as client:
        resp = client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for item in data.get("items", []):
        items.append({
            "title": _strip_html(item.get("title", "")),
            "description": _strip_html(item.get("description", "")),
            "link": item.get("link", ""),
            "pub_date": item.get("postdate", item.get("pubDate", "")),
            # video-specific fields
            "play_count": item.get("play_count", 0),
            "thumbnail": item.get("thumbnail", ""),
        })
    return items, data.get("total", 0)


def _analyze_sentiment(items: list[dict]) -> tuple[float, float]:
    """
    간이 감성 분석.
    Returns: (negative_ratio, positive_ratio)
    """
    if not items:
        return 0.0, 0.0
    neg = pos = 0
    for item in items:
        text = item["title"] + " " + item.get("description", "")
        if any(kw in text for kw in NEGATIVE_KEYWORDS):
            neg += 1
        if any(kw in text for kw in POSITIVE_KEYWORDS):
            pos += 1
    return round(neg / len(items), 3), round(pos / len(items), 3)


def _count_recent(items: list[dict], hours: int = 24) -> int:
    """
    최근 N시간 내 게시물 수 카운트.
    - 블로그/카페: postdate 형식 'YYYYMMDD'
    - 동영상: pubDate 형식 RFC 2822
    """
    cutoff = datetime.now() - timedelta(hours=hours)
    cutoff_str = cutoff.strftime("%Y%m%d")
    count = 0
    for item in items:
        pd = item.get("pub_date", "")
        # YYYYMMDD format (blog/cafe)
        if len(pd) == 8 and pd.isdigit():
            if pd >= cutoff_str:
                count += 1
        else:
            # RFC 2822 format (video)
            try:
                pub = parsedate_to_datetime(pd).replace(tzinfo=None)
                if pub >= cutoff:
                    count += 1
            except Exception:
                continue
    return count


def _build_signal(
    keyword: str,
    source_type: str,
    items: list[dict],
    total_count: int,
    max_total: int = 1,
) -> SocialSignal:
    """검색 결과로 SocialSignal 생성"""
    neg_ratio, pos_ratio = _analyze_sentiment(items)
    recent_24h = _count_recent(items, hours=24)

    # engagement_score: total_count 정규화 * 감성 가중치
    raw_engagement = total_count / max(max_total, 1)
    sentiment_weight = 1.0 + (pos_ratio - neg_ratio) * 0.5
    engagement_score = round(min(1.0, max(0.0, raw_engagement * sentiment_weight)), 3)

    # v2: theme tags + net sentiment
    theme_tags = _tag_themes(items)
    net_sentiment = round(pos_ratio - neg_ratio, 3)

    return SocialSignal(
        keyword=keyword,
        source_type=source_type,
        total_count=total_count,
        recent_24h=recent_24h,
        negative_ratio=neg_ratio,
        positive_ratio=pos_ratio,
        top_items=items[:5],
        engagement_score=engagement_score,
        # v2
        theme_tags=theme_tags,
        net_sentiment=net_sentiment,
    )


# ── v2: Theme Tagging ─────────────────────────────────────────────

# 메시지 테마 매핑 (키워드 → 테마)
_THEME_MAP = {
    "경제": "경제", "일자리": "경제", "고용": "경제", "실업": "경제",
    "부동산": "부동산", "집값": "부동산", "전세": "부동산", "분양": "부동산",
    "교통": "교통", "도로": "교통", "철도": "교통", "BRT": "교통",
    "청년": "청년", "대학": "청년", "취업": "청년",
    "복지": "복지", "지원금": "복지", "보조": "복지",
    "안전": "안전", "재난": "안전", "사고": "안전",
    "교육": "교육", "학교": "교육", "돌봄": "교육",
    "환경": "환경", "기후": "환경", "탄소": "환경",
    "국방": "안보", "방산": "안보", "군사": "안보",
    "의료": "의료", "병원": "의료", "건강": "의료",
    "선거": "선거", "투표": "선거", "후보": "선거",
    "비리": "스캔들", "논란": "스캔들", "의혹": "스캔들", "수사": "스캔들",
}


def _tag_themes(items: list[dict]) -> list[str]:
    """
    v2: 검색 결과 제목/설명에서 메시지 테마를 추출.
    상위 3개 테마를 빈도순으로 반환.
    """
    theme_counts: dict[str, int] = {}
    for item in items:
        text = item.get("title", "") + " " + item.get("description", "")
        found_themes = set()
        for kw, theme in _THEME_MAP.items():
            if kw in text:
                found_themes.add(theme)
        for t in found_themes:
            theme_counts[t] = theme_counts.get(t, 0) + 1

    sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
    return [t for t, _ in sorted_themes[:3]]


# ── Public API ──────────────────────────────────────────────────────

def search_blogs(query: str, display: int = 100) -> SocialSignal:
    """네이버 블로그 검색 — 여론 동향 파악"""
    items, total = _search(NAVER_BLOG_URL, query, display)
    return _build_signal(query, "blog", items, total, max_total=max(total, 1))


def search_cafes(query: str, display: int = 100) -> SocialSignal:
    """네이버 카페 검색 — 커뮤니티 여론"""
    items, total = _search(NAVER_CAFE_URL, query, display)
    return _build_signal(query, "cafe", items, total, max_total=max(total, 1))


def search_videos(query: str, display: int = 100) -> SocialSignal:
    """네이버 동영상 검색 — 앱 권한 없으면 빈 결과 즉시 반환"""
    if not NAVER_VIDEO_URL:
        return SocialSignal(keyword=query, source_type="video", total_count=0,
                            recent_24h=0, negative_ratio=0, positive_ratio=0,
                            top_items=[], engagement_score=0)
    items, total = _search(NAVER_VIDEO_URL, query, display)
    return _build_signal(query, "video", items, total, max_total=max(total, 1))


def collect_social_signals(
    keywords: list[str],
    candidate_name: str = "",
    opponents: list[str] = None,
) -> dict:
    """
    모든 소셜 채널에서 종합 시그널 수집.

    Returns:
    {
        "blog": [SocialSignal, ...],
        "cafe": [SocialSignal, ...],
        "video": [SocialSignal, ...],
        "summary": {
            "total_mentions": int,
            "sentiment": {"negative": float, "positive": float, "net": float},
            "hottest_channel": "blog" | "cafe" | "video",
            "hottest_keyword": str,
            "candidate_buzz": int,
            "opponent_buzz": {"김경수": int, ...},
        }
    }
    """
    opponents = opponents or []

    blog_signals: list[SocialSignal] = []
    cafe_signals: list[SocialSignal] = []
    video_signals: list[SocialSignal] = []

    # 1단계: 각 키워드별, 각 채널별 검색 → total_count 수집
    raw_data: dict[str, dict] = {}  # keyword -> {blog: (items, total), ...}
    for kw in keywords:
        raw_data[kw] = {}
        for label, url in [("blog", NAVER_BLOG_URL), ("cafe", NAVER_CAFE_URL), ("video", NAVER_VIDEO_URL)]:
            try:
                items, total = _search(url, kw)
                raw_data[kw][label] = (items, total)
            except Exception as e:
                print(f"  [경고] '{kw}' {label} 검색 실패: {e}")
                raw_data[kw][label] = ([], 0)

    # 2단계: 채널별 max_total 산출 (engagement_score 정규화용)
    max_totals = {"blog": 1, "cafe": 1, "video": 1}
    for kw_data in raw_data.values():
        for ch in ("blog", "cafe", "video"):
            _, total = kw_data.get(ch, ([], 0))
            if total > max_totals[ch]:
                max_totals[ch] = total

    # 3단계: SocialSignal 생성
    total_neg = 0.0
    total_pos = 0.0
    total_items_count = 0
    total_mentions = 0
    hottest_count = 0
    hottest_keyword = ""
    channel_totals = {"blog": 0, "cafe": 0, "video": 0}

    for kw in keywords:
        for ch, signals_list in [("blog", blog_signals), ("cafe", cafe_signals), ("video", video_signals)]:
            items, total = raw_data[kw].get(ch, ([], 0))
            sig = _build_signal(kw, ch, items, total, max_total=max_totals[ch])
            signals_list.append(sig)

            total_mentions += total
            channel_totals[ch] += total

            n = len(items) if items else 0
            total_neg += sig.negative_ratio * n
            total_pos += sig.positive_ratio * n
            total_items_count += n

            if total > hottest_count:
                hottest_count = total
                hottest_keyword = kw

    # 감성 종합
    avg_neg = round(total_neg / max(total_items_count, 1), 3)
    avg_pos = round(total_pos / max(total_items_count, 1), 3)
    net_sentiment = round(avg_pos - avg_neg, 3)

    # 가장 활발한 채널
    hottest_channel = max(channel_totals, key=channel_totals.get)

    # 후보 버즈 집계
    candidate_buzz = 0
    if candidate_name:
        try:
            for _, url in [("blog", NAVER_BLOG_URL), ("cafe", NAVER_CAFE_URL), ("video", NAVER_VIDEO_URL)]:
                _, total = _search(url, candidate_name, display=1)
                candidate_buzz += total
        except Exception:
            pass

    opponent_buzz: dict[str, int] = {}
    for opp in opponents:
        opp_total = 0
        try:
            for _, url in [("blog", NAVER_BLOG_URL), ("cafe", NAVER_CAFE_URL), ("video", NAVER_VIDEO_URL)]:
                _, total = _search(url, opp, display=1)
                opp_total += total
        except Exception:
            pass
        opponent_buzz[opp] = opp_total

    return {
        "blog": blog_signals,
        "cafe": cafe_signals,
        "video": video_signals,
        "summary": {
            "total_mentions": total_mentions,
            "sentiment": {
                "negative": avg_neg,
                "positive": avg_pos,
                "net": net_sentiment,
            },
            "hottest_channel": hottest_channel,
            "hottest_keyword": hottest_keyword,
            "candidate_buzz": candidate_buzz,
            "opponent_buzz": opponent_buzz,
        },
    }


def get_youtube_top_videos(query: str, count: int = 5) -> list[dict]:
    """
    특정 키워드의 인기 동영상 목록.
    네이버 동영상 API의 play_count 필드를 활용해 인기순 정렬.

    Returns: [{"title": str, "link": str, "play_count": int, "thumbnail": str}]
    """
    items, _ = _search(NAVER_VIDEO_URL, query, display=100, sort="date")

    # play_count 기준 내림차순 정렬
    sorted_items = sorted(items, key=lambda x: x.get("play_count", 0), reverse=True)

    results = []
    for item in sorted_items[:count]:
        results.append({
            "title": item["title"],
            "link": item["link"],
            "play_count": item.get("play_count", 0),
            "thumbnail": item.get("thumbnail", ""),
        })
    return results


def compare_candidate_buzz(
    candidate_name: str,
    opponents: list[str],
) -> dict:
    """
    후보 간 소셜 버즈 비교.

    Returns:
    {
        "박완수": {"blog": 123, "cafe": 45, "video": 67, "total": 235, "sentiment": 0.12},
        "김경수": {"blog": 156, "cafe": 89, "video": 45, "total": 290, "sentiment": -0.05},
        ...
        "buzz_leader": "김경수",
        "sentiment_leader": "박완수",
    }
    """
    all_candidates = [candidate_name] + (opponents or [])
    result: dict = {}

    max_total = 0

    for name in all_candidates:
        entry = {"blog": 0, "cafe": 0, "video": 0, "total": 0, "sentiment": 0.0}
        all_items = []

        for ch, url in [("blog", NAVER_BLOG_URL), ("cafe", NAVER_CAFE_URL), ("video", NAVER_VIDEO_URL)]:
            try:
                items, total = _search(url, name, display=100)
                entry[ch] = total
                all_items.extend(items)
            except Exception as e:
                print(f"  [경고] '{name}' {ch} 검색 실패: {e}")

        entry["total"] = entry["blog"] + entry["cafe"] + entry["video"]

        # 감성 점수: positive - negative
        neg_ratio, pos_ratio = _analyze_sentiment(all_items)
        entry["sentiment"] = round(pos_ratio - neg_ratio, 3)

        result[name] = entry
        if entry["total"] > max_total:
            max_total = entry["total"]

    # 리더 선정
    buzz_leader = max(all_candidates, key=lambda n: result[n]["total"])
    sentiment_leader = max(all_candidates, key=lambda n: result[n]["sentiment"])

    result["buzz_leader"] = buzz_leader
    result["sentiment_leader"] = sentiment_leader

    return result
