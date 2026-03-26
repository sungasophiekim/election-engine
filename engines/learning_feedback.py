from __future__ import annotations
"""
Engine — Learning Feedback Loop (Gap 3: 자동 학습)
과거 결정의 정확도 통계를 기반으로 향후 추천의 confidence를 자동 조정합니다.

기존 decision_logger + outcome_evaluator는 "관찰만" 담당.
이 모듈이 관찰 결과를 피드백으로 변환합니다.

피드백 루프:
  1. 결정 유형별 정확도 집계 (v5_outcomes 테이블)
  2. stance × keyword_pattern별 성공률 계산
  3. confidence 보정 계수 생성
  4. 다음 추천 시 confidence에 반영

원칙:
  - 직접 가중치를 수정하지 않음 (위험)
  - confidence 레벨만 조정 (high/medium/low)
  - 최소 5건 이상 평가된 경우에만 적용
  - 사람이 확인할 수 있는 근거 제공
"""
from dataclasses import dataclass, field
from datetime import datetime


MIN_SAMPLES = 5  # 최소 샘플 수


@dataclass
class StanceAccuracy:
    """stance별 정확도"""
    stance: str
    total: int = 0
    correct: int = 0
    partial: int = 0
    wrong: int = 0
    accuracy_rate: float = 0.0      # (correct + partial*0.5) / total
    confidence_modifier: str = ""   # "boost" | "maintain" | "reduce"

    def compute(self):
        if self.total < MIN_SAMPLES:
            self.confidence_modifier = "maintain"
            return
        self.accuracy_rate = (self.correct + self.partial * 0.5) / self.total
        if self.accuracy_rate >= 0.7:
            self.confidence_modifier = "boost"
        elif self.accuracy_rate >= 0.4:
            self.confidence_modifier = "maintain"
        else:
            self.confidence_modifier = "reduce"


@dataclass
class FeedbackProfile:
    """전체 피드백 프로파일 — 엔진이 참조"""
    stance_accuracy: dict[str, StanceAccuracy] = field(default_factory=dict)
    mode_accuracy: dict[str, float] = field(default_factory=dict)
    leading_index_accuracy: float = 0.0
    overall_accuracy: float = 0.0
    total_evaluated: int = 0
    last_updated: str = ""

    # 패턴 인사이트
    insights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "stance_accuracy": {
                k: {
                    "total": v.total,
                    "correct": v.correct,
                    "wrong": v.wrong,
                    "accuracy": round(v.accuracy_rate, 3),
                    "modifier": v.confidence_modifier,
                }
                for k, v in self.stance_accuracy.items()
            },
            "mode_accuracy": {k: round(v, 3) for k, v in self.mode_accuracy.items()},
            "leading_index_accuracy": round(self.leading_index_accuracy, 3),
            "overall_accuracy": round(self.overall_accuracy, 3),
            "total_evaluated": self.total_evaluated,
            "insights": self.insights,
            "last_updated": self.last_updated,
        }


# ── 인메모리 캐시 ──────────────────────────────────────────────
_cached_profile: FeedbackProfile | None = None


def build_feedback_profile(db=None) -> FeedbackProfile:
    """
    v5_outcomes 테이블에서 정확도 통계를 집계하고
    confidence 보정 프로파일을 생성합니다.

    Args:
        db: ElectionDB 인스턴스 (None이면 자동 생성)
    """
    global _cached_profile

    if db is None:
        try:
            from storage.database import ElectionDB
            db = ElectionDB()
            own_db = True
        except Exception:
            return FeedbackProfile(last_updated=datetime.now().isoformat())
    else:
        own_db = False

    profile = FeedbackProfile(last_updated=datetime.now().isoformat())

    try:
        # v5_outcomes에서 집계
        rows = db._conn.execute("""
            SELECT decision_type, keyword, recommended_value, outcome_grade,
                   predicted_metric, actual_metric
            FROM v5_outcomes
            ORDER BY evaluated_at DESC
        """).fetchall()

        if not rows:
            if own_db:
                db.close()
            return profile

        profile.total_evaluated = len(rows)

        # 1. Stance별 정확도
        stance_data: dict[str, StanceAccuracy] = {}
        mode_correct: dict[str, list[bool]] = {}

        for row in rows:
            row = dict(row)
            dtype = row["decision_type"]
            grade = row.get("outcome_grade", "inconclusive")
            rec_val = row.get("recommended_value", "")

            if dtype == "issue_stance":
                if rec_val not in stance_data:
                    stance_data[rec_val] = StanceAccuracy(stance=rec_val)
                sa = stance_data[rec_val]
                sa.total += 1
                if grade == "correct":
                    sa.correct += 1
                elif grade == "partially_correct":
                    sa.partial += 1
                elif grade == "wrong":
                    sa.wrong += 1

            elif dtype == "campaign_mode":
                if rec_val not in mode_correct:
                    mode_correct[rec_val] = []
                mode_correct[rec_val].append(grade in ("correct", "partially_correct"))

            elif dtype == "leading_index":
                if grade in ("correct", "partially_correct"):
                    profile.leading_index_accuracy += 1

        # Stance 정확도 계산
        for sa in stance_data.values():
            sa.compute()
        profile.stance_accuracy = stance_data

        # Mode 정확도
        for mode, results in mode_correct.items():
            if results:
                profile.mode_accuracy[mode] = sum(results) / len(results)

        # Leading Index 정확도
        li_total = sum(1 for r in rows if dict(r)["decision_type"] == "leading_index")
        if li_total > 0:
            profile.leading_index_accuracy /= li_total

        # 전체 정확도
        all_correct = sum(1 for r in rows if dict(r).get("outcome_grade") in ("correct", "partially_correct"))
        profile.overall_accuracy = all_correct / len(rows)

        # 2. 패턴 인사이트 생성
        profile.insights = _generate_insights(profile)

    except Exception:
        pass
    finally:
        if own_db:
            db.close()

    _cached_profile = profile
    return profile


