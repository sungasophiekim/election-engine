"""
Election Strategy Engine — Engine 3 & 4
Engine 3: Voter Segment Mapper  — 지역별 유권자 우선순위 계산
Engine 4: Opponent Response Pattern — 경쟁자 공격 예측
"""
import math
from datetime import datetime, date

from models.schemas import VoterSegment, OpponentSignal, IssueScore, CrisisLevel
from config.tenant_config import TenantConfig


# ══════════════════════════════════════════════════════════════════
# Engine 3: Voter Segment Mapper
# ══════════════════════════════════════════════════════════════════

def _days_until_election(election_date_str: str) -> int:
    try:
        election_date = datetime.strptime(election_date_str, "%Y-%m-%d").date()
        return max(0, (election_date - date.today()).days)
    except Exception:
        return 90


def _dynamic_weight(days_left: int) -> dict:
    """
    선거일이 가까울수록 경합 지역에 가중치를 더 줍니다.
    D-90+: 유권자 수 중심 / D-30 이하: 경합도 중심
    """
    if days_left >= 90:
        return {"voter_count": 0.50, "swing": 0.30, "online": 0.10, "issue": 0.10}
    elif days_left >= 30:
        return {"voter_count": 0.35, "swing": 0.45, "online": 0.12, "issue": 0.08}
    else:
        # 막판: 경합 지역에 화력 집중
        return {"voter_count": 0.20, "swing": 0.60, "online": 0.12, "issue": 0.08}


# 도시 지역: 온라인 활동도가 높은 지역
URBAN_REGIONS = {"창원시", "김해시", "양산시", "진주시"}


def _calculate_local_heat(region_name: str, key_issue: str, issue_scores: list[IssueScore]) -> float:
    """
    실제 이슈 데이터로부터 지역별 이슈 열기(heat)를 계산합니다.
    - 이슈 키워드에 지역명이 직접 언급되면 높은 가중치
    - 이슈 키워드가 지역 핵심 이슈 토픽과 매칭되면 중간 가중치
    """
    if not issue_scores:
        return 0.3  # 데이터 없을 때 기본값

    heat = 0.0
    for score in issue_scores:
        keyword = score.keyword.lower()
        # 지역명 직접 언급 (e.g., "창원 조선업" → 창원시)
        if region_name.replace("시", "") in keyword:
            heat += score.score / 100 * 0.8
        # 핵심 이슈 토픽 매칭 (e.g., "조선업 일자리" → ["조선업", "일자리"])
        key_words = key_issue.split()
        for kw in key_words:
            if kw in keyword:
                heat += score.score / 100 * 0.5

    return min(1.0, heat)


def calculate_voter_priorities(
    config: TenantConfig,
    issue_scores: list[IssueScore] = None,
) -> list[VoterSegment]:
    """
    지역별 우선순위 점수 계산.
    priority = voter_count_norm × w1
             + swing_index      × w2
             + online_activity  × w3
             + local_issue_heat × w4

    issue_scores가 제공되면 실제 이슈 데이터로 local_issue_heat를 계산합니다.
    """
    days_left = _days_until_election(config.election_date)
    weights   = _dynamic_weight(days_left)

    # 유권자 수 정규화 (최댓값 = 1.0)
    all_voters   = [r["voters"] for r in config.regions.values()]
    max_voters   = max(all_voters) if all_voters else 1

    segments = []
    for region_name, region_data in config.regions.items():
        voter_norm    = region_data["voters"] / max_voters
        swing_index   = region_data.get("swing_index", 0.5)
        key_issue     = region_data.get("key_issue", "")

        # 온라인 활동도: 도시 지역은 높고, 유권자 밀도로 보정
        online_act = 0.7 if region_name in URBAN_REGIONS else 0.4
        online_act = min(1.0, online_act + voter_norm * 0.2)

        # 지역 이슈 열기: 실제 이슈 데이터와 연동
        local_heat = _calculate_local_heat(region_name, key_issue, issue_scores)

        priority = (
            voter_norm  * weights["voter_count"]
          + swing_index * weights["swing"]
          + online_act  * weights["online"]
          + local_heat  * weights["issue"]
        )

        seg = VoterSegment(
            region=region_name,
            voter_count=region_data["voters"],
            swing_index=swing_index,
            online_activity=online_act,
            local_issue_heat=local_heat,
            priority_score=round(priority, 4),
        )
        segments.append(seg)

    return sorted(segments, key=lambda x: x.priority_score, reverse=True)


