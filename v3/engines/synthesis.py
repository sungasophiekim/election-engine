"""
Strategy Synthesis Engine — Layer 4
Public Intelligence + Internal Signals + Strategic Memory → AI 전략 제안
"""
from __future__ import annotations


import json
import logging
import os
from datetime import datetime
from typing import Optional

from v3.models.proposals import StrategyProposal, ProposalType, Urgency
from v3.models.signals import InternalSignal, SignalType
from v3.models.memory import StrategicMemory, MemoryType
from v3.storage import V3Storage

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """당신은 한국 선거 캠프의 전략 참모총장(AI Chief of Staff)입니다.

## 역할
- 공개 정보, 내부 시그널, 전략 메모리를 종합하여 전략 제안을 생성합니다.
- 최종 결정은 항상 전략실장(인간)이 합니다. 당신은 조언만 합니다.
- 전략실장의 override가 활성 상태이면 반드시 존중합니다.

## 현재 상황

### 이슈 점수 (공개 데이터)
{issue_scores}

### 활성 내부 시그널
{internal_signals}

### 활성 Override
{overrides}

### 활성 서사
{narratives}

### 차단어
{blocked_terms}

### 전략 메모리
{memory_summary}

### 여론조사
{polling_data}

## 지시사항

위 정보를 종합하여 다음을 생성하세요:

1. **즉시 행동 제안** (최대 3건): 긴급도별로 정렬
2. **이슈별 stance 추천**: push/counter/avoid/monitor/pivot
3. **메시지 추천**: 오늘의 핵심 메시지 (1~2개)
4. **지역 우선순위**: 주의가 필요한 지역
5. **리스크 경보**: 잠재 위험 요소

## 규칙
- 활성 override가 있는 이슈는 전략실장의 판단을 따르세요.
- 차단어는 절대 사용하지 마세요.
- 활성 서사와 일치하는 방향으로 추천하세요.
- 전략실장의 tactical_style을 반영하세요.
- 각 제안에 신뢰도(0.0~1.0)를 표시하세요.

JSON 배열로 응답하세요:
[
  {{
    "proposal_type": "stance | message | schedule | crisis_response | attack",
    "issue_id": "이슈명 또는 null",
    "recommendation": "구체적 행동 권장",
    "reasoning": "근거 (1~2문장)",
    "confidence": 0.0~1.0,
    "urgency": "immediate | today | 48h | monitoring",
    "data_sources": ["근거 데이터1", "근거 데이터2"]
  }}
]

최대 5개 제안만 생성하세요. 가장 중요한 것부터 정렬하세요.
"""