def _generate_insights(profile: FeedbackProfile) -> list[str]:
    """정확도 데이터에서 실행 가능한 인사이트 생성"""
    insights = []

    # Stance별 인사이트
    for stance, sa in profile.stance_accuracy.items():
        if sa.total < MIN_SAMPLES:
            continue
        if sa.accuracy_rate >= 0.8:
            insights.append(f"'{stance}' 입장 추천이 높은 정확도 ({sa.accuracy_rate:.0%}, {sa.total}건) — confidence 상향 적용")
        elif sa.accuracy_rate <= 0.3:
            insights.append(f"'{stance}' 입장 추천의 정확도가 낮음 ({sa.accuracy_rate:.0%}, {sa.total}건) — 신중하게 추천 필요")

    # 최고/최저 stance
    if len(profile.stance_accuracy) >= 2:
        sorted_stances = sorted(profile.stance_accuracy.values(), key=lambda x: x.accuracy_rate, reverse=True)
        valid = [s for s in sorted_stances if s.total >= MIN_SAMPLES]
        if len(valid) >= 2:
            best = valid[0]
            worst = valid[-1]
            if best.accuracy_rate - worst.accuracy_rate > 0.2:
                insights.append(
                    f"'{best.stance}'({best.accuracy_rate:.0%})가 '{worst.stance}'({worst.accuracy_rate:.0%})보다 "
                    f"유의미하게 정확 — '{worst.stance}' 추천 시 추가 검증 필요"
                )

    # Leading Index 인사이트
    if profile.leading_index_accuracy > 0:
        if profile.leading_index_accuracy >= 0.7:
            insights.append(f"선행지수 예측 정확도 {profile.leading_index_accuracy:.0%} — 신뢰도 높음")
        elif profile.leading_index_accuracy <= 0.3:
            insights.append(f"선행지수 예측 정확도 {profile.leading_index_accuracy:.0%} — 개선 필요")

    return insights


def adjust_confidence(
    original_confidence: str,
    decision_type: str,
    recommended_value: str = "",
) -> str:
    """
    피드백 프로파일 기반으로 confidence 레벨 조정.

    issue_response, strategy_mode 등에서 호출하여
    과거 정확도를 반영한 confidence를 반환합니다.

    Args:
        original_confidence: 엔진이 원래 결정한 confidence
        decision_type: "issue_stance" | "campaign_mode" | "leading_index"
        recommended_value: stance 값 등

    Returns:
        adjusted confidence: "high" | "medium" | "low"
    """
    profile = _cached_profile
    if not profile or profile.total_evaluated < MIN_SAMPLES:
        return original_confidence  # 데이터 부족 → 변경 없음

    # stance confidence 조정
    if decision_type == "issue_stance" and recommended_value in profile.stance_accuracy:
        sa = profile.stance_accuracy[recommended_value]
        if sa.total < MIN_SAMPLES:
            return original_confidence

        if sa.confidence_modifier == "boost":
            # low → medium, medium → high
            return {"low": "medium", "medium": "high", "high": "high"}[original_confidence]
        elif sa.confidence_modifier == "reduce":
            # high → medium, medium → low
            return {"high": "medium", "medium": "low", "low": "low"}[original_confidence]

    # campaign_mode confidence 조정
    elif decision_type == "campaign_mode" and recommended_value in profile.mode_accuracy:
        acc = profile.mode_accuracy[recommended_value]
        if acc >= 0.7:
            return {"low": "medium", "medium": "high", "high": "high"}[original_confidence]
        elif acc <= 0.3:
            return {"high": "medium", "medium": "low", "low": "low"}[original_confidence]

    # leading_index confidence 조정
    elif decision_type == "leading_index":
        if profile.leading_index_accuracy >= 0.7:
            return {"low": "medium", "medium": "high", "high": "high"}[original_confidence]
        elif profile.leading_index_accuracy <= 0.3:
            return {"high": "medium", "medium": "low", "low": "low"}[original_confidence]

    return original_confidence


def get_cached_profile() -> FeedbackProfile | None:
    """캐시된 프로파일 반환 (없으면 None)"""
    return _cached_profile
