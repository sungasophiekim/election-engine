"""
Election Strategy Engine — YouTube 수집기
YouTube Data API v3로 선거 관련 동영상 데이터를 수집합니다.

API 키 발급: https://console.cloud.google.com/apis/credentials
  → API 및 서비스 → 사용자 인증정보 → API 키 생성
  → YouTube Data API v3 활성화

무료: 10,000 units/일 (search = 100 units, 약 100회 검색)
"""
import os
import re
from datetime import datetime, timedelta
from dataclasses import dataclass, field

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")


@dataclass
class YouTubeVideo:
    """유튜브 동영상 1건"""
    video_id: str
    title: str
    channel: str
    published: str
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    description: str = ""
    thumbnail: str = ""


@dataclass
class YouTubeSignal:
    """유튜브 키워드 시그널"""
    keyword: str
    total_results: int
    recent_count: int          # 최근 7일 내 영상 수
    total_views: int           # 상위 영상 조회수 합계
    avg_views: int
    top_videos: list           # YouTubeVideo 리스트
    negative_ratio: float = 0.0
    positive_ratio: float = 0.0
    sentiment_keywords: dict = field(default_factory=dict)


# 감성 키워드
_NEG = ["논란", "비판", "의혹", "실패", "문제", "반발", "거짓", "폭로", "위기"]
_POS = ["지지", "환영", "성과", "비전", "혁신", "발전", "약속", "기대", "공약"]


def _has_api_key() -> bool:
    return bool(YOUTUBE_API_KEY)


def search_youtube(
    query: str,
    max_results: int = 20,
    days: int = 30,
) -> YouTubeSignal:
    """
    YouTube Data API v3으로 검색.
    API 키 없으면 빈 결과 반환 (graceful).
    """
    if not _has_api_key():
        return _search_youtube_fallback(query)

    try:
        from googleapiclient.discovery import build

        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

        # 날짜 필터
        after = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")

        # 검색
        search_resp = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            order="relevance",
            publishedAfter=after,
            maxResults=min(max_results, 50),
            regionCode="KR",
            relevanceLanguage="ko",
        ).execute()

        video_ids = [item["id"]["videoId"] for item in search_resp.get("items", [])]
        total_results = search_resp.get("pageInfo", {}).get("totalResults", 0)

        if not video_ids:
            return YouTubeSignal(keyword=query, total_results=0, recent_count=0,
                                 total_views=0, avg_views=0, top_videos=[])

        # 상세 정보 (조회수, 좋아요, 댓글)
        stats_resp = youtube.videos().list(
            id=",".join(video_ids),
            part="snippet,statistics",
        ).execute()

        videos = []
        total_views = 0
        recent_7d = 0
        cutoff_7d = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"
        neg_count = 0
        pos_count = 0

        for item in stats_resp.get("items", []):
            snippet = item["snippet"]
            stats = item.get("statistics", {})
            views = int(stats.get("viewCount", 0))
            total_views += views

            pub = snippet.get("publishedAt", "")
            if pub > cutoff_7d:
                recent_7d += 1

            title = snippet.get("title", "")
            desc = snippet.get("description", "")[:200]
            text = title + " " + desc

            if any(kw in text for kw in _NEG):
                neg_count += 1
            if any(kw in text for kw in _POS):
                pos_count += 1

            videos.append(YouTubeVideo(
                video_id=item["id"],
                title=title,
                channel=snippet.get("channelTitle", ""),
                published=pub[:10],
                view_count=views,
                like_count=int(stats.get("likeCount", 0)),
                comment_count=int(stats.get("commentCount", 0)),
                description=desc,
                thumbnail=snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
            ))

        videos.sort(key=lambda v: v.view_count, reverse=True)
        n = len(videos) or 1

        return YouTubeSignal(
            keyword=query,
            total_results=total_results,
            recent_count=recent_7d,
            total_views=total_views,
            avg_views=total_views // n,
            top_videos=videos[:10],
            negative_ratio=round(neg_count / n, 2),
            positive_ratio=round(pos_count / n, 2),
        )

    except Exception as e:
        print(f"  [YouTube] '{query}' 검색 실패: {e}")
        return _search_youtube_fallback(query)


def _search_youtube_fallback(query: str) -> YouTubeSignal:
    """API 키 없을 때 httpx로 유튜브 검색 페이지 파싱 (기본 정보만)"""
    try:
        import httpx
        resp = httpx.get(
            "https://www.youtube.com/results",
            params={"search_query": query},
            headers={"Accept-Language": "ko-KR"},
            timeout=10,
            follow_redirects=True,
        )
        text = resp.text
        # 대략적인 영상 수 추출
        titles = re.findall(r'"title":\{"runs":\[\{"text":"([^"]{5,80})"\}', text)
        views_raw = re.findall(r'조회수 ([\d,]+)회', text)
        views = [int(v.replace(",", "")) for v in views_raw[:10]]

        videos = []
        for i, title in enumerate(titles[:10]):
            videos.append(YouTubeVideo(
                video_id="", title=title, channel="",
                published="", view_count=views[i] if i < len(views) else 0,
            ))

        total_views = sum(views)
        return YouTubeSignal(
            keyword=query,
            total_results=len(titles),
            recent_count=len(titles),
            total_views=total_views,
            avg_views=total_views // max(len(views), 1),
            top_videos=videos,
        )
    except Exception as e:
        print(f"  [YouTube fallback] '{query}' 실패: {e}")
        return YouTubeSignal(keyword=query, total_results=0, recent_count=0,
                             total_views=0, avg_views=0, top_videos=[])


def search_youtube_bulk(keywords: list[str], max_per_kw: int = 10) -> dict:
    """
    여러 키워드 일괄 검색.
    Returns: {keyword: YouTubeSignal}
    """
    results = {}
    for kw in keywords:
        results[kw] = search_youtube(kw, max_results=max_per_kw)
    return results


# ── 테스트 ───────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

    # API 키 상태
    key = os.getenv("YOUTUBE_API_KEY", "")
    print(f"YouTube API Key: {'있음' if key else '없음 (fallback 모드)'}")

    result = search_youtube("경남도지사 선거", max_results=10)
    print(f"\n=== '{result.keyword}' ===")
    print(f"검색 결과: {result.total_results}건 | 최근 7일: {result.recent_count}건")
    print(f"총 조회수: {result.total_views:,} | 평균: {result.avg_views:,}")
    print(f"\nTOP 영상:")
    for v in result.top_videos[:5]:
        print(f"  {v.view_count:>10,}회 | {v.title[:50]}")
