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


# ── 유튜브 댓글 수집 + 감성 분석 ────────────────────────────────

@dataclass
class YouTubeComment:
    """유튜브 댓글 1건"""
    text: str
    author: str = ""
    like_count: int = 0
    published: str = ""
    sentiment: str = ""      # "positive" | "negative" | "neutral"


@dataclass
class YouTubeCommentSignal:
    """영상 1개의 댓글 분석 결과"""
    video_id: str
    video_title: str = ""
    total_comments: int = 0
    fetched_comments: int = 0
    comments: list = field(default_factory=list)  # list[YouTubeComment]

    # 감성 집계
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    net_sentiment: float = 0.0     # -1.0 ~ +1.0
    dominant_sentiment: str = ""   # "positive" | "negative" | "neutral"

    # 주요 키워드
    top_keywords: list = field(default_factory=list)   # [{"word": str, "count": int}]
    mobilization_detected: bool = False  # "투표", "심판" 등 동원 키워드


@dataclass
class YouTubeCommentReport:
    """키워드별 유튜브 댓글 종합"""
    keyword: str
    videos_analyzed: int = 0
    total_comments: int = 0
    signals: list = field(default_factory=list)  # list[YouTubeCommentSignal]

    # 종합 감성
    net_sentiment: float = 0.0
    positive_ratio: float = 0.0
    negative_ratio: float = 0.0
    dominant_sentiment: str = ""
    mobilization_detected: bool = False

    # 대표 댓글
    top_positive: list = field(default_factory=list)   # [str]
    top_negative: list = field(default_factory=list)   # [str]

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "videos_analyzed": self.videos_analyzed,
            "total_comments": self.total_comments,
            "net_sentiment": round(self.net_sentiment, 3),
            "positive_ratio": round(self.positive_ratio, 2),
            "negative_ratio": round(self.negative_ratio, 2),
            "dominant_sentiment": self.dominant_sentiment,
            "mobilization_detected": self.mobilization_detected,
            "top_positive": self.top_positive[:3],
            "top_negative": self.top_negative[:3],
        }


# 댓글 감성 사전
_COMMENT_NEG = [
    "실망", "최악", "거짓", "사기", "반대", "못해", "쓰레기",
    "싫", "문제", "비판", "논란", "허위", "무능", "도망",
    "걱정", "위험", "실패", "후퇴", "답답", "한심",
]
_COMMENT_POS = [
    "지지", "응원", "기대", "좋아", "훌륭", "최고", "파이팅",
    "감사", "대단", "멋지", "옳", "찬성", "공감", "변화",
    "발전", "성공", "혁신", "잘해", "응원합니다", "화이팅",
]
_MOBILIZATION = ["투표", "심판", "반드시", "꼭", "국민의힘", "민주당", "찍자", "뽑자", "정권교체"]


