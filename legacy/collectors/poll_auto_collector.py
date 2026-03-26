"""
Poll Auto Collector — 여론조사 자동 수집
A. nesdc 자동 동기화
B. 뉴스에서 여론조사 결과 패턴 추출

사용:
  new_polls = auto_collect_polls()
  → [{"source": "뉴스추출", "kim": 38.5, "park": 36.2, "date": "2026-03-23", ...}, ...]
"""
from __future__ import annotations
import re
import os
import time
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DetectedPoll:
    """자동 감지된 여론조사"""
    source: str              # "nesdc" | "뉴스추출"
    org: str = ""            # 조사기관
    date: str = ""           # 조사 날짜
    kim: float = 0.0         # 김경수 %
    park: float = 0.0        # 박완수 %
    gap: float = 0.0         # 격차
    title: str = ""          # 원문 제목
    confidence: float = 0.0  # 추출 신뢰도 (0~1)
    url: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "org": self.org,
            "date": self.date,
            "kim": self.kim,
            "park": self.park,
            "gap": round(self.gap, 1),
            "title": self.title,
            "confidence": round(self.confidence, 2),
            "url": self.url,
        }


# ═══════════════════════════════════════════════════════════════
# A. nesdc 자동 동기화
# ═══════════════════════════════════════════════════════════════

def sync_nesdc() -> list[DetectedPoll]:
    """nesdc에서 새 여론조사 동기화."""
    results = []
    try:
        from engines.nesdc_scraper import NesdcScraper
        scraper = NesdcScraper()
        polls = scraper.collect_new_and_save()
        for p in polls:
            if p.our_support and p.opponent_support:
                results.append(DetectedPoll(
                    source="nesdc",
                    org=p.org,
                    date=p.survey_date or p.pub_date or "",
                    kim=p.our_support,
                    park=p.opponent_support,
                    gap=round(p.our_support - p.opponent_support, 1),
                    title=f"nesdc #{p.ntt_id}",
                    confidence=0.95,
                ))
        if results:
            print(f"[PollAuto] nesdc: {len(results)}건 새 여론조사 발견")
    except Exception as e:
        print(f"[PollAuto] nesdc 동기화 실패: {e}")
    return results


# ═══════════════════════════════════════════════════════════════
# B. 뉴스에서 여론조사 결과 패턴 추출
# ═══════════════════════════════════════════════════════════════

# 여론조사 결과 추출 패턴
POLL_PATTERNS = [
    # "김경수 38.5% 박완수 36.2%" 또는 "김경수 38.5%...박완수 36.2%"
    re.compile(r'김경수[^0-9]*?(\d{1,2}\.?\d?)%[^0-9]*?박완수[^0-9]*?(\d{1,2}\.?\d?)%'),
    # "박완수 36.2% 김경수 38.5%"
    re.compile(r'박완수[^0-9]*?(\d{1,2}\.?\d?)%[^0-9]*?김경수[^0-9]*?(\d{1,2}\.?\d?)%'),
    # "김경수 38.5% vs 박완수 36.2%"
    re.compile(r'김경수[^0-9]*?(\d{1,2}\.?\d?)\s*%?\s*(?:vs|대)\s*박완수[^0-9]*?(\d{1,2}\.?\d?)\s*%?'),
]

# 조사기관 키워드
ORG_KEYWORDS = {
    "KSOI": "KSOI", "한국갤럽": "한국갤럽", "리얼미터": "리얼미터",
    "케이스텟": "케이스텟", "서던포스트": "서던포스트", "모노커뮤": "모노커뮤",
    "여론조사꽃": "여론조사꽃", "한길리서치": "한길리서치", "조원씨앤아이": "조원씨앤아이",
    "KBS": "KBS", "KNN": "KNN", "MBC": "MBC경남",
    "경남신문": "경남신문", "경남일보": "경남일보", "부산일보": "부산일보",
    "경남매일": "경남매일",
}


def extract_polls_from_news() -> list[DetectedPoll]:
    """네이버 뉴스에서 여론조사 결과 숫자 패턴 추출."""
    results = []
    try:
        from collectors.naver_news import search_news

        queries = [
            "경남도지사 여론조사 결과",
            "김경수 박완수 여론조사",
            "경남지사 지지율",
        ]

        seen_titles = set()
        articles = []
        for q in queries:
            arts = search_news(q, display=20, pages=1)
            for a in arts:
                if a["title"] not in seen_titles:
                    seen_titles.add(a["title"])
                    articles.append(a)
            time.sleep(0.3)

        for art in articles:
            text = art.get("title", "") + " " + art.get("description", "")

            # 여론조사 관련 키워드 체크
            if not any(kw in text for kw in ["여론조사", "지지율", "조사 결과", "여론"]):
                continue

            for pattern in POLL_PATTERNS:
                m = pattern.search(text)
                if m:
                    groups = m.groups()
                    # 첫 번째 패턴: 김경수, 박완수 순서
                    if "박완수" in pattern.pattern[:10]:
                        park_val = float(groups[0])
                        kim_val = float(groups[1])
                    else:
                        kim_val = float(groups[0])
                        park_val = float(groups[1])

                    # 유효성 체크
                    if 15 <= kim_val <= 70 and 15 <= park_val <= 70:
                        # 조사기관 추출
                        org = ""
                        for kw, name in ORG_KEYWORDS.items():
                            if kw in text:
                                org = name
                                break

                        # 날짜 추출 시도
                        date_match = re.search(r'(\d{4})[.-](\d{1,2})[.-](\d{1,2})', text)
                        poll_date = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}" if date_match else ""

                        results.append(DetectedPoll(
                            source="뉴스추출",
                            org=org,
                            date=poll_date or art.get("pub_date", "")[:10],
                            kim=kim_val,
                            park=park_val,
                            gap=round(kim_val - park_val, 1),
                            title=art["title"][:60],
                            confidence=0.7 if org else 0.5,
                            url=art.get("link", ""),
                        ))
                    break  # 한 기사에서 1개만

        if results:
            print(f"[PollAuto] 뉴스 추출: {len(results)}건 여론조사 패턴 발견")

    except Exception as e:
        print(f"[PollAuto] 뉴스 추출 실패: {e}")

    return results


def auto_collect_polls() -> list[DetectedPoll]:
    """A + B 통합: nesdc + 뉴스 추출."""
    all_polls = []

    # A. nesdc
    all_polls.extend(sync_nesdc())

    time.sleep(0.5)

    # B. 뉴스 추출
    all_polls.extend(extract_polls_from_news())

    # 중복 제거 (같은 kim+park 조합)
    seen = set()
    unique = []
    for p in all_polls:
        key = f"{p.kim:.1f}_{p.park:.1f}"
        if key not in seen:
            seen.add(key)
            unique.append(p)

    # 신뢰도 순 정렬
    unique.sort(key=lambda x: -x.confidence)

    return unique
