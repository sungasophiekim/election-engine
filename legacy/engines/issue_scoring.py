"""
Election Strategy Engine — Engine 1: Issue Scoring
뉴스/SNS 데이터로 이슈 위험도를 0~100으로 계산합니다.

v2: 승수(multiplicative) 방식 → 가산(additive) 보너스 방식으로 변경.
    기존 승수 시스템은 거의 모든 이슈를 100점으로 만들어 변별력이 없었음.
"""
import math
from datetime import datetime, date

from models.schemas import IssueSignal, IssueScore, CrisisLevel
from config.tenant_config import TenantConfig


# 언론사 등급별 기본 가중치
MEDIA_TIER_WEIGHT = {1: 1.0, 2: 0.6, 3: 0.3}

# 가산 보너스 (multiplier 대신 additive bonus)
# v5: 이슈 키워드에서 변별력 확보를 위해 보너스 축소
# - candidate_linked: 대부분 true라 변별력 낮음 → 제거
# - portal_trending: 150건 기준이 너무 낮음 → 축소
# - tv_reported: 방송 보도는 의미 있지만 과대평가 → 축소
CANDIDATE_LINK_BONUS = 0    # 후보 연결 — 이슈 키워드에선 거의 항상 true, 변별력 없음
PORTAL_TRENDING_BONUS = 4   # 포털 실검 진입 (8→4)
TV_REPORTED_BONUS = 6       # 방송 보도 (12→6)


def _election_proximity_bonus(election_date_str: str) -> float:
    """
    선거일이 가까울수록 추가되는 보너스 점수 (0~10).
    D-90+: +0  /  D-60: +2  /  D-30: +5  /  D-14: +7  /  D-7: +10
    부드러운 보간(interpolation) 사용.
    """
    try:
        election_date = datetime.strptime(election_date_str, "%Y-%m-%d").date()
        days_left = (election_date - date.today()).days
        if days_left <= 0:
            return 10.0
        if days_left >= 90:
            return 0.0

        # 구간별 선형 보간
        # (days_left, bonus) 기준점
        breakpoints = [
            (90, 0.0),
            (60, 2.0),
            (30, 5.0),
            (14, 7.0),
            (7,  10.0),
        ]

        # days_left가 7 이하면 최대 보너스
        if days_left <= 7:
            return 10.0

        # 해당 구간 찾기
        for i in range(len(breakpoints) - 1):
            d_high, b_low = breakpoints[i]
            d_low, b_high = breakpoints[i + 1]
            if d_low <= days_left <= d_high:
                # 선형 보간: days_left가 d_high→d_low로 갈수록 bonus 증가
                ratio = (d_high - days_left) / (d_high - d_low)
                return b_low + ratio * (b_high - b_low)

        return 0.0
    except Exception:
        return 0.0


def _velocity_score(velocity: float, mention_count: int = 0) -> float:
    """
    언급 증가율(velocity) → 점수 기여분 (0~25).
    velocity가 낮더라도 절대 언급수가 높으면 일정 점수 부여.
    """
    # mention_count_bonus: 절대 언급수가 높으면 velocity가 낮아도 점수 부여
    mention_count_bonus = min(5.0, mention_count / 20.0)

    # velocity <= 1.0이면 증가율 기여분은 0, 하지만 mention_count_bonus는 반영
    if velocity <= 1.0:
        return min(25.0, mention_count_bonus)

    # log2 스케일 + mention_count 보정
    return min(25.0, math.log2(velocity) * 8.0 + mention_count_bonus)


def _mention_score(mention_count: int) -> float:
    """
    시간당 언급 수 → 점수 기여분 (0~25).
    실제 데이터 기준(24h 기준 0~100건)에 맞게 스케일링.
    """
    if mention_count <= 0:
        return 0.0
    return min(25.0, math.log10(mention_count + 1) * 12.5)


def _media_score(media_tier: int) -> float:
    """언론사 등급 → 점수 기여분 (0~10)"""
    return MEDIA_TIER_WEIGHT.get(media_tier, 0.3) * 10


def _sentiment_score(negative_ratio: float) -> float:
    """부정 감정 비율 → 점수 기여분 (0~15)"""
    return negative_ratio * 15


