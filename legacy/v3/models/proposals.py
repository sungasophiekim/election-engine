"""
Strategy Proposal Models — Layer 5: Human Decision Layer
AI 제안 → 인간 승인/수정/거부 워크플로우
"""
from __future__ import annotations


import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ProposalType(str, Enum):
    STANCE = "stance"
    MESSAGE = "message"
    SCHEDULE = "schedule"
    CRISIS_RESPONSE = "crisis_response"
    ATTACK = "attack"


class Urgency(str, Enum):
    IMMEDIATE = "immediate"
    TODAY = "today"
    H48 = "48h"
    MONITORING = "monitoring"


_proposal_counter = 0


def _next_proposal_id() -> str:
    global _proposal_counter
    _proposal_counter += 1
    return f"P-{_proposal_counter:04d}"


@dataclass
class StrategyProposal:
    """AI가 생성하는 전략 제안. 인간 승인 대기."""

    proposal_type: ProposalType
    ai_recommendation: str
    ai_reasoning: str

    id: str = field(default_factory=_next_proposal_id)
    created_at: datetime = field(default_factory=datetime.utcnow)
    issue_id: Optional[str] = None
    ai_confidence: float = 0.5
    ai_data_sources: list = field(default_factory=list)

    # Human decision
    status: ProposalStatus = ProposalStatus.PENDING
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    human_version: Optional[str] = None
    rejection_reason: Optional[str] = None
    assigned_owner: Optional[str] = None

    # Outcome tracking
    outcome: Optional[str] = None
    outcome_reason: Optional[str] = None

    # Meta
    urgency: Urgency = Urgency.TODAY
    expiry: Optional[datetime] = None
    tags: list = field(default_factory=list)

    # Conflict
    conflict_with_override: bool = False
    override_id: Optional[str] = None

    def approve(self, decided_by: str = "strategy_director",
                assigned_owner: Optional[str] = None):
        self.status = ProposalStatus.APPROVED
        self.decided_by = decided_by
        self.decided_at = datetime.utcnow()
        if assigned_owner:
            self.assigned_owner = assigned_owner

    def reject(self, reason: str, decided_by: str = "strategy_director"):
        self.status = ProposalStatus.REJECTED
        self.decided_by = decided_by
        self.decided_at = datetime.utcnow()
        self.rejection_reason = reason

    def edit(self, human_version: str, decided_by: str = "strategy_director",
             assigned_owner: Optional[str] = None):
        self.status = ProposalStatus.EDITED
        self.decided_by = decided_by
        self.decided_at = datetime.utcnow()
        self.human_version = human_version
        if assigned_owner:
            self.assigned_owner = assigned_owner

    def record_outcome(self, outcome: str, reason: str = ""):
        self.outcome = outcome
        self.outcome_reason = reason

    @property
    def is_pending(self) -> bool:
        return self.status == ProposalStatus.PENDING

    @property
    def is_expired(self) -> bool:
        if self.expiry and datetime.utcnow() > self.expiry:
            return True
        return False

    @property
    def final_recommendation(self) -> str:
        """승인된 최종 버전 (수정 시 수정본, 아니면 AI 원본)."""
        if self.status == ProposalStatus.EDITED and self.human_version:
            return self.human_version
        return self.ai_recommendation

    def to_db_row(self) -> tuple:
        return (
            self.id,
            self.created_at.isoformat(),
            self.issue_id,
            self.proposal_type.value,
            self.ai_recommendation,
            self.ai_reasoning,
            self.ai_confidence,
            json.dumps(self.ai_data_sources, ensure_ascii=False),
            self.status.value,
            self.decided_by,
            self.decided_at.isoformat() if self.decided_at else None,
            self.human_version,
            self.rejection_reason,
            self.assigned_owner,
            self.outcome,
            self.outcome_reason,
            self.urgency.value,
            self.expiry.isoformat() if self.expiry else None,
            json.dumps(self.tags, ensure_ascii=False),
            1 if self.conflict_with_override else 0,
            self.override_id,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "issue_id": self.issue_id,
            "proposal_type": self.proposal_type.value,
            "ai_recommendation": self.ai_recommendation,
            "ai_reasoning": self.ai_reasoning,
            "ai_confidence": self.ai_confidence,
            "ai_data_sources": self.ai_data_sources,
            "status": self.status.value,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "human_version": self.human_version,
            "rejection_reason": self.rejection_reason,
            "assigned_owner": self.assigned_owner,
            "outcome": self.outcome,
            "urgency": self.urgency.value,
            "final_recommendation": self.final_recommendation,
            "conflict_with_override": self.conflict_with_override,
        }

    def to_telegram_notification(self) -> str:
        """텔레그램 알림 형식."""
        urgency_icon = {
            Urgency.IMMEDIATE: "🔴",
            Urgency.TODAY: "🟠",
            Urgency.H48: "🟡",
            Urgency.MONITORING: "🟢",
        }.get(self.urgency, "⚪")

        lines = [
            f"━━━━━━━━━━━━━━━━━━",
            f"🔔 전략 제안 #{self.id}",
        ]
        if self.issue_id:
            lines.append(f"이슈: {self.issue_id}")
        lines.extend([
            f"AI 판단: {self.ai_recommendation} (신뢰도 {self.ai_confidence:.2f})",
            f"근거: {self.ai_reasoning}",
            f"긴급도: {urgency_icon} {self.urgency.value}",
            f"━━━━━━━━━━━━━━━━━━",
            f"",
            f"/approve {self.id}",
            f"/reject {self.id} [사유]",
            f"/edit {self.id} [수정내용]",
        ])
        return "\n".join(lines)

    @classmethod
    def from_db_row(cls, row: dict) -> "StrategyProposal":
        return cls(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
            issue_id=row.get("issue_id"),
            proposal_type=ProposalType(row["proposal_type"]),
            ai_recommendation=row["ai_recommendation"],
            ai_reasoning=row.get("ai_reasoning", ""),
            ai_confidence=row.get("ai_confidence", 0.5),
            ai_data_sources=json.loads(row.get("ai_data_sources", "[]")),
            status=ProposalStatus(row.get("status", "pending")),
            decided_by=row.get("decided_by"),
            decided_at=datetime.fromisoformat(row["decided_at"]) if row.get("decided_at") else None,
            human_version=row.get("human_version"),
            rejection_reason=row.get("rejection_reason"),
            assigned_owner=row.get("assigned_owner"),
            outcome=row.get("outcome"),
            outcome_reason=row.get("outcome_reason"),
            urgency=Urgency(row.get("urgency", "today")),
            expiry=datetime.fromisoformat(row["expiry"]) if row.get("expiry") else None,
            tags=json.loads(row.get("tags_json", "[]")),
            conflict_with_override=bool(row.get("conflict_with_override", 0)),
            override_id=row.get("override_id"),
        )
