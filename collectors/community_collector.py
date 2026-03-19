"""
Election Strategy Engine — 한국 커뮤니티 수집기
API 없는 주요 커뮤니티를 Google/Naver 검색으로 간접 모니터링합니다.

수집 방법: site:커뮤니티도메인 키워드 → 검색 결과 건수 + 제목 + 감성
직접 스크래핑 없음 — 검색 엔진 결과만 사용 (합법적)
"""
import os
import re
import httpx
from dataclasses import dataclass, field
from datetime import datetime


# ── 한국 주요 커뮤니티 정의 ──────────────────────────────────
COMMUNITIES = {
    "dcinside": {
        "name": "DC인사이드",
        "domain": "dcinside.com",
        "type": "정치/이슈",
        "demographic": "전 연령 남성 중심",
        "influence": "매우 높음 — 프레임/밈 생산지",
        "icon": "🟥",
    },
    "fmkorea": {
        "name": "에펨코리아",
        "domain": "fmkorea.com",
        "type": "종합",
        "demographic": "2030 남성",
        "influence": "높음 — 정치 여론 바로미터",
        "icon": "🟦",
    },
    "clien": {
        "name": "클리앙",
        "domain": "clien.net",
        "type": "IT/시사",
        "demographic": "3040 남성, 진보 성향",
        "influence": "중간",
        "icon": "🟩",
    },
    "ppomppu": {
        "name": "뽐뿌",
        "domain": "ppomppu.co.kr",
        "type": "생활/쇼핑",
        "demographic": "3040 중도",
        "influence": "중간 — 민생 여론",
        "icon": "🟧",
    },
    "ruliweb": {
        "name": "루리웹",
        "domain": "ruliweb.com",
        "type": "게임/문화",
        "demographic": "2030",
        "influence": "중간",
        "icon": "🟪",
    },
    "theqoo": {
        "name": "더쿠",
        "domain": "theqoo.net",
        "type": "연예/이슈",
        "demographic": "2030 여성",
        "influence": "높음 — 여성 여론",
        "icon": "🩷",
    },
    "natepann": {
        "name": "네이트판",
        "domain": "pann.nate.com",
        "type": "자유/이슈",
        "demographic": "전 연령",
        "influence": "높음 — 대중 여론",
        "icon": "🟨",
    },
}


@dataclass
class CommunitySignal:
    """커뮤니티 1곳 시그널"""
    community_id: str
    name: str
    icon: str
    keyword: str
    result_count: int           # 검색 결과 건수
    recent_titles: list[str]    # 최근 게시물 제목
    negative_ratio: float = 0.0
    positive_ratio: float = 0.0
    tone: str = ""              # 전체 분위기
    sample_url: str = ""


@dataclass
class CommunityReport:
    """전체 커뮤니티 종합 보고"""
    keyword: str
    signals: list[CommunitySignal]
    total_mentions: int = 0
    hottest_community: str = ""
    overall_tone: str = ""
    timestamp: str = ""


# 감성 키워드
# 감성 키워드 — 커뮤니티 특화 (과잉 판정 방지)
_NEG = ["논란", "비판", "반발", "실패", "거짓", "폭로", "구라", "답없", "무능", "탈당", "퇴진"]
_POS = ["지지", "기대", "좋다", "성과", "찬성", "응원", "비전", "잘한다", "화이팅",
        "대단", "대박", "레전드", "인정", "공감", "당선", "기대된다"]


