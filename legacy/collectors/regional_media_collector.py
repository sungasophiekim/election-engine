"""
Regional Media Tone Tracker — 경남 지역 언론 톤 별도 분석
경남신문, KNN, 경남도민일보, 경남일보 등 지역 매체의
후보별 보도 톤을 국가 언론과 분리하여 추적.

지역 언론이 중요한 이유:
  - 도민이 가장 많이 접하는 매체 = 지역 TV(KNN) + 지역 신문
  - 지역 이슈(조선업, 부울경, 혁신도시) 보도 밀도가 높음
  - 현직 도지사 평가/비판 기사가 집중됨
  - 전국 언론과 톤이 다를 수 있음 (지역 이해관계 반영)

사용법:
  result = scan_regional_media("김경수", "경남")
  → 지역 언론사별 보도량/톤/감성 + 종합 스코어
"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass, field
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# 경남 지역 언론사 DB
# ═══════════════════════════════════════════════════════════════

REGIONAL_MEDIA = {
    "KNN": {
        "domain": "knn.co.kr",
        "type": "방송",
        "tier": 1,           # 지역 Tier 1 = 지역 공영방송
        "influence": 1.5,    # 가중치 (전국 Tier1 = 1.0 기준)
        "desc": "경남방송 — 도민 뉴스 시청률 1위",
    },
    "경남신문": {
        "domain": "gnews.kr",
        "type": "종합일간",
        "tier": 1,
        "influence": 1.3,
        "desc": "경남 최대 일간지",
    },
    "경남도민일보": {
        "domain": "idomin.com",
        "type": "종합일간",
        "tier": 1,
        "influence": 1.2,
        "desc": "진보 성향 지역지",
    },
    "경남일보": {
        "domain": "gnnews.co.kr",
        "type": "종합일간",
        "tier": 1,
        "influence": 1.1,
        "desc": "보수 성향 지역지",
    },
    "경남매일": {
        "domain": "gnmaeil.com",
        "type": "경제",
        "tier": 2,
        "influence": 0.8,
        "desc": "경남 경제 전문",
    },
    "창원시민신문": {
        "domain": "cwsm.kr",
        "type": "지역",
        "tier": 2,
        "influence": 0.6,
        "desc": "창원 지역 밀착",
    },
    "거제신문": {
        "domain": "geojenews.co.kr",
        "type": "지역",
        "tier": 2,
        "influence": 0.5,
        "desc": "거제 지역",
    },
    # ── 방송 (추가) ──
    "MBC경남": {
        "domain": "mbc-gn.co.kr",
        "type": "방송",
        "tier": 1,
        "influence": 1.4,
        "desc": "MBC 경남 — 양대 지역방송, 여론조사 의뢰",
    },
    "KBS창원": {
        "domain": "news.kbs.co.kr",
        "type": "방송",
        "tier": 1,
        "influence": 1.3,
        "desc": "KBS 창원 — 여론조사(케이스텟) 의뢰",
    },
    "CJ경남방송": {
        "domain": "cj-gn.co.kr",
        "type": "방송",
        "tier": 2,
        "influence": 0.7,
        "desc": "CJ 경남 케이블",
    },
    # ── 부산+경남 영향권 ──
    "부산일보": {
        "domain": "busan.com",
        "type": "종합일간",
        "tier": 1,
        "influence": 1.3,
        "desc": "부산일보 — 여론조사(KSOI) 의뢰, 부산·경남 영향권",
    },
    "국제신문": {
        "domain": "kookje.co.kr",
        "type": "종합일간",
        "tier": 1,
        "influence": 1.1,
        "desc": "국제신문 — 부산·경남 2대 일간지",
    },
    # ── 지역 신문 (추가) ──
    "진주신문": {
        "domain": "jinjunews.co.kr",
        "type": "지역",
        "tier": 2,
        "influence": 0.6,
        "desc": "진주 — 서부경남 핵심",
    },
    "양산시민신문": {
        "domain": "yangsanilbo.com",
        "type": "지역",
        "tier": 2,
        "influence": 0.6,
        "desc": "양산 — 스윙 지역",
    },
    "뉴스경남": {
        "domain": "newsgyeongnam.kr",
        "type": "온라인",
        "tier": 2,
        "influence": 0.5,
        "desc": "경남 온라인 뉴스",
    },
    "경남연합일보": {
        "domain": "gnynews.co.kr",
        "type": "온라인",
        "tier": 2,
        "influence": 0.4,
        "desc": "경남 연합 온라인",
    },
    "경남데일리": {
        "domain": "gnsdaily.kr",
        "type": "온라인",
        "tier": 2,
        "influence": 0.4,
        "desc": "경남 데일리 온라인",
    },
    "뉴스사천": {
        "domain": "newssacheon.co.kr",
        "type": "지역",
        "tier": 2,
        "influence": 0.4,
        "desc": "사천 지역",
    },
    "거창타임즈": {
        "domain": "gctnews.com",
        "type": "지역",
        "tier": 2,
        "influence": 0.3,
        "desc": "거창 지역",
    },
    "김해뉴스": {
        "domain": "gimhaenews.co.kr",
        "type": "지역",
        "tier": 2,
        "influence": 0.5,
        "desc": "김해 지역",
    },
}


# 지역 특화 감성 키워드 (기존 키워드 + 경남 맥락)
REGIONAL_POSITIVE = [
    "도민 지원", "지역 발전", "경남 투자", "일자리 창출", "조선 호황",
    "방산 수출", "혁신도시 활성", "부울경 협력", "메가시티", "도민 체감",
    "청년 정주", "도시 재생", "지방 주도", "경남 우선",
]

REGIONAL_NEGATIVE = [
    "조선 위기", "산업 침체", "인구 유출", "지역 소외", "예산 삭감",
    "도정 비판", "도민 불만", "행정 부실", "사업 지연", "도청 논란",
    "지방 차별", "복지 후퇴", "교통 불편", "환경 오염",
]


# ═══════════════════════════════════════════════════════════════
# 데이터 구조
# ═══════════════════════════════════════════════════════════════

@dataclass
class MediaToneSignal:
    """개별 언론사 톤 분석 결과"""
    media_name: str
    domain: str
    media_type: str          # 방송 / 종합일간 / 경제 / 지역
    tier: int
    influence: float

    # 보도량
    article_count: int = 0
    recent_24h: int = 0      # 최근 24시간 기사 수

    # 감성 분석
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    positive_ratio: float = 0.0
    negative_ratio: float = 0.0
    net_sentiment: float = 0.0   # -1.0 ~ +1.0

    # 지역 특화
    regional_positive: int = 0   # 지역 긍정 키워드 매칭
    regional_negative: int = 0   # 지역 부정 키워드 매칭

    # 샘플
    sample_titles: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "media": self.media_name,
            "domain": self.domain,
            "type": self.media_type,
            "tier": self.tier,
            "influence": self.influence,
            "articles": self.article_count,
            "recent_24h": self.recent_24h,
            "positive": self.positive_count,
            "negative": self.negative_count,
            "neutral": self.neutral_count,
            "positive_ratio": round(self.positive_ratio, 3),
            "negative_ratio": round(self.negative_ratio, 3),
            "net_sentiment": round(self.net_sentiment, 3),
            "regional_positive": self.regional_positive,
            "regional_negative": self.regional_negative,
            "sample_titles": self.sample_titles[:5],
        }


@dataclass
class RegionalMediaReport:
    """지역 언론 종합 보고서"""
    region: str
    keyword: str
    candidate: str

    # 종합 지표
    total_articles: int = 0
    total_recent_24h: int = 0
    net_sentiment: float = 0.0       # 가중 평균 (-1.0 ~ +1.0)
    regional_grade: str = "LOW"      # EXPLOSIVE | HOT | ACTIVE | LOW
    dominant_tone: str = "중립"       # 긍정 | 부정 | 중립

    # 국가 vs 지역 비교
    national_sentiment: float = 0.0  # 전국 언론 감성 (비교용)
    gap_vs_national: float = 0.0     # 지역 - 전국 (양수 = 지역이 더 우호적)

    # 개별 언론사
    media_signals: list = field(default_factory=list)  # list[MediaToneSignal]

    # 전략 시사점
    insight: str = ""

    computed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "region": self.region,
            "keyword": self.keyword,
            "candidate": self.candidate,
            "total_articles": self.total_articles,
            "total_recent_24h": self.total_recent_24h,
            "net_sentiment": round(self.net_sentiment, 3),
            "regional_grade": self.regional_grade,
            "dominant_tone": self.dominant_tone,
            "national_sentiment": round(self.national_sentiment, 3),
            "gap_vs_national": round(self.gap_vs_national, 3),
            "media_signals": [m.to_dict() for m in self.media_signals],
            "insight": self.insight,
            "computed_at": self.computed_at,
        }


# ═══════════════════════════════════════════════════════════════
# 수집 + 분석
# ═══════════════════════════════════════════════════════════════

def _analyze_article_sentiment(title: str, desc: str) -> str:
    """단일 기사 감성 판정 (긍정/부정/중립)."""
    from collectors.naver_news import NEGATIVE_KEYWORDS, POSITIVE_KEYWORDS

    text = title + " " + desc
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)

    # 지역 키워드 추가 가중
    neg += sum(0.5 for kw in REGIONAL_NEGATIVE if kw in text)
    pos += sum(0.5 for kw in REGIONAL_POSITIVE if kw in text)

    if neg > pos + 1:
        return "negative"
    elif pos > neg + 1:
        return "positive"
    return "neutral"


def _count_regional_keywords(title: str, desc: str) -> tuple:
    """지역 특화 키워드 매칭 수."""
    text = title + " " + desc
    rp = sum(1 for kw in REGIONAL_POSITIVE if kw in text)
    rn = sum(1 for kw in REGIONAL_NEGATIVE if kw in text)
    return rp, rn


def _is_recent_24h(pub_date: str) -> bool:
    """기사가 최근 24시간 이내인지."""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(pub_date)
        from datetime import timezone
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() < 86400
    except Exception:
        return False


def scan_regional_media(
    keyword: str,
    candidate_name: str = "김경수",
    opponent_name: str = "박완수",
    national_sentiment: float = 0.0,   # 비교용 전국 감성
) -> RegionalMediaReport:
    """
    경남 지역 언론사별 보도 톤 분석.

    네이버 뉴스 API로 각 언론사 도메인 필터링하여 수집.
    기사별 감성 분석 → 언론사별 집계 → 가중 평균 → 종합 보고.
    """
    from collectors.naver_news import search_news

    report = RegionalMediaReport(
        region="경상남도",
        keyword=keyword,
        candidate=candidate_name,
        national_sentiment=national_sentiment,
        computed_at=datetime.now().isoformat(),
    )

    weighted_sentiment_sum = 0.0
    total_weight = 0.0

    for media_name, media_info in REGIONAL_MEDIA.items():
        domain = media_info["domain"]

        # 네이버 뉴스에서 해당 언론사 기사만 검색
        try:
            # 방법 1: 도메인 필터 검색
            query = f"{keyword} {media_name}"
            articles = search_news(query, display=30, pages=1)

            # 도메인 매칭 필터
            matched = [a for a in articles if domain in a.get("source", "") or domain in a.get("link", "")]

            # 매칭 안 되면 언론사명 포함 기사로 대체
            if not matched:
                matched = [a for a in articles if media_name in a.get("title", "") or media_name in a.get("description", "")]

            time.sleep(0.3)  # API rate limit

        except Exception:
            matched = []

        # 감성 분석
        signal = MediaToneSignal(
            media_name=media_name,
            domain=domain,
            media_type=media_info["type"],
            tier=media_info["tier"],
            influence=media_info["influence"],
            article_count=len(matched),
        )

        for art in matched:
            title = art.get("title", "")
            desc = art.get("description", "")

            sentiment = _analyze_article_sentiment(title, desc)
            if sentiment == "positive":
                signal.positive_count += 1
            elif sentiment == "negative":
                signal.negative_count += 1
            else:
                signal.neutral_count += 1

            rp, rn = _count_regional_keywords(title, desc)
            signal.regional_positive += rp
            signal.regional_negative += rn

            if _is_recent_24h(art.get("pub_date", "")):
                signal.recent_24h += 1

            if len(signal.sample_titles) < 5:
                signal.sample_titles.append(title)

        # 비율 계산
        total = signal.article_count
        if total > 0:
            signal.positive_ratio = signal.positive_count / total
            signal.negative_ratio = signal.negative_count / total
            signal.net_sentiment = (signal.positive_count - signal.negative_count) / total

        # 가중 합산
        weighted_sentiment_sum += signal.net_sentiment * media_info["influence"]
        total_weight += media_info["influence"]

        report.media_signals.append(signal)
        report.total_articles += signal.article_count
        report.total_recent_24h += signal.recent_24h

    # 종합 감성 (가중 평균)
    if total_weight > 0:
        report.net_sentiment = weighted_sentiment_sum / total_weight

    # 등급 판정
    if report.total_articles >= 20 and report.total_recent_24h >= 5:
        report.regional_grade = "EXPLOSIVE"
    elif report.total_articles >= 10 and report.total_recent_24h >= 3:
        report.regional_grade = "HOT"
    elif report.total_articles >= 5:
        report.regional_grade = "ACTIVE"
    else:
        report.regional_grade = "LOW"

    # 톤 판정
    if report.net_sentiment > 0.15:
        report.dominant_tone = "긍정"
    elif report.net_sentiment < -0.15:
        report.dominant_tone = "부정"
    else:
        report.dominant_tone = "중립"

    # 국가 vs 지역 격차
    report.gap_vs_national = report.net_sentiment - national_sentiment

    # 전략 시사점
    report.insight = _generate_insight(report, candidate_name, opponent_name)

    return report


def scan_both_candidates(
    candidate_name: str = "김경수",
    opponent_name: str = "박완수",
) -> dict:
    """양 후보의 지역 언론 톤을 비교."""
    our_report = scan_regional_media(candidate_name, candidate_name, opponent_name)
    time.sleep(1)  # rate limit
    opp_report = scan_regional_media(opponent_name, candidate_name, opponent_name)

    return {
        "our_candidate": our_report.to_dict(),
        "opponent": opp_report.to_dict(),
        "comparison": {
            "our_sentiment": round(our_report.net_sentiment, 3),
            "opp_sentiment": round(opp_report.net_sentiment, 3),
            "gap": round(our_report.net_sentiment - opp_report.net_sentiment, 3),
            "our_articles": our_report.total_articles,
            "opp_articles": opp_report.total_articles,
            "our_grade": our_report.regional_grade,
            "opp_grade": opp_report.regional_grade,
        },
        "computed_at": datetime.now().isoformat(),
    }


def get_media_list() -> list[dict]:
    """지역 언론사 목록."""
    return [
        {
            "name": name,
            "domain": info["domain"],
            "type": info["type"],
            "tier": info["tier"],
            "influence": info["influence"],
            "desc": info["desc"],
        }
        for name, info in REGIONAL_MEDIA.items()
    ]


# ═══════════════════════════════════════════════════════════════
# 전략 시사점 생성
# ═══════════════════════════════════════════════════════════════

def _generate_insight(
    report: RegionalMediaReport,
    candidate: str,
    opponent: str,
) -> str:
    """지역 언론 분석 결과 → 전략 시사점."""
    parts = []

    # 보도량
    if report.total_articles < 5:
        parts.append(f"지역 언론 노출 부족 ({report.total_articles}건). 지역 언론 대상 보도자료 강화 필요.")
    elif report.total_articles >= 15:
        parts.append(f"지역 언론 관심 높음 ({report.total_articles}건).")

    # 톤
    if report.net_sentiment > 0.2:
        parts.append(f"지역 언론 톤 우호적 ({report.net_sentiment:+.2f}). 현재 프레임 유지.")
    elif report.net_sentiment < -0.2:
        parts.append(f"지역 언론 톤 부정적 ({report.net_sentiment:+.2f}). 지역 언론 대응 필요.")

    # 국가 vs 지역 격차
    gap = report.gap_vs_national
    if gap > 0.15:
        parts.append(f"지역이 전국보다 우호적 (격차 +{gap:.2f}). 지역 밀착 전략 효과적.")
    elif gap < -0.15:
        parts.append(f"지역이 전국보다 부정적 (격차 {gap:.2f}). 지역 현안 대응 시급.")

    # 특정 언론사 주목
    if report.media_signals:
        worst = min(report.media_signals, key=lambda m: m.net_sentiment if m.article_count > 0 else 0)
        best = max(report.media_signals, key=lambda m: m.net_sentiment if m.article_count > 0 else 0)
        if worst.net_sentiment < -0.3 and worst.article_count >= 3:
            parts.append(f"⚠ {worst.media_name} 부정 톤 강함 ({worst.net_sentiment:+.2f}). 해당 매체 관계 관리 필요.")
        if best.net_sentiment > 0.3 and best.article_count >= 3:
            parts.append(f"✅ {best.media_name} 우호적 ({best.net_sentiment:+.2f}). 해당 매체 활용 강화.")

    return " ".join(parts) if parts else "지역 언론 데이터 부족. 다음 갱신 시 분석."
