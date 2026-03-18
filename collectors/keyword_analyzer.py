"""
Election Strategy Engine — 키워드 상세 분석기
키워드 클릭 시 연관 단어, 감정 톤, 프레임, 맥락을 분석합니다.
"""
import re
from collections import Counter
from dataclasses import dataclass, field

from collectors.naver_news import search_news, analyze_sentiment, NEGATIVE_KEYWORDS, POSITIVE_KEYWORDS
from collectors.social_collector import search_blogs, search_cafes


# 감정 톤 카테고리
TONE_KEYWORDS = {
    "분노": ["규탄", "분노", "반발", "항의", "퇴진", "탄핵", "배신", "기만"],
    "불안": ["우려", "불안", "위기", "위험", "불확실", "혼란", "갈등"],
    "기대": ["기대", "희망", "기회", "비전", "약속", "성장", "발전"],
    "신뢰": ["신뢰", "검증", "경험", "실력", "전문", "안정", "리더십"],
    "비판": ["비판", "문제", "실패", "허위", "거짓", "부실", "무능"],
    "지지": ["지지", "환영", "찬성", "응원", "공감", "호응", "지원"],
    "냉소": ["실망", "냉소", "무관심", "진부", "뻔한", "식상", "그놈이그놈"],
    "관심": ["화제", "주목", "관심", "이목", "핫", "급등", "화두"],
}

# 불용어
STOPWORDS = {
    "경남", "경상남도", "도지사", "후보", "선거", "오늘", "내일", "최근",
    "관련", "대한", "위한", "통해", "이번", "올해", "것으로", "이후",
    "때문", "한편", "이날", "지역", "전국", "동시", "지방", "예비",
    "뉴스", "기사", "보도", "발표", "진행", "사업", "계획",
}


@dataclass
class KeywordAnalysis:
    """키워드 상세 분석 결과"""
    keyword: str

    # 연관 단어
    co_words: list[dict]          # [{"word": str, "count": int, "type": "noun"|"entity"}]
    bigrams: list[dict]           # [{"phrase": str, "count": int}]

    # 감정 톤
    tone_distribution: dict       # {"분노": 3, "기대": 12, ...}
    dominant_tone: str            # 가장 강한 감정
    tone_score: float             # -1(극부정) ~ +1(극긍정)

    # 프레임/내러티브
    frames: list[str]             # ["현직 성과 부족론", "변화 필요론"]
    key_narratives: list[dict]    # [{"narrative": str, "count": int, "sample": str}]

    # 주체 분석
    who_talks: dict               # {"언론": 45, "블로거": 30, "카페": 5}
    about_whom: dict              # {"김경수": 12, "박완수": 8, "전희영": 2}

    # 채널별 샘플
    news_samples: list[str]
    blog_samples: list[str]
    cafe_samples: list[str]

    # 메타
    total_analyzed: int
    data_freshness: str           # "실시간" | "1시간 전" | ...


