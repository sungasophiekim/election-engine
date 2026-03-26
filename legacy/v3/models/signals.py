"""
Internal Signal Models — Layer 2: Internal Input Engine
텔레그램/대시보드를 통한 내부 시그널의 데이터 모델
"""
from __future__ import annotations


import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class SignalType(str, Enum):
    FIELD_REPORT = "field_report"
    ORDER = "order"
    HYPOTHESIS = "hypothesis"
    BLOCK = "block"
    NARRATIVE = "narrative"
    OVERRIDE = "override"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Priority(str, Enum):
    URGENT = "urgent"
    NORMAL = "normal"
    LOW = "low"


class Visibility(str, Enum):
    DIRECTOR_ONLY = "director_only"
    STRATEGY_TEAM = "strategy_team"
    ALL = "all"


class SignalStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


@dataclass
class InternalSignal:
    """내부 시그널 객체. 모든 텔레그램/대시보드 입력은 이 형태로 정규화."""

    content: str
    signal_type: SignalType

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = "strategy_director"
    issue_id: Optional[str] = None
    region: Optional[str] = None
    confidence: Confidence = Confidence.MEDIUM
    priority: Priority = Priority.NORMAL
    visibility: Visibility = Visibility.DIRECTOR_ONLY
    expiry: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)
    status: SignalStatus = SignalStatus.ACTIVE
    telegram_message_id: Optional[int] = None
    telegram_chat_id: Optional[int] = None

    @property
    def is_expired(self) -> bool:
        if self.expiry and datetime.utcnow() > self.expiry:
            return True
        return False

    def to_db_row(self) -> tuple:
        """DB INSERT용 튜플 반환."""
        return (
            self.id,
            self.timestamp.isoformat(),
            self.source,
            self.signal_type.value,
            self.issue_id,
            self.region,
            self.content,
            self.confidence.value,
            self.priority.value,
            self.visibility.value,
            self.expiry.isoformat() if self.expiry else None,
            json.dumps(self.metadata, ensure_ascii=False),
            self.status.value,
            self.telegram_message_id,
            self.telegram_chat_id,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "signal_type": self.signal_type.value,
            "issue_id": self.issue_id,
            "region": self.region,
            "content": self.content,
            "confidence": self.confidence.value,
            "priority": self.priority.value,
            "visibility": self.visibility.value,
            "expiry": self.expiry.isoformat() if self.expiry else None,
            "metadata": self.metadata,
            "status": self.status.value,
        }

    def to_telegram_display(self) -> str:
        """텔레그램 표시용 포맷."""
        icon = {
            SignalType.FIELD_REPORT: "📡",
            SignalType.ORDER: "⚡",
            SignalType.HYPOTHESIS: "🔬",
            SignalType.BLOCK: "🚫",
            SignalType.NARRATIVE: "📖",
            SignalType.OVERRIDE: "⚠️",
        }.get(self.signal_type, "📌")

        parts = [f"{icon} [{self.signal_type.value}] {self.id}"]
        if self.issue_id:
            parts.append(f"이슈: {self.issue_id}")
        if self.region:
            parts.append(f"지역: {self.region}")
        parts.append(f"내용: {self.content}")
        parts.append(f"신뢰도: {self.confidence.value} | 우선순위: {self.priority.value}")
        if self.expiry:
            parts.append(f"만료: {self.expiry.strftime('%m/%d %H:%M')}")
        return "\n".join(parts)

    @classmethod
    def from_db_row(cls, row: dict) -> "InternalSignal":
        """DB row dict → InternalSignal."""
        return cls(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
            source=row["source"],
            signal_type=SignalType(row["signal_type"]),
            issue_id=row.get("issue_id"),
            region=row.get("region"),
            content=row["content"],
            confidence=Confidence(row.get("confidence", "medium")),
            priority=Priority(row.get("priority", "normal")),
            visibility=Visibility(row.get("visibility", "director_only")),
            expiry=datetime.fromisoformat(row["expiry"]) if row.get("expiry") else None,
            metadata=json.loads(row.get("metadata_json", "{}")),
            status=SignalStatus(row.get("status", "active")),
            telegram_message_id=row.get("telegram_message_id"),
            telegram_chat_id=row.get("telegram_chat_id"),
        )
