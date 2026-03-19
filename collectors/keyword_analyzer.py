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
    # 지역/선거 일반
    "경남", "경상남도", "도지사", "후보", "선거", "경상", "남도",
    # 시간
    "오늘", "내일", "최근", "올해", "이번", "지난", "이후", "이날", "오는", "앞서",
    # 조사/어미/서술어 (한국어 불용어)
    "있다", "했다", "한다", "된다", "것으로", "대한", "위한", "통해", "있는",
    "하는", "되는", "에서", "으로", "까지", "부터", "에게", "라며", "라고",
    "밝혔다", "전했다", "말했다", "설명했다", "강조했다", "대해", "따르면",
    "것이다", "됐다", "했다고", "한다고", "있다고", "한편", "때문", "또한",
    "이라고", "라면서", "보인다", "나타났다", "알려졌다", "것이라고",
    # 일반 서술/수식
    "대표는", "대표", "위원", "위원장", "의원", "관계자", "대변인",
    "관련", "해당", "매우", "가장", "이상", "이하", "정도", "현재",
    "등을", "에는", "으며", "에도", "에다", "에만",
    # 뉴스 상투어
    "뉴스", "기사", "보도", "발표", "진행", "사업", "계획",
    "예정", "전국", "동시", "지방", "예비", "지역",
    "인터뷰", "취재", "특파원", "앵커", "속보",
    # 수치/단위 관련
    "인당", "만원", "천억", "개소", "노선", "개월", "세계",
    "지급", "준공", "착공", "조성", "추진", "실시", "시행",
    "확보", "예산", "규모", "목표", "달성", "기준",
    # 일반 부사/형용사/접속
    "위해", "함께", "좋은", "새로운", "다른", "같은", "모든", "필요",
    "가능", "중요", "주요", "다양", "적극", "실질", "특별", "본격",
    "연계한", "통한", "대비", "마련", "방안", "방문",
    "예비후보", "예비후보는", "후보로", "후보는", "후보가",
    # 기타 무의미
    "것으", "하면서", "이라는", "라는", "라는게", "있으며",
    "만큼", "그러나", "하지만", "그리고", "또는", "이런",
    "그동안", "앞으로", "하겠다", "해야", "한다며", "했으며",
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
        filtered = []
        for w in words:
            if w in STOPWORDS or w in kw_words or len(w) < 2:
                continue
            # 조사/어미 붙은 변형 필터 (예: 공약을, 부울경이, 창원특례시가)
            suffixes = ('는','을','를','이','가','에','의','로','와','과','도','만',
                        '에서','으로','에는','에도','했다','한다','이다','으며',
                        '에게','까지','부터','처럼','보다','라는','라고','이며')
            skip = False
            for sf in suffixes:
                if w.endswith(sf) and len(w) > len(sf) + 1:
                    base = w[:-len(sf)]
                    if base in kw_words or len(base) < 2:
                        skip = True
                        break
            if skip:
                continue
            filtered.append(w)

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