def _classify_comment(text: str) -> str:
    """단순 사전 기반 댓글 감성 분류"""
    neg = sum(1 for w in _COMMENT_NEG if w in text)
    pos = sum(1 for w in _COMMENT_POS if w in text)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def fetch_video_comments(
    video_id: str,
    max_comments: int = 50,
    video_title: str = "",
) -> YouTubeCommentSignal:
    """
    YouTube Data API v3으로 영상 1개의 댓글을 수집합니다.
    API 비용: commentThreads.list = 1 unit (저렴)
    """
    result = YouTubeCommentSignal(video_id=video_id, video_title=video_title)

    if not _has_api_key():
        return result

    try:
        from googleapiclient.discovery import build
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

        resp = youtube.commentThreads().list(
            videoId=video_id,
            part="snippet",
            maxResults=min(max_comments, 100),
            order="relevance",
            textFormat="plainText",
        ).execute()

        result.total_comments = resp.get("pageInfo", {}).get("totalResults", 0)
        comments = []

        for item in resp.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            text = snippet.get("textDisplay", "")
            sentiment = _classify_comment(text)

            comment = YouTubeComment(
                text=text[:200],
                author=snippet.get("authorDisplayName", ""),
                like_count=snippet.get("likeCount", 0),
                published=snippet.get("publishedAt", "")[:10],
                sentiment=sentiment,
            )
            comments.append(comment)

            if sentiment == "positive":
                result.positive_count += 1
            elif sentiment == "negative":
                result.negative_count += 1
            else:
                result.neutral_count += 1

        result.comments = comments
        result.fetched_comments = len(comments)

        # 감성 집계
        total = result.positive_count + result.negative_count + result.neutral_count
        if total > 0:
            result.net_sentiment = (result.positive_count - result.negative_count) / total
            if result.positive_count > result.negative_count:
                result.dominant_sentiment = "positive"
            elif result.negative_count > result.positive_count:
                result.dominant_sentiment = "negative"
            else:
                result.dominant_sentiment = "neutral"

        # 동원 키워드 감지
        all_text = " ".join(c.text for c in comments)
        result.mobilization_detected = any(kw in all_text for kw in _MOBILIZATION)

    except Exception as e:
        # 댓글 비활성화 영상 등
        if "commentsDisabled" not in str(e):
            print(f"  [YouTube Comments] video={video_id} 실패: {e}")

    return result


def fetch_keyword_comments(
    keyword: str,
    top_n_videos: int = 3,
    max_comments_per_video: int = 30,
) -> YouTubeCommentReport:
    """
    키워드 검색 → 상위 N개 영상 → 각 영상 댓글 수집 → 종합 감성.

    API 비용: search(100) + commentThreads(1) × N = ~103 units
    """
    report = YouTubeCommentReport(keyword=keyword)

    # 먼저 영상 검색
    yt_signal = search_youtube(keyword, max_results=top_n_videos)
    if not yt_signal.top_videos:
        return report

    videos_to_analyze = [v for v in yt_signal.top_videos[:top_n_videos] if v.video_id]
    if not videos_to_analyze:
        return report

    total_pos = 0
    total_neg = 0
    total_neu = 0
    all_positive_comments = []
    all_negative_comments = []

    for video in videos_to_analyze:
        cs = fetch_video_comments(
            video_id=video.video_id,
            max_comments=max_comments_per_video,
            video_title=video.title,
        )
        report.signals.append(cs)
        total_pos += cs.positive_count
        total_neg += cs.negative_count
        total_neu += cs.neutral_count
        report.total_comments += cs.fetched_comments

        if cs.mobilization_detected:
            report.mobilization_detected = True

        # 대표 댓글 수집 (좋아요 많은 순)
        sorted_comments = sorted(cs.comments, key=lambda c: c.like_count, reverse=True)
        for c in sorted_comments[:3]:
            if c.sentiment == "positive" and len(all_positive_comments) < 5:
                all_positive_comments.append(c.text[:100])
            elif c.sentiment == "negative" and len(all_negative_comments) < 5:
                all_negative_comments.append(c.text[:100])

    report.videos_analyzed = len(videos_to_analyze)
    report.top_positive = all_positive_comments
    report.top_negative = all_negative_comments

    # 종합 감성
    total = total_pos + total_neg + total_neu
    if total > 0:
        report.positive_ratio = total_pos / total
        report.negative_ratio = total_neg / total
        report.net_sentiment = (total_pos - total_neg) / total
        if total_pos > total_neg:
            report.dominant_sentiment = "positive"
        elif total_neg > total_pos:
            report.dominant_sentiment = "negative"
        else:
            report.dominant_sentiment = "neutral"

    return report


def search_youtube_bulk(keywords: list[str], max_per_kw: int = 10) -> dict:
    """
    여러 키워드 일괄 검색.
    Returns: {keyword: YouTubeSignal}
    """
    results = {}
    for kw in keywords:
        results[kw] = search_youtube(kw, max_results=max_per_kw)
    return results
