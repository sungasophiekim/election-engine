"""
Election Strategy Engine — Instagram 수집기

2가지 모드:
  1. Graph API 모드 (토큰 있을 때): 비즈니스 계정 인사이트 직접 조회
  2. Fallback 모드 (토큰 없을 때): 네이버/구글 검색으로 간접 추적

Instagram Graph API 연동 방법:
  1. 김경수 인스타 계정을 비즈니스/크리에이터 계정으로 전환
  2. https://developers.facebook.com → 앱 생성
  3. Instagram Graph API 추가 → 페이스북 페이지 연결
  4. 액세스 토큰 생성 (장기 토큰 권장)
  5. .env에 INSTAGRAM_ACCESS_TOKEN=xxx 추가
  6. .env에 INSTAGRAM_BUSINESS_ID=xxx 추가 (비즈니스 계정 ID)

필요한 권한:
  - instagram_basic
  - instagram_manage_insights
  - pages_show_list
  - pages_read_engagement
"""
import os
import re
import httpx
from dataclasses import dataclass, field
from datetime import datetime

INSTAGRAM_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_BIZ_ID = os.getenv("INSTAGRAM_BUSINESS_ID", "")

GRAPH_API_URL = "https://graph.facebook.com/v19.0"


@dataclass
class InstagramPost:
    """인스타그램 게시물 1건"""
    post_id: str = ""
    caption: str = ""
    media_type: str = ""       # IMAGE | VIDEO | CAROUSEL_ALBUM
    permalink: str = ""
    timestamp: str = ""
    like_count: int = 0
    comments_count: int = 0
    engagement: int = 0        # likes + comments


@dataclass
class InstagramMetrics:
    """인스타그램 채널 성과"""
    account_id: str = ""
    username: str = ""
    name: str = ""
    followers: int = 0
    following: int = 0
    media_count: int = 0
    biography: str = ""
    profile_url: str = ""

    # 성과 지표
    recent_posts: list = field(default_factory=list)  # InstagramPost 리스트
    avg_engagement: float = 0.0
    total_recent_likes: int = 0
    total_recent_comments: int = 0
    engagement_rate: float = 0.0   # avg_engagement / followers * 100

    # 메타
    source: str = ""           # "graph_api" | "fallback"
    last_updated: str = ""
    error: str = ""


def _has_token() -> bool:
    return bool(INSTAGRAM_TOKEN and INSTAGRAM_BIZ_ID)


# ═══════════════════════════════════════════════════════════
# 모드 1: Instagram Graph API (토큰 있을 때)
# ═══════════════════════════════════════════════════════════

