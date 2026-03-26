"""
Strategic Memory Models — Layer 3: Strategic Memory Engine
후보 / 캠페인 / 전략실장 / 현장 / 결정 메모리
"""
from __future__ import annotations


import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Union


class MemoryType(str, Enum):
    CANDIDATE = "candidate"
    CAMPAIGN = "campaign"
    DIRECTOR = "director"
    FIELD = "field"
    DECISION = "decision"


@dataclass
class StrategicMemory:
    """전략 메모리 단위. type + key 조합으로 유니크."""

    memory_type: MemoryType
    memory_key: str
    value: Union[dict, list]

    source: str = "system"          # system | director_input | auto_learned
    confidence: float = 0.5
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    def to_db_row(self) -> tuple:
        return (
            self.memory_type.value,
            self.memory_key,
            json.dumps(self.value, ensure_ascii=False),
            self.source,
            self.confidence,
            self.created_at.isoformat(),
            self.updated_at.isoformat(),
            self.expires_at.isoformat() if self.expires_at else None,
        )

    def to_dict(self) -> dict:
        return {
            "memory_type": self.memory_type.value,
            "memory_key": self.memory_key,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "StrategicMemory":
        return cls(
            memory_type=MemoryType(row["memory_type"]),
            memory_key=row["memory_key"],
            value=json.loads(row["value_json"]),
            source=row.get("source", "system"),
            confidence=row.get("confidence", 0.5),
            created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row.get("created_at"), str) else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if isinstance(row.get("updated_at"), str) else datetime.utcnow(),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row.get("expires_at") else None,
        )


# ─── Default Memory Seeds ────────────────────────────────────────────

DEFAULT_CANDIDATE_MEMORY = {
    "speaking_strengths": {
        "value": ["경제비전 제시", "지역개발 경험", "현장밀착형 소통"],
        "notes": "초기값. 실제 관찰 후 업데이트 필요."
    },
    "weak_topics": {
        "value": ["강남발언", "과거 논란"],
        "notes": "이 주제에서 즉흥 응답 회피 권장."
    },
    "forbidden_expressions": {
        "value": ["퍼주기", "무상", "공짜"],
        "notes": "후보 발언에서 절대 사용 금지."
    },
    "emotional_risk_patterns": {
        "value": ["즉흥 반박 시 실언 위험", "피로 누적 시 공격적 어조"],
        "notes": "스케줄 관리와 연계."
    },
    "best_format": {
        "value": "현장방문 + 짧은 핵심 메시지 (3문장 이내)",
    },
    "avoid_format": {
        "value": "기자회견 장시간 질의응답, 토론 중 감정적 반응",
    },
}

DEFAULT_CAMPAIGN_MEMORY = {
    "main_narratives": {
        "value": [
            {"frame": "구조적 경제회복", "priority": 1, "active": True},
            {"frame": "조선·방산 르네상스", "priority": 2, "active": True},
            {"frame": "부울경 메가시티", "priority": 3, "active": True},
        ]
    },
    "approved_frames": {
        "value": ["미래산업", "일자리", "지역균형", "청년정주", "경제자립"]
    },
    "prohibited_themes": {
        "value": ["현금살포 연상", "포퓰리즘 프레임", "지역감정 자극"]
    },
    "crisis_playbooks": {
        "value": {
            "강남발언": {
                "stance": "avoid",
                "owner": "대변인",
                "message": "이미 입장 표명 완료. 추가 대응 불필요.",
                "pivot_to": "조선업 현장방문"
            },
        }
    },
}

DEFAULT_DIRECTOR_MEMORY = {
    "tactical_style": {
        "value": "선제공격보다 후속 프레이밍 선호",
        "source": "initial"
    },
    "attack_preference": {
        "value": "직접공격 회피, 우회적 비교 활용",
        "source": "initial"
    },
    "silence_preference": {
        "value": "불리한 이슈는 24시간 침묵 후 판단",
        "source": "initial"
    },
    "override_habits": {
        "value": {
            "counter_to_avoid": 0.0,
            "push_to_monitor": 0.0,
            "total_overrides": 0,
            "total_approvals": 0,
        },
        "source": "auto_learned"
    },
}