def _naver_search_site(keyword: str, domain: str, display: int = 30) -> tuple:
    """네이버 검색에서 특정 사이트 결과 조회"""
    client_id = os.getenv("NAVER_CLIENT_ID", "")
    client_secret = os.getenv("NAVER_CLIENT_SECRET", "")
    if not client_id:
        return [], 0

    # site: 검색이 네이버 API에서는 지원 안 됨 → 도메인 + 2026 연도 필터
    query = f"{keyword} {domain} 2026"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }

    try:
        # 웹 검색 사용 (블로그/뉴스보다 커뮤니티 결과 잘 잡힘)
        resp = httpx.get(
            "https://openapi.naver.com/v1/search/webkr.json",
            params={"query": query, "display": display, "sort": "date"},
            headers=headers, timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        total = data.get("total", 0)

        items = []
        for item in data.get("items", []):
            title = re.sub(r"<[^>]+>", "", item.get("title", ""))
            link = item.get("link", "")
            # 해당 도메인 결과만 필터
            if domain in link:
                items.append({"title": title, "link": link})

        return items, total
    except Exception:
        return [], 0


def _google_search_site(keyword: str, domain: str) -> tuple:
    """Google 검색으로 특정 사이트 결과 조회 (fallback)"""
    try:
        query = f"site:{domain} {keyword}"
        resp = httpx.get(
            "https://www.google.com/search",
            params={"q": query, "hl": "ko", "num": 10},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9",
            },
            timeout=10,
            follow_redirects=True,
        )
        text = resp.text

        # 대략적 결과 수 추출
        count_match = re.search(r'약 ([\d,]+)개', text)
        count = int(count_match.group(1).replace(",", "")) if count_match else 0

        # 제목 추출
        titles = re.findall(r'<h3[^>]*>([^<]+)</h3>', text)

        items = [{"title": t, "link": ""} for t in titles[:10]]
        return items, count
    except Exception:
        return [], 0


def _analyze_tone(titles: list[str]) -> tuple:
    """제목 리스트의 감성 분석"""
    if not titles:
        return 0.0, 0.0, "데이터 없음"

    neg = pos = 0
    for t in titles:
        if any(kw in t for kw in _NEG):
            neg += 1
        if any(kw in t for kw in _POS):
            pos += 1

    n = len(titles)
    neg_r = round(neg / n, 2)
    pos_r = round(pos / n, 2)

    if neg_r > 0.5:
        tone = "부정적 🔴"
    elif pos_r > 0.3:
        tone = "긍정적 🟢"
    elif pos_r > neg_r:
        tone = "다소 긍정 🟢"
    elif neg_r > pos_r + 0.1:
        tone = "다소 부정 🟡"
    else:
        tone = "중립 ⚪"

    return neg_r, pos_r, tone


def search_community(
    keyword: str,
    community_id: str,
) -> CommunitySignal:
    """특정 커뮤니티에서 키워드 검색"""
    comm = COMMUNITIES.get(community_id)
    if not comm:
        return CommunitySignal(
            community_id=community_id, name="?", icon="?",
            keyword=keyword, result_count=0, recent_titles=[],
        )

    # 네이버 웹 검색 먼저, 실패하면 Google
    items, total = _naver_search_site(keyword, comm["domain"])
    if not items:
        items, total = _google_search_site(keyword, comm["domain"])

    titles = [i["title"] for i in items]
    neg_r, pos_r, tone = _analyze_tone(titles)

    return CommunitySignal(
        community_id=community_id,
        name=comm["name"],
        icon=comm["icon"],
        keyword=keyword,
        result_count=total,
        recent_titles=titles[:10],
        negative_ratio=neg_r,
        positive_ratio=pos_r,
        tone=tone,
        sample_url=items[0]["link"] if items and items[0].get("link") else "",
    )


def scan_all_communities(keyword: str) -> CommunityReport:
    """모든 커뮤니티 병렬 스캔"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    signals = []
    total = 0
    max_count = 0
    hottest = ""

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(search_community, keyword, cid): cid for cid in COMMUNITIES}
        for f in as_completed(futures):
            try:
                sig = f.result(timeout=5)
                signals.append(sig)
                total += sig.result_count
                if sig.result_count > max_count:
                    max_count = sig.result_count
                    hottest = sig.name
            except Exception:
                pass

    # 전체 톤
    all_titles = []
    for s in signals:
        all_titles.extend(s.recent_titles)
    _, _, overall_tone = _analyze_tone(all_titles)

    return CommunityReport(
        keyword=keyword,
        signals=sorted(signals, key=lambda s: s.result_count, reverse=True),
        total_mentions=total,
        hottest_community=hottest,
        overall_tone=overall_tone,
        timestamp=datetime.now().isoformat(),
    )


def scan_multiple_keywords(keywords: list[str]) -> dict:
    """여러 키워드 × 모든 커뮤니티"""
    results = {}
    for kw in keywords:
        results[kw] = scan_all_communities(kw)
    return results
