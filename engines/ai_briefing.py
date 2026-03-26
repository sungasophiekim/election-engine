"""
AI Briefing Generator — Claude 기반 전략 브리핑 자동 생성
"수치 → 해석 → 함의" 3단 구조로 캠프 전략 분석가 톤의 브리핑 생성.

스타일 원칙:
  - 숫자를 인정하되 패턴의 의미를 강조
  - 위험은 냉정하게, 기회는 데이터 근거로
  - 톤 = "모니터이자 조언자"
  - 전문 용어 최소화, 일반인도 이해 가능
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AIBriefing:
    """AI 생성 전략 브리핑"""
    date: str = ""
    headline: str = ""           # 한줄 요약
    situation: str = ""          # 판세 분석 (3~5문장)

    issues: list = field(default_factory=list)
    # [{"keyword": str, "analysis": str, "action": str, "urgency": "high"|"medium"|"low"}, ...]

    risks: list = field(default_factory=list)
    # [{"title": str, "current": str, "reason": str, "threshold": str}, ...]

    opportunities: list = field(default_factory=list)
    # [{"title": str, "evidence": str, "action": str}, ...]

    tomorrow: list = field(default_factory=list)
    # ["액션1 — 근거", "액션2 — 근거", ...]

    channel_insight: str = ""    # 채널별 요약
    feedback: str = ""           # 어제 액션 피드백

    generated_at: str = ""
    model: str = ""

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "headline": self.headline,
            "situation": self.situation,
            "issues": self.issues,
            "risks": self.risks,
            "opportunities": self.opportunities,
            "tomorrow": self.tomorrow,
            "channel_insight": self.channel_insight,
            "feedback": self.feedback,
            "generated_at": self.generated_at,
            "model": self.model,
        }


def generate_briefing(
    # 핵심 데이터
    poll_kim: float = 0.0,
    poll_park: float = 0.0,
    poll_source: str = "",
    leading_index: float = 50.0,
    leading_direction: str = "stable",
    leading_delta: float = 0.0,
    turnout_gap: float = 0.0,
    # 이슈
    top_issues: list = None,          # [{"keyword": str, "score": float, "sentiment": str, "mention_count": int}, ...]
    # 채널
    channel_data: dict = None,        # {"youtube": {"pos": 24, "neg": 13}, ...}
    # 전일 대비
    prev_leading: float = 50.0,
    # 위기
    crisis_count: int = 0,
    crisis_issues: list = None,
    # 기타
    president_approval: float = 0.0,
    party_gap: float = 0.0,
) -> AIBriefing:
    """실제 데이터를 Claude에게 보내 전략 브리핑 생성."""

    top_issues = top_issues or []
    channel_data = channel_data or {}
    crisis_issues = crisis_issues or []

    result = AIBriefing(
        date=datetime.now().strftime("%Y-%m-%d"),
        generated_at=datetime.now().isoformat(),
    )

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _fallback_briefing(result, poll_kim, poll_park, leading_index, leading_direction, turnout_gap, top_issues)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # 데이터 요약 구성
        issues_text = "\n".join([
            f"- {iss.get('keyword','?')}: 이슈지수 {iss.get('score',0):.0f}, 뉴스 {iss.get('mention_count',0)}건, 감성 {iss.get('sentiment','중립')}"
            for iss in top_issues[:5]
        ]) or "- 이슈 데이터 없음"

        channel_text = "\n".join([
            f"- {ch}: 긍정 {d.get('pos',0)}%, 부정 {d.get('neg',0)}%"
            for ch, d in channel_data.items()
        ]) or "- 채널 데이터 없음"

        prompt = f"""당신은 경남도지사 선거 캠프의 전략 분석가입니다.
아래 데이터를 보고 전략 브리핑을 작성하세요.

[우리 후보: 김경수 / 상대: 박완수]

[여론조사]
김경수 {poll_kim}% vs 박완수 {poll_park}% (출처: {poll_source})
격차: {poll_kim - poll_park:+.1f}%p

[판세 (선행지수)]
현재: {leading_index:.1f}/100 (50=중립, 50이상=우리 유리)
방향: {leading_direction}
전일 대비: {leading_delta:+.1f}

[투표율 모델]
실투표 반영 격차: {turnout_gap:+.1f}%p (음수=열세)

[대통령 효과]
대통령 지지율: {president_approval}%, 정당 격차: +{party_gap}%p

[주요 이슈]
{issues_text}

[채널별 감성]
{channel_text}

[위기 이슈]
{crisis_count}건 {'(' + ', '.join(crisis_issues[:3]) + ')' if crisis_issues else ''}

