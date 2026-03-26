"""
V3 Storage — Internal Signals, Proposals, Memory, Decision Log
기존 ElectionDB를 확장하여 V3 테이블 CRUD 제공
"""
from __future__ import annotations


import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from v3.models.signals import InternalSignal, SignalType, SignalStatus
from v3.models.proposals import StrategyProposal, ProposalStatus
from v3.models.memory import StrategicMemory, MemoryType

_V3_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "storage" / "schema_v3.sql"


class V3Storage:
    """V3 전략 OS 저장소. 기존 ElectionDB와 같은 SQLite 파일 사용."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_v3_tables()

    def _init_v3_tables(self):
        schema_sql = _V3_SCHEMA_PATH.read_text(encoding="utf-8")
        self._conn.executescript(schema_sql)
        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ──────────────────────────────────────────────────────────────────
    # Internal Signals
    # ──────────────────────────────────────────────────────────────────

    def save_signal(self, signal: InternalSignal) -> str:
        self._conn.execute(
            """INSERT INTO internal_signals
               (id, created_at, source, signal_type, issue_id, region,
                content, confidence, priority, visibility, expiry,
                metadata_json, status, telegram_message_id, telegram_chat_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            signal.to_db_row(),
        )
        self._conn.commit()
        return signal.id

    def get_active_signals(self, signal_type: Optional[SignalType] = None,
                           issue_id: Optional[str] = None) -> list[InternalSignal]:
        """활성 시그널 조회. 만료된 것은 자동 비활성화."""
        self._expire_signals()

        query = "SELECT * FROM internal_signals WHERE status='active'"
        params = []
        if signal_type:
            query += " AND signal_type=?"
            params.append(signal_type.value)
        if issue_id:
            query += " AND issue_id=?"
            params.append(issue_id)
        query += " ORDER BY created_at DESC"

        rows = self._conn.execute(query, params).fetchall()
        return [InternalSignal.from_db_row(dict(r)) for r in rows]

    def get_active_overrides(self) -> list[InternalSignal]:
        return self.get_active_signals(signal_type=SignalType.OVERRIDE)

    def get_active_blocks(self) -> list[dict]:
        """활성 차단어 목록."""
        self._expire_blocked_terms()
        rows = self._conn.execute(
            "SELECT * FROM blocked_terms WHERE status='active'"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_active_narratives(self) -> list[dict]:
        """활성 서사 목록 (priority 순)."""
        self._expire_narratives()
        rows = self._conn.execute(
            "SELECT * FROM active_narratives WHERE status='active' ORDER BY priority ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    def save_block(self, term: str, reason: str, scope: str = "all",
                   expiry: Optional[datetime] = None):
        self._conn.execute(
            "INSERT INTO blocked_terms (term, reason, scope, expiry) VALUES (?,?,?,?)",
            (term, reason, scope, expiry.isoformat() if expiry else None),
        )
        self._conn.commit()

    def save_narrative(self, priority: int, frame: str,
                       keywords: list[str] = None,
                       expiry: Optional[datetime] = None):
        self._conn.execute(
            """INSERT INTO active_narratives (priority, frame, keywords_json, expiry)
               VALUES (?,?,?,?)""",
            (priority, frame,
             json.dumps(keywords or [], ensure_ascii=False),
             expiry.isoformat() if expiry else None),
        )
        self._conn.commit()

    def get_all_signals(self, limit: int = 50) -> list[InternalSignal]:
        rows = self._conn.execute(
            "SELECT * FROM internal_signals ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [InternalSignal.from_db_row(dict(r)) for r in rows]

    def _expire_signals(self):
        self._conn.execute(
            "UPDATE internal_signals SET status='expired' WHERE status='active' AND expiry IS NOT NULL AND expiry < ?",
            (datetime.utcnow().isoformat(),),
        )
        self._conn.commit()

    def _expire_blocked_terms(self):
        self._conn.execute(
            "UPDATE blocked_terms SET status='expired' WHERE status='active' AND expiry IS NOT NULL AND expiry < ?",
            (datetime.utcnow().isoformat(),),
        )
        self._conn.commit()

    def _expire_narratives(self):
        self._conn.execute(
            "UPDATE active_narratives SET status='expired' WHERE status='active' AND expiry IS NOT NULL AND expiry < ?",
            (datetime.utcnow().isoformat(),),
        )
        self._conn.commit()

    # ──────────────────────────────────────────────────────────────────
    # Strategy Proposals (Execution Queue)
    # ──────────────────────────────────────────────────────────────────

    def save_proposal(self, proposal: StrategyProposal) -> str:
        self._conn.execute(
            """INSERT INTO strategy_proposals
               (id, created_at, issue_id, proposal_type,
                ai_recommendation, ai_reasoning, ai_confidence, ai_data_sources,
                status, decided_by, decided_at, human_version,
                rejection_reason, assigned_owner, outcome, outcome_reason,
                urgency, expiry, tags_json, conflict_with_override, override_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            proposal.to_db_row(),
        )
        self._conn.commit()
        return proposal.id

    def get_pending_proposals(self) -> list[StrategyProposal]:
        """대기 중 제안 목록."""
        self._expire_proposals()
        rows = self._conn.execute(
            """SELECT * FROM strategy_proposals
               WHERE status='pending'
               ORDER BY
                 CASE urgency
                   WHEN 'immediate' THEN 0
                   WHEN 'today' THEN 1
                   WHEN '48h' THEN 2
                   WHEN 'monitoring' THEN 3
                 END,
                 created_at DESC"""
        ).fetchall()
        return [StrategyProposal.from_db_row(dict(r)) for r in rows]

    def get_proposal(self, proposal_id: str) -> Optional[StrategyProposal]:
        row = self._conn.execute(
            "SELECT * FROM strategy_proposals WHERE id=?", (proposal_id,)
        ).fetchone()
        return StrategyProposal.from_db_row(dict(row)) if row else None

    def update_proposal_status(self, proposal_id: str, status: ProposalStatus,
                               decided_by: str = "strategy_director",
                               human_version: Optional[str] = None,
                               rejection_reason: Optional[str] = None,
                               assigned_owner: Optional[str] = None):
        """제안 상태 업데이트 + decision_log 기록."""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return

        before_state = {"status": proposal.status.value}
        after_state = {"status": status.value}

        self._conn.execute(
            """UPDATE strategy_proposals
               SET status=?, decided_by=?, decided_at=?,
                   human_version=?, rejection_reason=?, assigned_owner=?
               WHERE id=?""",
            (status.value, decided_by, datetime.utcnow().isoformat(),
             human_version, rejection_reason, assigned_owner, proposal_id),
        )

        # Decision log
        self._conn.execute(
            """INSERT INTO decision_log
               (proposal_id, action, actor, before_state_json, after_state_json, reason)
               VALUES (?,?,?,?,?,?)""",
            (proposal_id, status.value, decided_by,
             json.dumps(before_state), json.dumps(after_state),
             rejection_reason or human_version or ""),
        )
        self._conn.commit()

    def get_approved_today(self) -> list[StrategyProposal]:
        """오늘 승인된 제안 목록 (Command Box용)."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        rows = self._conn.execute(
            """SELECT * FROM strategy_proposals
               WHERE status IN ('approved', 'edited')
               AND date(decided_at) = ?
               ORDER BY
                 CASE urgency
                   WHEN 'immediate' THEN 0
                   WHEN 'today' THEN 1
                   WHEN '48h' THEN 2
                   WHEN 'monitoring' THEN 3
                 END
               LIMIT 10""",
            (today,),
        ).fetchall()
        return [StrategyProposal.from_db_row(dict(r)) for r in rows]

    def _expire_proposals(self):
        self._conn.execute(
            """UPDATE strategy_proposals SET status='expired'
               WHERE status='pending' AND expiry IS NOT NULL AND expiry < ?""",
            (datetime.utcnow().isoformat(),),
        )
        self._conn.commit()

    # ──────────────────────────────────────────────────────────────────
    # Strategic Memory
    # ──────────────────────────────────────────────────────────────────

    def save_memory(self, memory: StrategicMemory):
        """메모리 upsert (type+key 유니크)."""
        self._conn.execute(
            """INSERT INTO strategic_memory
               (memory_type, memory_key, value_json, source, confidence,
                created_at, updated_at, expires_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(memory_type, memory_key) DO UPDATE SET
                 value_json=excluded.value_json,
                 source=excluded.source,
                 confidence=excluded.confidence,
                 updated_at=excluded.updated_at,
                 expires_at=excluded.expires_at""",
            memory.to_db_row(),
        )
        self._conn.commit()

    def get_memory(self, memory_type: MemoryType,
                   memory_key: Optional[str] = None) -> list[StrategicMemory]:
        if memory_key:
            rows = self._conn.execute(
                "SELECT * FROM strategic_memory WHERE memory_type=? AND memory_key=?",
                (memory_type.value, memory_key),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM strategic_memory WHERE memory_type=?",
                (memory_type.value,),
            ).fetchall()
        return [StrategicMemory.from_db_row(dict(r)) for r in rows]

    def get_all_memory(self) -> dict[str, list[StrategicMemory]]:
        """모든 메모리를 타입별로 그룹핑하여 반환."""
        result = {}
        for mt in MemoryType:
            memories = self.get_memory(mt)
            if memories:
                result[mt.value] = memories
        return result

    # ──────────────────────────────────────────────────────────────────
    # Decision Log / Analytics
    # ──────────────────────────────────────────────────────────────────

    def get_decision_log(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM decision_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_override_patterns(self) -> dict:
        """전략실장 override 패턴 분석 (auto_learned 메모리 업데이트용)."""
        rows = self._conn.execute(
            """SELECT
                 sp.ai_recommendation as ai_rec,
                 sp.human_version as human_ver,
                 sp.status,
                 sp.rejection_reason
               FROM strategy_proposals sp
               WHERE sp.status IN ('edited', 'rejected', 'approved')
               ORDER BY sp.decided_at DESC
               LIMIT 100"""
        ).fetchall()

        stats = {
            "total": len(rows),
            "approved": sum(1 for r in rows if r["status"] == "approved"),
            "edited": sum(1 for r in rows if r["status"] == "edited"),
            "rejected": sum(1 for r in rows if r["status"] == "rejected"),
            "approval_rate": 0.0,
        }
        if stats["total"] > 0:
            stats["approval_rate"] = stats["approved"] / stats["total"]

        return stats

    # ──────────────────────────────────────────────────────────────────
    # Dashboard Aggregates
    # ──────────────────────────────────────────────────────────────────

    def get_dashboard_status(self) -> dict:
        """상단 바 + 요약 데이터."""
        pending = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM strategy_proposals WHERE status='pending'"
        ).fetchone()["cnt"]

        active_overrides = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM internal_signals WHERE signal_type='override' AND status='active'"
        ).fetchone()["cnt"]

        active_signals = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM internal_signals WHERE status='active'"
        ).fetchone()["cnt"]

        return {
            "pending_proposals": pending,
            "active_overrides": active_overrides,
            "active_signals": active_signals,
        }
