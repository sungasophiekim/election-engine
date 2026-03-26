"""
AI Sentiment Analyzer — Claude 기반 정밀 감성 분석
기존 사전 기반 분석을 Claude AI로 보완합니다.

기능:
  1. 뉴스 제목 배치 감성 분류 (긍정/부정/중립 + 타겟 + 톤)
  2. 후보별 유불리 판단
  3. 조롱/분노/지지/동원 톤 감지
  4. 연관어 + 프레임 추출

비용 최적화:
  - Haiku 모델 사용 (저렴 + 빠름)
  - 제목 20개씩 배치 처리 (API 호출 최소화)
  - 캐싱 (같은 키워드 1시간 내 재호출 방지)
"""
from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime


# ── 캐시 ──────────────────────────────────────────────────────
_cache: dict[str, tuple[dict, float]] = {}
_CACHE_TTL = 3600  # 1시간


@dataclass
class AISentimentResult:
    """AI 감성 분석 결과"""
    keyword: str
    total_analyzed: int = 0

    # 감성 분류
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    net_sentiment: float = 0.0       # -1.0 ~ +1.0

    # 타겟 분류
    about_us_positive: int = 0
    about_us_negative: int = 0
    about_opponent_positive: int = 0
    about_opponent_negative: int = 0

    # 톤 분석
    tone_distribution: dict = field(default_factory=dict)  # {"조롱": 3, "분노": 5, "지지": 8, ...}
    dominant_tone: str = ""          # "지지" | "분노" | "조롱" | "불안" | "기대"
    mobilization_detected: bool = False  # "투표", "심판" 등 동원 표현

    # 6분류 감성 (v2)
    support_count: int = 0           # 지지·기대
    swing_count: int = 0             # 경쟁력 유보·비교
    identity_attack_count: int = 0   # 정체성 압박·불신
    policy_critique_count: int = 0   # 정책·자질 비판
    sentiment_6way: dict = field(default_factory=dict)  # {"지지": 23, "스윙": 15, "부정": 8, "정체성": 5, "정책": 3, "중립": 46}

    # 강점/약점 주제 분류 (v2)
    strength_topics: list = field(default_factory=list)  # [{"topic": "경제 공약", "count": 12, "sample": "..."}, ...]
    weakness_topics: list = field(default_factory=list)   # [{"topic": "사법리스크", "count": 8, "sample": "..."}, ...]

    # 프레임/연관어
    key_frames: list[str] = field(default_factory=list)
    key_narratives: list[str] = field(default_factory=list)

    # 요약
    summary: str = ""
    risk_assessment: str = ""
    opportunity: str = ""

    # 메타
    model: str = ""
    analyzed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "total_analyzed": self.total_analyzed,
            "positive": self.positive_count,
            "negative": self.negative_count,
            "neutral": self.neutral_count,
            "net_sentiment": round(self.net_sentiment, 3),
            "about_us": {"positive": self.about_us_positive, "negative": self.about_us_negative},
            "about_opponent": {"positive": self.about_opponent_positive, "negative": self.about_opponent_negative},
            "tone_distribution": self.tone_distribution,
            "dominant_tone": self.dominant_tone,
            "mobilization_detected": self.mobilization_detected,
            "sentiment_6way": self.sentiment_6way,
            "strength_topics": self.strength_topics[:5],
            "weakness_topics": self.weakness_topics[:5],
            "positive_ratio": self.positive_count / max(self.total_analyzed, 1),
            "negative_ratio": self.negative_count / max(self.total_analyzed, 1),
            "key_frames": self.key_frames[:5],
            "key_narratives": self.key_narratives[:3],
            "summary": self.summary,
            "risk": self.risk_assessment,
            "opportunity": self.opportunity,
            "model": self.model,
        }