def get_schedule_weights(config: TenantConfig, issue_scores: list[IssueScore] = None) -> dict:
    """일정 에이전트에 전달할 지역별 가중치 딕셔너리"""
    segments = calculate_voter_priorities(config, issue_scores)
    return {s.region: round(s.priority_score, 3) for s in segments}


# ══════════════════════════════════════════════════════════════════
# Engine 4: Opponent Response Pattern Engine
# ══════════════════════════════════════════════════════════════════

def _mention_acceleration(recent_mentions: int, baseline: int = 50) -> float:
    """최근 언급 수 가속도 (baseline 대비 배수)"""
    if baseline <= 0:
        return 1.0
    return recent_mentions / baseline


def estimate_attack_probability(
    opponent_name:      str,
    recent_mentions:    int,
    our_issue_scores:   list[IssueScore],
    days_until_election: int,
    has_message_shift:  bool = False,
) -> float:
    """
    72시간 내 공격 확률 추정 (0.0 ~ 1.0).

    attack_prob = f(
        경쟁자 최근 언급 급등,
        우리 캠프 취약 이슈 존재 여부,
        선거일 근접도,
        경쟁자 메시지 전환 신호
    )
    """
    # 경쟁자 활동성 신호 (0~0.3)
    activity_signal = min(0.30, math.log(max(recent_mentions, 1) + 1, 10) * 0.12)

    # 우리 취약점 신호 (0~0.35): 높은 이슈 스코어가 있으면 공격 유인 증가
    vulnerability = 0.0
    if our_issue_scores:
        top_score = our_issue_scores[0].score
        if top_score >= 60:
            vulnerability = 0.35
        elif top_score >= 30:
            vulnerability = 0.20
        else:
            vulnerability = 0.05

    # 선거일 근접 신호 (0~0.20)
    if days_until_election <= 7:
        proximity_signal = 0.20
    elif days_until_election <= 30:
        proximity_signal = 0.12
    else:
        proximity_signal = 0.05

    # 메시지 전환 신호 (0~0.15)
    shift_signal = 0.15 if has_message_shift else 0.0

    prob = activity_signal + vulnerability + proximity_signal + shift_signal
    return round(min(1.0, prob), 3)


def analyze_opponents(
    config: TenantConfig,
    opponent_data: list[dict],    # [{"name": str, "recent_mentions": int, "message_shift": str}, ...]
    our_issue_scores: list[IssueScore],
) -> list[OpponentSignal]:
    """
    경쟁 후보 분석 및 72h 공격 예측.
    opponent_data는 외부 수집 결과를 받습니다.
    """
    days_left = _days_until_election(config.election_date)
    results   = []

    for opp in opponent_data:
        name            = opp.get("name", "")
        recent_mentions = opp.get("recent_mentions", 0)
        message_shift   = opp.get("message_shift", "")
        has_shift       = bool(message_shift)

        attack_prob = estimate_attack_probability(
            opponent_name=name,
            recent_mentions=recent_mentions,
            our_issue_scores=our_issue_scores,
            days_until_election=days_left,
            has_message_shift=has_shift,
        )

        # 권고 행동 결정
        if attack_prob >= 0.70:
            action = f"[선제 대응 권고] {name} 후보의 공격 확률 {attack_prob*100:.0f}%. 즉시 방어 논리 준비 및 선제 발표 검토"
        elif attack_prob >= 0.40:
            action = f"[모니터링 강화] {name} 후보 동향 주시. 대응 초안 사전 준비"
        else:
            action = f"[정상 모니터링] {name} 후보 특이 동향 없음"

        results.append(OpponentSignal(
            opponent_name=name,
            recent_mentions=recent_mentions,
            message_shift=message_shift or "없음",
            attack_prob_72h=attack_prob,
            recommended_action=action,
        ))

    return sorted(results, key=lambda x: x.attack_prob_72h, reverse=True)
