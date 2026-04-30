"""
Engine 5 — Polling Tracker
여론조사 추적, 승률 계산, 유권자 트렌드 분석
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

from models.schemas import PollingData

# ---------------------------------------------------------------------------
# 실제 2026 경남도지사 여론조사 데이터
# ---------------------------------------------------------------------------
# 중앙선거여론조사심의위원회 등록 데이터 기반 (nesdc.go.kr)
# nesdc_scraper로 자동 수집 후 DB 저장 → _load_initial_polls()에서 로드
# 아래는 스크래퍼 미작동 시 fallback 초기 데이터
INITIAL_POLLS = [
    # 출처: nesdc.go.kr 등록번호 14916 — 한국갤럽/경남신문
    {"date": "2025-12-26", "pollster": "한국갤럽/경남신문 (nesdc:16900)", "our_support": 43.0, "opponent_support": {"박완수": 45.0}, "margin_of_error": 3.1, "sample_size": 1008},
    # 출처: nesdc.go.kr 등록번호 15024 — 한국사회여론연구소/부산일보
    {"date": "2026-01-02", "pollster": "KSOI/부산일보 (nesdc:17025)", "our_support": 38.1, "opponent_support": {"박완수": 38.3}, "margin_of_error": 3.1, "sample_size": 1011},
    # 출처: nesdc.go.kr 등록번호 15143 — 리얼미터/경남일보
    {"date": "2026-01-24", "pollster": "리얼미터/경남일보 (nesdc:17162)", "our_support": 41.1, "opponent_support": {"박완수": 43.3}, "margin_of_error": 3.1, "sample_size": 1001},
    # 출처: nesdc.go.kr 등록번호 15369 — 케이스탯리서치/KBS
    {"date": "2026-02-10", "pollster": "케이스탯리서치/KBS (nesdc:17373)", "our_support": 30.0, "opponent_support": {"박완수": 29.0}, "margin_of_error": 3.5, "sample_size": 805},
    # 출처: nesdc.go.kr 등록번호 15497 — 서던포스트/KNN
    {"date": "2026-03-03", "pollster": "서던포스트/KNN (nesdc:17574)", "our_support": 36.4, "opponent_support": {"박완수": 34.0}, "margin_of_error": 3.1, "sample_size": 1007},
    # 출처: 톱스타뉴스/여론조사꽃 — Trend Report 수집
    {"date": "2026-01-28", "pollster": "여론조사꽃/톱스타뉴스", "our_support": 47.7, "opponent_support": {"박완수": 37.4}, "margin_of_error": 3.1, "sample_size": 1005},
    # 출처: 오마이뉴스 — 가상대결 (단수공천 이후)
    {"date": "2026-03-17", "pollster": "리얼미터/경남일보 (단수공천후)", "our_support": 38.1, "opponent_support": {"박완수": 38.3}, "margin_of_error": 3.1, "sample_size": 1001},
    # 출처: 한국갤럽/세계일보 — 전화면접(CATI), 양자 가상대결, 응답률 15.4%
    {"date": "2026-04-08", "pollster": "한국갤럽/세계일보 (면접)", "our_support": 44.0, "opponent_support": {"박완수": 40.0}, "margin_of_error": 3.5, "sample_size": 806},
    # 출처: 한국리서치/KBS창원 — 전화면접, 다자대결, 응답률 20.6%
    {"date": "2026-04-16", "pollster": "한국리서치/KBS창원 (면접)", "our_support": 37.0, "opponent_support": {"박완수": 27.0, "전희영": 1.0}, "margin_of_error": 3.5, "sample_size": 800},
    # 출처: KSOI/MBC경남 — ARS(무선100%), 다자대결, 응답률 5.8%
    {"date": "2026-04-21", "pollster": "KSOI/MBC경남 (ARS)", "our_support": 46.9, "opponent_support": {"박완수": 35.7, "전희영": 3.3}, "margin_of_error": 3.1, "sample_size": 1001},
]


class PollingTracker:
    """여론조사 추적 및 승률 분석 엔진"""

    def __init__(self, config=None):
        self.config = config
        self.polls: list[PollingData] = []
        self._load_initial_polls()

    # ------------------------------------------------------------------
    # 데이터 로드 / 추가
    # ------------------------------------------------------------------
    def _load_initial_polls(self):
        """Embed 데이터 + DB 저장 데이터 모두 로드"""
        for p in INITIAL_POLLS:
            poll = PollingData(
                poll_date=p["date"],
                pollster=p["pollster"],
                sample_size=p["sample_size"],
                margin_of_error=p["margin_of_error"],
                our_support=p["our_support"],
                opponent_support=p["opponent_support"],
            )
            self.polls.append(poll)
        # DB에 저장된 추가 여론조사 로드
        try:
            from storage.database import ElectionDB
            db = ElectionDB()
            db_polls = db.get_all_polls()
            db.close()
            existing = {(p.poll_date, p.pollster) for p in self.polls}
            for dp in db_polls:
                key = (dp.get("poll_date", ""), dp.get("pollster", ""))
                if key not in existing:
                    self.polls.append(PollingData(
                        poll_date=dp["poll_date"],
                        pollster=dp["pollster"],
                        sample_size=dp.get("sample_size", 1000),
                        margin_of_error=dp.get("margin_of_error", 3.0),
                        our_support=dp["our_support"],
                        opponent_support=dp.get("opponent_support", {}),
                        undecided=dp.get("undecided", 0),
                    ))
        except Exception:
            pass
        self.polls.sort(key=lambda p: p.poll_date)

    def add_poll(self, poll: PollingData):
        """새 여론조사 추가 (메모리 + DB 저장)"""
        self.polls.append(poll)
        self.polls.sort(key=lambda p: p.poll_date)
        try:
            from storage.database import ElectionDB
            db = ElectionDB()
            db.save_poll(
                poll_date=poll.poll_date, pollster=poll.pollster,
                sample_size=poll.sample_size, margin_of_error=poll.margin_of_error,
                our_support=poll.our_support, opponent_support=poll.opponent_support,
                undecided=poll.undecided,
            )
            db.close()
        except Exception:
            pass

    def get_latest(self) -> Optional[PollingData]:
        """가장 최근 여론조사 반환"""
        if not self.polls:
            return None
        return max(self.polls, key=lambda p: p.poll_date)

    # ------------------------------------------------------------------
    # 트렌드 분석
    # ------------------------------------------------------------------
    def calculate_trend(self, days: int = 30) -> dict:
        """
        최근 N일간 지지율 추세 계산.
        선형 회귀(수동 구현)로 일별 변화율 산출.
        """
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        recent = [p for p in self.polls if p.poll_date >= cutoff]

        if len(recent) < 2:
            return {
                "our_trend": 0.0,
                "opponent_trends": {},
                "momentum": "stable",
                "trend_summary": f"최근 {days}일간 데이터 부족 (2개 미만)",
            }

        # X축: 기준일로부터의 일수, Y축: 지지율
        base_date = datetime.strptime(recent[0].poll_date, "%Y-%m-%d")
        xs = [(datetime.strptime(p.poll_date, "%Y-%m-%d") - base_date).days for p in recent]
        ys_our = [p.our_support for p in recent]

        our_slope = self._linear_slope(xs, ys_our)

        # 상대 후보별 트렌드
        opponent_names: set[str] = set()
        for p in recent:
            opponent_names.update(p.opponent_support.keys())

        opponent_trends = {}
        for name in opponent_names:
            ys_opp = [p.opponent_support.get(name, 0.0) for p in recent]
            opponent_trends[name] = round(self._linear_slope(xs, ys_opp), 4)

        # 모멘텀 판정
        if our_slope > 0.05:
            momentum = "gaining"
        elif our_slope < -0.05:
            momentum = "losing"
        else:
            momentum = "stable"

        total_change = our_slope * (xs[-1] - xs[0]) if xs[-1] != xs[0] else 0.0
        direction = "상승" if total_change >= 0 else "하락"

        return {
            "our_trend": round(our_slope, 4),
            "opponent_trends": opponent_trends,
            "momentum": momentum,
            "trend_summary": f"최근 {days}일간 {abs(total_change):.1f}%p {direction} 추세",
        }

    # ------------------------------------------------------------------
    # 승률 계산
    # ------------------------------------------------------------------
    def calculate_win_probability(self) -> dict:
        """
        최근 3개 여론조사의 가중 평균 + 오차범위 기반 승률 추정.
        scipy 없이 math.erf 로 정규분포 CDF 근사.
        """
        if not self.polls:
            return {"win_prob": 0.5, "our_avg": 0.0, "opponent_avg": {}, "gap": 0.0,
                    "confidence": "low", "assessment": "데이터 없음"}

        sorted_polls = sorted(self.polls, key=lambda p: p.poll_date, reverse=True)
        last_n = sorted_polls[:min(3, len(sorted_polls))]

        # 가중치: (1/days_old + 1) * sqrt(sample_size)
        today = datetime.now()
        weights = []
        for p in last_n:
            poll_dt = datetime.strptime(p.poll_date, "%Y-%m-%d")
            days_old = max((today - poll_dt).days, 1)
            w = (1.0 / days_old + 1.0) * math.sqrt(p.sample_size)
            weights.append(w)

        total_w = sum(weights)
        if total_w == 0:
            total_w = 1.0

        our_avg = sum(p.our_support * w for p, w in zip(last_n, weights)) / total_w

        # 상대 후보별 가중 평균
        opponent_names: set[str] = set()
        for p in last_n:
            opponent_names.update(p.opponent_support.keys())

        opponent_avg: dict[str, float] = {}
        for name in opponent_names:
            opp_sum = sum(p.opponent_support.get(name, 0.0) * w for p, w in zip(last_n, weights))
            opponent_avg[name] = round(opp_sum / total_w, 2)

        # 주적 후보 (최고 지지율)
        main_opp_name = max(opponent_avg, key=opponent_avg.get) if opponent_avg else None
        main_opp_avg = opponent_avg.get(main_opp_name, 0.0) if main_opp_name else 0.0

        gap = our_avg - main_opp_avg

        # 결합 표준오차: sqrt(sum(moe_i^2 * w_i) / sum(w_i)) — 가중 평균 오차
        combined_stderr = math.sqrt(
            sum((p.margin_of_error ** 2) * w for p, w in zip(last_n, weights)) / total_w
        )
        if combined_stderr == 0:
            combined_stderr = 3.0  # fallback

        # P(우리 > 상대) = Phi((our_avg - opp_avg) / combined_stderr)
        # Phi(x) = 0.5 * (1 + erf(x / sqrt(2)))
        z = gap / combined_stderr
        win_prob = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

        # 신뢰도 판정
        if len(last_n) >= 3 and combined_stderr < 3.5:
            confidence = "high"
        elif len(last_n) >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        # 평가 문구
        abs_gap = abs(gap)
        if abs_gap <= 2.0:
            assessment = f"초박빙 접전 — {abs_gap:.1f}%p 차이로 승패 예측 어려움"
        elif gap > 0:
            if gap > 5.0:
                assessment = f"우세 — {gap:.1f}%p 리드 중"
            else:
                assessment = f"소폭 우세 — {gap:.1f}%p 리드, 오차범위 내"
        else:
            if abs_gap > 5.0:
                assessment = f"열세 — {abs_gap:.1f}%p 뒤처짐, 반전 전략 필요"
            else:
                assessment = f"소폭 열세 — {abs_gap:.1f}%p 뒤처짐, 오차범위 내 역전 가능"

        return {
            "win_prob": round(win_prob, 4),
            "our_avg": round(our_avg, 2),
            "opponent_avg": opponent_avg,
            "gap": round(gap, 2),
            "confidence": confidence,
            "assessment": assessment,
        }

    # ------------------------------------------------------------------
    # 부동층 분석
    # ------------------------------------------------------------------
    def analyze_swing_voters(self) -> dict:
        """미결정 유권자 풀 분석"""
        latest = self.get_latest()
        if not latest:
            return {"undecided_pct": 0.0, "needed_from_undecided": 0.0,
                    "strategy": "데이터 없음"}

        # 미정 비율 추정: 100 - 우리 - 상대 합계
        total_declared = latest.our_support + sum(latest.opponent_support.values())
        undecided_pct = max(100.0 - total_declared, 0.0)

        # 주적 후보
        main_opp = max(latest.opponent_support.values()) if latest.opponent_support else 0.0
        deficit = main_opp - latest.our_support

        if deficit <= 0:
            # 이미 앞서고 있음
            needed = 0.0
            strategy = "현 지지율 유지 전략 — 리드 유지에 집중"
        elif undecided_pct <= 0:
            needed = 100.0  # 부동층 없이 역전 불가
            strategy = "상대 지지층 이탈 유도 필요 — 부동층 부재"
        else:
            needed = round((deficit / undecided_pct) * 100.0, 1)
            if needed > 60:
                strategy = "공격적 유권자 확보 필요 — 부동층 대부분 확보해야 역전"
            elif needed > 40:
                strategy = "적극적 부동층 공략 — 절반 이상 확보 필요"
            else:
                strategy = "부동층 분할 시 역전 가능 — 메시지 차별화 집중"

        return {
            "undecided_pct": round(undecided_pct, 1),
            "needed_from_undecided": needed,
            "strategy": strategy,
        }

    # ------------------------------------------------------------------
    # 요약
    # ------------------------------------------------------------------
    def get_polling_summary(self) -> str:
        """전략 엔진용 여론조사 요약 텍스트 반환"""
        latest = self.get_latest()
        trend = self.calculate_trend()
        prob = self.calculate_win_probability()
        swing = self.analyze_swing_voters()

        lines = [
            "=== 여론조사 현황 ===",
        ]
        if latest:
            main_opp_name = max(latest.opponent_support, key=latest.opponent_support.get) if latest.opponent_support else "N/A"
            main_opp_val = latest.opponent_support.get(main_opp_name, 0.0) if latest.opponent_support else 0.0
            lines.append(f"최신 조사: {latest.pollster} ({latest.poll_date})")
            lines.append(f"  우리 후보: {latest.our_support}% | {main_opp_name}: {main_opp_val}%")

        lines.append(f"추세: {trend['trend_summary']} (모멘텀: {trend['momentum']})")
        lines.append(f"승률: {prob['win_prob']*100:.1f}% (가중평균 {prob['our_avg']}% vs {prob.get('opponent_avg', {})})")
        lines.append(f"판정: {prob['assessment']}")
        lines.append(f"부동층: {swing['undecided_pct']}% — {swing['strategy']}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 유틸리티
    # ------------------------------------------------------------------
    @staticmethod
    def _linear_slope(xs: list[float], ys: list[float]) -> float:
        """단순 선형 회귀 기울기 (최소자승법)"""
        n = len(xs)
        if n < 2:
            return 0.0
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        den = sum((x - mean_x) ** 2 for x in xs)
        if den == 0:
            return 0.0
        return num / den
