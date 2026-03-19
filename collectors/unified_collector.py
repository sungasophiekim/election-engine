"""
Election Strategy Engine — 통합 수집기
뉴스 + 블로그 + 카페 + 유튜브 + Google Trends를 한번에 수집하여
이슈별 종합 시그널을 생성합니다.

v2: 병렬 수집 + 캐싱으로 속도 개선
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from models.schemas import IssueSignal
from collectors.naver_news import (
    collect_issue_signals as _collect_news,
    analyze_sentiment,
)
from collectors.social_collector import (
    search_blogs,
    search_cafes,
    search_videos,
    SocialSignal,
)
from collectors.youtube_collector import search_youtube
from collectors.trends_collector import get_search_trend

# ── 캐싱 (5분) ──────────────────────────────────────────────
_cache = {}
_CACHE_TTL = 300  # 5분

def _cached(key, fn):
    """5분 캐싱 래퍼"""
    now = time.time()
    if key in _cache and now - _cache[key][1] < _CACHE_TTL:
        return _cache[key][0]
    try:
        result = fn()
        _cache[key] = (result, now)
        return result
    except Exception:
        return _cache[key][0] if key in _cache else None


@dataclass
class UnifiedSignal:
    """뉴스 + 소셜 통합 시그널"""
    keyword: str

    # 뉴스
    news_mentions: int = 0
    news_negative: float = 0.0
    news_velocity: float = 0.0
    news_tv_reported: bool = False
    news_portal_trending: bool = False

    # 블로그
    blog_total: int = 0
    blog_recent: int = 0
    blog_negative: float = 0.0
    blog_positive: float = 0.0

    # 카페 (커뮤니티)
    cafe_total: int = 0
    cafe_recent: int = 0
    cafe_negative: float = 0.0
    cafe_positive: float = 0.0

    # 동영상 (네이버)
    video_total: int = 0
    video_recent: int = 0
    video_negative: float = 0.0
    video_positive: float = 0.0

    # 유튜브 (YouTube Data API)
    yt_total: int = 0
    yt_recent_7d: int = 0
    yt_total_views: int = 0
    yt_avg_views: int = 0
    yt_top_videos: list = field(default_factory=list)

    # Google Trends
    trend_interest: int = 0         # 현재 관심도 (0~100)
    trend_change_7d: float = 0.0    # 7일 변화율 (%)
    trend_direction: str = ""       # ↑급상승/↑상승/→유지/↓하락
    trend_related: list = field(default_factory=list)  # 연관 검색어

    # 종합
    total_mentions: int = 0
    combined_negative: float = 0.0
    combined_positive: float = 0.0
    candidate_linked: bool = False
    media_tier: int = 3

    # 원본 시그널 (이슈 스코어링에 전달용)
    issue_signal: IssueSignal = None

    # 24시간 변화량 (이전 수집 대비)
    prev_total: int = 0             # 이전 수집 시 총 언급량
    change_count: int = 0           # 변화량 (현재 - 이전)
    change_pct: float = 0.0         # 등락률 (%)

    # 채널별 상위 항목
    top_articles: list = field(default_factory=list)
    top_blogs: list = field(default_factory=list)
    top_cafe_posts: list = field(default_factory=list)


def collect_unified_signals(
    keywords: list[str],
    candidate_name: str = "",
    opponents: list[str] = None,
    include_social: bool = True,
    include_youtube: bool = True,
    include_trends: bool = True,
) -> list[UnifiedSignal]:
    """
    뉴스 + 소셜 + 유튜브 + Google Trends 통합 수집.

    Parameters:
        keywords: 검색 키워드 리스트
        candidate_name: 우리 후보 이름
        opponents: 상대 후보 이름 리스트
        include_social: 소셜 수집 포함 여부 (False면 뉴스만)

    Returns:
        키워드별 UnifiedSignal 리스트
    """
    opponents = opponents or []

    # 1. 뉴스 수집 (캐싱)
    cache_key = f"news:{','.join(sorted(keywords))}"
    news_signals = _cached(cache_key, lambda: _collect_news(
        keywords,
        candidate_name=candidate_name,
        opponents=opponents,
    ))
    news_signals = news_signals or []
    news_map = {s.keyword: s for s in news_signals}

    # ── 키워드별 병렬 수집 ─────────────────────────────────────
    def _collect_one(kw):
        """키워드 1개에 대해 모든 채널 수집 (병렬 실행 단위)"""
        ns = news_map.get(kw)
        u = UnifiedSignal(keyword=kw)

        # 뉴스 데이터
        if ns:
            u.news_mentions = ns.mention_count
            u.news_negative = ns.negative_ratio
            u.news_velocity = ns.velocity
            u.news_tv_reported = ns.tv_reported
            u.news_portal_trending = ns.portal_trending
            u.candidate_linked = ns.candidate_linked
            u.media_tier = ns.media_tier

        # 소셜 데이터 (블로그 + 카페)
        if include_social:
            blog = _cached(f"blog:{kw}", lambda _kw=kw: search_blogs(_kw))
            if blog:
                u.blog_total = blog.total_count
                u.blog_recent = blog.recent_24h
                u.blog_negative = blog.negative_ratio
                u.blog_positive = blog.positive_ratio
                u.top_blogs = blog.top_items[:3]

            cafe = _cached(f"cafe:{kw}", lambda _kw=kw: search_cafes(_kw))
            if cafe:
                u.cafe_total = cafe.total_count
                u.cafe_recent = cafe.recent_24h
                u.cafe_negative = cafe.negative_ratio
                u.cafe_positive = cafe.positive_ratio
                u.top_cafe_posts = cafe.top_items[:3]

        # 유튜브 (선택적)
        if include_youtube:
            yt = _cached(f"yt:{kw}", lambda _kw=kw: search_youtube(_kw, max_results=5))
            if yt:
                u.yt_total = yt.total_results
                u.yt_recent_7d = yt.recent_count
                u.yt_total_views = yt.total_views
                u.yt_avg_views = yt.avg_views
                u.yt_top_videos = [
                    {"title": v.title, "channel": v.channel, "views": v.view_count,
                     "published": v.published}
                    for v in yt.top_videos[:5]
                ]

        # Google Trends (선택적)
        if include_trends:
            tr = _cached(f"tr:{kw}", lambda _kw=kw: get_search_trend(_kw))
            if tr:
                u.trend_interest = tr.interest_now
                u.trend_change_7d = tr.change_7d
                u.trend_direction = tr.trend_direction
                u.trend_related = tr.related_queries[:5]

        return u

    # 병렬 실행 (최대 3 스레드 — 네이버 API rate limit 방지)
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_collect_one, kw): kw for kw in keywords}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception:
                pass

    # 원래 키워드 순서 유지
    kw_order = {kw: i for i, kw in enumerate(keywords)}
    results.sort(key=lambda u: kw_order.get(u.keyword, 999))

    # ── 종합 계산 ─────────────────────────────────────────────
    for u in results:
        # 종합 계산
        channels = []
        if u.news_mentions > 0:
            channels.append(("news", u.news_mentions, u.news_negative))
        if u.blog_total > 0:
            channels.append(("blog", u.blog_recent or u.blog_total, u.blog_negative))
        if u.cafe_total > 0:
            channels.append(("cafe", u.cafe_recent or u.cafe_total, u.cafe_negative))
        if u.yt_total > 0:
            channels.append(("youtube", u.yt_recent_7d or u.yt_total, 0.0))
        if u.video_total > 0:
            channels.append(("video", u.video_recent or u.video_total, u.video_negative))

        u.total_mentions = sum(c[1] for c in channels)

        if channels:
            total_weight = sum(c[1] for c in channels)
            if total_weight > 0:
                u.combined_negative = sum(c[1] * c[2] for c in channels) / total_weight
            # 긍정도 계산
            pos_channels = [
                (u.blog_recent or u.blog_total, u.blog_positive),
                (u.cafe_recent or u.cafe_total, u.cafe_positive),
                (u.video_recent or u.video_total, u.video_positive),
            ]
            pos_weight = sum(c[0] for c in pos_channels)
            if pos_weight > 0:
                u.combined_positive = sum(c[0] * c[1] for c in pos_channels) / pos_weight

        # IssueSignal 생성 (기존 엔진과 호환)
        ns = news_map.get(u.keyword)
        social_boost = min(u.blog_recent + u.cafe_recent, 50)
        boosted_mentions = (ns.mention_count if ns else 0) + social_boost
        final_negative = u.combined_negative if channels else (ns.negative_ratio if ns else 0)
        social_trending = (u.blog_recent + u.cafe_recent) >= 30

        u.issue_signal = IssueSignal(
            keyword=u.keyword,
            mention_count=boosted_mentions,
            velocity=ns.velocity if ns else (u.total_mentions / 10.0),
            negative_ratio=final_negative,
            media_tier=ns.media_tier if ns else 3,
            candidate_linked=u.candidate_linked,
            portal_trending=(ns.portal_trending if ns else False) or social_trending,
            tv_reported=ns.tv_reported if ns else False,
        )

    return results


def format_unified_report(signals: list[UnifiedSignal]) -> str:
    """통합 수집 결과 보고서"""
    lines = ["=" * 64, "  통합 수집 보고서 (뉴스 + 블로그 + 카페 + 동영상)", "=" * 64, ""]

    for s in sorted(signals, key=lambda x: x.total_mentions, reverse=True):
        lines.append(f"  {s.keyword}")
        lines.append(f"    뉴스 {s.news_mentions}건 | 블로그 {s.blog_recent}건"
                     f" | 카페 {s.cafe_recent}건 | 동영상 {s.video_recent}건"
                     f" | 총 {s.total_mentions}건")
        lines.append(f"    부정 {s.combined_negative:.0%} | 긍정 {s.combined_positive:.0%}"
                     f" | {'👤후보' if s.candidate_linked else ''}"
                     f" {'📺TV' if s.news_tv_reported else ''}"
                     f" {'🔥트렌딩' if s.news_portal_trending else ''}")
        if s.top_blogs:
            lines.append(f"    블로그: {s.top_blogs[0].get('title', '')[:50]}")
        if s.top_cafe_posts:
            lines.append(f"    카페: {s.top_cafe_posts[0].get('title', '')[:50]}")
        lines.append("")

    return "\n".join(lines)
