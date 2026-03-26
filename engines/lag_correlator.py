"""
Engine — Lag Correlator (Gap 1: Polling ↔ Leading Index)
선행지수와 여론조사 사이의 시차 상관관계를 계산합니다.

"Leading Index가 42로 떨어진 5일 후 지지율이 -1.2%p 하락했다"
→ lag=5일, correlation=0.78

이를 통해:
1. Leading Index가 여론조사를 실제로 선행하는지 검증
2. 최적 lag window 자동 탐색 (3, 5, 7, 14일)
3. 시차 상관 계수로 forecast 신뢰도 결정
"""
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta


# ── 인메모리 히스토리 ──────────────────────────────────────────
# leading_index_engine의 _leading_index_snapshots는 최신 1개만 보관
# 여기서는 시계열 전체를 보관
_index_history: list[dict] = []   # [{"date": "2026-03-20", "index": 58.2, "direction": "gaining"}]
_poll_history: list[dict] = []    # [{"date": "2026-03-15", "our": 36.4, "gap": 2.4}]

MAX_HISTORY = 180  # 최대 6개월


def record_index_snapshot(index_value: float, direction: str = "stable", date_str: str = ""):
    """Leading Index 결과를 시계열에 기록"""
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    # 같은 날짜 중복 방지 — 최신값으로 갱신
    for entry in _index_history:
        if entry["date"] == date_str:
            entry["index"] = index_value
            entry["direction"] = direction
            return
    _index_history.append({"date": date_str, "index": index_value, "direction": direction})
    _index_history.sort(key=lambda x: x["date"])
    if len(_index_history) > MAX_HISTORY:
        _index_history.pop(0)


def record_poll_snapshot(our_support: float, gap: float, date_str: str = ""):
    """여론조사 결과를 시계열에 기록"""
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    for entry in _poll_history:
        if entry["date"] == date_str:
            entry["our"] = our_support
            entry["gap"] = gap
            return
    _poll_history.append({"date": date_str, "our": our_support, "gap": gap})
    _poll_history.sort(key=lambda x: x["date"])
    if len(_poll_history) > MAX_HISTORY:
        _poll_history.pop(0)


def seed_from_polling_tracker(polling_tracker):
    """PollingTracker의 기존 데이터로 poll_history 초기화"""
    for p in polling_tracker.polls:
        opp_val = max(p.opponent_support.values()) if p.opponent_support else 0
        gap = p.our_support - opp_val
        record_poll_snapshot(p.our_support, gap, p.poll_date)


# ── 상관 계산 ──────────────────────────────────────────────────

@dataclass
class LagCorrelation:
    """특정 lag에서의 상관 결과"""
    lag_days: int
    correlation: float = 0.0        # -1 ~ +1 (피어슨)
    sample_count: int = 0           # 매칭된 데이터 쌍 수
    avg_index_delta: float = 0.0    # index가 50 초과 시 평균 poll 변화
    avg_poll_change: float = 0.0    # lag 이후 실제 poll 변화
    is_significant: bool = False    # sample >= 3 and |corr| >= 0.4


@dataclass
class LagAnalysis:
    """전체 래그 분석 결과"""
    best_lag: int = 7                    # 최적 lag (일)
    best_correlation: float = 0.0        # 최적 상관 계수
    lag_results: list[LagCorrelation] = field(default_factory=list)
    data_points: int = 0                 # 사용 가능한 데이터 수
    confidence: str = "low"              # "high" (≥5 pairs, |r|≥0.6) / "medium" / "low"
    explanation: str = ""

    # Forecast에 사용할 회귀 계수
    regression_slope: float = 0.0        # index 1pt 변화 → poll 변화 %p
    regression_intercept: float = 0.0

    def to_dict(self) -> dict:
        return {
            "best_lag": self.best_lag,
            "best_correlation": round(self.best_correlation, 3),
            "confidence": self.confidence,
            "explanation": self.explanation,
            "data_points": self.data_points,
            "regression_slope": round(self.regression_slope, 4),
            "regression_intercept": round(self.regression_intercept, 4),
            "lag_results": [
                {
                    "lag": lr.lag_days,
                    "corr": round(lr.correlation, 3),
                    "samples": lr.sample_count,
                    "significant": lr.is_significant,
                }
                for lr in self.lag_results
            ],
        }


def _pearson(xs: list[float], ys: list[float]) -> float:
    """피어슨 상관 계수 (scipy 없이 수동 계산)"""
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    std_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    std_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if std_x == 0 or std_y == 0:
        return 0.0
    return cov / (std_x * std_y)


def _linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """단순 선형 회귀: slope, intercept"""
    n = len(xs)
    if n < 2:
        return 0.0, 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    if ss_xx == 0:
        return 0.0, mean_y
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x
    return slope, intercept


