"""
V3 API Routes — FastAPI endpoints for Strategy OS Dashboard
기존 dashboard/app.py에 마운트하여 사용

v5: /api/v3/learning/* 엔드포인트 추가 — 학습 루프 API
"""
from __future__ import annotations


import json
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from v3.storage import V3Storage
from v3.models.signals import InternalSignal, SignalType, Confidence, Priority
from v3.models.proposals import ProposalStatus
from v3.models.memory import MemoryType

router = APIRouter(prefix="/api/v3", tags=["v3"])

# Storage는 앱 시작 시 주입
_storage: Optional[V3Storage] = None

# v5: ElectionDB (learning loop용)
_election_db = None


def init_storage(storage: V3Storage):
    global _storage, _election_db
    _storage = storage

    # ElectionDB 초기화 (v5 learning loop tables 포함)
    try:
        from storage.database import ElectionDB
        _db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data", "election_engine.db",
        )
        _election_db = ElectionDB(_db_path)
    except Exception as e:
        print(f"[V5] Warning: ElectionDB init failed: {e}")


def _get_storage() -> V3Storage:
    if _storage is None:
        raise HTTPException(500, "V3 Storage not initialized")
    return _storage


def _get_election_db():
    if _election_db is None:
        raise HTTPException(500, "ElectionDB not initialized")
    return _election_db


# ──────────────────────────────────────────────────────────────────
# Request Models
# ──────────────────────────────────────────────────────────────────

class SignalCreate(BaseModel):
    signal_type: str
    content: str
    issue_id: Optional[str] = None
    region: Optional[str] = None
    confidence: str = "medium"
    priority: str = "normal"
    expiry_hours: Optional[int] = None


class ProposalDecision(BaseModel):
    decided_by: str = "strategy_director"
    human_version: Optional[str] = None
    rejection_reason: Optional[str] = None
    assigned_owner: Optional[str] = None


class NarrativeCreate(BaseModel):
    priority: int
    frame: str
    keywords: list[str] = []
    expiry_hours: Optional[int] = None


class BlockCreate(BaseModel):
    term: str
    reason: str = ""
    scope: str = "all"
    expiry_hours: Optional[int] = None


class MemoryUpdate(BaseModel):
    value: dict
    source: str = "director_input"


class OutcomeRecord(BaseModel):
    outcome: str  # positive | negative | neutral | unknown
    reason: str = ""


# ──────────────────────────────────────────────────────────────────
# Dashboard Status
# ──────────────────────────────────────────────────────────────────

@router.get("/dashboard/status-bar")
def get_status_bar():
    """상단 바 데이터: pending proposals, active overrides, signals."""
    s = _get_storage()
    return s.get_dashboard_status()


@router.get("/dashboard/command-box")
def get_command_box():
    """오늘 승인된 Top 3 실행 지시."""
    s = _get_storage()
    approved = s.get_approved_today()
    return [p.to_dict() for p in approved[:3]]


# ──────────────────────────────────────────────────────────────────
# Internal Signals
# ──────────────────────────────────────────────────────────────────

@router.get("/signals")
def list_signals(signal_type: Optional[str] = None, limit: int = 50):
    s = _get_storage()
    if signal_type:
        signals = s.get_active_signals(signal_type=SignalType(signal_type))
    else:
        signals = s.get_all_signals(limit=limit)
    return [sig.to_dict() for sig in signals]


@router.post("/signals")
def create_signal(body: SignalCreate):
    s = _get_storage()
    from datetime import timedelta
    expiry = None
    if body.expiry_hours:
        expiry = datetime.utcnow() + timedelta(hours=body.expiry_hours)

    signal = InternalSignal(
        signal_type=SignalType(body.signal_type),
        content=body.content,
        issue_id=body.issue_id,
        region=body.region,
        confidence=Confidence(body.confidence),
        priority=Priority(body.priority),
        expiry=expiry,
        source="dashboard",
    )
    signal_id = s.save_signal(signal)
    return {"id": signal_id, "status": "saved"}


# ──────────────────────────────────────────────────────────────────
# Proposals (Execution Queue)
# ──────────────────────────────────────────────────────────────────

@router.get("/proposals")
def list_proposals(status: Optional[str] = None):
    s = _get_storage()
    if status == "pending":
        proposals = s.get_pending_proposals()
    else:
        # 최근 50건
        proposals = s.get_pending_proposals()  # TODO: all statuses
    return [p.to_dict() for p in proposals]


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: str):
    s = _get_storage()
    p = s.get_proposal(proposal_id)
    if not p:
        raise HTTPException(404, "Proposal not found")
    return p.to_dict()