def analyze_sentiment_ai(
    titles: list[str],
    keyword: str = "",
    candidate_name: str = "",
    opponents: list[str] = None,
    max_titles: int = 30,
) -> AISentimentResult:
    """
    Claude Haiku로 뉴스/블로그 제목 배치 감성 분석.

    Args:
        titles: 분석할 제목 리스트
        keyword: 분석 키워드
        candidate_name: 우리 후보
        opponents: 상대 후보들
        max_titles: 최대 분석 제목 수

    Returns:
        AISentimentResult with detailed sentiment breakdown
    """
    opponents = opponents or []
    result = AISentimentResult(
        keyword=keyword,
        analyzed_at=datetime.now().isoformat(),
    )

    if not titles:
        return result

    # 캐시 확인
    cache_key = f"{keyword}:{len(titles)}"
    if cache_key in _cache:
        cached, ts = _cache[cache_key]
        if time.time() - ts < _CACHE_TTL:
            return _from_cache(cached, keyword)

    # 제목 수 제한
    titles = titles[:max_titles]
    result.total_analyzed = len(titles)

    # API 키 확인
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or "xxxxx" in api_key:
        return _fallback_analysis(titles, keyword, candidate_name, opponents)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        opp_str = ", ".join(opponents) if opponents else "상대 후보"
        titles_str = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))

        prompt = f"""다음은 "{keyword}" 관련 뉴스/블로그 제목 {len(titles)}건입니다.
선거 캠프 관점에서 분석하세요. 우리 후보: {candidate_name}, 상대: {opp_str}

{titles_str}

반드시 아래 JSON 형식으로만 응답하세요. 설명 없이 JSON만:
{{
  "positive": 긍정 기사 수,
  "negative": 부정 기사 수,
  "neutral": 중립 기사 수,
  "about_us_positive": {candidate_name}에게 긍정적인 기사 수,
  "about_us_negative": {candidate_name}에게 부정적인 기사 수,
  "about_opp_positive": {opp_str}에게 긍정적인 기사 수,
  "about_opp_negative": {opp_str}에게 부정적인 기사 수,
  "sentiment_6way": {{"지지": 지지·기대 수, "스윙": 비교·유보 수, "부정": 비난 수, "정체성": 정체성압박·불신 수, "정책": 정책·자질비판 수, "중립": 중립 수}},
  "strength_topics": [{{"topic": "지지이유", "count": 수, "sample": "대표제목"}}, ...최대3개],
  "weakness_topics": [{{"topic": "비판이유", "count": 수, "sample": "대표제목"}}, ...최대3개],
  "tones": {{"지지": 수, "기대": 수, "분노": 수, "비판": 수, "조롱": 수, "불안": 수, "중립": 수}},
  "dominant_tone": "가장 많은 톤",
  "mobilization": true/false,
  "frames": ["프레임1", "프레임2"],
  "narratives": ["서사1"],
  "summary": "2문장 전략 요약",
  "risk": "위험 1문장",
  "opportunity": "기회 1문장"
}}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        # JSON 파싱
        import re
        raw = re.sub(r'[\n\r\t]+', ' ', raw)
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        # { } 추출
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            raw = m.group()

        # 잘린 JSON 복구 시도
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            open_braces = raw.count("{") - raw.count("}")
            open_brackets = raw.count("[") - raw.count("]")
            if open_brackets > 0:
                raw = raw.rstrip(", ") + "]" * open_brackets
            if open_braces > 0:
                raw = raw.rstrip(", ") + "}" * open_braces
            data = json.loads(raw)

        result.positive_count = data.get("positive", 0)
        result.negative_count = data.get("negative", 0)
        result.neutral_count = data.get("neutral", 0)
        total = result.positive_count + result.negative_count + result.neutral_count
        if total > 0:
            result.net_sentiment = (result.positive_count - result.negative_count) / total

        result.about_us_positive = data.get("about_us_positive", 0)
        result.about_us_negative = data.get("about_us_negative", 0)
        result.about_opponent_positive = data.get("about_opp_positive", 0)
        result.about_opponent_negative = data.get("about_opp_negative", 0)

        result.tone_distribution = data.get("tones", {})
        result.dominant_tone = data.get("dominant_tone", "")
        result.mobilization_detected = data.get("mobilization", False)
        result.key_frames = data.get("frames", [])
        result.key_narratives = data.get("narratives", [])
        result.summary = data.get("summary", "")
        result.risk_assessment = data.get("risk", "")
        result.opportunity = data.get("opportunity", "")
        result.model = "claude-haiku"

        # 6분류 감성 (v2)
        s6 = data.get("sentiment_6way", {})
        result.sentiment_6way = s6
        result.support_count = s6.get("지지", 0)
        result.swing_count = s6.get("스윙", 0)
        result.identity_attack_count = s6.get("정체성", 0)
        result.policy_critique_count = s6.get("정책", 0)

        # 강점/약점 주제 (v2)
        result.strength_topics = data.get("strength_topics", [])
        result.weakness_topics = data.get("weakness_topics", [])

        # 캐시 저장
        _cache[cache_key] = (data, time.time())

    except Exception as e:
        print(f"  [AI Sentiment] '{keyword}' 실패: {e}")
        return _fallback_analysis(titles, keyword, candidate_name, opponents)

    return result


def _fallback_analysis(
    titles: list[str], keyword: str, candidate_name: str, opponents: list[str],
) -> AISentimentResult:
    """AI 호출 실패 시 사전 기반 fallback"""
    from collectors.naver_news import NEGATIVE_KEYWORDS, POSITIVE_KEYWORDS

    result = AISentimentResult(keyword=keyword, total_analyzed=len(titles), model="lexicon-fallback")
    for t in titles:
        neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in t)
        pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in t)
        if neg > pos:
            result.negative_count += 1
        elif pos > neg:
            result.positive_count += 1
        else:
            result.neutral_count += 1

        if candidate_name and candidate_name in t:
            if neg > pos:
                result.about_us_negative += 1
            elif pos > neg:
                result.about_us_positive += 1
        for opp in opponents:
            if opp in t:
                if neg > pos:
                    result.about_opponent_negative += 1
                elif pos > neg:
                    result.about_opponent_positive += 1

    total = result.positive_count + result.negative_count + result.neutral_count
    if total > 0:
        result.net_sentiment = (result.positive_count - result.negative_count) / total
    return result


def _from_cache(data: dict, keyword: str) -> AISentimentResult:
    """캐시에서 결과 복원"""
    r = AISentimentResult(keyword=keyword, model="cached")
    r.positive_count = data.get("positive", 0)
    r.negative_count = data.get("negative", 0)
    r.neutral_count = data.get("neutral", 0)
    total = r.positive_count + r.negative_count + r.neutral_count
    if total > 0:
        r.net_sentiment = (r.positive_count - r.negative_count) / total
    r.about_us_positive = data.get("about_us_positive", 0)
    r.about_us_negative = data.get("about_us_negative", 0)
    r.about_opponent_positive = data.get("about_opp_positive", 0)
    r.about_opponent_negative = data.get("about_opp_negative", 0)
    r.tone_distribution = data.get("tones", {})
    r.dominant_tone = data.get("dominant_tone", "")
    r.mobilization_detected = data.get("mobilization", False)
    r.key_frames = data.get("frames", [])
    r.key_narratives = data.get("narratives", [])
    r.summary = data.get("summary", "")
    r.risk_assessment = data.get("risk", "")
    r.opportunity = data.get("opportunity", "")
    return r


def batch_analyze(
    keyword_titles: dict[str, list[str]],
    candidate_name: str = "",
    opponents: list[str] = None,
) -> dict[str, AISentimentResult]:
    """여러 키워드 배치 분석"""
    results = {}
    for keyword, titles in keyword_titles.items():
        results[keyword] = analyze_sentiment_ai(
            titles=titles,
            keyword=keyword,
            candidate_name=candidate_name,
            opponents=opponents,
        )
        time.sleep(0.5)  # API rate limit
    return results


# ── 후보 버즈 배치 분석 (1회 API 호출, 6시간 캐시) ───────────────

_candidate_cache: dict[str, tuple[dict, float]] = {}
_CANDIDATE_CACHE_TTL = 1800  # 30분


def analyze_candidate_buzz_batch(
    keyword_titles: dict[str, list[str]],
    candidate_name: str = "",
    opponents: list[str] = None,
    max_titles_per_kw: int = 15,
) -> dict[str, AISentimentResult]:
    """
    후보추적 키워드 전체를 1회 API 호출로 감성 분석.

    - 모든 후보 키워드의 제목을 하나의 프롬프트에 묶어 배치 처리
    - 6시간 캐시 (후보 감성은 급변하지 않음)
    - 비용: 하루 ~4콜 (Haiku)

    Returns:
        {keyword: AISentimentResult} dict
    """
    opponents = opponents or []

    # 캐시 확인 — 키워드 조합 해시
    kw_sorted = sorted(keyword_titles.keys())
    cache_key = "|".join(kw_sorted)
    if cache_key in _candidate_cache:
        cached_data, ts = _candidate_cache[cache_key]
        if time.time() - ts < _CANDIDATE_CACHE_TTL:
            # 캐시에서 복원
            results = {}
            for kw, data in cached_data.items():
                results[kw] = _from_cache(data, kw)
            return results

    # 제목 수 제한 + 포맷
    sections = []
    for kw in kw_sorted:
        titles = keyword_titles.get(kw, [])[:max_titles_per_kw]
        if not titles:
            continue
        titles_str = "\n".join(f"  - {t}" for t in titles)
        sections.append(f"[{kw}]\n{titles_str}")

    if not sections:
        return {}

    combined = "\n\n".join(sections)

    # API 키 확인
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or "xxxxx" in api_key:
        # fallback: 개별 사전 분석
        results = {}
        for kw, titles in keyword_titles.items():
            results[kw] = _fallback_analysis(titles[:max_titles_per_kw], kw, candidate_name, opponents)
        return results

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        opp_str = ", ".join(opponents) if opponents else "상대 후보"
        kw_list_str = ", ".join(kw_sorted)

        prompt = f"""선거 후보 관련 키워드별 뉴스 제목을 감성 분석하세요.
