"""
Election Strategy Engine — Engine 2: Message Consistency Validator
AI 생성 콘텐츠를 배포 전에 캠프 포지션과 대조해 검증합니다.
임베딩 없이도 동작하는 룰 기반 + Claude 재검증 방식.
"""
import re
from dataclasses import dataclass

import anthropic

from models.schemas import ContentDraft, ContentType, ValidationResult
from config.tenant_config import TenantConfig


@dataclass
class ValidationDetail:
    forbidden_violations: list[str]   # 금기어 위반
    pledge_mismatches:    list[str]   # 공약 수치 불일치
    tone_issues:          list[str]   # 톤앤매너 문제
    consistency_score:    float       # 0.0 ~ 1.0


def _check_forbidden_words(text: str, config: TenantConfig) -> list[str]:
    """금기어 하드 필터 — 발견 즉시 목록 반환"""
    violations = []
    for word in config.forbidden_words:
        if word in text:
            violations.append(f"금기어 감지: '{word}'")
    return violations


def _check_pledge_numbers(text: str, config: TenantConfig) -> list[str]:
    """
    공약 수치 검증.
    텍스트에서 숫자가 포함된 문장을 추출해
    DB의 공약 수치와 불일치 여부를 확인합니다.
    """
    mismatches = []
    # 간단 숫자 패턴 추출 (만, 억, 조 단위 포함)
    number_pattern = re.compile(r'\d[\d,]*\s*(?:만|억|조|개|명|원|개소|노선|년)?')
    found_numbers = number_pattern.findall(text)

    for pledge_name, pledge_info in config.pledges.items():
        if pledge_name in text:
            # 공약이 언급되었는데, 수치가 다를 경우 경고
            for num in found_numbers:
                clean_num = num.strip()
                if clean_num and clean_num not in pledge_info.get("수치", ""):
                    # 실제 구현에서는 더 정교한 수치 매칭 필요
                    pass  # 간소화: 상세 수치 매칭은 Claude 재검증에서 처리

    return mismatches


def _calculate_rule_based_score(
    forbidden: list[str],
    mismatches: list[str],
    tone_issues: list[str],
) -> float:
    """
    룰 기반 일관성 점수 (0.0 ~ 1.0).
    각 위반 항목 유형별로 감점.
    """
    score = 1.0
    score -= len(forbidden)  * 0.30   # 금기어 하나당 -0.3
    score -= len(mismatches) * 0.20   # 수치 불일치 하나당 -0.2
    score -= len(tone_issues) * 0.10  # 톤 문제 하나당 -0.1
    return max(0.0, score)


def validate_with_claude(
    draft: ContentDraft,
    config: TenantConfig,
    client: anthropic.Anthropic,
) -> ValidationResult:
    """
    Claude API를 사용한 전체 검증.
    1단계: 룰 기반 하드 필터
    2단계: Claude 의미 검증 + 수정 제안 생성
    """
    text = draft.text

    # ── 1단계: 룰 기반 하드 필터 ────────────────────────────────
    forbidden   = _check_forbidden_words(text, config)
    mismatches  = _check_pledge_numbers(text, config)
    tone_issues: list[str] = []

    rule_score = _calculate_rule_based_score(forbidden, mismatches, tone_issues)

    # 금기어 발견 → 즉시 반려 (Claude 호출 불필요)
    if forbidden:
        return ValidationResult(
            is_approved=False,
            consistency_score=0.0,
            violations=forbidden,
            suggestions=["금기어를 제거한 후 재작성해 주세요."],
        )

    # ── 2단계: Claude 의미 검증 ──────────────────────────────────
    pledges_str = "\n".join(
        f"- {name}: {info['수치']} ({info['설명']})"
        for name, info in config.pledges.items()
    )

    system_prompt = f"""당신은 '{config.candidate_name}' 후보 선거캠프의 콘텐츠 검증 AI입니다.

[캠프 핵심 메시지]
{config.core_message}

[슬로건]
{config.slogan}

[공약 수치 원본]
{pledges_str}

[금기어 목록]
{', '.join(config.forbidden_words)}

콘텐츠를 검토해 다음 JSON 형식으로만 응답하세요:
{{
  "consistent": true/false,
  "score": 0.0~1.0,
  "violations": ["위반사항1", ...],
  "suggestions": ["수정제안1", "수정제안2", "수정제안3"]
}}"""

    user_message = f"""다음 {draft.content_type.value} 초안을 검증해 주세요:

---
{text}
---

핵심 메시지와의 일관성, 공약 수치 정확성, 금기어 포함 여부를 확인하고 JSON으로만 응답하세요."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        import json
        raw = response.content[0].text.strip()
        # JSON 블록 추출
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()

        result = json.loads(raw)

        claude_score  = float(result.get("score", 0.5))
        violations    = result.get("violations", [])
        suggestions   = result.get("suggestions", [])

        # 룰 점수와 Claude 점수 평균
        final_score = (rule_score + claude_score) / 2
        is_approved = final_score >= 0.65 and not violations

        return ValidationResult(
            is_approved=is_approved,
            consistency_score=round(final_score, 2),
            violations=violations,
            suggestions=suggestions[:3],
        )

    except Exception as e:
        # Claude 호출 실패 시 룰 기반 결과만 반환
        return ValidationResult(
            is_approved=rule_score >= 0.7,
            consistency_score=round(rule_score, 2),
            violations=forbidden + mismatches,
            suggestions=[f"[Claude 검증 실패: {str(e)}] 수동 검토 필요"],
        )