작성 원칙:
- "수치 → 해석 → 함의" 3단 구조
- 숫자를 인정하되 패턴의 의미를 강조
- 위험은 냉정하게, 기회는 데이터 근거로
- 전문 용어 최소화, 캠프 실무진이 바로 이해할 수 있게
- 모든 판단에 데이터 근거 명시

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "headline": "한 문장 핵심 요약 (30자 이내)",
  "situation": "현재 판세를 3~4문장으로 분석. 수치 인용하되 해석과 함의까지.",
  "issues": [
    {{"keyword": "이슈명", "analysis": "이 이슈가 왜 중요하고 현재 어떤 상태인지 2문장", "action": "구체적 대응 방안 1문장", "urgency": "high/medium/low"}},
    ...최대 3개
  ],
  "risks": [
    {{"title": "위험 제목", "current": "현재 상태", "reason": "왜 위험한지 1문장", "threshold": "어떤 기준 넘으면 위기인지"}},
    ...최대 3개
  ],
  "opportunities": [
    {{"title": "기회 제목", "evidence": "데이터 근거", "action": "활용 방안 1문장"}},
    ...최대 3개
  ],
  "tomorrow": ["내일 할 일 1 — 근거", "내일 할 일 2 — 근거", "내일 할 일 3 — 근거"],
  "channel_insight": "채널별 상황 요약 2문장",
  "feedback": "전일 대비 변화 해석 1~2문장"
}}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        import re
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            raw = m.group()

        data = json.loads(raw)

        result.headline = data.get("headline", "")
        result.situation = data.get("situation", "")
        result.issues = data.get("issues", [])
        result.risks = data.get("risks", [])
        result.opportunities = data.get("opportunities", [])
        result.tomorrow = data.get("tomorrow", [])
        result.channel_insight = data.get("channel_insight", "")
        result.feedback = data.get("feedback", "")
        result.model = "claude-haiku"

    except Exception as e:
        print(f"[AI Briefing] 생성 실패: {e}")
        return _fallback_briefing(result, poll_kim, poll_park, leading_index, leading_direction, turnout_gap, top_issues)

    return result


def _fallback_briefing(
    result: AIBriefing,
    poll_kim: float, poll_park: float,
    leading_index: float, leading_direction: str,
    turnout_gap: float, top_issues: list,
) -> AIBriefing:
    """AI 호출 실패 시 규칙 기반 브리핑."""
    gap = poll_kim - poll_park
    dir_ko = "상승" if leading_direction == "gaining" else "하락" if leading_direction == "losing" else "안정"

    result.headline = f"여론조사 {poll_kim:.1f}:{poll_park:.1f} {'우세' if gap >= 0 else '열세'}. 판세 {leading_index:.1f} {dir_ko}."

    result.situation = (
        f"여론조사에서 {abs(gap):.1f}%p {'앞서고' if gap >= 0 else '뒤지고'} 있으나 오차범위 내 초박빙입니다. "
        f"판세(선행지수) {leading_index:.1f}점으로 {dir_ko} 추세입니다. "
        f"투표율 구조를 반영하면 {abs(turnout_gap):.1f}%p 열세로, 3040 세대 투표율 동원이 승패를 결정합니다."
    )

    result.issues = [
        {"keyword": iss.get("keyword", "?"),
         "analysis": f"이슈 지수 {iss.get('score', 0):.0f}점. 뉴스 {iss.get('mention_count', 0)}건 보도.",
         "action": "반응 방향 확인 후 확산 또는 프레임 전환 판단 필요.",
         "urgency": "high" if iss.get("score", 0) >= 60 else "medium"}
        for iss in top_issues[:3]
    ]

    result.risks = [
        {"title": "투표율 구조 열세", "current": f"{abs(turnout_gap):.1f}%p 열세",
         "reason": "60대 이상 고투표율이 원인. 여론조사와 실제 투표 결과가 다를 수 있습니다.",
         "threshold": "20%p 이상 벌어지면 동원 전략 전면 재검토"},
    ]

    result.opportunities = [
        {"title": "대통령 효과", "evidence": "대통령 지지율 67%, 정당 +12%p 우위",
         "action": "대통령 효과가 유지되는 동안 지지층 결집과 부동층 설득에 집중"},
    ]

    result.tomorrow = [
        "갱신 버튼으로 최신 데이터 수집 — 실측 기반 분석 필요",
    ]

    result.model = "fallback"
    result.generated_at = datetime.now().isoformat()

    return result
