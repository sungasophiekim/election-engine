"""
Natural Language Classifier — 자연어 텔레그램 메시지 → InternalSignal
Claude Haiku를 사용하여 비구조화 입력을 자동 분류
"""
from __future__ import annotations


import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from v3.models.signals import (
    InternalSignal, SignalType, Confidence, Priority,
)

logger = logging.getLogger(__name__)

CLASSIFY_PROMPT = """당신은 선거 캠프 전략 운영체제의 입력 분류기입니다.

전략실장이 텔레그램으로 보낸 메시지를 분석하여 구조화된 시그널로 변환하세요.

메시지: {message}

다음 JSON으로만 응답하세요 (다른 텍스트 없이):
{{
    "signal_type": "field_report | order | hypothesis | block | narrative | override",
    "issue": "연결된 이슈명 (없으면 null)",
    "region": "지역명 (없으면 null)",
    "content": "핵심 내용 요약 (1~2문장)",
    "confidence": "high | medium | low",
    "priority": "urgent | normal | low",
    "expiry_hours": null 또는 숫자 (예: 24)
}}

분류 기준:
- field_report: 현장 상황, 반응, 분위기 보고
- order: 명확한 지시/명령 ("~하지 마라", "~만 해라")
- hypothesis: 추측, 가설, 테스트 제안
- block: 특정 단어/표현 사용 금지 요청
- narrative: 캠페인 서사/프레임 방향 설정
- override: 기존 AI 판단에 대한 반대/수정 의견
"""


class NaturalLanguageClassifier:
    """Claude Haiku를 사용한 자연어 메시지 자동 분류."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                api_key = os.getenv("ANTHROPIC_API_KEY", "")
                if not api_key:
                    return None
                self._client = anthropic.AsyncAnthropic(api_key=api_key)
            except ImportError:
                logger.warning("anthropic package not installed")
                return None
        return self._client

    async def classify(self, text: str, chat_id: int = None,
                       message_id: int = None) -> Optional[InternalSignal]:
        """자연어 메시지를 InternalSignal로 변환."""
        client = self._get_client()
        if not client:
            return None

        try:
            model = os.getenv("HAIKU_MODEL", "claude-haiku-4-5-20251001")
            response = await client.messages.create(
                model=model,
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": CLASSIFY_PROMPT.format(message=text),
                }],
            )

            raw = response.content[0].text.strip()
            # JSON 파싱 (```json ... ``` 래핑 처리)
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)

            signal_type = SignalType(data["signal_type"])
            expiry = None
            if data.get("expiry_hours"):
                expiry = datetime.utcnow() + timedelta(hours=int(data["expiry_hours"]))

            return InternalSignal(
                signal_type=signal_type,
                content=data.get("content", text[:200]),
                issue_id=data.get("issue"),
                region=data.get("region"),
                confidence=Confidence(data.get("confidence", "medium")),
                priority=Priority(data.get("priority", "normal")),
                expiry=expiry,
                source="strategy_director",
                metadata={"original_text": text, "auto_classified": True},
                telegram_chat_id=chat_id,
                telegram_message_id=message_id,
            )
        except Exception as e:
            logger.error(f"nl_classification_failed: {e}")
            return None
