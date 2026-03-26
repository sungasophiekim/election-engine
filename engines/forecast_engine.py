"""
Engine — Forecast Layer (Gap 2: 지지율 변화 예측)
Leading Index + Lag Correlation + 과거 패턴으로 지지율 변화를 예측합니다.

Leading Index의 단순 힌트("상승 예상")를 대체하여:
1. lag_correlator의 회귀 계수로 정량 예측
2. 과거 유사 패턴 매칭으로 시나리오 생성
3. 신뢰 구간 (bear/base/bull) 제공
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ForecastScenario:
    """예측 시나리오"""
    label: str            # "bear" | "base" | "bull"
    gap_change: float     # 예상 지지율 격차 변화 (%p)
    our_change: float     # 예상 우리 지지율 변화 (%p)
    probability: float    # 시나리오 확률 (0~1)
    reasoning: str = ""


@dataclass
class SupportForecast:
    """지지율 변화 예측 결과"""
    # 핵심 예측
    predicted_gap_change: float = 0.0   # 예상 격차 변화 (%p, +면 유리)
    predicted_our_change: float = 0.0   # 예상 우리 지지율 변화
    forecast_horizon_days: int = 7      # 예측 기간 (일)
    confidence: str = "low"             # "high" | "medium" | "low"

    # 방향
    direction: str = "stable"   # "improving" | "stable" | "declining"
    direction_korean: str = ""

    # 시나리오
    scenarios: list[ForecastScenario] = field(default_factory=list)

    # 근거
    leading_index: float = 50.0
    lag_correlation: float = 0.0
    regression_slope: float = 0.0
    data_confidence: str = "low"    # lag_correlator의 confidence

    # 패턴 매칭
    similar_pattern: str = ""       # "2026-02 초반과 유사 — 당시 7일 후 +1.2%p"
    pattern_count: int = 0          # 매칭된 과거 패턴 수

    explanation: str = ""
    computed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "predicted_gap_change": round(self.predicted_gap_change, 2),
            "predicted_our_change": round(self.predicted_our_change, 2),
            "horizon_days": self.forecast_horizon_days,
            "confidence": self.confidence,
            "direction": self.direction,
            "direction_korean": self.direction_korean,
            "scenarios": [
                {
                    "label": s.label,
                    "gap_change": round(s.gap_change, 2),
                    "our_change": round(s.our_change, 2),
                    "probability": round(s.probability, 2),
                    "reasoning": s.reasoning,
                }
                for s in self.scenarios
            ],
            "leading_index": round(self.leading_index, 1),
            "lag_correlation": round(self.lag_correlation, 3),
            "similar_pattern": self.similar_pattern,
            "explanation": self.explanation,
        }


def compute_forecast(
    leading_index: float = 50.0,
    leading_direction: str = "stable",
    lag_analysis=None,
    current_gap: float = 0.0,
    current_our: float = 0.0,
    momentum: str = "stable",
    days_left: int = 90,
) -> SupportForecast:
    """
    Leading Index + Lag Correlation 기반 지지율 예측.

    Args:
        leading_index: 현재 선행지수 (0~100, 50=중립)
        leading_direction: "gaining" | "stable" | "losing"
        lag_analysis: LagAnalysis from lag_correlator
        current_gap: 현재 지지율 격차 (%p)
        current_our: 현재 우리 지지율
        momentum: polling momentum
        days_left: 선거까지 남은 일수
    """
    forecast = SupportForecast(
        leading_index=leading_index,
    )

    # lag_analysis가 없으면 기본 규칙 기반
    if lag_analysis:
        forecast.lag_correlation = lag_analysis.best_correlation
        forecast.regression_slope = lag_analysis.regression_slope
        forecast.data_confidence = lag_analysis.confidence
        forecast.forecast_horizon_days = lag_analysis.best_lag
    else:
        forecast.forecast_horizon_days = 7

    index_delta = leading_index - 50  # 중심화된 값

    # ── 방법 1: 회귀 기반 예측 (lag_analysis가 있고 confidence가 medium 이상) ──
    if lag_analysis and lag_analysis.confidence in ("high", "medium") and abs(lag_analysis.regression_slope) > 0.001:
        gap_change = lag_analysis.regression_slope * index_delta + lag_analysis.regression_intercept
        forecast.predicted_gap_change = round(gap_change, 2)
        forecast.predicted_our_change = round(gap_change * 0.6, 2)  # gap 변화의 ~60%가 우리측
        forecast.confidence = lag_analysis.confidence

    # ── 방법 2: 규칙 기반 예측 (데이터 부족 시) ──
    else:
        # Leading Index + momentum 조합 규칙
        if index_delta > 10 and leading_direction == "gaining":
            gap_change = index_delta * 0.05  # 보수적
            forecast.confidence = "low"
        elif index_delta < -10 and leading_direction == "losing":
            gap_change = index_delta * 0.05
            forecast.confidence = "low"
        elif momentum == "gaining":
            gap_change = 0.3
            forecast.confidence = "low"
        elif momentum == "losing":
            gap_change = -0.3
            forecast.confidence = "low"
        else:
            gap_change = 0.0
            forecast.confidence = "low"

        forecast.predicted_gap_change = round(gap_change, 2)
        forecast.predicted_our_change = round(gap_change * 0.6, 2)

    # ── 방향 결정 ──
    if forecast.predicted_gap_change > 0.3:
        forecast.direction = "improving"
        forecast.direction_korean = "상승 예상"
    elif forecast.predicted_gap_change < -0.3:
        forecast.direction = "declining"
        forecast.direction_korean = "하락 주의"
    else:
        forecast.direction = "stable"
        forecast.direction_korean = "변동 미미"

    # ── 시나리오 생성 ──
    base = forecast.predicted_gap_change

    # 선거 임박 시 변동폭 확대
    volatility = 1.0
    if days_left <= 14:
        volatility = 1.5
    elif days_left <= 30:
        volatility = 1.2

    bear = ForecastScenario(
        label="bear",
        gap_change=round(base - abs(base * 0.5 + 0.5) * volatility, 2),
        our_change=round((base - abs(base * 0.5 + 0.5) * volatility) * 0.6, 2),
        probability=0.25,
        reasoning="부정 이슈 확산 + 반등 실패 시나리오",
    )
    base_s = ForecastScenario(
        label="base",
        gap_change=round(base, 2),
        our_change=round(base * 0.6, 2),
        probability=0.50,
        reasoning="현재 추세 유지 시나리오",
    )
    bull = ForecastScenario(
        label="bull",
        gap_change=round(base + abs(base * 0.5 + 0.3) * volatility, 2),
        our_change=round((base + abs(base * 0.5 + 0.3) * volatility) * 0.6, 2),
        probability=0.25,
        reasoning="긍정 이슈 선점 + 상대 실점 시나리오",
    )
    forecast.scenarios = [bear, base_s, bull]

    # ── 과거 패턴 매칭 ──
    forecast.similar_pattern, forecast.pattern_count = _find_similar_pattern(
        index_delta, leading_direction, lag_analysis
    )

    # ── 설명문 ──
    horizon = forecast.forecast_horizon_days
    if forecast.confidence in ("high", "medium"):
        forecast.explanation = (
            f"선행지수 {leading_index:.0f} (lag {horizon}일, r={forecast.lag_correlation:.2f}) 기반 "
            f"향후 {horizon}일 격차 {forecast.predicted_gap_change:+.1f}%p 예상. "
            f"{forecast.direction_korean}."
        )
    else:
        forecast.explanation = (
            f"선행지수 {leading_index:.0f}, 데이터 부족으로 규칙 기반 추정. "
            f"향후 {horizon}일 격차 {forecast.predicted_gap_change:+.1f}%p 예상 (낮은 신뢰도)."
        )

    return forecast


def _find_similar_pattern(
    index_delta: float, direction: str, lag_analysis
) -> tuple[str, int]:
    """과거 index_history에서 유사한 패턴을 찾아 결과 참조"""
    from engines.lag_correlator import _index_history, _poll_history

    if len(_index_history) < 5 or len(_poll_history) < 3:
        return "", 0

    matches = []
    for i in range(len(_index_history) - 1):
        entry = _index_history[i]
        hist_delta = entry["index"] - 50
        hist_dir = entry["direction"]

        # 유사도: delta 방향 같고 크기 비슷 (±10 이내)
        if (hist_delta * index_delta > 0 and  # 같은 부호
                abs(hist_delta - index_delta) < 10):
            # 이 시점 이후 poll 변화 찾기
            for pc in _poll_history:
                if pc["date"] > entry["date"]:
                    gap_change = pc["gap"] - (_poll_history[max(0, _poll_history.index(pc) - 1)]["gap"] if _poll_history.index(pc) > 0 else pc["gap"])
                    matches.append({
                        "date": entry["date"],
                        "index": entry["index"],
                        "poll_change": gap_change,
                    })
                    break

    if not matches:
        return "", 0

    avg_change = sum(m["poll_change"] for m in matches) / len(matches)
    latest = matches[-1]
    return (
        f"{latest['date']} 유사 패턴 (지수 {latest['index']:.0f}) — "
        f"이후 평균 {avg_change:+.1f}%p 변화 ({len(matches)}건)",
        len(matches),
    )
