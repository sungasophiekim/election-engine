"""
Election Strategy Engine — 한국 커뮤니티 수집기
API 없는 주요 커뮤니티를 Google/Naver 검색으로 간접 모니터링합니다.

수집 방법: site:커뮤니티도메인 키워드 → 검색 결과 건수 + 제목 + 감성
직접 스크래핑 없음 — 검색 엔진 결과만 사용 (합법적)
"""
import os
import re
import time
import threading
import httpx
from dataclasses import dataclass, field
from datetime import datetime

# 네이버 API 글로벌 rate limiter (초당 10건 제한 → 0.12초 간격)
_naver_lock = threading.Lock()
_naver_last_call = 0.0
_NAVER_MIN_INTERVAL = 0.12  # 초당 ~8건 (안전 마진)


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
    "todayhumor": {
        "name": "오늘의유머",
        "domain": "todayhumor.co.kr",
        "type": "유머/시사",
        "demographic": "3040 남성, 진보 성향",
        "influence": "높음 — 정치 유머/풍자",
        "icon": "😂",
    },
    "mlbpark": {
        "name": "MLB파크",
        "domain": "mlbpark.donga.com",
        "type": "스포츠/시사",
        "demographic": "3040 남성",
        "influence": "중간 — BULLPEN 정치 토론",
        "icon": "⚾",
    },
    # momcafe 제거 — social_collector의 네이버 카페 API와 중복 (이중 카운트 방지)
    # "경남 맘카페" 키워드가 별도 이슈 추적에 포함되어 있으므로 커버됨
    "yeosidae": {
        "name": "여성시대",
        "domain": "yeosidae.com",
        "type": "여성/이슈",
        "demographic": "2040 여성",
        "influence": "중간 — 여성 의제 여론",
        "icon": "👩",
    },
    # ── 중도·진보 주요 커뮤니티 (캠프 전략 보고서 기반) ──
    "damoa": {
        "name": "다모앙",
        "domain": "damoang.net",
        "type": "IT/시사",
        "demographic": "3050 (클리앙 이주민, 진보 결집지)",
        "influence": "높음 — 2024 신생, 진보 새 거점",
        "icon": "🟦",
    },
    "ddanzi": {
        "name": "딴지일보",
        "domain": "ddanzi.com",
        "type": "풍자/시사",
        "demographic": "4050 열성 지지층",
        "influence": "높음 — 강한 어조, 열성 지지층 온도계",
        "icon": "🔥",
    },
    "bobae": {
        "name": "보배드림",
        "domain": "bobaedream.co.kr",
        "type": "자동차/시사",
        "demographic": "3050 남성",
        "influence": "높음 — 자동차 기반이나 정치 화력 강함",
        "icon": "🚗",
    },
    "82cook": {
        "name": "82쿡",
        "domain": "82cook.com",
        "type": "살림/시사",
        "demographic": "3050 여성 (진보 합리주의)",
        "influence": "높음 — 살림+사회현안, 진지한 토론",
        "icon": "🍳",
    },
    "instiz": {
        "name": "인스티즈",
        "domain": "instiz.net",
        "type": "연예/이슈",
        "demographic": "1020 여성",
        "influence": "중간 — 젊은 여성, 인권/복지 우호",
        "icon": "💜",
    },
    "slrclub": {
        "name": "SLR클럽",
        "domain": "slrclub.com",
        "type": "사진/시사",
        "demographic": "3050 남성 (중도진보)",
        "influence": "중간 — 중장년 남성 여론 형성지",
        "icon": "📷",
    },
    # ── 경남 맘카페 (개별 등록 — 캠프 전략 보고서 기반) ──
    "momcafe_changwon": {
        "name": "창원줌마렐라",
        "domain": "cafe.naver.com/changwonjoom",
        "type": "육아/생활",
        "demographic": "3040 여성 (창원/함안)",
        "influence": "매우 높음 — 경남 최대 25만, 창원 여론의 핵",
        "icon": "👩‍👧",
        "search_suffix": "창원줌마렐라",
        "region": "창원",
        "members": 250000,
    },
    "momcafe_gimhae": {
        "name": "김해줌마렐라",
        "domain": "cafe.naver.com/gimhaejoom",
        "type": "육아/생활",
        "demographic": "3040 여성 (김해)",
        "influence": "높음 — 11만, 김해 신도시 민심 척도",
        "icon": "👩‍👧",
        "search_suffix": "김해줌마렐라",
        "region": "김해",
        "members": 110000,
    },
    "momcafe_jinju": {
        "name": "진주아지매",
        "domain": "cafe.naver.com/jinjuajimae",
        "type": "육아/생활",
        "demographic": "3040 여성 (진주/서부경남)",
        "influence": "높음 — 8.5만, 서부경남 여론 주도",
        "icon": "👩‍👧",
        "search_suffix": "진주아지매",
        "region": "진주",
        "members": 85000,
    },
    "momcafe_yangsan": {
        "name": "러브양산맘",
        "domain": "cafe.naver.com/loveyangsan",
        "type": "육아/생활",
        "demographic": "3040 여성 (양산 물금/사송)",
        "influence": "높음 — 8.5만, 양산 신도시 3040 결집지",
        "icon": "👩‍👧",
        "search_suffix": "러브양산맘",
        "region": "양산",
        "members": 85000,
    },
    "momcafe_sacheon": {
        "name": "우리끼리미수다",
        "domain": "cafe.naver.com/sacheonmom",
        "type": "육아/생활",
        "demographic": "3040 여성 (사천/삼천포)",
        "influence": "중간 — 5.5만, 항공우주 배후",
        "icon": "👩‍👧",
        "search_suffix": "우리끼리미수다 사천",
        "region": "사천",
        "members": 55000,
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

    # v2: reaction intelligence
    has_viral_signals: bool = False   # 인기글/추천글 패턴 감지 여부
    viral_title_count: int = 0       # 바이럴 패턴이 감지된 제목 수
    derision_score: float = 0.0      # 조롱/비아냥 톤 비율 (0.0~1.0)
    slang_density: float = 0.0       # 비속어/인터넷 은어 밀도


@dataclass
class CommunityReport:
    """전체 커뮤니티 종합 보고"""
    keyword: str
    signals: list[CommunitySignal]
    total_mentions: int = 0
    hottest_community: str = ""
    overall_tone: str = ""
    timestamp: str = ""

    # v2: 커뮤니티 전체 반응 종합
    community_resonance: float = 0.0  # 0.0~1.0, 커뮤니티 전체 공명도
    has_any_viral: bool = False       # 어느 커뮤니티든 바이럴 감지 여부
    dominant_tone: str = ""           # "조롱", "분노", "지지", "무관심" 등


# 감성 키워드
# 감성 키워드 — 커뮤니티 특화 (과잉 판정 방지)
_NEG = ["논란", "비판", "반발", "실패", "거짓", "폭로", "구라", "답없", "무능", "탈당", "퇴진"]
_POS = ["지지", "기대", "좋다", "성과", "찬성", "응원", "비전", "잘한다", "화이팅",
        "대단", "대박", "레전드", "인정", "공감", "당선", "기대된다"]

# v2: 조롱/비아냥 톤 키워드 (커뮤니티 특화)
_DERISION = [
    "ㅋㅋ", "ㅎㅎ", "웃기", "코미디", "개그", "어이없", "헛소리", "뻔뻔",
    "장난", "역대급", "레전드 ㅋ", "어그로", "핵노잼", "핵꿀잼", "웃프",
    "짤", "패러디", "개꿀", "ㄹㅇ", "존웃",
]

# v2: 인터넷 은어/비속어 (슬랭 밀도 측정용)
_SLANG = [
    "ㅅㅂ", "ㅈㄹ", "ㄲㅈ", "ㅁㅊ", "ㄴㅁ", "ㅂㅅ",
    "존나", "졸라", "씹", "개같", "지랄", "미친",
]

# v2: 인기글/바이럴 제목 패턴 (추천수, 조회수 표시 커뮤니티)
_VIRAL_PATTERNS = re.compile(
    r'\[(\d{2,})\]'          # [123] — DC, FM 추천수/조회수
    r'|(?:추천|개추)\s*\d+'  # 추천 123
    r'|(?:조회|읽음)\s*\d+'  # 조회 1234
    r'|베스트|인기|HOT'       # 인기글 카테고리
)


def _naver_rate_limit():
    """글로벌 rate limiter — 병렬 호출에서도 초당 10건 미만 보장"""
    global _naver_last_call
    with _naver_lock:
        now = time.time()
        elapsed = now - _naver_last_call
        if elapsed < _NAVER_MIN_INTERVAL:
            time.sleep(_NAVER_MIN_INTERVAL - elapsed)
        _naver_last_call = time.time()


def _naver_search_site(keyword: str, domain: str, display: int = 30) -> tuple:
    """네이버 검색에서 특정 사이트 결과 조회 (v2: 품질 개선)"""
    client_id = os.getenv("NAVER_CLIENT_ID", "")
    client_secret = os.getenv("NAVER_CLIENT_SECRET", "")
    if not client_id:
        return [], 0

    # search_suffix가 있으면 도메인 대신 사용 (맘카페 등)
    search_extra = COMMUNITIES.get("", {}).get("search_suffix", "")

    # v2: 도메인 직접 포함 + 최근 날짜 필터
    # 네이버 웹검색에서 site: 미지원 → "keyword site:domain" 패턴
    query = f"{keyword} site:{domain}"

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }

    _naver_rate_limit()
    try:
        resp = httpx.get(
            "https://openapi.naver.com/v1/search/webkr.json",
            params={"query": query, "display": display, "sort": "date"},
            headers=headers, timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        items = []
        seen_titles = set()  # v2: 중복 제거
        for item in data.get("items", []):
            title = re.sub(r"<[^>]+>", "", item.get("title", ""))
            link = item.get("link", "")
            desc = re.sub(r"<[^>]+>", "", item.get("description", ""))

            # v2: 도메인 필터 강화
            if domain not in link:
                continue

            # v2: 제목 중복 제거 (같은 글이 여러 번 잡히는 것 방지)
            title_key = title[:30].strip()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)

            items.append({
                "title": title,
                "link": link,
                "description": desc,  # v2: 본문 미리보기 추가
            })

        # v2: total은 실제 매칭된 건수 사용 (네이버 추정 total 대신)
        actual_count = len(items)
        # 네이버가 반환한 total을 참고하되, 실제 필터링 결과로 보정
        raw_total = data.get("total", 0)
        # 실제 매칭률 기반 추정 (display 30개 중 실제 도메인 매칭 비율)
        raw_items = len(data.get("items", []))
        if raw_items > 0:
            match_ratio = actual_count / raw_items
            estimated_total = int(raw_total * match_ratio)
        else:
            estimated_total = 0

        return items, estimated_total
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


