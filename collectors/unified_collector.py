"""
Election Strategy Engine — 통합 수집기
뉴스 + 블로그 + 카페 + 동영상을 한번에 수집하여
이슈별 종합 시그널을 생성합니다.
"""
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

    # 동영상 (유튜브/네이버TV)
    video_total: int = 0
    video_recent: int = 0
    video_negative: float = 0.0
    video_positive: float = 0.0

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
) -> list[UnifiedSignal]:
    """
    뉴스 + 소셜 통합 수집.

    Parameters:
        keywords: 검색 키워드 리스트
        candidate_name: 우리 후보 이름
        opponents: 상대 후보 이름 리스트
        include_social: 소셜 수집 포함 여부 (False면 뉴스만)

    Returns:
        키워드별 UnifiedSignal 리스트
    """
    opponents = opponents or []

    # 1. 뉴스 수집
    news_signals = _collect_news(
        keywords,
        candidate_name=candidate_name,
        opponents=opponents,
    )
    news_map = {s.keyword: s for s in news_signals}

    results = []

    for kw in keywords:
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

        # 소셜 데이터
        if include_social:
            try:
                blog = search_blogs(kw)
                u.blog_total = blog.total_count
                u.blog_recent = blog.recent_24h
                u.blog_negative = blog.negative_ratio
                u.blog_positive = blog.positive_ratio
                u.top_blogs = blog.top_items[:3]
            except Exception:
                pass

            try:
                cafe = search_cafes(kw)
                u.cafe_total = cafe.total_count
                u.cafe_recent = cafe.recent_24h
                u.cafe_negative = cafe.negative_ratio
                u.cafe_positive = cafe.positive_ratio
                u.top_cafe_posts = cafe.top_items[:3]
            except Exception:
                pass

            try:
                video = search_videos(kw)
                u.video_total = video.total_count
                u.video_recent = video.recent_24h
                u.video_negative = video.negative_ratio
                u.video_positive = video.positive_ratio
            except Exception:
                pass

        # 종합 계산
        channels = []
        if u.news_mentions > 0:
            channels.append(("news", u.news_mentions, u.news_negative))
        if u.blog_total > 0:
            channels.append(("blog", u.blog_recent or u.blog_total, u.blog_negative))
        if u.cafe_total > 0:
            channels.append(("cafe", u.cafe_recent or u.cafe_total, u.cafe_negative))
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
        # 소셜 데이터를 반영하여 mention_count와 velocity 보정
        social_boost = min(u.blog_recent + u.cafe_recent, 50)  # 소셜 최대 50건 보정
        boosted_mentions = (ns.mention_count if ns else 0) + social_boost

        # 소셜에서 부정 비율이 더 높으면 반영
        final_negative = u.combined_negative if channels else (ns.negative_ratio if ns else 0)

        # 카페/블로그에서 활발하면 포털 트렌딩 추정 강화
        social_trending = (u.blog_recent + u.cafe_recent) >= 30

        u.issue_signal = IssueSignal(
            keyword=kw,
            mention_count=boosted_mentions,
            velocity=ns.velocity if ns else (u.total_mentions / 10.0),
            negative_ratio=final_negative,
            media_tier=ns.media_tier if ns else 3,
            candidate_linked=u.candidate_linked,
            portal_trending=(ns.portal_trending if ns else False) or social_trending,
            tv_reported=ns.tv_reported if ns else False,
        )

        results.append(u)

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


# ── 테스트 ───────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

    from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG as c

    signals = collect_unified_signals(
        ["경남도지사 선거", f"{c.candidate_name} 경남", "부울경 행정통합", "경남 청년 정책"],
        candidate_name=c.candidate_name,
        opponents=c.opponents,
    )
    print(format_unified_report(signals))
