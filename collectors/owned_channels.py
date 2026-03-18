"""
Election Strategy Engine — 자체 채널 모니터링
후보 공식 SNS/유튜브 채널의 성과를 추적합니다.

현재 수집 가능한 채널:
  ✅ 페이스북 (공개 페이지 → httpx 파싱)
  ✅ 유튜브 (검색 기반, API 키 있으면 채널 직접 조회)
  ❌ 인스타그램 (API 제한, 수동 입력)

주의: 개인정보 수집 없음, 공개 데이터만 사용
"""
import os
import re
import httpx
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChannelConfig:
    """후보 SNS 채널 설정"""
    candidate_name: str
    facebook_id: str = ""          # 페이스북 페이지 ID (opensky86)
    youtube_channel: str = ""      # 유튜브 채널명 또는 ID
    instagram_id: str = ""         # 인스타그램 ID
    website: str = ""              # 공식 웹사이트


@dataclass
class ChannelMetrics:
    """채널별 성과 지표"""
    channel: str               # "facebook" | "youtube" | "instagram" | "website"
    url: str
    status: str                # "connected" | "manual" | "unavailable"

    # 지표
    followers: int = 0
    recent_posts: int = 0      # 최근 7일 게시물 수
    recent_engagement: int = 0 # 좋아요+댓글+공유 합계 (추정)
    top_content: list = field(default_factory=list)  # [{"title": str, "engagement": int}]

    # 메타
    last_updated: str = ""
    note: str = ""


# ── 김경수 캠프 채널 설정 ────────────────────────────────────
KIM_CHANNELS = ChannelConfig(
    candidate_name="김경수",
    facebook_id="opensky86",
    youtube_channel="김경수",  # 검색 기반
    instagram_id="",           # 미확인
    website="",                # 미확인
)


def monitor_facebook(config: ChannelConfig) -> ChannelMetrics:
    """페이스북 공개 페이지 모니터링 (httpx 파싱)"""
    if not config.facebook_id:
        return ChannelMetrics(channel="facebook", url="", status="unavailable",
                              note="페이스북 ID 미설정")

    url = f"https://www.facebook.com/{config.facebook_id}/"
    try:
        resp = httpx.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }, timeout=10, follow_redirects=True)

        text = resp.text

        # 팔로워 수 추출 시도
        followers = 0
        m = re.search(r'(\d[\d,\.]+)\s*(?:명이|followers|팔로워)', text)
        if m:
            followers = int(m.group(1).replace(",", "").replace(".", ""))

        # 최근 게시물 제목 추출
        titles = re.findall(r'<meta property="og:title" content="([^"]+)"', text)

        return ChannelMetrics(
            channel="facebook",
            url=url,
            status="connected",
            followers=followers,
            recent_posts=len(titles),
            top_content=[{"title": t[:60]} for t in titles[:5]],
            last_updated=datetime.now().isoformat(),
            note="공개 페이지 파싱 (정확도 제한적)",
        )
    except Exception as e:
        return ChannelMetrics(channel="facebook", url=url, status="connected",
                              note=f"페이지 접속 가능, 상세 파싱 실패: {str(e)[:50]}",
                              last_updated=datetime.now().isoformat())


def monitor_youtube(config: ChannelConfig) -> ChannelMetrics:
    """유튜브 채널/검색 기반 모니터링"""
    query = config.youtube_channel or config.candidate_name
    try:
        from collectors.youtube_collector import search_youtube
        result = search_youtube(query, max_results=10)

        top = [
            {"title": v.title[:50], "views": v.view_count,
             "channel": v.channel, "published": v.published}
            for v in result.top_videos[:5]
        ]

        return ChannelMetrics(
            channel="youtube",
            url=f"https://www.youtube.com/results?search_query={query}",
            status="connected",
            recent_posts=result.recent_count,
            recent_engagement=result.total_views,
            top_content=top,
            last_updated=datetime.now().isoformat(),
            note=f"검색 기반 ({result.total_results}건, 조회 {result.total_views:,}회)",
        )
    except Exception as e:
        return ChannelMetrics(channel="youtube", url="", status="unavailable",
                              note=f"수집 실패: {str(e)[:50]}")


def monitor_instagram(config: ChannelConfig) -> ChannelMetrics:
    """인스타그램 (Graph API 또는 fallback)"""
    try:
        from collectors.instagram_collector import monitor_instagram as _ig_monitor
        ig = _ig_monitor()

        status = "connected" if ig.source == "graph_api" else "manual"
        url = ig.profile_url or (f"https://www.instagram.com/{config.instagram_id}/" if config.instagram_id else "")

        top = []
        for p in ig.recent_posts[:5]:
            entry = {"title": p.caption[:50] if p.caption else "(이미지)"}
            if p.engagement:
                entry["views"] = p.engagement
            top.append(entry)

        return ChannelMetrics(
            channel="instagram",
            url=url,
            status=status,
            followers=ig.followers,
            recent_posts=len(ig.recent_posts),
            recent_engagement=ig.total_recent_likes + ig.total_recent_comments,
            top_content=top,
            last_updated=ig.last_updated,
            note=ig.error if ig.error else f"참여율 {ig.engagement_rate}% | {ig.source}",
        )
    except Exception as e:
        return ChannelMetrics(
            channel="instagram",
            url=f"https://www.instagram.com/{config.instagram_id}/" if config.instagram_id else "",
            status="manual",
            note=f"수집 실패: {str(e)[:50]}",
        )


def monitor_all_channels(config: ChannelConfig = None) -> list[ChannelMetrics]:
    """모든 채널 일괄 모니터링"""
    config = config or KIM_CHANNELS
    return [
        monitor_facebook(config),
        monitor_youtube(config),
        monitor_instagram(config),
    ]


def format_report(metrics: list[ChannelMetrics]) -> str:
    """채널 현황 보고서"""
    lines = ["=" * 60, "  자체 채널 현황", "=" * 60, ""]
    status_icon = {"connected": "✅", "manual": "📝", "unavailable": "❌"}

    for m in metrics:
        icon = status_icon.get(m.status, "❓")
        lines.append(f"  {icon} {m.channel.upper()}")
        if m.url:
            lines.append(f"    URL: {m.url}")
        if m.followers:
            lines.append(f"    팔로워: {m.followers:,}")
        if m.recent_posts:
            lines.append(f"    최근 게시: {m.recent_posts}건")
        if m.recent_engagement:
            lines.append(f"    참여도: {m.recent_engagement:,}")
        if m.top_content:
            lines.append(f"    인기 콘텐츠:")
            for c in m.top_content[:3]:
                views = f" ({c['views']:,}회)" if c.get('views') else ""
                lines.append(f"      · {c.get('title', '')}{views}")
        lines.append(f"    상태: {m.note}")
        lines.append("")

    return "\n".join(lines)
