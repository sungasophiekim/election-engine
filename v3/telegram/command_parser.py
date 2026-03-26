"""
Telegram Command Parser — Layer 2: Internal Input Engine
구조화 명령어 (/report, /order, /hypo, /block, /narrative, /override) 파싱
+ 자연어 입력 자동 분류
"""
from __future__ import annotations


import re
from datetime import datetime, timedelta
from typing import Optional

from v3.models.signals import (
    InternalSignal, SignalType, Confidence, Priority, Visibility,
)


class CommandParser:
    """텔레그램 구조화 명령어 → InternalSignal 변환."""

    COMMAND_MAP = {
        "/report": SignalType.FIELD_REPORT,
        "/order": SignalType.ORDER,
        "/hypo": SignalType.HYPOTHESIS,
        "/block": SignalType.BLOCK,
        "/narrative": SignalType.NARRATIVE,
        "/override": SignalType.OVERRIDE,
    }

    def is_structured_command(self, text: str) -> bool:
        first_word = text.strip().split()[0] if text.strip() else ""
        return first_word in self.COMMAND_MAP

    def parse(self, text: str, chat_id: int = None,
              message_id: int = None) -> Optional[InternalSignal]:
        """구조화 명령어를 파싱하여 InternalSignal 반환."""
        text = text.strip()
        lines = text.split("\n")
        first_line = lines[0].strip()
        command = first_line.split()[0]

        if command not in self.COMMAND_MAP:
            return None

        signal_type = self.COMMAND_MAP[command]
        fields = self._parse_fields(lines[1:])

        # signal_type별 특수 처리
        if signal_type == SignalType.BLOCK:
            return self._build_block_signal(fields, chat_id, message_id)
        elif signal_type == SignalType.NARRATIVE:
            return self._build_narrative_signal(fields, chat_id, message_id)
        elif signal_type == SignalType.OVERRIDE:
            return self._build_override_signal(fields, chat_id, message_id)
        else:
            return self._build_generic_signal(signal_type, fields, chat_id, message_id)

    def _parse_fields(self, lines: list[str]) -> dict:
        """key: value 형태의 줄들을 파싱."""
        fields = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip().lower()] = value.strip()
        return fields

    def _parse_expiry(self, expiry_str: str) -> Optional[datetime]:
        """만료 시간 파싱. '24h', '7d', 'today 18:00' 등."""
        expiry_str = expiry_str.strip().lower()

        # "24h", "48h" 형식
        match = re.match(r"(\d+)h", expiry_str)
        if match:
            return datetime.utcnow() + timedelta(hours=int(match.group(1)))

        # "7d" 형식
        match = re.match(r"(\d+)d", expiry_str)
        if match:
            return datetime.utcnow() + timedelta(days=int(match.group(1)))

        # "today 18:00" 형식
        match = re.match(r"today\s+(\d{1,2}):(\d{2})", expiry_str)
        if match:
            now = datetime.utcnow()
            return now.replace(
                hour=int(match.group(1)),
                minute=int(match.group(2)),
                second=0, microsecond=0,
            )

        return None

    def _build_generic_signal(self, signal_type: SignalType, fields: dict,
                              chat_id: int, message_id: int) -> InternalSignal:
        return InternalSignal(
            signal_type=signal_type,
            content=fields.get("content", fields.get("instruction", fields.get("hypothesis", ""))),
            issue_id=fields.get("issue"),
            region=fields.get("region"),
            confidence=Confidence(fields.get("confidence", "medium")),
            priority=Priority(fields.get("priority", "normal")),
            expiry=self._parse_expiry(fields["expiry"]) if "expiry" in fields else None,
            metadata=fields,
            telegram_chat_id=chat_id,
            telegram_message_id=message_id,
        )

    def _build_block_signal(self, fields: dict, chat_id: int,
                            message_id: int) -> InternalSignal:
        return InternalSignal(
            signal_type=SignalType.BLOCK,
            content=f"차단어: {fields.get('term', '')} / 사유: {fields.get('reason', '')}",
            metadata={
                "term": fields.get("term", ""),
                "reason": fields.get("reason", ""),
                "scope": fields.get("scope", "all"),
            },
            expiry=self._parse_expiry(fields["expiry"]) if "expiry" in fields else None,
            telegram_chat_id=chat_id,
            telegram_message_id=message_id,
        )

    def _build_narrative_signal(self, fields: dict, chat_id: int,
                                message_id: int) -> InternalSignal:
        keywords = [k.strip() for k in fields.get("keywords", "").split(",") if k.strip()]
        return InternalSignal(
            signal_type=SignalType.NARRATIVE,
            content=fields.get("frame", ""),
            priority=Priority(fields.get("priority_level", "normal")) if fields.get("priority_level") else Priority.NORMAL,
            metadata={
                "priority_rank": int(fields.get("priority", 1)),
                "frame": fields.get("frame", ""),
                "keywords": keywords,
            },
            expiry=self._parse_expiry(fields["expiry"]) if "expiry" in fields else None,
            telegram_chat_id=chat_id,
            telegram_message_id=message_id,
        )

    def _build_override_signal(self, fields: dict, chat_id: int,
                               message_id: int) -> InternalSignal:
        return InternalSignal(
            signal_type=SignalType.OVERRIDE,
            content=f"AI: {fields.get('ai_stance', '?')} → 실장: {fields.get('my_stance', '?')}",
            issue_id=fields.get("issue"),
            metadata={
                "ai_stance": fields.get("ai_stance", ""),
                "my_stance": fields.get("my_stance", ""),
                "reason": fields.get("reason", ""),
            },
            expiry=self._parse_expiry(fields["expiry"]) if "expiry" in fields else None,
            confidence=Confidence.HIGH,
            telegram_chat_id=chat_id,
            telegram_message_id=message_id,
        )


class ApprovalParser:
    """텔레그램 승인/거부/수정 명령어 파싱."""

    def parse_approve(self, text: str) -> Optional[dict]:
        """/approve P-0042 [owner]"""
        parts = text.strip().split(maxsplit=2)
        if len(parts) < 2:
            return None
        return {
            "action": "approve",
            "proposal_id": parts[1],
            "assigned_owner": parts[2] if len(parts) > 2 else None,
        }

    def parse_reject(self, text: str) -> Optional[dict]:
        """/reject P-0042 팩트 미확인"""
        parts = text.strip().split(maxsplit=2)
        if len(parts) < 2:
            return None
        return {
            "action": "reject",
            "proposal_id": parts[1],
            "reason": parts[2] if len(parts) > 2 else "사유 미기재",
        }

    def parse_edit(self, text: str) -> Optional[dict]:
        """/edit P-0042 stance=avoid, owner=전략팀"""
        parts = text.strip().split(maxsplit=2)
        if len(parts) < 3:
            return None
        return {
            "action": "edit",
            "proposal_id": parts[1],
            "human_version": parts[2],
        }
