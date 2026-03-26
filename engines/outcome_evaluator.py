"""
Election Strategy Engine — Outcome Evaluator (v5)
과거 결정의 결과를 평가합니다.

이 모듈은 '관찰'만 담당합니다.
- 24-48시간 전 추천 vs 실제 결과 비교
- 정확도 통계 집계
- 어떤 유형의 추천이 잘 맞았는지 리포트

자동 가중치 조정은 하지 않습니다.
사람이 리포트를 보고 판단합니다.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class OutcomeRecord:
    """하나의 추천에 대한 실제 결과"""
    decision_id: str             # DecisionRecord.decision_id 참조
    decision_type: str           # "issue_stance" | "campaign_mode" 등
    keyword: str = ""
    region: str = ""

    # 추천 당시
    recommended_value: str = ""
    confidence: str = ""

    # 실제 결과 (24-48h 후 측정)
    actual_outcome: str = ""     # 실제 관찰된 결과
    outcome_grade: str = ""      # "correct" | "partially_correct" | "wrong" | "inconclusive"

    # 수치 비교 (가능한 경우)
    predicted_metric: float = 0.0   # 예측값
    actual_metric: float = 0.0      # 실측값
    metric_delta: float = 0.0       # actual - predicted

    # 메타
    evaluated_at: datetime = field(default_factory=datetime.now)
    evaluator_note: str = ""     # 평가자 코멘트


@dataclass
class AccuracyReport:
    """결정 유형별 정확도 리포트"""
    decision_type: str
    total_evaluated: int = 0
    correct_count: int = 0
    partial_count: int = 0
    wrong_count: int = 0
    inconclusive_count: int = 0

    @property
    def accuracy_rate(self) -> float:
        """정확도 비율 (correct + partial*0.5) / total"""
        if self.total_evaluated == 0:
            return 0.0
        return (self.correct_count + self.partial_count * 0.5) / self.total_evaluated

    def to_dict(self) -> dict:
        return {
            "decision_type": self.decision_type,
            "total": self.total_evaluated,
            "correct": self.correct_count,
            "partial": self.partial_count,
            "wrong": self.wrong_count,
            "inconclusive": self.inconclusive_count,
            "accuracy_rate": round(self.accuracy_rate, 3),
        }


# ── 평가 함수 ──────────────────────────────────────────────────

def evaluate_issue_stance(
    decision_record,
    current_issue_score: float,
    current_level: str,
    current_neg_ratio: float,
) -> OutcomeRecord:
    """
    이슈 대응 입장 추천의 결과 평가.

    Logic:
    - stance="push"인데 이슈 점수가 올라갔고 부정비율이 올랐으면 → wrong
    - stance="push"인데 이슈 점수가 내려가거나 안정되면 → correct
    - stance="counter"인데 부정비율이 줄었으면 → correct
    - stance="avoid"인데 이슈가 자연 소멸되면 → correct
    """
    ctx = decision_record.context_snapshot
    prev_score = ctx.get("score", 0)
    prev_level = ctx.get("level", "NORMAL")
    stance = decision_record.recommended_value
    score_delta = current_issue_score - prev_score

    outcome = OutcomeRecord(
        decision_id=decision_record.decision_id,
        decision_type="issue_stance",
        keyword=decision_record.keyword,
        recommended_value=stance,
        confidence=decision_record.confidence,
        predicted_metric=prev_score,
        actual_metric=current_issue_score,
        metric_delta=score_delta,
    )

    if stance == "push":
        if score_delta <= 5 and current_neg_ratio < 0.5:
            outcome.outcome_grade = "correct"
            outcome.actual_outcome = f"이슈 안정 유지 (점수 {score_delta:+.0f}, 부정 {current_neg_ratio:.0%})"
        elif score_delta > 10 and current_neg_ratio > 0.6:
            outcome.outcome_grade = "wrong"
            outcome.actual_outcome = f"이슈 악화 (점수 {score_delta:+.0f}, 부정 {current_neg_ratio:.0%})"
        else:
            outcome.outcome_grade = "partially_correct"
            outcome.actual_outcome = f"혼재 결과 (점수 {score_delta:+.0f})"

    elif stance == "counter":
        if current_neg_ratio < 0.4:
            outcome.outcome_grade = "correct"
            outcome.actual_outcome = f"반박 효과 — 부정 비율 {current_neg_ratio:.0%}로 하락"
        elif current_neg_ratio > 0.7:
            outcome.outcome_grade = "wrong"
            outcome.actual_outcome = f"반박 실패 — 부정 비율 {current_neg_ratio:.0%}로 상승"
        else:
            outcome.outcome_grade = "partially_correct"
            outcome.actual_outcome = f"반박 효과 미미 (부정 {current_neg_ratio:.0%})"

    elif stance == "avoid":
        if score_delta < -10:
            outcome.outcome_grade = "correct"
            outcome.actual_outcome = "이슈 자연 소멸"
        elif score_delta > 10:
            outcome.outcome_grade = "wrong"
            outcome.actual_outcome = f"회피했으나 이슈 확대 (점수 {score_delta:+.0f})"
        else:
            outcome.outcome_grade = "partially_correct"
            outcome.actual_outcome = "이슈 유지 중"

    elif stance in ("monitor", "pivot"):
        outcome.outcome_grade = "inconclusive"
        outcome.actual_outcome = f"모니터링/전환 — 효과 측정 어려움 (점수 {score_delta:+.0f})"

    return outcome


def evaluate_leading_index(
    decision_record,
    actual_poll_change: float,    # 실제 여론조사 변화 (%p)
) -> OutcomeRecord:
    """
    선행지수 예측의 결과 평가.

    Logic:
    - predicted_direction이 "상승 예상"인데 실제로 올랐으면 → correct
    - predicted_magnitude와 actual 차이가 1.5%p 이내면 → correct
    """
    ctx = decision_record.context_snapshot
    predicted_dir = ctx.get("predicted_direction", "")
    predicted_mag = ctx.get("predicted_magnitude", 0.0)
    index_value = ctx.get("index", 50.0)

    outcome = OutcomeRecord(
        decision_id=decision_record.decision_id,
        decision_type="leading_index",
        recommended_value=decision_record.recommended_value,
        confidence=decision_record.confidence,
        predicted_metric=predicted_mag,
        actual_metric=actual_poll_change,
        metric_delta=actual_poll_change - predicted_mag,
    )

    # 방향 일치 체크
    direction_match = False
    if "상승" in predicted_dir and actual_poll_change > 0:
        direction_match = True
    elif "하락" in predicted_dir and actual_poll_change < 0:
        direction_match = True
    elif "미미" in predicted_dir and abs(actual_poll_change) < 1.0:
        direction_match = True

    # 크기 일치 체크
    magnitude_match = abs(actual_poll_change - predicted_mag) <= 1.5

    if direction_match and magnitude_match:
        outcome.outcome_grade = "correct"
        outcome.actual_outcome = f"예측 적중: 방향·크기 모두 일치 (예측 {predicted_mag:+.1f}%p, 실제 {actual_poll_change:+.1f}%p)"
    elif direction_match:
        outcome.outcome_grade = "partially_correct"
        outcome.actual_outcome = f"방향 일치, 크기 차이 (예측 {predicted_mag:+.1f}%p, 실제 {actual_poll_change:+.1f}%p)"
    else:
        outcome.outcome_grade = "wrong"
        outcome.actual_outcome = f"방향 불일치 (예측: {predicted_dir}, 실제 {actual_poll_change:+.1f}%p)"

    return outcome


def evaluate_campaign_mode(
    decision_record,
    next_poll_gap_change: float,   # 다음 여론조사 격차 변화
) -> OutcomeRecord:
    """
    캠페인 모드 추천의 결과 평가.

    Logic:
    - ATTACK 모드 → 격차가 줄어들면 correct
    - DEFENSE 모드 → 리드가 유지/확대되면 correct
    - INITIATIVE 모드 → 유리해지면 correct
    """
    mode = decision_record.recommended_value

    outcome = OutcomeRecord(
        decision_id=decision_record.decision_id,
        decision_type="campaign_mode",
        recommended_value=mode,
        confidence=decision_record.confidence,
        predicted_metric=0,
        actual_metric=next_poll_gap_change,
        metric_delta=next_poll_gap_change,
    )

    if mode == "공격":  # ATTACK
        if next_poll_gap_change > 0:
            outcome.outcome_grade = "correct"
            outcome.actual_outcome = f"공격 모드 효과 — 격차 {next_poll_gap_change:+.1f}%p 개선"
        elif next_poll_gap_change > -1:
            outcome.outcome_grade = "partially_correct"
            outcome.actual_outcome = f"공격 모드 — 격차 소폭 변동 ({next_poll_gap_change:+.1f}%p)"
        else:
            outcome.outcome_grade = "wrong"
            outcome.actual_outcome = f"공격 모드 역효과 — 격차 {next_poll_gap_change:+.1f}%p 악화"

    elif mode == "수비":  # DEFENSE
        if next_poll_gap_change >= -1:
            outcome.outcome_grade = "correct"
            outcome.actual_outcome = f"수비 모드 성공 — 리드 유지 ({next_poll_gap_change:+.1f}%p)"
        else:
            outcome.outcome_grade = "wrong"
            outcome.actual_outcome = f"수비 모드 실패 — 리드 축소 ({next_poll_gap_change:+.1f}%p)"

    elif mode == "선점":  # INITIATIVE
        if next_poll_gap_change > 0.5:
            outcome.outcome_grade = "correct"
            outcome.actual_outcome = f"선점 모드 효과 — 지지 상승 ({next_poll_gap_change:+.1f}%p)"
        elif next_poll_gap_change > -0.5:
            outcome.outcome_grade = "partially_correct"
            outcome.actual_outcome = f"선점 모드 — 변동 미미 ({next_poll_gap_change:+.1f}%p)"
        else:
            outcome.outcome_grade = "wrong"
            outcome.actual_outcome = f"선점 모드 실패 — 지지 하락 ({next_poll_gap_change:+.1f}%p)"

    elif mode == "위기대응":  # CRISIS
        if next_poll_gap_change > -2:
            outcome.outcome_grade = "correct"
            outcome.actual_outcome = f"위기 관리 성공 — 하락 제한 ({next_poll_gap_change:+.1f}%p)"
        else:
            outcome.outcome_grade = "wrong"
            outcome.actual_outcome = f"위기 관리 실패 — 큰 폭 하락 ({next_poll_gap_change:+.1f}%p)"

    return outcome


def build_accuracy_report(outcomes: list[OutcomeRecord]) -> list[AccuracyReport]:
    """
    결과 목록에서 결정 유형별 정확도 리포트 생성.
    대시보드에서 주기적으로 호출하여 엔진 성능을 모니터링.
    """
    type_map: dict[str, AccuracyReport] = {}

    for o in outcomes:
        if o.decision_type not in type_map:
            type_map[o.decision_type] = AccuracyReport(decision_type=o.decision_type)
        report = type_map[o.decision_type]
        report.total_evaluated += 1

        if o.outcome_grade == "correct":
            report.correct_count += 1
        elif o.outcome_grade == "partially_correct":
            report.partial_count += 1
        elif o.outcome_grade == "wrong":
            report.wrong_count += 1
        else:
            report.inconclusive_count += 1

    return list(type_map.values())