def _fetch_graph(endpoint: str, params: dict = None) -> dict:
    """Graph API 호출"""
    params = params or {}
    params["access_token"] = INSTAGRAM_TOKEN
    resp = httpx.get(f"{GRAPH_API_URL}/{endpoint}", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_instagram_profile() -> InstagramMetrics:
    """비즈니스 계정 프로필 + 최근 게시물"""
    if not _has_token():
        return _fallback_instagram()

    try:
        # 프로필 정보
        profile = _fetch_graph(INSTAGRAM_BIZ_ID, {
            "fields": "username,name,biography,followers_count,follows_count,media_count,profile_picture_url"
        })

        metrics = InstagramMetrics(
            account_id=INSTAGRAM_BIZ_ID,
            username=profile.get("username", ""),
            name=profile.get("name", ""),
            followers=profile.get("followers_count", 0),
            following=profile.get("follows_count", 0),
            media_count=profile.get("media_count", 0),
            biography=profile.get("biography", ""),
            profile_url=f"https://www.instagram.com/{profile.get('username', '')}/",
            source="graph_api",
            last_updated=datetime.now().isoformat(),
        )

        # 최근 게시물 (최대 25개)
        media = _fetch_graph(f"{INSTAGRAM_BIZ_ID}/media", {
            "fields": "id,caption,media_type,permalink,timestamp,like_count,comments_count",
            "limit": 25,
        })

        posts = []
        total_likes = 0
        total_comments = 0

        for item in media.get("data", []):
            likes = item.get("like_count", 0)
            comments = item.get("comments_count", 0)
            total_likes += likes
            total_comments += comments

            posts.append(InstagramPost(
                post_id=item.get("id", ""),
                caption=(item.get("caption", "") or "")[:100],
                media_type=item.get("media_type", ""),
                permalink=item.get("permalink", ""),
                timestamp=item.get("timestamp", "")[:10],
                like_count=likes,
                comments_count=comments,
                engagement=likes + comments,
            ))

        posts.sort(key=lambda p: p.engagement, reverse=True)

        n = len(posts) or 1
        avg_eng = (total_likes + total_comments) / n
        eng_rate = (avg_eng / max(metrics.followers, 1)) * 100

        metrics.recent_posts = posts[:10]
        metrics.avg_engagement = round(avg_eng, 1)
        metrics.total_recent_likes = total_likes
        metrics.total_recent_comments = total_comments
        metrics.engagement_rate = round(eng_rate, 2)

        return metrics

    except Exception as e:
        return InstagramMetrics(
            source="graph_api",
            error=f"Graph API 오류: {str(e)[:80]}",
            last_updated=datetime.now().isoformat(),
        )


# ═══════════════════════════════════════════════════════════
# 모드 2: Fallback (토큰 없을 때 — 검색 기반 간접 추적)
# ═══════════════════════════════════════════════════════════

def _fallback_instagram(username: str = "") -> InstagramMetrics:
    """네이버 검색으로 인스타그램 활동 간접 추적"""
    from collectors.naver_news import search_news

    query = f"김경수 인스타그램" if not username else f"{username} 인스타그램"

    try:
        articles = search_news(query, display=20)
        blog_mentions = 0
        sample_titles = []

        for a in articles:
            sample_titles.append(a["title"][:60])
            if "인스타" in a["title"]:
                blog_mentions += 1

        # 네이버 블로그에서도 검색
        from collectors.social_collector import search_blogs
        blog = search_blogs(query, display=20)

        return InstagramMetrics(
            username=username or "미확인",
            profile_url=f"https://www.instagram.com/{username}/" if username else "",
            recent_posts=[
                InstagramPost(caption=t) for t in sample_titles[:5]
            ],
            source="fallback",
            last_updated=datetime.now().isoformat(),
            error=(
                "Instagram API 토큰 미설정. 검색 기반 간접 추적 중.\n"
                "연동 방법:\n"
                "1. 인스타 비즈니스 계정 전환\n"
                "2. Meta Developer 앱 생성 → Instagram Graph API\n"
                "3. .env에 INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ID 추가"
            ),
        )
    except Exception as e:
        return InstagramMetrics(
            source="fallback",
            error=f"Fallback 수집 실패: {str(e)[:50]}",
            last_updated=datetime.now().isoformat(),
        )


# ═══════════════════════════════════════════════════════════
# 통합 함수
# ═══════════════════════════════════════════════════════════

def monitor_instagram() -> InstagramMetrics:
    """인스타그램 모니터링 (토큰 유무에 따라 자동 선택)"""
    if _has_token():
        return fetch_instagram_profile()
    else:
        username = os.getenv("INSTAGRAM_USERNAME", "")
        return _fallback_instagram(username)


# ── 테스트 ───────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

    # 토큰 상태 확인
    print(f"Instagram Token: {'있음' if _has_token() else '없음 (fallback 모드)'}")
    print()

    result = monitor_instagram()
    print(f"=== Instagram 모니터링 ===")
    print(f"소스: {result.source}")
    print(f"계정: {result.username}")
    if result.followers:
        print(f"팔로워: {result.followers:,}")
        print(f"게시물: {result.media_count}")
        print(f"참여율: {result.engagement_rate}%")
    if result.recent_posts:
        print(f"\n최근 게시물:")
        for p in result.recent_posts[:5]:
            eng = f" ({p.engagement:,})" if p.engagement else ""
            print(f"  · {p.caption[:50]}{eng}")
    if result.error:
        print(f"\n{result.error}")