@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: str, body: ProposalDecision):
    s = _get_storage()
    p = s.get_proposal(proposal_id)
    if not p:
        raise HTTPException(404, "Proposal not found")
    if not p.is_pending:
        raise HTTPException(400, f"Already {p.status.value}")

    s.update_proposal_status(
        proposal_id, ProposalStatus.APPROVED,
        decided_by=body.decided_by,
        assigned_owner=body.assigned_owner,
    )
    return {"status": "approved", "id": proposal_id}


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: str, body: ProposalDecision):
    s = _get_storage()
    p = s.get_proposal(proposal_id)
    if not p:
        raise HTTPException(404)
    if not p.is_pending:
        raise HTTPException(400, f"Already {p.status.value}")

    s.update_proposal_status(
        proposal_id, ProposalStatus.REJECTED,
        decided_by=body.decided_by,
        rejection_reason=body.rejection_reason,
    )
    return {"status": "rejected", "id": proposal_id}


@router.post("/proposals/{proposal_id}/edit")
def edit_proposal(proposal_id: str, body: ProposalDecision):
    s = _get_storage()
    p = s.get_proposal(proposal_id)
    if not p:
        raise HTTPException(404)
    if not p.is_pending:
        raise HTTPException(400, f"Already {p.status.value}")

    s.update_proposal_status(
        proposal_id, ProposalStatus.EDITED,
        decided_by=body.decided_by,
        human_version=body.human_version,
        assigned_owner=body.assigned_owner,
    )
    return {"status": "edited", "id": proposal_id}


@router.post("/proposals/{proposal_id}/outcome")
def record_outcome(proposal_id: str, body: OutcomeRecord):
    """결정 결과 기록 (positive/negative/neutral/unknown)."""
    s = _get_storage()
    p = s.get_proposal(proposal_id)
    if not p:
        raise HTTPException(404)

    # DB에 직접 업데이트
    s._conn.execute(
        "UPDATE strategy_proposals SET outcome=?, outcome_reason=? WHERE id=?",
        (body.outcome, body.reason, proposal_id),
    )
    s._conn.commit()
    return {"status": "recorded", "outcome": body.outcome}


# ──────────────────────────────────────────────────────────────────
# Overrides
# ──────────────────────────────────────────────────────────────────

@router.get("/overrides")
def list_overrides():
    s = _get_storage()
    overrides = s.get_active_overrides()
    return [ov.to_dict() for ov in overrides]


# ──────────────────────────────────────────────────────────────────
# Memory
# ──────────────────────────────────────────────────────────────────

@router.get("/memory")
def list_all_memory():
    s = _get_storage()
    all_mem = s.get_all_memory()
    result = {}
    for mem_type, memories in all_mem.items():
        result[mem_type] = [m.to_dict() for m in memories]
    return result


@router.get("/memory/{memory_type}")
def get_memory_by_type(memory_type: str):
    s = _get_storage()
    memories = s.get_memory(MemoryType(memory_type))
    return [m.to_dict() for m in memories]


@router.put("/memory/{memory_type}/{memory_key}")
def update_memory(memory_type: str, memory_key: str, body: MemoryUpdate):
    from v3.models.memory import StrategicMemory
    s = _get_storage()
    s.save_memory(StrategicMemory(
        memory_type=MemoryType(memory_type),
        memory_key=memory_key,
        value=body.value,
        source=body.source,
        confidence=0.8,
    ))
    return {"status": "updated"}


# ──────────────────────────────────────────────────────────────────
# Narratives & Blocked Terms
# ──────────────────────────────────────────────────────────────────

@router.get("/narratives")
def list_narratives():
    s = _get_storage()
    return s.get_active_narratives()


@router.post("/narratives")
def create_narrative(body: NarrativeCreate):
    from datetime import timedelta
    s = _get_storage()
    expiry = None
    if body.expiry_hours:
        expiry = datetime.utcnow() + timedelta(hours=body.expiry_hours)
    s.save_narrative(body.priority, body.frame, body.keywords, expiry)
    return {"status": "created"}


@router.get("/blocked-terms")
def list_blocked_terms():
    s = _get_storage()
    return s.get_active_blocks()


