"""
Election Strategy Engine — Strategy Orchestrator
4개 엔진 결과를 통합해 Claude API로 최종 전략 브리핑을 생성합니다.
"""
import json
import os
from datetime import datetime

import anthropic

from models.schemas import (
    IssueSignal, ContentDraft, ContentType,
    StrategicBrief, CrisisLevel,
)
from config.tenant_config import TenantConfig
from engines.issue_scoring    import score_multiple_signals
from engines.message_validator import validate_with_claude
from engines.voter_and_opponent import (
    calculate_voter_priorities,
    get_schedule_weights,
    analyze_opponents,
)


class ElectionStrategyOrchestrator:
    """
    Election Strategy Engine 메인 오케스트레이터.
    캠프별로 독립된 인스턴스를 사용합니다 (멀티테넌트 격리).
    """

    def __init__(self, config: TenantConfig, anthropic_api_key: str):
        self.config = config
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)

    # ── 핵심 메서드: 모닝 브리핑 생성 ─────────────────────────────
    def generate_morning_brief(
        self,
        issue_signals:  list[IssueSignal],
        opponent_data:  list[dict],
    ) -> StrategicBrief:
        """
        매일 아침 자동 실행되는 전략 브리핑 생성.
        1. 이슈 스코어링
        2. 지역 우선순위 계산
        3. 경쟁자 분석
        4. Claude로 통합 브리핑 생성
        """
        # ── 엔진 1: 이슈 스코어링 ───────────────────────────────
        scored_issues = score_multiple_signals(issue_signals, self.config)
        top_issues    = scored_issues[:5]  # 상위 5개만

        # 전체 위기 레벨 결정 (최고 점수 기준)
        overall_level = CrisisLevel.NORMAL
        if top_issues:
            overall_level = top_issues[0].level

        # ── 엔진 3: 지역 우선순위 (이슈 연동) ─────────────────────
        schedule_weights = get_schedule_weights(self.config, top_issues)

        # ── 엔진 4: 경쟁자 분석 ──────────────────────────────────
        opponent_signals = analyze_opponents(
            self.config, opponent_data, top_issues
        )

        # ── Claude 통합 브리핑 ────────────────────────────────────
        brief_text, actions, drafts = self._call_claude_for_brief(
            top_issues, schedule_weights, opponent_signals
        )

        return StrategicBrief(
            tenant_id        = self.config.tenant_id,
            generated_at     = datetime.now(),
            top_issues       = top_issues,
            crisis_level     = overall_level,
            response_actions = actions,
            content_drafts   = drafts,
            schedule_weights = schedule_weights,
            opponent_alerts  = [s.recommended_action for s in opponent_signals],
        )

    def _call_claude_for_brief(
        self,
        top_issues,
        schedule_weights,
        opponent_signals,
    ) -> tuple[str, list[str], list[str]]:
        """Claude API로 통합 전략 브리핑 생성"""

        issues_str = "\n".join(
            f"- [{i.level.name}] {i.keyword}: {i.score:.0f}점 (반감기 {i.estimated_halflife_hours}h)"
            for i in top_issues
        )

        top_regions = sorted(schedule_weights.items(), key=lambda x: x[1], reverse=True)[:3]
        regions_str = ", ".join(f"{r}({s:.2f})" for r, s in top_regions)

        opp_str = "\n".join(
            f"- {s.opponent_name}: 공격확률 {s.attack_prob_72h*100:.0f}% / {s.message_shift}"
            for s in opponent_signals
        )

        pledges_str = "\n".join(
            f"- {name}: {info['수치']}"
            for name, info in self.config.pledges.items()
        )

        system_prompt = f"""당신은 '{self.config.candidate_name}' 후보 ({self.config.region} {self.config.election_type})의 수석 전략 참모 AI입니다.

[후보 슬로건] {self.config.slogan}
[핵심 메시지] {self.config.core_message}
[주요 공약]
{pledges_str}
[금기사항] {', '.join(self.config.forbidden_words[:5])}

당신의 역할:
- 오늘의 이슈, 지역 우선순위, 경쟁자 동향을 종합해 캠프 운영 지시를 내립니다.
- 모든 제안은 핵심 메시지와 일관성을 유지해야 합니다.
- 검증되지 않은 수치는 절대 제시하지 않습니다.
- 반드시 JSON 형식으로만 응답합니다."""

        user_message = f"""오늘 날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}

[이슈 스코어링 결과]
{issues_str if issues_str else "특이 이슈 없음"}

[오늘 유세 우선 지역 TOP3]
{regions_str}

[경쟁자 동향]
{opp_str if opp_str else "특이 동향 없음"}

위 정보를 바탕으로 오늘의 전략 브리핑을 작성해 주세요.
다음 JSON 형식으로만 응답하세요:

{{
  "situation_summary": "오늘 전체 상황 2~3문장 요약",
  "priority_actions": [
    "즉시 해야 할 행동 1",
    "즉시 해야 할 행동 2",
    "즉시 해야 할 행동 3"
  ],
  "press_release_draft": "오늘 유세 관련 보도자료 초안 (3~4문단)",
  "sns_draft": "X(트위터)용 오늘의 메시지 초안 (140자 내외)",
  "risk_assessment": "오늘의 주요 리스크 한 문장"
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            raw = response.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()

            data = json.loads(raw)

            actions = data.get("priority_actions", [])
            drafts  = []
            if data.get("press_release_draft"):
                drafts.append(f"[보도자료 초안]\n{data['press_release_draft']}")
            if data.get("sns_draft"):
                drafts.append(f"[SNS 초안]\n{data['sns_draft']}")
            if data.get("risk_assessment"):
                drafts.append(f"[리스크 평가]\n{data['risk_assessment']}")

            return raw, actions, drafts

        except Exception as e:
            fallback = f"Claude 브리핑 생성 실패: {str(e)}"
            return fallback, ["수동 대응 필요"], []

    # ── 콘텐츠 검증 래퍼 ─────────────────────────────────────────
    def validate_content(self, draft: ContentDraft):
        """엔진 2 래퍼 — 콘텐츠 배포 전 검증"""
        return validate_with_claude(draft, self.config, self.client)

    # ── 실시간 위기 대응 ─────────────────────────────────────────
    def handle_crisis(self, issue_signal: IssueSignal) -> dict:
        """
        위기 이슈 하나에 대한 즉각 대응 패키지 생성.
        알림 + 대응 시나리오 3가지 + 초안 문구를 한 번에 반환합니다.
        """
        from engines.issue_scoring import calculate_issue_score
        scored = calculate_issue_score(issue_signal, self.config)

        system_prompt = f"""당신은 '{self.config.candidate_name}' 후보 선거캠프의 위기대응 AI입니다.