def _analyze_tone(titles: list[str], items: list[dict] = None) -> tuple:
    """제목 + 본문 미리보기의 감성 분석 (v2: description 활용)"""
    if not titles:
        return 0.0, 0.0, "데이터 없음"

    items = items or []
    neg = pos = 0
    for i, t in enumerate(titles):
        # v2: 제목 + description 결합 분석
        text = t
        if i < len(items) and items[i].get("description"):
            text += " " + items[i]["description"]

        if any(kw in text for kw in _NEG):
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


def _analyze_reaction_depth(titles: list[str]) -> dict:
    """
    v2: 제목 리스트에서 반응 깊이 분석.
    - has_viral_signals: 인기글 패턴 감지 여부
    - viral_title_count: 바이럴 패턴이 있는 제목 수
    - derision_score: 조롱/비아냥 톤 비율
    - slang_density: 비속어/은어 밀도
    """
    if not titles:
        return {"has_viral_signals": False, "viral_title_count": 0,
                "derision_score": 0.0, "slang_density": 0.0}

    viral_count = 0
    derision_count = 0
    slang_count = 0

    for t in titles:
        if _VIRAL_PATTERNS.search(t):
            viral_count += 1
        if any(kw in t for kw in _DERISION):
            derision_count += 1
        if any(kw in t for kw in _SLANG):
            slang_count += 1

    n = len(titles)
    return {
        "has_viral_signals": viral_count > 0,
        "viral_title_count": viral_count,
        "derision_score": round(derision_count / n, 3),
        "slang_density": round(slang_count / n, 3),
    }