@router.post("/blocked-terms")
def create_blocked_term(body: BlockCreate):
    from datetime import timedelta
    s = _get_storage()
    expiry = None
    if body.expiry_hours:
        expiry = datetime.utcnow() + timedelta(hours=body.expiry_hours)
    s.save_block(body.term, body.reason, body.scope, expiry)
    return {"status": "created"}


# ──────────────────────────────────────────────────────────────────
# Decision Log & Analytics
# ──────────────────────────────────────────────────────────────────

@router.get("/decisions")
def list_decisions(limit: int = 50):
    s = _get_storage()
    return s.get_decision_log(limit=limit)


@router.get("/decisions/patterns")
def get_decision_patterns():
    """전략실장 override 패턴 분석."""
    s = _get_storage()
    return s.get_override_patterns()


# ──────────────────────────────────────────────────────────────────
# V5 Learning Loop — Decision Review & Outcome Tracking
# ──────────────────────────────────────────────────────────────────

class OverrideRequest(BaseModel):
    """추천 수정 요청"""
    new_value: str                  # 변경할 값 ("counter", "DEFENSE" 등)
    reason: str = ""                # 변경 사유
    overridden_by: str = "전략실장"  # 누가


class ExecutionRequest(BaseModel):
    """실행 확인 요청"""
    was_executed: bool = True
    note: str = ""                  # "보도자료 배포 완료" 등


class ManualOutcomeRequest(BaseModel):
    """수동 결과 평가 요청"""
    outcome_grade: str              # "correct" | "partially_correct" | "wrong" | "inconclusive"
    actual_outcome: str = ""        # 실제 결과 설명
    actual_metric: Optional[float] = None  # 실측값 (있으면)
    evaluator_note: str = ""


class BatchEvaluateRequest(BaseModel):
    """자동 결과 평가 요청 — 현재 데이터 기반으로 대기 중인 결정 평가"""
    tenant_id: str = ""


# ── 추천 목록 조회 ──────────────────────────────────────────────