def calculate_issue_score(
    signal: IssueSignal,
    config: TenantConfig,
    anomaly_result=None,    # v2: AnomalyResult — surprise_score로 보너스 부여
    dedup_metrics: dict = None,  # v2: {"raw_count": N, "story_count": M, "dedup_ratio": R}
) -> IssueScore:
    """
    핵심 스코어링 함수.

    base_score = velocity(0~25) + mention(0~25) + media(0~10)
               = 0~60

    bonuses (additive):
      candidate_linked: +10
      portal_trending:  +8
      tv_reported:      +12
      election_proximity: +0~10
      anomaly_surprise:  +0~8  (v2)

    final = clamp(base + bonuses, 0, 100)

    NOTE: sentiment는 스코어에서 제거됨 — AI 에이전트가 별도 분석
    """
    v_score  = _velocity_score(signal.velocity, signal.mention_count)
    m_score  = _mention_score(signal.mention_count)
    md_score = _media_score(signal.media_tier)
    s_score  = 0.0  # sentiment 제거 — AI 에이전트로 이관

    base = v_score + m_score + md_score

    # 가산 보너스 적용
    bonus = 0.0
    if signal.candidate_linked:
        bonus += CANDIDATE_LINK_BONUS
    if signal.portal_trending:
        bonus += PORTAL_TRENDING_BONUS
    if signal.tv_reported:
        bonus += TV_REPORTED_BONUS

    proximity_bonus = _election_proximity_bonus(config.election_date)
    bonus += proximity_bonus

    # v2: anomaly surprise bonus (0~8)
    anomaly_bonus = 0.0
    if anomaly_result and hasattr(anomaly_result, 'surprise_score'):
        # surprise_score 0~100 → bonus 0~8
        anomaly_bonus = min(8.0, anomaly_result.surprise_score / 100.0 * 8.0)
        bonus += anomaly_bonus

    # v3: reaction-based bonus (0~7)
    # engagement_score 0~1 → bonus 0~4
    # candidate_action_linked → bonus +3
    reaction_bonus = 0.0
    if signal.engagement_score > 0:
        reaction_bonus += min(4.0, signal.engagement_score * 4.0)
    if signal.candidate_action_linked:
        reaction_bonus += 3.0
    bonus += reaction_bonus

    raw_score = base + bonus

    # 0~100 클램프
    score = max(0.0, min(100.0, raw_score))

    # 위험도 레벨 분류 (config 값 사용)
    if score >= config.score_threshold_lv3:
        level = CrisisLevel.CRISIS
    elif score >= config.score_threshold_lv2:
        level = CrisisLevel.ALERT
    elif score >= config.score_threshold_lv1:
        level = CrisisLevel.WATCH
    else:
        level = CrisisLevel.NORMAL

    # v2: anomaly surge → 자동 레벨 격상
    if anomaly_result and hasattr(anomaly_result, 'is_surge') and anomaly_result.is_surge:
        if level.value < CrisisLevel.ALERT.value:
            level = CrisisLevel.ALERT

    # 이슈 반감기 추정 (단위: 시간)
    # 점수가 높을수록 오래 지속, 방송 보도면 더 오래
    halflife = 6.0 + (score / 100) * 42
    if signal.tv_reported:
        halflife *= 2.0

    breakdown = {
        "velocity_score":    round(v_score,  2),
        "mention_score":     round(m_score,  2),
        "media_score":       round(md_score, 2),
        "sentiment_score":   round(s_score,  2),
        "base_score":        round(base,     2),
        "bonus":             round(bonus,    2),
        "proximity_bonus":   round(proximity_bonus, 2),
        "anomaly_bonus":     round(anomaly_bonus, 2),
        "reaction_bonus":    round(reaction_bonus, 2),
        "final_score":       round(score,    2),
    }

    # v2: dedup metrics 포함
    if dedup_metrics:
        breakdown["raw_article_count"] = dedup_metrics.get("raw_count", 0)
        breakdown["deduped_story_count"] = dedup_metrics.get("story_count", 0)
        breakdown["dedup_ratio"] = dedup_metrics.get("dedup_ratio", 0.0)

    # v3: reaction metrics 포함
    if signal.reaction_volume > 0 or signal.engagement_score > 0:
        breakdown["reaction_volume"] = signal.reaction_volume
        breakdown["reaction_velocity"] = signal.reaction_velocity
        breakdown["engagement_score"] = signal.engagement_score

    # v3: influence_score — mention 기반 점수 + reaction 기반 점수의 가중 합산
    # mention_weight(60%) + reaction_weight(40%) 블렌딩
    mention_component = score  # 이미 계산된 기존 점수
    reaction_component = 0.0
    if signal.reaction_volume > 0:
        # reaction_volume의 log 스케일 + engagement + velocity 가중
        rv_log = min(25.0, math.log10(signal.reaction_volume + 1) * 12.5)
        rv_eng = signal.engagement_score * 25.0
        rv_vel = min(25.0, signal.reaction_velocity * 10.0) if signal.reaction_velocity > 1.0 else 0.0
        reaction_component = min(100.0, rv_log + rv_eng + rv_vel)
    influence_score = round(mention_component * 0.6 + reaction_component * 0.4, 2)

    return IssueScore(
        keyword=signal.keyword,
        score=round(score, 2),
        level=level,
        breakdown=breakdown,
        estimated_halflife_hours=round(halflife, 1),
        # v3: pass-through fields
        influence_score=influence_score,
        segment_hint=signal.segment_hint,
        message_theme=signal.message_theme,
        region=signal.region,
    )


def score_multiple_signals(
    signals: list[IssueSignal],
    config:  TenantConfig,
    anomaly_results: list = None,   # v2: list[AnomalyResult] keyed by keyword
    dedup_results: dict = None,     # v2: {keyword: {"raw_count": N, "story_count": M, "dedup_ratio": R}}
) -> list[IssueScore]:
    """여러 이슈 신호를 일괄 스코어링 후 점수 내림차순 반환"""
    # v2: build lookup maps
    anomaly_map = {}
    if anomaly_results:
        for ar in anomaly_results:
            if hasattr(ar, 'keyword'):
                anomaly_map[ar.keyword] = ar

    dedup_results = dedup_results or {}

    results = [
        calculate_issue_score(
            s, config,
            anomaly_result=anomaly_map.get(s.keyword),
            dedup_metrics=dedup_results.get(s.keyword),
        )
        for s in signals
    ]
    return sorted(results, key=lambda x: x.score, reverse=True)