def compute_lag_correlation(
    lag_windows: list[int] = None,
) -> LagAnalysis:
    """
    Leading Index 시계열과 여론조사 시계열 사이의
    시차 상관관계를 여러 lag window에서 계산.

    Args:
        lag_windows: 테스트할 래그 일수 목록 (기본 [3, 5, 7, 10, 14])

    Returns:
        LagAnalysis with best_lag, correlations, regression coefficients
    """
    lag_windows = lag_windows or [3, 5, 7, 10, 14]

    analysis = LagAnalysis()
    analysis.data_points = min(len(_index_history), len(_poll_history))

    if len(_index_history) < 2 or len(_poll_history) < 2:
        analysis.explanation = "데이터 부족 — 선행지수 또는 여론조사 이력이 2개 미만"
        return analysis

    # 날짜를 기준 일수로 변환
    def _to_days(date_str: str) -> int:
        return (datetime.strptime(date_str, "%Y-%m-%d") - datetime(2025, 1, 1)).days

    # Poll 변화율 계산 (이전 poll 대비)
    poll_changes: list[dict] = []  # {"date": str, "days": int, "change": float}
    for i in range(1, len(_poll_history)):
        prev = _poll_history[i - 1]
        curr = _poll_history[i]
        change = curr["gap"] - prev["gap"]  # gap 변화 사용 (순수 지지율보다 노이즈 적음)
        poll_changes.append({
            "date": curr["date"],
            "days": _to_days(curr["date"]),
            "change": change,
        })

    if not poll_changes:
        analysis.explanation = "여론조사 변화 데이터 부족"
        return analysis

    # 각 lag window에서 상관 계산
    best_corr = 0.0
    best_lag = 7
    best_pairs_x: list[float] = []
    best_pairs_y: list[float] = []

    for lag in lag_windows:
        # index_value(date T) → poll_change(date T+lag)
        xs: list[float] = []  # index values
        ys: list[float] = []  # poll changes at T+lag

        for idx_entry in _index_history:
            idx_days = _to_days(idx_entry["date"])
            idx_val = idx_entry["index"] - 50  # 중심화 (50=중립)

            # lag일 후 poll 변화 찾기 (±2일 허용)
            target_days = idx_days + lag
            closest = None
            closest_dist = 999
            for pc in poll_changes:
                dist = abs(pc["days"] - target_days)
                if dist < closest_dist and dist <= 2:
                    closest_dist = dist
                    closest = pc

            if closest:
                xs.append(idx_val)
                ys.append(closest["change"])

        corr = _pearson(xs, ys)
        is_sig = len(xs) >= 3 and abs(corr) >= 0.4

        lr = LagCorrelation(
            lag_days=lag,
            correlation=corr,
            sample_count=len(xs),
            is_significant=is_sig,
        )
        if xs:
            lr.avg_index_delta = sum(xs) / len(xs)
            lr.avg_poll_change = sum(ys) / len(ys)

        analysis.lag_results.append(lr)

        if abs(corr) > abs(best_corr) and len(xs) >= 2:
            best_corr = corr
            best_lag = lag
            best_pairs_x = xs
            best_pairs_y = ys

    analysis.best_lag = best_lag
    analysis.best_correlation = best_corr

    # 회귀 계수 (best lag 기준)
    if best_pairs_x:
        slope, intercept = _linear_regression(best_pairs_x, best_pairs_y)
        analysis.regression_slope = slope
        analysis.regression_intercept = intercept

    # 신뢰도 판정
    sig_count = sum(1 for lr in analysis.lag_results if lr.is_significant)
    if sig_count >= 2 and abs(best_corr) >= 0.6:
        analysis.confidence = "high"
    elif sig_count >= 1 and abs(best_corr) >= 0.4:
        analysis.confidence = "medium"
    else:
        analysis.confidence = "low"

    # 설명문 생성
    if analysis.confidence == "low":
        analysis.explanation = f"래그 상관 분석 결과 유의미한 패턴 미발견 (최고 r={best_corr:.2f}, lag={best_lag}일, 데이터 {analysis.data_points}건)"
    else:
        dir_text = "양의" if best_corr > 0 else "음의"
        analysis.explanation = (
            f"선행지수는 여론조사를 약 {best_lag}일 선행 ({dir_text} 상관 r={best_corr:.2f}). "
            f"지수 1pt 변화 → 약 {abs(analysis.regression_slope):.3f}%p 지지율 변화 예상."
        )

    return analysis


def get_history_summary() -> dict:
    """대시보드용 히스토리 요약"""
    return {
        "index_history": _index_history[-30:],  # 최근 30개
        "poll_history": _poll_history[-30:],
        "index_count": len(_index_history),
        "poll_count": len(_poll_history),
    }