@router.get("/learning/decisions/pending")
def get_pending_decisions(tenant_id: str = ""):
    """
    승인/수정 대기 중인 오늘의 추천 목록.
    대시보드 '추천 카드' 섹션에 표시.
    """
    db = _get_election_db()
    # 아직 평가되지 않은 최근 결정 (24h 이내)
    rows = db._conn.execute(
        """SELECT * FROM v5_decisions
           WHERE created_at >= datetime('now', '-24 hours')
           ORDER BY created_at DESC""",
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        if d.get("context_snapshot"):
            try:
                d["context_snapshot"] = json.loads(d["context_snapshot"])
            except (json.JSONDecodeError, TypeError):
                pass
        # 상태 표시 추가 (SQLite stores bool as 0/1)
        was_exec = d.get("was_executed")
        if d.get("override_value"):
            d["status"] = "overridden"
        elif was_exec is not None and was_exec:
            d["status"] = "executed"
        elif was_exec is not None and not was_exec:
            d["status"] = "skipped"
        else:
            d["status"] = "pending"
        results.append(d)
    return results


@router.get("/learning/decisions/by-type/{decision_type}")
def get_decisions_by_type(decision_type: str, days: int = 7):
    """결정 유형별 이력 조회."""
    db = _get_election_db()
    rows = db._conn.execute(
        """SELECT * FROM v5_decisions
           WHERE decision_type = ? AND created_at >= datetime('now', ?)
           ORDER BY created_at DESC""",
        (decision_type, f"-{days} days"),
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        if d.get("context_snapshot"):
            try:
                d["context_snapshot"] = json.loads(d["context_snapshot"])
            except (json.JSONDecodeError, TypeError):
                pass
        results.append(d)
    return results


# ── 추천 수정 (Override) ────────────────────────────────────────

@router.post("/learning/decisions/{decision_id}/override")
def override_decision(decision_id: str, body: OverrideRequest):
    """
    엔진 추천을 사람이 수정.
    예: issue_stance "push" → "counter"
    """
    db = _get_election_db()

    # 해당 결정 존재 확인
    row = db._conn.execute(
        "SELECT * FROM v5_decisions WHERE decision_id = ?", (decision_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, f"Decision {decision_id} not found")

    from engines.decision_logger import log_override
    override = log_override(
        decision_id=decision_id,
        original_value=row["recommended_value"],
        new_value=body.new_value,
        reason=body.reason,
        overridden_by=body.overridden_by,
    )
    db.save_override(override)

    return {
        "status": "overridden",
        "decision_id": decision_id,
        "original": row["recommended_value"],
        "new_value": body.new_value,
        "reason": body.reason,
    }


# ── 실행 확인 ────────────────────────────────────────────────

@router.post("/learning/decisions/{decision_id}/executed")
def mark_executed(decision_id: str, body: ExecutionRequest):
    """
    추천이 실제로 실행되었는지 기록.
    대시보드 체크박스 또는 텔레그램 /executed 커맨드에서 호출.
    """
    db = _get_election_db()

    row = db._conn.execute(
        "SELECT * FROM v5_decisions WHERE decision_id = ?", (decision_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, f"Decision {decision_id} not found")

    from engines.decision_logger import log_execution
    exec_rec = log_execution(decision_id, body.was_executed, body.note)
    db.save_execution(exec_rec)

    return {
        "status": "recorded",
        "decision_id": decision_id,
        "was_executed": body.was_executed,
        "note": body.note,
    }


# ── 결과 평가 ────────────────────────────────────────────────

@router.get("/learning/outcomes/awaiting")
def get_awaiting_evaluation(hours_ago: int = 24, tenant_id: str = ""):
    """
    평가 대기 중인 결정 목록 (24-48h 지난 것).
    대시보드 '결과 평가' 섹션에 표시.
    """
    db = _get_election_db()
    pending = db.get_pending_decisions(
        hours_ago=hours_ago,
        tenant_id=tenant_id if tenant_id else None,
    )
    return pending


@router.post("/learning/outcomes/{decision_id}")
def record_outcome_manual(decision_id: str, body: ManualOutcomeRequest):
    """
    수동 결과 평가.
    자동 평가가 어려운 경우 사람이 직접 판단.
    """
    db = _get_election_db()

    row = db._conn.execute(
        "SELECT * FROM v5_decisions WHERE decision_id = ?", (decision_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, f"Decision {decision_id} not found")

    from engines.outcome_evaluator import OutcomeRecord
    outcome = OutcomeRecord(
        decision_id=decision_id,
        decision_type=row["decision_type"],
        keyword=row["keyword"] or "",
        region=row["region"] or "",
        recommended_value=row["recommended_value"] or "",
        actual_outcome=body.actual_outcome,
        outcome_grade=body.outcome_grade,
        predicted_metric=0,
        actual_metric=body.actual_metric or 0,
        metric_delta=0,
        evaluator_note=body.evaluator_note,
    )
    db.save_outcomes([outcome])

    return {
        "status": "evaluated",
        "decision_id": decision_id,
        "grade": body.outcome_grade,
    }


@router.post("/learning/outcomes/auto-evaluate")
def auto_evaluate_outcomes(body: BatchEvaluateRequest):
    """
    자동 결과 평가 — 현재 이슈 점수/여론 데이터와 비교하여 대기 중인 결정을 평가.
    대시보드에서 '자동 평가 실행' 버튼으로 호출.
    """
    db = _get_election_db()
    pending = db.get_pending_decisions(
        hours_ago=24,
        tenant_id=body.tenant_id if body.tenant_id else None,
    )

    if not pending:
        return {"evaluated": 0, "message": "평가 대기 건 없음"}

    from engines.outcome_evaluator import (
        evaluate_issue_stance, evaluate_leading_index,
        evaluate_campaign_mode, OutcomeRecord,
    )
    from engines.decision_logger import DecisionRecord

    # 현재 이슈 점수 조회
    latest_scores = {r["keyword"]: r for r in db.get_latest_scores()}

    outcomes = []
    for row in pending:
        dtype = row["decision_type"]
        ctx = row.get("context_snapshot", {})

        # DecisionRecord-like object 생성
        dr = DecisionRecord(
            decision_id=row["decision_id"],
            tenant_id=row.get("tenant_id", ""),
            decision_type=dtype,
            keyword=row.get("keyword", ""),
            region=row.get("region", ""),
            recommended_value=row.get("recommended_value", ""),
            confidence=row.get("confidence", ""),
            context_snapshot=ctx,
        )

        if dtype == "issue_stance" and dr.keyword:
            current = latest_scores.get(dr.keyword)
            if current:
                outcome = evaluate_issue_stance(
                    dr,
                    current_issue_score=current.get("score", 0),
                    current_level=current.get("crisis_level", "NORMAL"),
                    current_neg_ratio=current.get("negative_ratio", 0.5) or 0.5,
                )
                outcomes.append(outcome)

        elif dtype == "leading_index":
            # 선행지수는 여론조사 변화가 필요 — 수동 평가로 남김
            pass

        elif dtype == "campaign_mode":
            # 캠페인 모드도 여론조사 변화 필요 — 수동 평가로 남김
            pass

    if outcomes:
        db.save_outcomes(outcomes)

    return {
        "evaluated": len(outcomes),
        "pending_manual": len(pending) - len(outcomes),
        "results": [
            {
                "decision_id": o.decision_id,
                "keyword": o.keyword,
                "grade": o.outcome_grade,
                "outcome": o.actual_outcome,
            }
            for o in outcomes
        ],
    }


# ── 정확도 리포트 ────────────────────────────────────────────

@router.get("/learning/accuracy")
def get_accuracy_report(tenant_id: str = "", days: int = 7):
    """
    결정 유형별 정확도 리포트.
    대시보드 차트에 사용.
    """
    db = _get_election_db()
    summary = db.get_accuracy_summary(
        tenant_id=tenant_id if tenant_id else None,
        days=days,
    )

    # 정확도 비율 계산
    for row in summary:
        total = row.get("total", 0)
        if total > 0:
            row["accuracy_rate"] = round(
                (row.get("correct", 0) + row.get("partial", 0) * 0.5) / total,
                3,
            )
        else:
            row["accuracy_rate"] = 0

    return {
        "period_days": days,
        "by_type": summary,
        "overall": _calc_overall(summary),
    }


def _calc_overall(summary: list) -> dict:
    """전체 정확도 집계."""
    total = sum(r.get("total", 0) for r in summary)
    if total == 0:
        return {"total": 0, "accuracy_rate": 0}
    correct = sum(r.get("correct", 0) for r in summary)
    partial = sum(r.get("partial", 0) for r in summary)
    wrong = sum(r.get("wrong", 0) for r in summary)
    return {
        "total": total,
        "correct": correct,
        "partial": partial,
        "wrong": wrong,
        "accuracy_rate": round((correct + partial * 0.5) / total, 3),
    }


# ── 오버라이드 패턴 ──────────────────────────────────────────

@router.get("/learning/override-stats")
def get_override_stats(tenant_id: str = "", days: int = 7):
    """
    어떤 유형의 추천을 사람이 가장 많이 바꾸는가.
    → 엔진이 약한 영역을 식별.
    """
    db = _get_election_db()
    stats = db.get_override_stats(
        tenant_id=tenant_id if tenant_id else None,
        days=days,
    )

    # 오버라이드 비율 계산
    for dtype, data in stats.items():
        total = data.get("total", 0)
        overridden = data.get("overridden", 0)
        data["override_rate"] = round(overridden / total, 3) if total > 0 else 0

    return {
        "period_days": days,
        "by_type": stats,
    }


# ── 학습 대시보드 요약 ────────────────────────────────────────

@router.get("/learning/summary")
def get_learning_summary(tenant_id: str = ""):
    """
    학습 루프 전체 현황 요약 — 대시보드 상단 카드에 표시.
    """
    db = _get_election_db()
    tid = tenant_id if tenant_id else None

    # 오늘 결정 수
    today_count_row = db._conn.execute(
        """SELECT COUNT(*) as cnt FROM v5_decisions
           WHERE created_at >= datetime('now', '-24 hours')"""
    ).fetchone()
    today_decisions = today_count_row["cnt"] if today_count_row else 0

    # 오늘 오버라이드 수
    today_override_row = db._conn.execute(
        """SELECT COUNT(*) as cnt FROM v5_decisions
           WHERE override_value IS NOT NULL
             AND created_at >= datetime('now', '-24 hours')"""
    ).fetchone()
    today_overrides = today_override_row["cnt"] if today_override_row else 0

    # 평가 대기 건수
    awaiting = db.get_pending_decisions(hours_ago=24, tenant_id=tid)

    # 7일 정확도
    accuracy = db.get_accuracy_summary(tenant_id=tid, days=7)
    overall_acc = _calc_overall(accuracy)

    return {
        "today_decisions": today_decisions,
        "today_overrides": today_overrides,
        "awaiting_evaluation": len(awaiting),
        "accuracy_7d": overall_acc,
    }