class StrategySynthesisEngine:
    """Layer 4: 전략 합성 엔진."""

    def __init__(self, v3_storage: V3Storage):
        self.storage = v3_storage
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                api_key = os.getenv("ANTHROPIC_API_KEY", "")
                if api_key:
                    self._client = anthropic.AsyncAnthropic(api_key=api_key)
            except ImportError:
                pass
        return self._client

    async def synthesize(
        self,
        issue_scores: list[dict],
        polling_data: Optional[dict] = None,
    ) -> list[StrategyProposal]:
        """
        공개 데이터 + 내부 시그널 + 메모리 → 전략 제안 리스트.

        Parameters:
            issue_scores: V2 엔진의 이슈 점수 리스트
            polling_data: 최신 여론조사 데이터
        Returns:
            list[StrategyProposal]: 승인 대기 제안들
        """
        # 1. 내부 시그널 수집
        active_signals = self.storage.get_active_signals()
        overrides = self.storage.get_active_overrides()
        narratives = self.storage.get_active_narratives()
        blocked = self.storage.get_active_blocks()

        # 2. 메모리 로드
        memory = self.storage.get_all_memory()
        memory_summary = self._format_memory(memory)

        # 3. 이슈 점수에 내부 시그널 보정 적용
        adjusted_scores = self._adjust_scores(issue_scores, active_signals)

        # 4. Override 반영
        override_map = {}
        for ov in overrides:
            if ov.issue_id:
                override_map[ov.issue_id] = ov.metadata

        # 5. AI Synthesis
        client = self._get_client()
        if not client:
            logger.warning("ai_client_unavailable, returning rule-based proposals")
            return self._rule_based_proposals(adjusted_scores, overrides, blocked)

        prompt = SYNTHESIS_PROMPT.format(
            issue_scores=json.dumps(adjusted_scores[:15], ensure_ascii=False, indent=2),
            internal_signals=self._format_signals(active_signals[:20]),
            overrides=self._format_overrides(overrides),
            narratives=json.dumps(narratives[:5], ensure_ascii=False, indent=2),
            blocked_terms=json.dumps([b["term"] for b in blocked], ensure_ascii=False),
            memory_summary=memory_summary,
            polling_data=json.dumps(polling_data or {}, ensure_ascii=False),
        )

        try:
            model = os.getenv("SONNET_MODEL", "claude-sonnet-4-5-20250929")
            response = await client.messages.create(
                model=model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            proposals_data = json.loads(raw)
        except Exception as e:
            logger.error(f"synthesis_failed: {e}")
            return self._rule_based_proposals(adjusted_scores, overrides, blocked)

        # 6. StrategyProposal 객체 생성
        proposals = []
        for pd in proposals_data:
            issue_id = pd.get("issue_id")

            # Override 충돌 확인
            conflict = issue_id in override_map if issue_id else False
            override_id = None
            if conflict:
                # override 활성 시: AI 제안에 충돌 표시
                for ov in overrides:
                    if ov.issue_id == issue_id:
                        override_id = ov.id
                        break

            # 차단어 필터링
            rec = pd.get("recommendation", "")
            for bt in blocked:
                if bt["term"] in rec:
                    rec = rec.replace(bt["term"], f"[차단:{bt['term']}]")

            proposal = StrategyProposal(
                proposal_type=ProposalType(pd.get("proposal_type", "stance")),
                ai_recommendation=rec,
                ai_reasoning=pd.get("reasoning", ""),
                issue_id=issue_id,
                ai_confidence=pd.get("confidence", 0.5),
                ai_data_sources=pd.get("data_sources", []),
                urgency=Urgency(pd.get("urgency", "today")),
                conflict_with_override=conflict,
                override_id=override_id,
            )
            proposals.append(proposal)

        # 7. DB 저장
        for p in proposals:
            self.storage.save_proposal(p)

        logger.info(f"synthesis_complete: {len(proposals)} proposals generated")
        return proposals

    def _adjust_scores(self, scores: list[dict],
                       signals: list[InternalSignal]) -> list[dict]:
        """내부 시그널로 이슈 점수 보정."""
        adjusted = [dict(s) for s in scores]  # shallow copy

        signal_by_issue = {}
        for sig in signals:
            if sig.issue_id:
                signal_by_issue.setdefault(sig.issue_id, []).append(sig)

        for score in adjusted:
            issue_id = score.get("issue_id") or score.get("keyword", "")
            if issue_id not in signal_by_issue:
                continue

            sigs = signal_by_issue[issue_id]
            for sig in sigs:
                if sig.signal_type == SignalType.FIELD_REPORT:
                    # 현장 보고가 "부정적" 키워드 포함 시 점수 상향
                    neg_keywords = ["냉담", "부정", "약", "위험", "안좋", "문제"]
                    if any(k in sig.content for k in neg_keywords):
                        score["score"] = min(100, score.get("score", 0) + 5)
                        score["internal_boost"] = "+5 (현장보고 부정적)"

                elif sig.signal_type == SignalType.ORDER:
                    score["director_order"] = sig.content

        return adjusted

    def _rule_based_proposals(self, scores: list[dict],
                              overrides: list[InternalSignal],
                              blocked: list[dict]) -> list[StrategyProposal]:
        """AI 없이 규칙 기반 제안 생성 (fallback)."""
        proposals = []

        # 상위 3개 이슈에 대해 기본 stance 제안
        for score in scores[:3]:
            issue = score.get("issue_id") or score.get("keyword", "unknown")
            s = score.get("score", 0)
            crisis = score.get("crisis_level", "NORMAL")

            if crisis == "CRISIS":
                stance = "avoid"
                urgency = Urgency.IMMEDIATE
                reasoning = f"위기 수준 이슈 (score={s}), 즉각 대응 필요"
            elif s >= 60:
                stance = "counter"
                urgency = Urgency.TODAY
                reasoning = f"고점수 이슈 (score={s}), 당일 대응 권장"
            else:
                stance = "monitor"
                urgency = Urgency.MONITORING
                reasoning = f"모니터링 수준 (score={s})"

            # Override 확인
            override_active = any(ov.issue_id == issue for ov in overrides)

            proposal = StrategyProposal(
                proposal_type=ProposalType.STANCE,
                ai_recommendation=f"stance={stance}",
                ai_reasoning=reasoning,
                issue_id=issue,
                ai_confidence=0.4,  # rule-based → 낮은 신뢰도
                urgency=urgency,
                conflict_with_override=override_active,
            )
            proposals.append(proposal)
            self.storage.save_proposal(proposal)

        return proposals

    def _format_signals(self, signals: list[InternalSignal]) -> str:
        if not signals:
            return "없음"
        items = []
        for s in signals:
            items.append({
                "type": s.signal_type.value,
                "issue": s.issue_id,
                "region": s.region,
                "content": s.content[:100],
                "confidence": s.confidence.value,
                "priority": s.priority.value,
            })
        return json.dumps(items, ensure_ascii=False, indent=2)

    def _format_overrides(self, overrides: list[InternalSignal]) -> str:
        if not overrides:
            return "없음"
        items = []
        for ov in overrides:
            items.append({
                "issue": ov.issue_id,
                "ai_stance": ov.metadata.get("ai_stance", "?"),
                "director_stance": ov.metadata.get("my_stance", "?"),
                "reason": ov.metadata.get("reason", ""),
                "expiry": ov.expiry.isoformat() if ov.expiry else "무기한",
            })
        return json.dumps(items, ensure_ascii=False, indent=2)

    def _format_memory(self, memory: dict) -> str:
        if not memory:
            return "메모리 비어있음"
        summary = {}
        for mem_type, memories in memory.items():
            summary[mem_type] = {m.memory_key: str(m.value)[:100] for m in memories[:5]}
        return json.dumps(summary, ensure_ascii=False, indent=2)