# ── 공개 커뮤니티 본문 크롤링 (5곳) ───────────────────────────
# DC인사이드, 에펨코리아, 클리앙, 더쿠, 네이트판
# 맘카페(네이버 카페)는 폐쇄형이므로 기존 API 방식 유지

_SCRAPE_CONFIGS = {
    "dcinside": {
        "search_url": "https://search.dcinside.com/post/p/1/sort/accuracy/search_type/search_all/keyword/{query}",
        "title_sel": ".sch_res_title a",
        "body_sel": ".sch_res_txt",
        "link_sel": ".sch_res_title a",
    },
    "fmkorea": {
        "search_url": "https://www.fmkorea.com/index.php?mid=best&search_keyword={query}&search_target=title_content",
        "title_sel": ".title a",
        "body_sel": ".xe_content",
        "link_sel": ".title a",
    },
    "clien": {
        "search_url": "https://www.clien.net/service/search?q={query}&sort=recency&boardCd=&is498=false",
        "title_sel": ".subject_fixed",
        "body_sel": ".list_content",
        "link_sel": ".subject_fixed",
    },
    "theqoo": {
        "search_url": "https://theqoo.net/index.php?mid=hot&search_keyword={query}&search_target=title_content",
        "title_sel": ".title a",
        "body_sel": ".xe_content",
        "link_sel": ".title a",
    },
    "natepann": {
        "search_url": "https://pann.nate.com/search?q={query}&t=0",
        "title_sel": ".tit a",
        "body_sel": ".txt_sub",
        "link_sel": ".tit a",
    },
}