핵심 메시지: {self.config.core_message}
금기사항: {', '.join(self.config.forbidden_words[:5])}
반드시 JSON으로만 응답합니다."""

        user_message = f"""위기 이슈 감지:
- 키워드: {issue_signal.keyword}
- 위험도: {scored.score:.0f}/100 ({scored.level.name})
- 부정 비율: {issue_signal.negative_ratio*100:.0f}%
- 방송 보도: {'예' if issue_signal.tv_reported else '아니오'}

다음 JSON으로 즉각 대응 패키지를 작성해 주세요:
{{
  "alert_message": "선대위원장에게 보낼 카카오톡 알림 문자 (3줄)",
  "scenarios": [
    {{"name": "선제 발표", "pros": "장점", "cons": "단점", "draft": "발표문 초안"}},
    {{"name": "침묵 유지", "pros": "장점", "cons": "단점", "draft": ""}},
    {{"name": "이슈 전환", "pros": "장점", "cons": "단점", "draft": "전환 메시지 초안"}}
  ],
  "recommended": "선제 발표 | 침묵 유지 | 이슈 전환 중 택일",
  "golden_time_hours": 2
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1200,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = response.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            return {"score": scored, "response_package": json.loads(raw)}
        except Exception as e:
            return {"score": scored, "error": str(e)}
