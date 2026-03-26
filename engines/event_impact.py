"""
Event Impact Quantifier — 이벤트 유형별 여론 영향 정량화
"정책 발표 vs TV 토론 vs 스캔들, 각각 몇 %p 움직이는가?"

리서치 근거:
  - 정책 발표: +0.5~3.0%p (규모에 따라)
  - TV 토론: ±1.0~5.0%p (승패에 따라 양방향)
  - 스캔들/위기: -1.0~8.0%p (유형별 차등)
  - 지지선언: +0.2~1.5%p (조직 규모에 따라)
  - 지역 방문: +0.1~1.0%p (지역 한정)
  - SNS 캠페인: +0.1~0.5%p (바이럴 시 확대)

사용법:
  result = estimate_event_impact("policy", severity="major", ...)
  → 예상 여론 변화 %p + 신뢰 구간 + 전략 권고

Leading Index 연동:
  이벤트 감지 시 issue_pressure에 event_type별 가중치 적용.
  compute_leading_index()에서 event_context 파라미터로 전달.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# 이벤트 유형 정의 + 기저 임팩트
# ═══════════════════════════════════════════════════════════════

# 기저 임팩트 (%p) — 학술연구 + 캠프 보고서 + 과거 선거 사례 기반
# 각 이벤트 유형의 "표준 크기" 발생 시 예상 여론 변화

EVENT_TYPES = {
    "policy": {
        "label": "정책 발표",
        "icon": "📋",
        "base_impact": 1.5,       # %p
        "range": (0.5, 3.0),      # min~max
        "lag_hours": 24,          # 여론 반영까지 시간
        "decay_days": 7,          # 효과 소멸까지 일수
        "evidence": "7대 지선 김경수 '경남형 일자리' → 지지율 +2.1%p (1주)",
    },
    "debate": {
        "label": "TV 토론",
        "icon": "🎙",
        "base_impact": 2.0,       # 승리 시 (패배 시 -2.0)
        "range": (1.0, 5.0),
        "lag_hours": 6,           # 토론 직후 즉시 반영
        "decay_days": 14,         # 비교적 오래 지속
        "evidence": "2022 대선 TV토론 → 윤석열 +3.2%p, 2017 대선 문재인 +4.1%p",
    },
    "scandal": {
        "label": "스캔들/위기",
        "icon": "⚠",
        "base_impact": -2.5,      # 기본 부정
        "range": (-1.0, -8.0),
        "lag_hours": 12,
        "decay_days": 21,         # 오래 지속 (프레이밍 고착)
        "evidence": "김경수 사법리스크 프레임 → 지속적 -2~3%p 압력",
    },
    "endorsement": {
        "label": "지지선언",
        "icon": "🤝",
        "base_impact": 0.5,
        "range": (0.2, 1.5),
        "lag_hours": 48,          # 조직 내 전파 시간 필요
        "decay_days": 10,
        "evidence": "민주노총 경남본부 지지선언 → 산업단지 투표율 +3%p 추정",
    },
    "visit": {
        "label": "지역 방문",
        "icon": "📍",
        "base_impact": 0.3,
        "range": (0.1, 1.0),
        "lag_hours": 24,
        "decay_days": 3,          # 빨리 소멸
        "evidence": "현장 방문은 지역 뉴스 1회 노출, 전도 효과는 제한적",
    },
    "sns_campaign": {
        "label": "SNS 캠페인",
        "icon": "📱",
        "base_impact": 0.2,
        "range": (0.1, 0.5),
        "lag_hours": 6,
        "decay_days": 2,          # 매우 빨리 소멸
        "evidence": "바이럴 성공 시 검색량 +50~200%, 여론 직접 영향은 제한적",
    },
    "gaffe": {
        "label": "실언/실수",
        "icon": "💬",
        "base_impact": -1.5,
        "range": (-0.5, -5.0),
        "lag_hours": 3,           # 즉시 확산
        "decay_days": 5,
        "evidence": "2022 지선 실언 → SNS 밈화 → -1~3%p (바이럴 정도에 따라)",
    },
    "poll_release": {
        "label": "여론조사 발표",
        "icon": "📊",
        "base_impact": 0.0,       # 방향은 결과에 따라
        "range": (-2.0, 2.0),
        "lag_hours": 12,
        "decay_days": 5,
        "evidence": "Stanford 연구: 앞선 후보 → 편승효과 +1~2%p, 뒤진 후보 → 동정표 효과",
    },
}


# ═══════════════════════════════════════════════════════════════
# 컨텍스트 승수 (multiplier)
# ═══════════════════════════════════════════════════════════════

SEVERITY_MULTIPLIER = {
    "critical": 2.0,   # 초대형 (대선급 스캔들, 전국 토론)
    "major": 1.5,      # 대형 (도지사 토론, 핵심 공약)
    "standard": 1.0,   # 표준
    "minor": 0.5,      # 소형 (일상 행보, 소규모 방문)
}

TIMING_MULTIPLIER = {
    "news_vacuum": 1.3,     # 다른 뉴스 없을 때 (독점 노출)
    "weekend": 0.7,         # 주말 (뉴스 소비 감소)
    "competing_news": 0.6,  # 대형 뉴스와 경쟁 (묻힘)
    "election_day_near": 1.4,  # D-30 이내 (관심 집중기)
    "normal": 1.0,          # 평시
}

MEDIA_TIER_MULTIPLIER = {
    "tv_main": 1.5,     # 지상파 메인 뉴스
    "portal_top": 1.3,  # 네이버 메인 노출
    "regional": 0.8,    # 지역 언론만
    "online_only": 0.6, # 온라인만
    "normal": 1.0,
}

# 상대방 반격 시 할인율
COUNTER_DISCOUNT = {
    "immediate_counter": 0.5,  # 즉시 반박/반격 → 효과 반감
    "delayed_counter": 0.7,    # 24시간 후 반격
    "no_counter": 1.0,         # 반격 없음
}


# ═══════════════════════════════════════════════════════════════
# 데이터 구조
# ═══════════════════════════════════════════════════════════════

@dataclass
class EventImpactEstimate:
    """이벤트 임팩트 추정 결과"""
    event_type: str
    event_label: str
    event_icon: str

    # 예상 영향
    expected_impact: float          # 예상 %p 변화
    impact_range: tuple             # (최소, 최대) %p
    confidence: float               # 0.0~1.0

    # 적용된 승수
    severity: str
    severity_mult: float
    timing_mult: float
    media_mult: float
    counter_discount: float
    regional_factor: float          # 전국 vs 지역 (0.3~1.0)

    # 시간 프로파일
    lag_hours: int                  # 반영까지 시간
    peak_hours: int                 # 최대 효과 시점
    decay_days: int                 # 효과 소멸 기간

    # 세대별 차등 영향
    age_impact: dict = field(default_factory=dict)  # {"20s": +2.0, "60s": +0.5}

    # 전략 권고
    recommendation: str = ""
    counter_strategy: str = ""      # 우리가 당한 경우 대응 전략

    # 메타
    evidence: str = ""
    computed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "event_label": self.event_label,
            "event_icon": self.event_icon,
            "expected_impact": round(self.expected_impact, 2),
            "impact_range": [round(self.impact_range[0], 2), round(self.impact_range[1], 2)],
            "confidence": round(self.confidence, 2),
            "severity": self.severity,
            "multipliers": {
                "severity": self.severity_mult,
                "timing": self.timing_mult,
                "media": self.media_mult,
                "counter_discount": self.counter_discount,
                "regional": self.regional_factor,
            },
            "time_profile": {
                "lag_hours": self.lag_hours,
                "peak_hours": self.peak_hours,
                "decay_days": self.decay_days,
            },
            "age_impact": self.age_impact,
            "recommendation": self.recommendation,
            "counter_strategy": self.counter_strategy,
            "evidence": self.evidence,
            "computed_at": self.computed_at,
        }


@dataclass
class EventImpactHistory:
    """이벤트 실적 기록 (학습용)"""
    event_type: str
    predicted_impact: float
    actual_impact: float            # 실제 여론 변화 (T+72h 기준)
    error: float                    # actual - predicted
    date: str = ""
    description: str = ""


# ═══════════════════════════════════════════════════════════════
# 세대별 차등 영향 프로파일
# ═══════════════════════════════════════════════════════════════

# 이벤트 유형별로 어느 세대에 더 영향을 미치는가
AGE_IMPACT_PROFILE = {
    "policy": {
        "20s": 0.8,   # 정책 관심 낮음
        "30s": 1.2,   # 생활 밀접 정책에 민감 (육아, 주거)
        "40s": 1.1,   # 경제/교육 정책
        "50s": 1.0,   # 표준
        "60s": 0.9,   # 관심은 있으나 변심 적음
        "70+": 0.7,   # 정당 충성 (정책 영향 적음)
    },
    "debate": {
        "20s": 1.3,   # TV/유튜브로 시청, 인상 변화 큼
        "30s": 1.1,
        "40s": 1.0,
        "50s": 1.0,
        "60s": 0.8,   # 이미 마음 정한 경우 많음
        "70+": 0.6,
    },
    "scandal": {
        "20s": 1.4,   # 도덕적 기준 엄격, SNS 확산 주도
        "30s": 1.2,
        "40s": 1.0,
        "50s": 0.9,
        "60s": 0.7,   # 우리 편이면 방어적
        "70+": 0.5,
    },
    "endorsement": {
        "20s": 0.5,   # 조직 지지선언에 무관심
        "30s": 0.8,   # 맘카페 추천은 영향 있음
        "40s": 1.2,   # 노조/직능단체 영향
        "50s": 1.3,   # 조직 소속감 높음
        "60s": 1.0,
        "70+": 0.8,
    },
    "visit": {
        "20s": 0.3,   # 거의 무관심
        "30s": 0.5,
        "40s": 0.8,
        "50s": 1.0,
        "60s": 1.5,   # 방문 = 존중, 고령층 감동
        "70+": 1.8,   # 직접 만남에 크게 반응
    },
    "sns_campaign": {
        "20s": 2.0,   # SNS 주력 세대
        "30s": 1.5,
        "40s": 0.8,
        "50s": 0.4,
        "60s": 0.2,
        "70+": 0.1,
    },
    "gaffe": {
        "20s": 1.5,   # 밈화 + 확산
        "30s": 1.2,
        "40s": 1.0,
        "50s": 0.8,
        "60s": 0.6,
        "70+": 0.4,
    },
    "poll_release": {
        "20s": 1.2,   # 편승효과 민감
        "30s": 1.1,
        "40s": 1.0,
        "50s": 0.9,
        "60s": 0.7,
        "70+": 0.5,
    },
}


# ═══════════════════════════════════════════════════════════════
# 핵심 계산
# ═══════════════════════════════════════════════════════════════

def estimate_event_impact(
    event_type: str,
    severity: str = "standard",
    is_our_event: bool = True,       # True=우리 이벤트, False=상대 이벤트
    timing: str = "normal",
    media_tier: str = "normal",
    counter_response: str = "no_counter",
    is_regional: bool = False,       # True=경남 1개 시군 한정
    region: str = "",                # 특정 지역 (빈 문자열=전체)
    description: str = "",           # 이벤트 설명
    # 추가 컨텍스트
    poll_gap: float = 0.0,          # 현재 여론 격차 (양수=우리 유리)
    days_to_election: int = 90,      # D-day
) -> EventImpactEstimate:
    """
    이벤트 유형 + 컨텍스트 → 예상 여론 변화 %p 추정.

    Returns:
        EventImpactEstimate with expected_impact in %p
    """
    if event_type not in EVENT_TYPES:
        event_type = "policy"  # 기본값

    et = EVENT_TYPES[event_type]
    base = et["base_impact"]

    # ── 승수 적용 ──
    sev_m = SEVERITY_MULTIPLIER.get(severity, 1.0)
    tim_m = TIMING_MULTIPLIER.get(timing, 1.0)
    med_m = MEDIA_TIER_MULTIPLIER.get(media_tier, 1.0)
    cnt_d = COUNTER_DISCOUNT.get(counter_response, 1.0)

    # D-day 근접 보정
    if days_to_election <= 30:
        tim_m *= 1.3  # 선거 임박 → 관심 집중
    elif days_to_election <= 14:
        tim_m *= 1.5  # 2주 전 → 최대 관심

    # 지역 한정 보정
    regional_factor = 0.3 if is_regional else 1.0

    # 접전도 보정 (접전일수록 이벤트 영향 확대)
    closeness_mult = 1.0 + max(0, (3 - abs(poll_gap))) * 0.1  # 격차 0 → 1.3

    # 최종 예상 임팩트
    expected = base * sev_m * tim_m * med_m * cnt_d * regional_factor * closeness_mult

    # 상대 이벤트면 부호 반전 (상대 정책 발표 → 우리에게 -)
    if not is_our_event:
        expected = -expected

    # 범위 계산
    range_low = et["range"][0] * sev_m * regional_factor
    range_high = et["range"][1] * sev_m * regional_factor
    if not is_our_event:
        range_low, range_high = -range_high, -range_low

    # 신뢰도 (승수가 많이 적용될수록 불확실)
    total_mult = sev_m * tim_m * med_m * cnt_d * closeness_mult
    confidence = max(0.3, min(0.9, 1.0 - abs(total_mult - 1.0) * 0.3))

    # ── 세대별 차등 ──
    age_profile = AGE_IMPACT_PROFILE.get(event_type, {})
    age_impact = {}
    for age_key, mult in age_profile.items():
        age_impact[age_key] = round(expected * mult, 2)

    # ── 시간 프로파일 ──
    lag = et["lag_hours"]
    peak = lag + (et["decay_days"] * 24 // 4)  # 소멸의 1/4 지점이 피크
    decay = et["decay_days"]

    # ── 전략 권고 ──
    recommendation = _generate_recommendation(event_type, expected, is_our_event, severity)
    counter_strategy = _generate_counter_strategy(event_type) if not is_our_event else ""

    return EventImpactEstimate(
        event_type=event_type,
        event_label=et["label"],
        event_icon=et["icon"],
        expected_impact=expected,
        impact_range=(range_low, range_high),
        confidence=confidence,
        severity=severity,
        severity_mult=sev_m,
        timing_mult=tim_m,
        media_mult=med_m,
        counter_discount=cnt_d,
        regional_factor=regional_factor,
        lag_hours=lag,
        peak_hours=peak,
        decay_days=decay,
        age_impact=age_impact,
        recommendation=recommendation,
        counter_strategy=counter_strategy,
        evidence=et["evidence"],
        computed_at=datetime.now().isoformat(),
    )


def estimate_all_event_impacts(
    is_our_event: bool = True,
    severity: str = "standard",
    timing: str = "normal",
    poll_gap: float = 0.0,
    days_to_election: int = 90,
) -> list[dict]:
    """모든 이벤트 유형의 예상 임팩트를 한번에 계산."""
    results = []
    for etype in EVENT_TYPES:
        est = estimate_event_impact(
            event_type=etype,
            severity=severity,
            is_our_event=is_our_event,
            timing=timing,
            poll_gap=poll_gap,
            days_to_election=days_to_election,
        )
        results.append(est.to_dict())

    # 절대 영향 크기 순 정렬
    results.sort(key=lambda x: -abs(x["expected_impact"]))
    return results


def get_event_impact_for_leading_index(event_type: str, severity: str = "standard") -> float:
    """
    Leading Index issue_pressure 가중치 보정용.
    이벤트가 감지되면 issue_pressure에 이 값을 곱한다.

    Returns:
        가중치 승수 (1.0 = 변화 없음, 2.0 = 영향 2배)
    """
    if event_type not in EVENT_TYPES:
        return 1.0

    base = abs(EVENT_TYPES[event_type]["base_impact"])
    sev = SEVERITY_MULTIPLIER.get(severity, 1.0)

    # base_impact 기준으로 가중치 산출
    # 1.5%p 기준(정책) = 1.0, 5%p(토론 대형) = 2.0
    weight = 0.5 + (base * sev) / 3.0
    return round(max(0.5, min(2.5, weight)), 2)


# ═══════════════════════════════════════════════════════════════
# 전략 권고 생성
# ═══════════════════════════════════════════════════════════════

def _generate_recommendation(
    event_type: str,
    expected_impact: float,
    is_our_event: bool,
    severity: str,
) -> str:
    """이벤트에 대한 전략 권고."""
    if is_our_event:
        if event_type == "policy":
            if severity in ("major", "critical"):
                return "핵심 공약 — 맘카페/신도시 타겟 확산 + 지역 언론 동시 배포. 상대 반박 대비 팩트시트 준비."
            return "정책 발표 후 24시간 내 SNS 확산. 커뮤니티 반응 모니터링."
        elif event_type == "debate":
            return "토론 직후 하이라이트 클립 제작 → SNS 즉시 배포. 팩트체크 선제 대응. 맘카페 후기 유도."
        elif event_type == "endorsement":
            return "지지선언 후 조직 내부 동원 캠페인 연계. 해당 세대/지역 타겟 메시지."
        elif event_type == "visit":
            return "방문 후 사진/영상 → 지역 SNS 배포. 주민 증언 콘텐츠 제작."
        elif event_type == "sns_campaign":
            return "초기 24시간 집중 부스팅. 리액션 지수 모니터링 후 2차 콘텐츠 결정."
        return "이벤트 후 반응 모니터링. 긍정 반응 시 후속 콘텐츠 제작."
    else:
        # 상대 이벤트
        if abs(expected_impact) > 2.0:
            return f"고위험 상대 이벤트 (예상 {expected_impact:+.1f}%p). 즉시 대응 메시지 준비. 프레임 전환 필요."
        elif abs(expected_impact) > 1.0:
            return f"중위험 상대 이벤트 (예상 {expected_impact:+.1f}%p). 24시간 내 대응. 상대 약점 카운터."
        return f"저위험 상대 이벤트 (예상 {expected_impact:+.1f}%p). 모니터링 유지."


def _generate_counter_strategy(event_type: str) -> str:
    """상대 이벤트에 대한 대응 전략."""
    strategies = {
        "policy": "상대 공약의 재원/실현 가능성 의문 제기. 우리 대안 정책 즉시 발표.",
        "debate": "토론 패배 시 — 핵심 발언 팩트체크 + 우리 후보 발언 하이라이트 확산.",
        "scandal": "우리 스캔들 발생 시 — 신속 해명 + 프레임 전환 (정책 이슈로). 침묵은 인정으로 해석됨.",
        "endorsement": "상대 지지선언 시 — 우리 조직 지지 릴레이 기획. 규모로 압도.",
        "visit": "상대 방문 지역에 우리도 동시 방문 or 해당 지역 주민 불만 부각.",
        "sns_campaign": "상대 SNS 바이럴 시 — 팩트체크 + 패러디 콘텐츠. 과잉 대응 금지.",
        "gaffe": "상대 실언 시 — 클립 확산 + 반복 노출. 단, 과도한 네거티브는 역효과.",
        "poll_release": "불리한 여론조사 시 — '역전 가능' 프레임. 유리 시 — 편승효과 극대화.",
    }
    return strategies.get(event_type, "상대 이벤트 모니터링 후 24시간 내 대응 결정.")


# ═══════════════════════════════════════════════════════════════
# 이벤트 이력 관리 (학습용)
# ═══════════════════════════════════════════════════════════════

_event_history: list[EventImpactHistory] = []


def record_event_result(
    event_type: str,
    predicted_impact: float,
    actual_impact: float,
    description: str = "",
):
    """이벤트 결과 기록 (예측 vs 실제 비교 학습용)."""
    _event_history.append(EventImpactHistory(
        event_type=event_type,
        predicted_impact=predicted_impact,
        actual_impact=actual_impact,
        error=round(actual_impact - predicted_impact, 2),
        date=datetime.now().strftime("%Y-%m-%d"),
        description=description,
    ))


def get_event_accuracy() -> dict:
    """이벤트 유형별 예측 정확도 리포트."""
    if not _event_history:
        return {"total_events": 0, "message": "기록된 이벤트 없음"}

    by_type = {}
    for h in _event_history:
        if h.event_type not in by_type:
            by_type[h.event_type] = []
        by_type[h.event_type].append(h.error)

    result = {"total_events": len(_event_history), "by_type": {}}
    for etype, errors in by_type.items():
        avg_error = sum(errors) / len(errors)
        abs_errors = [abs(e) for e in errors]
        result["by_type"][etype] = {
            "count": len(errors),
            "avg_error": round(avg_error, 2),
            "avg_abs_error": round(sum(abs_errors) / len(abs_errors), 2),
            "accuracy_within_1pp": sum(1 for e in abs_errors if e < 1.0) / len(errors),
        }

    return result