# 크롤링 가능 커뮤니티 ID
SCRAPE_COMMUNITIES = set(_SCRAPE_CONFIGS.keys())


def scrape_community_posts(keyword: str, community_id: str, max_posts: int = 5) -> list[dict]:
    """네이버 검색 API로 커뮤니티 게시글 제목 + 본문 미리보기 수집"""
    comm = COMMUNITIES.get(community_id)
    if not comm:
        return []

    domain = comm["domain"]
    search_extra = comm.get("search_suffix", "")
    if search_extra:
        items, _ = _naver_search_site(f"{keyword} {search_extra}", domain, display=max_posts * 2)
    else:
        items, _ = _naver_search_site(keyword, domain, display=max_posts * 2)

    posts = []
    for it in items[:max_posts]:
        title = it.get("title", "").strip()
        desc = it.get("description", "").strip()
        if title and len(title) > 5 and desc and len(desc) > 10:
            posts.append({
                "title": title[:100],
                "body": desc[:300],
                "community_id": community_id,
                "community_name": comm.get("name", community_id),
                "demographic": comm.get("demographic", "전체"),
            })

    return posts


def scrape_communities_for_keyword(keyword: str, max_posts_per_comm: int = 5) -> list[dict]:
    """주요 공개 커뮤니티에서 본문 미리보기 수집 (네이버 검색 API 기반)"""
    all_posts = []
    for cid in SCRAPE_COMMUNITIES:
        try:
            posts = scrape_community_posts(keyword, cid, max_posts_per_comm)
            all_posts.extend(posts)
        except Exception:
            pass
    return all_posts


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
    # search_suffix가 있으면 도메인 대신 suffix 키워드를 추가 (맘카페 등)
    search_domain = comm["domain"]
    search_extra = comm.get("search_suffix", "")
    if search_extra:
        items, total = _naver_search_site(f"{keyword} {search_extra}", search_domain)
    else:
        items, total = _naver_search_site(keyword, search_domain)
    if not items:
        items, total = _google_search_site(keyword, search_domain)

    titles = [i["title"] for i in items]
    neg_r, pos_r, tone = _analyze_tone(titles, items)

    # v2: reaction depth
    reaction = _analyze_reaction_depth(titles)

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
        # v2
        has_viral_signals=reaction["has_viral_signals"],
        viral_title_count=reaction["viral_title_count"],
        derision_score=reaction["derision_score"],
        slang_density=reaction["slang_density"],
    )


def scan_all_communities(keyword: str) -> CommunityReport:
    """모든 커뮤니티 병렬 스캔"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    signals = []
    total = 0
    max_count = 0
    hottest = ""

    with ThreadPoolExecutor(max_workers=2) as pool:
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

    # v2: 커뮤니티 반응 종합
    has_any_viral = any(s.has_viral_signals for s in signals)
    avg_derision = (
        sum(s.derision_score for s in signals) / len(signals)
        if signals else 0.0
    )

    # community_resonance: 게시 커뮤니티 수 / 전체 커뮤니티 수 × 활성도 가중
    active_communities = sum(1 for s in signals if s.result_count > 0)
    resonance = round(active_communities / max(len(COMMUNITIES), 1), 3)
    if has_any_viral:
        resonance = min(1.0, resonance * 1.3)

    # dominant_tone 판별
    if avg_derision > 0.3:
        dominant_tone = "조롱"
    elif overall_tone.startswith("부정"):
        dominant_tone = "분노"
    elif overall_tone.startswith("긍정") or overall_tone.startswith("다소 긍정"):
        dominant_tone = "지지"
    elif total == 0:
        dominant_tone = "무관심"
    else:
        dominant_tone = "중립"

    return CommunityReport(
        keyword=keyword,
        signals=sorted(signals, key=lambda s: s.result_count, reverse=True),
        total_mentions=total,
        hottest_community=hottest,
        overall_tone=overall_tone,
        timestamp=datetime.now().isoformat(),
        # v2
        community_resonance=resonance,
        has_any_viral=has_any_viral,
        dominant_tone=dominant_tone,
    )


def scan_multiple_keywords(keywords: list[str]) -> dict:
    """여러 키워드 × 모든 커뮤니티"""
    results = {}
    for kw in keywords:
        results[kw] = scan_all_communities(kw)
    return results
