"""
Election Strategy Engine — Decision Logger (v5)
전략 엔진의 추천을 기록하고, 사람의 수정/승인을 추적합니다.

이 모듈은 '관찰 가능성'만 담당합니다.
- 추천 기록 (recommendation)
- 사람 수정 기록 (override)
- 실행 기록 (execution)
- 결과 관찰은 outcome_evaluator.py가 담당

자동 학습/적응은 하지 않습니다. 먼저 데이터를 모아야 합니다.
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


# ── 로깅 데이터 객체 ────────────────────────────────────────────

@dataclass
class DecisionRecord:
    """엔진이 내린 하나의 추천 기록"""
    decision_id: str             # "{tenant_id}_{date}_{seq}"
    tenant_id: str
    decision_type: str           # "issue_stance" | "campaign_mode" | "region_priority" |
                                 # "opponent_action" | "key_message" | "leading_index"
    keyword: str = ""            # 관련 이슈 키워드 (있으면)
    region: str = ""             # 관련 지역 (있으면)

    # 엔진 추천
    recommended_value: str = ""  # 추천 값 (stance="push", mode="ATTACK" 등)
    confidence: str = ""         # "high" | "medium" | "low"
    reasoning: str = ""          # 왜 이 추천을 했는가

    # 컨텍스트 스냅샷 (나중에 결과와 비교할 때 필요)
    context_snapshot: dict = field(default_factory=dict)
    # {"issue_score": 75, "neg_ratio": 0.3, "poll_gap": -2.1, ...}

    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d


@dataclass
class OverrideRecord:
    """사람이 엔진 추천을 수정한 기록"""
    decision_id: str             # DecisionRecord.decision_id 참조
    original_value: str          # 엔진이 추천한 값
    overridden_value: str        # 사람이 바꾼 값
    override_reason: str = ""    # 왜 바꿨는가 (선택)
    overridden_by: str = ""      # 누가 (선택)
    overridden_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["overridden_at"] = self.overridden_at.isoformat()
        return d


@dataclass
class ExecutionRecord:
    """추천이 실제로 실행되었는지 기록"""
    decision_id: str
    was_executed: bool = False   # 실행 여부
    execution_note: str = ""     # "보도자료 배포 완료" 등
    executed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.executed_at:
            d["executed_at"] = self.executed_at.isoformat()
        return d


# ── 로깅 함수 ──────────────────────────────────────────────────

def _make_decision_id(tenant_id: str, decision_type: str, seq: int = 0) -> str:
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    return f"{tenant_id}_{date_str}_{decision_type}_{seq}"


def log_strategy_decisions(
    daily_strategy,
    issue_responses: list,
    leading_index=None,
    tenant_id: str = "",
) -> list[DecisionRecord]:
    """
    오케스트레이터 파이프라인 완료 후 호출.
    DailyStrategy + IssueResponse + LeadingIndex에서 주요 결정을 추출하여 기록.

    Returns:
        list[DecisionRecord] — DB에 저장할 결정 기록 목록
    """
    records = []
    seq = 0

    # 1. 캠페인 모드 결정
    records.append(DecisionRecord(
        decision_id=_make_decision_id(tenant_id, "campaign_mode", seq),
        tenant_id=tenant_id,
        decision_type="campaign_mode",
        recommended_value=daily_strategy.campaign_mode.value,
        confidence=daily_strategy.confidence,
        reasoning=daily_strategy.mode_reasoning,
        context_snapshot={
            "win_probability": daily_strategy.win_probability,
            "days_left": daily_strategy.days_left,
            "risk_level": daily_strategy.risk_level,
        },
    ))
    seq += 1

    # 2. 지역 우선순위 결정
    for r in daily_strategy.region_schedule:
        records.append(DecisionRecord(
            decision_id=_make_decision_id(tenant_id, "region_priority", seq),
            tenant_id=tenant_id,
            decision_type="region_priority",
            region=r["region"],
            recommended_value=f"priority_{r['priority']}",
            reasoning=r["reason"],
            context_snapshot={
                "priority": r["priority"],
                "talking_points": r.get("talking_points", []),
            },
        ))
        seq += 1

    # 3. 이슈별 대응 입장 결정
    for ir in issue_responses:
        records.append(DecisionRecord(
            decision_id=_make_decision_id(tenant_id, "issue_stance", seq),
            tenant_id=tenant_id,
            decision_type="issue_stance",
            keyword=ir.keyword,
            recommended_value=ir.stance,
            confidence="high" if ir.urgency == "즉시" else "medium",
            reasoning=ir.stance_reason,
            context_snapshot={
                "score": ir.score,
                "level": ir.level.name if hasattr(ir.level, 'name') else str(ir.level),
                "urgency": ir.urgency,
                "owner": ir.owner,
                "lifecycle": ir.lifecycle,
                "golden_time_hours": ir.golden_time_hours,
            },
        ))
        seq += 1

    # 4. 상대 대응 결정
    for oa in daily_strategy.opponent_actions:
        records.append(DecisionRecord(
            decision_id=_make_decision_id(tenant_id, "opponent_action", seq),
            tenant_id=tenant_id,
            decision_type="opponent_action",
            keyword=oa["opponent"],
            recommended_value=oa["action"],
            reasoning=oa["detail"],
        ))
        seq += 1

    # 5. 선행지수 예측
    if leading_index and leading_index.index != 50.0:
        records.append(DecisionRecord(
            decision_id=_make_decision_id(tenant_id, "leading_index", seq),
            tenant_id=tenant_id,
            decision_type="leading_index",
            recommended_value=leading_index.direction,
            confidence=leading_index.confidence,
            reasoning=leading_index.explanation_text,
            context_snapshot={
                "index": leading_index.index,
                "predicted_direction": leading_index.predicted_direction,
                "predicted_magnitude": leading_index.predicted_magnitude,
                "primary_driver": leading_index.primary_driver,
                "components": leading_index.components,
            },
        ))
        seq += 1

    return records


def log_override(
    decision_id: str,
    original_value: str,
    new_value: str,
    reason: str = "",
    overridden_by: str = "",
) -> OverrideRecord:
    """사람이 엔진 추천을 수정할 때 호출"""
    return OverrideRecord(
        decision_id=decision_id,
        original_value=original_value,
        overridden_value=new_value,
        override_reason=reason,
        overridden_by=overridden_by,
    )


def log_execution(
    decision_id: str,
    was_executed: bool,
    note: str = "",
) -> ExecutionRecord:
    """추천이 실행되었는지 기록할 때 호출"""
    return ExecutionRecord(
        decision_id=decision_id,
        was_executed=was_executed,
        execution_note=note,
        executed_at=datetime.now() if was_executed else None,
    )