우리: {candidate_name}, 상대: {opp_str}

{combined}

JSON으로만 응답. 각 키워드별:
{{
  "키워드": {{
    "positive": 긍정수, "negative": 부정수, "neutral": 중립수,
    "sentiment_6way": {{"지지": 수, "스윙": 수, "부정": 수, "정체성": 수, "정책": 수, "중립": 수}},
    "dominant_tone": "톤",
    "summary": "1문장"
  }}
}}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        import re
        raw = re.sub(r'[\n\r\t]+', ' ', raw)
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            raw = m.group()

        # JSON 파싱 — 잘린 경우 복구 시도
        try:
            all_data = json.loads(raw)
        except json.JSONDecodeError:
            # 닫히지 않은 중괄호 보완
            open_braces = raw.count("{") - raw.count("}")
            if open_braces > 0:
                raw = raw.rstrip(", ") + "}" * open_braces
            try:
                all_data = json.loads(raw)
            except json.JSONDecodeError as e2:
                print(f"[AI CandidateBuzz] JSON 복구 실패: {e2}")
                raise

        # 결과 파싱
        results = {}
        cache_store = {}
        for kw in kw_sorted:
            data = all_data.get(kw, {})
            if not data:
                continue
            r = AISentimentResult(keyword=kw, model="claude-haiku-batch")
            r.total_analyzed = len(keyword_titles.get(kw, [])[:max_titles_per_kw])
            r.positive_count = data.get("positive", 0)
            r.negative_count = data.get("negative", 0)
            r.neutral_count = data.get("neutral", 0)
            total = r.positive_count + r.negative_count + r.neutral_count
            if total > 0:
                r.net_sentiment = (r.positive_count - r.negative_count) / total
            r.about_us_positive = data.get("about_us_positive", 0)
            r.about_us_negative = data.get("about_us_negative", 0)
            r.about_opponent_positive = data.get("about_opp_positive", 0)
            r.about_opponent_negative = data.get("about_opp_negative", 0)
            r.tone_distribution = data.get("tones", {})
            r.dominant_tone = data.get("dominant_tone", "")
            r.mobilization_detected = data.get("mobilization", False)
            r.summary = data.get("summary", "")

            s6 = data.get("sentiment_6way", {})
            r.sentiment_6way = s6
            r.support_count = s6.get("지지", 0)
            r.swing_count = s6.get("스윙", 0)
            r.identity_attack_count = s6.get("정체성", 0)
            r.policy_critique_count = s6.get("정책", 0)
            r.strength_topics = data.get("strength_topics", [])
            r.weakness_topics = data.get("weakness_topics", [])
            r.analyzed_at = datetime.now().isoformat()

            results[kw] = r
            cache_store[kw] = data

        # 캐시 저장
        _candidate_cache[cache_key] = (cache_store, time.time())
        print(f"[AI CandidateBuzz] {len(results)}개 키워드 배치 분석 완료 (6시간 캐시)")
        return results

    except Exception as e:
        print(f"[AI CandidateBuzz] 배치 분석 실패: {e}")
        results = {}
        for kw, titles in keyword_titles.items():
            results[kw] = _fallback_analysis(titles[:max_titles_per_kw], kw, candidate_name, opponents)
        return results
