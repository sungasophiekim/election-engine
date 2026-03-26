"""
Memory Consolidation Engine — Layer 3
Decision Memory 축적 → Director Pattern 분석 → Memory 자동 업데이트
"""
from __future__ import annotations


import json
import logging
from datetime import datetime
from typing import Optional

from v3.models.memory import (
    StrategicMemory, MemoryType,
    DEFAULT_CANDIDATE_MEMORY, DEFAULT_CAMPAIGN_MEMORY, DEFAULT_DIRECTOR_MEMORY,
)
from v3.storage import V3Storage

logger = logging.getLogger(__name__)


class MemoryEngine:
    """전략 메모리 관리 + 자동 학습."""

    def __init__(self, storage: V3Storage):
        self.storage = storage

    def seed_defaults(self):
        """초기 메모리 시드. 이미 존재하면 건너뜀."""
        existing = self.storage.get_all_memory()
        if existing.get("candidate"):
            logger.info("memory_already_seeded")
            return

        # Candidate Memory
        for key, value in DEFAULT_CANDIDATE_MEMORY.items():
            self.storage.save_memory(StrategicMemory(
                memory_type=MemoryType.CANDIDATE,
                memory_key=key,
                value=value,
                source="initial_seed",
                confidence=0.3,
            ))

        # Campaign Memory
        for key, value in DEFAULT_CAMPAIGN_MEMORY.items():
            self.storage.save_memory(StrategicMemory(
                memory_type=MemoryType.CAMPAIGN,
                memory_key=key,
                value=value,
                source="initial_seed",
                confidence=0.3,
            ))

        # Director Memory
        for key, value in DEFAULT_DIRECTOR_MEMORY.items():
            self.storage.save_memory(StrategicMemory(
                memory_type=MemoryType.DIRECTOR,
                memory_key=key,
                value=value,
                source="initial_seed",
                confidence=0.3,
            ))

        logger.info("memory_seeded: candidate + campaign + director defaults")

    def consolidate(self):
        """
        주기적 메모리 통합 (24h마다 실행 권장).
        Decision log → Director Memory 패턴 업데이트.
        """
        patterns = self.storage.get_override_patterns()
        if patterns["total"] == 0:
            return

        # Director override_habits 업데이트
        habits = {
            "approval_rate": patterns["approval_rate"],
            "total_decisions": patterns["total"],
            "approved": patterns["approved"],
            "edited": patterns["edited"],
            "rejected": patterns["rejected"],
        }

        self.storage.save_memory(StrategicMemory(
            memory_type=MemoryType.DIRECTOR,
            memory_key="override_habits",
            value=habits,
            source="auto_learned",
            confidence=min(0.9, 0.3 + patterns["total"] * 0.01),
            updated_at=datetime.utcnow(),
        ))

        logger.info(
            "memory_consolidated",
            extra={
                "total_decisions": patterns["total"],
                "approval_rate": f"{patterns['approval_rate']:.2%}",
            },
        )

    def record_decision_outcome(self, proposal_id: str, outcome: str,
                                reason: str = ""):
        """
        결정 결과 기록 → Decision Memory에 추가.
        outcome: positive | negative | neutral | unknown
        """
        proposal = self.storage.get_proposal(proposal_id)
        if not proposal:
            return

        decision_entry = {
            "proposal_id": proposal_id,
            "timestamp": datetime.utcnow().isoformat(),
            "issue_id": proposal.issue_id,
            "ai_recommendation": proposal.ai_recommendation,
            "human_decision": proposal.status.value,
            "human_version": proposal.human_version,
            "outcome": outcome,
            "reason": reason,
        }

        # Decision Memory에 추가 (append to list)
        existing = self.storage.get_memory(MemoryType.DECISION, "decision_history")
        if existing:
            history = existing[0].value
            if isinstance(history, list):
                history.append(decision_entry)
                # 최근 100건만 유지
                history = history[-100:]
            else:
                history = [decision_entry]
        else:
            history = [decision_entry]

        self.storage.save_memory(StrategicMemory(
            memory_type=MemoryType.DECISION,
            memory_key="decision_history",
            value=history,
            source="auto_learned",
            confidence=0.8,
        ))

        logger.info(f"decision_outcome_recorded: {proposal_id} = {outcome}")

    def update_field_memory(self, region: str, key: str, value: str):
        """현장 메모리 업데이트."""
        existing = self.storage.get_memory(MemoryType.FIELD, f"region_{region}")
        if existing:
            data = existing[0].value
            if isinstance(data, dict):
                if key not in data:
                    data[key] = []
                if isinstance(data[key], list):
                    data[key].append({"value": value, "date": datetime.utcnow().isoformat()})
                    data[key] = data[key][-20:]  # 최근 20건
                else:
                    data[key] = value
            else:
                data = {key: value}
        else:
            data = {key: value}

        self.storage.save_memory(StrategicMemory(
            memory_type=MemoryType.FIELD,
            memory_key=f"region_{region}",
            value=data,
            source="field_report",
            confidence=0.6,
        ))

    def get_synthesis_context(self) -> dict:
        """Strategy Synthesis Engine에 전달할 메모리 컨텍스트."""
        all_mem = self.storage.get_all_memory()

        context = {
            "candidate": {},
            "campaign": {},
            "director": {},
            "field": {},
            "recent_decisions": [],
        }

        for mem_type, memories in all_mem.items():
            for m in memories:
                if mem_type == "decision" and m.memory_key == "decision_history":
                    context["recent_decisions"] = m.value[-10:] if isinstance(m.value, list) else []
                else:
                    context[mem_type][m.memory_key] = m.value

        return context
