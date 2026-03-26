"""
National Poll Collector — 대통령/정당 지지율 수집
지방선거 판세의 약 50%를 결정하는 중앙정치 환경을 측정합니다.

수집 방법:
  1. 네이버 뉴스에서 "한국갤럽 대통령 지지율" 최신 기사 파싱
  2. 수동 입력 (초기 데이터)
  3. 향후: 갤럽 웹 자동 수집

Leading Index에 신규 component로 반영.
"""
from __future__ import annotations
import re
import os
import time
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NationalPollData:
    """대통령/정당 지지율 데이터"""
    date: str = ""                      # "2026-03-19"
    source: str = ""                    # "한국갤럽 제655호"

    # 대통령 직무수행 평가
    president_approval: float = 0.0     # 긍정 %
    president_disapproval: float = 0.0  # 부정 %

    # 정당 지지율
    dem_support: float = 0.0            # 더불어민주당 %
    ppp_support: float = 0.0            # 국민의힘 %
    other_support: float = 0.0          # 기타 정당 합산 %

    # 지방선거 영향 추정
    honeymoon_score: float = 0.0        # 대통령효과 효과 점수 (-50 ~ +50)
    party_gap: float = 0.0             # 민주-국힘 격차 (%p)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "source": self.source,
            "president_approval": self.president_approval,
            "president_disapproval": self.president_disapproval,
            "dem_support": self.dem_support,
            "ppp_support": self.ppp_support,
            "party_gap": round(self.party_gap, 1),
            "honeymoon_score": round(self.honeymoon_score, 1),
        }


# ── 초기 데이터 (수동 입력 — 뉴스 기사 기반) ──
INITIAL_NATIONAL_POLLS = [
    # 출처: 한국갤럽 + 뉴스 보도
    {"date": "2025-12-19", "source": "한국갤럽 제641호", "president_approval": 55.0, "president_disapproval": 30.0, "dem_support": 41.0, "ppp_support": 24.0},
    {"date": "2026-01-16", "source": "한국갤럽 제645호", "president_approval": 58.0, "president_disapproval": 28.0, "dem_support": 43.0, "ppp_support": 22.0},
    {"date": "2026-02-06", "source": "한국갤럽 제648호", "president_approval": 60.0, "president_disapproval": 27.0, "dem_support": 44.0, "ppp_support": 22.0},
    {"date": "2026-02-27", "source": "한국갤럽 제651호", "president_approval": 63.0, "president_disapproval": 26.0, "dem_support": 44.0, "ppp_support": 22.0},
    {"date": "2026-03-06", "source": "한국갤럽 제652호", "president_approval": 60.0, "president_disapproval": 27.0, "dem_support": 43.0, "ppp_support": 22.0},
    {"date": "2026-03-13", "source": "한국갤럽 제653호", "president_approval": 66.0, "president_disapproval": 24.0, "dem_support": 47.0, "ppp_support": 20.0},
    {"date": "2026-03-19", "source": "한국갤럽 제655호", "president_approval": 67.0, "president_disapproval": 25.0, "dem_support": 46.0, "ppp_support": 20.0},
]


def _calc_honeymoon(approval: float, dem: float, ppp: float) -> float:
    """
    대통령효과 효과 점수 산출 (-50 ~ +50).
    대통령 지지율 + 정당 격차 기반.

    높을수록 여당(민주) 후보에게 유리.
    """
    # 대통령 지지율 기여 (50% 기준)
    approval_effect = (approval - 50) * 0.5  # 67% → +8.5

    # 정당 격차 기여
    gap = dem - ppp  # 46-20 = 26
    gap_effect = gap * 0.3  # 26 → +7.8

    # 합산 (-50 ~ +50)
    score = max(-50, min(50, approval_effect + gap_effect))
    return round(score, 1)


def get_latest_national_poll() -> NationalPollData:
    """최신 대통령/정당 지지율 반환"""
    if not INITIAL_NATIONAL_POLLS:
        return NationalPollData()

    latest = max(INITIAL_NATIONAL_POLLS, key=lambda x: x["date"])
    data = NationalPollData(
        date=latest["date"],
        source=latest["source"],
        president_approval=latest["president_approval"],
        president_disapproval=latest["president_disapproval"],
        dem_support=latest["dem_support"],
        ppp_support=latest["ppp_support"],
        party_gap=latest["dem_support"] - latest["ppp_support"],
    )
    data.honeymoon_score = _calc_honeymoon(
        data.president_approval, data.dem_support, data.ppp_support
    )
    return data


def get_national_poll_trend() -> list[dict]:
    """대통령/정당 지지율 시계열"""
    result = []
    for p in sorted(INITIAL_NATIONAL_POLLS, key=lambda x: x["date"]):
        gap = p["dem_support"] - p["ppp_support"]
        honeymoon = _calc_honeymoon(p["president_approval"], p["dem_support"], p["ppp_support"])
        result.append({
            "date": p["date"],
            "approval": p["president_approval"],
            "dem": p["dem_support"],
            "ppp": p["ppp_support"],
            "gap": round(gap, 1),
            "honeymoon": round(honeymoon, 1),
        })
    return result


def fetch_latest_from_news() -> NationalPollData | None:
    """네이버 뉴스에서 최신 갤럽 지지율 자동 파싱 (best effort)"""
    try:
        from collectors.naver_news import search_news
        articles = search_news("한국갤럽 대통령 지지율", display=5, pages=1)

        for art in articles:
            title = art.get("title", "")
            desc = art.get("description", "")
            text = title + " " + desc

            # 패턴: "지지율 67%", "긍정 67%"
            approval_match = re.search(r'(?:지지율|긍정)\s*(\d+)%', text)
            # 패턴: "민주당 46%", "민주 46%"
            dem_match = re.search(r'(?:민주당?)\s*(\d+)%', text)
            # 패턴: "국민의힘 20%", "국힘 20%"
            ppp_match = re.search(r'(?:국민의힘|국힘)\s*(\d+)%', text)

            if approval_match and dem_match:
                approval = float(approval_match.group(1))
                dem = float(dem_match.group(1))
                ppp = float(ppp_match.group(1)) if ppp_match else 20.0

                data = NationalPollData(
                    date=datetime.now().strftime("%Y-%m-%d"),
                    source=f"네이버 뉴스 자동 파싱",
                    president_approval=approval,
                    dem_support=dem,
                    ppp_support=ppp,
                    party_gap=dem - ppp,
                )
                data.honeymoon_score = _calc_honeymoon(approval, dem, ppp)
                return data

    except Exception as e:
        print(f"  [NationalPoll] 뉴스 파싱 실패: {e}")

    return None