def analyze_keyword(
    keyword: str,
    candidate_name: str = "",
    opponents: list[str] = None,
) -> KeywordAnalysis:
    """
    키워드 하나에 대한 심층 분석.
    뉴스 + 블로그 + 카페를 수집하여 연관 단어, 감정, 프레임을 분석.
    """
    opponents = opponents or []
    all_texts = []
    news_titles = []
    blog_titles = []
    cafe_titles = []

    # 1. 데이터 수집
    try:
        news = search_news(keyword, display=100)
        for a in news:
            all_texts.append(a["title"] + " " + a.get("description", ""))
            news_titles.append(a["title"])
    except Exception:
        news = []

    try:
        blog = search_blogs(keyword, display=50)
        for b in blog.top_items[:30]:
            all_texts.append(b.get("title", "") + " " + b.get("description", ""))
            blog_titles.append(b.get("title", ""))
    except Exception:
        pass

    try:
        cafe = search_cafes(keyword, display=50)
        for c in cafe.top_items[:30]:
            all_texts.append(c.get("title", "") + " " + c.get("description", ""))
            cafe_titles.append(c.get("title", ""))
    except Exception:
        pass

    if not all_texts:
        return KeywordAnalysis(
            keyword=keyword, co_words=[], bigrams=[],
            tone_distribution={}, dominant_tone="데이터 없음", tone_score=0,
            frames=[], key_narratives=[],
            who_talks={}, about_whom={},
            news_samples=[], blog_samples=[], cafe_samples=[],
            total_analyzed=0, data_freshness="데이터 없음",
        )

    # 2. 연관 단어 추출
    word_counter = Counter()
    bigram_counter = Counter()
    entity_counter = Counter()

    kw_words = set(re.findall(r'[가-힣]{2,}', keyword))

    for text in all_texts:
        words = re.findall(r'[가-힣]{2,6}', text)
        filtered = [w for w in words if w not in STOPWORDS and w not in kw_words and len(w) >= 2]

        for w in filtered:
            word_counter[w] += 1

        # 바이그램
        for i in range(len(filtered) - 1):
            bg = f"{filtered[i]} {filtered[i+1]}"
            bigram_counter[bg] += 1

    # 인명/기관명 (3글자 이상, 빈도 높은 것)
    people = [candidate_name] + opponents
    for text in all_texts:
        for name in people:
            if name in text:
                entity_counter[name] += 1

    co_words = [
        {"word": w, "count": c, "type": "noun"}
        for w, c in word_counter.most_common(20)
        if c >= 2
    ]

    bigrams = [
        {"phrase": bg, "count": c}
        for bg, c in bigram_counter.most_common(10)
        if c >= 2
    ]

    # 3. 감정 톤 분석
    tone_dist = {tone: 0 for tone in TONE_KEYWORDS}
    for text in all_texts:
        for tone, keywords_list in TONE_KEYWORDS.items():
            for kw in keywords_list:
                if kw in text:
                    tone_dist[tone] += 1

    # 지배적 톤
    dominant = max(tone_dist, key=tone_dist.get) if any(tone_dist.values()) else "중립"
    if tone_dist.get(dominant, 0) == 0:
        dominant = "중립"

    # 톤 스코어: 긍정 톤(기대, 신뢰, 지지) - 부정 톤(분노, 비판, 냉소)
    positive_tones = tone_dist.get("기대", 0) + tone_dist.get("신뢰", 0) + tone_dist.get("지지", 0)
    negative_tones = tone_dist.get("분노", 0) + tone_dist.get("비판", 0) + tone_dist.get("냉소", 0)
    total_tone = positive_tones + negative_tones
    tone_score = (positive_tones - negative_tones) / max(total_tone, 1)
    tone_score = max(-1, min(1, tone_score))

    # 4. 프레임/내러티브 추출
    frames = []
    narratives = []

    # 프레임 패턴 매칭
    frame_patterns = {
        "현직 성과 부족론": ["성과", "뭘 했", "실적", "부족", "체감"],
        "변화 필요론": ["변화", "교체", "새로운", "바꿔야", "안 되"],
        "안정 지속론": ["안정", "지속", "이어", "경험", "검증"],
        "경제 위기론": ["경기", "침체", "위기", "불황", "어려"],
        "민생 우선론": ["민생", "생활", "물가", "서민", "복지"],
        "미래 비전론": ["미래", "비전", "성장", "발전", "혁신"],
        "도덕성 논란": ["도덕", "윤리", "사법", "의혹", "비리"],
        "포퓰리즘 비판": ["포퓰리즘", "퍼주기", "재원", "세금", "빚"],
        "지역 소외론": ["소외", "편중", "차별", "형평", "균형"],
    }

    for frame_name, frame_kws in frame_patterns.items():
        count = 0
        sample = ""
        for text in all_texts:
            if any(fk in text for fk in frame_kws):
                count += 1
                if not sample:
                    sample = text[:80]
        if count >= 2:
            frames.append(frame_name)
            narratives.append({"narrative": frame_name, "count": count, "sample": sample})

    narratives.sort(key=lambda x: x["count"], reverse=True)

    # 5. 주체 분석
    about_whom = dict(entity_counter.most_common(5))
    who_talks = {
        "뉴스": len(news_titles),
        "블로그": len(blog_titles),
        "카페": len(cafe_titles),
    }

    return KeywordAnalysis(
        keyword=keyword,
        co_words=co_words,
        bigrams=bigrams,
        tone_distribution={k: v for k, v in tone_dist.items() if v > 0},
        dominant_tone=dominant,
        tone_score=round(tone_score, 2),
        frames=frames[:5],
        key_narratives=narratives[:5],
        who_talks=who_talks,
        about_whom=about_whom,
        news_samples=news_titles[:5],
        blog_samples=blog_titles[:5],
        cafe_samples=cafe_titles[:5],
        total_analyzed=len(all_texts),
        data_freshness="실시간",
    )
