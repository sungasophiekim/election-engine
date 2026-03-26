"""
Engine V2 — Baseline-Aware Anomaly Detection
단순 6h/18h velocity를 대체하는 이력 기반 이상치 탐지.

문제:
  velocity = 6h건수 / 18h건수 는 야간/주말에 분모가 0에 가까워 폭발,
  기저 트래픽이 높은 상시 키워드(김경수 경남)는 항상 높게 나옴,
  진짜 이상 급등과 잡음을 구분하지 못함.

해결:
  1. 롤링 히스토리 기반 baseline (7일 이동평균 + 표준편차)
  2. z-score 기반 surprise_score
  3. day-over-day 변화율
  4. 3가지 시간 윈도우 표준화: 6h, 24h, 7d
"""
import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TimeWindowMetrics:
    """표준화된 시간 윈도우 메트릭"""
    window: str           # "6h" | "24h" | "7d"
    mention_count: int = 0
    story_count: int = 0  # 중복 제거 후
    negative_ratio: float = 0.0
    positive_ratio: float = 0.0


@dataclass
class AnomalyResult:
    """이상치 탐지 결과"""
    keyword: str

    # 현재값
    current_24h: int = 0
    current_6h: int = 0

    # 기저선 (7일 이동평균)
    baseline_24h_mean: float = 0.0
    baseline_24h_std: float = 0.0

    # 핵심 지표
    z_score: float = 0.0           # (현재 - 평균) / 표준편차
    surprise_score: float = 0.0    # 0~100 정규화된 놀람도
    day_over_day: float = 0.0      # 전일 대비 변화율 (%)
    velocity_6h: float = 0.0       # 6h / 기저선의 1/4 (6h 상당)

    # 판정
    is_anomaly: bool = False       # surprise ≥ 60
    is_surge: bool = False         # surprise ≥ 80
    anomaly_reason: str = ""

    # 표준화 윈도우 메트릭
    windows: dict = field(default_factory=dict)  # {"6h": TimeWindowMetrics, "24h": ..., "7d": ...}


class AnomalyDetector:
    """
    히스토리 기반 이상치 탐지기.

    사용법:
        detector = AnomalyDetector()
        result = detector.analyze(
            keyword="김경수 경남",
            current_24h=91,
            current_6h=45,
            history_7d=[12, 15, 18, 14, 20, 16, 22],  # 지난 7일 24h 건수
            yesterday_24h=22,
        )
        print(result.surprise_score)  # 0~100
        print(result.is_anomaly)      # True
    """

    # z-score → surprise_score 변환용 상수
    # z=0 → 0, z=1 → 30, z=2 → 60, z=3 → 85, z=4+ → 100
    Z_TO_SURPRISE = [
        (0.0, 0),
        (1.0, 30),
        (2.0, 60),
        (3.0, 85),
        (4.0, 100),
    ]

    def __init__(self, min_baseline_days: int = 3, anomaly_threshold: float = 60, surge_threshold: float = 80):
        self.min_baseline_days = min_baseline_days
        self.anomaly_threshold = anomaly_threshold
        self.surge_threshold = surge_threshold

    def _z_to_surprise(self, z: float) -> float:
        """z-score → 0~100 surprise_score 변환 (구간별 선형보간)"""
        z = abs(z)
        if z <= 0:
            return 0.0
        if z >= 4.0:
            return 100.0

        for i in range(len(self.Z_TO_SURPRISE) - 1):
            z_low, s_low = self.Z_TO_SURPRISE[i]
            z_high, s_high = self.Z_TO_SURPRISE[i + 1]
            if z_low <= z <= z_high:
                ratio = (z - z_low) / (z_high - z_low)
                return s_low + ratio * (s_high - s_low)

        return 100.0

    def analyze(
        self,
        keyword: str,
        current_24h: int,
        current_6h: int = 0,
        history_7d: list[int] = None,
        yesterday_24h: int = 0,
        windows: dict = None,
    ) -> AnomalyResult:
        """
        키워드 1개에 대한 이상치 분석.

        Args:
            keyword: 키워드
            current_24h: 최근 24시간 건수
            current_6h: 최근 6시간 건수
            history_7d: 지난 7일간 각 일별 24시간 건수 리스트
            yesterday_24h: 어제 24시간 건수
            windows: 표준 윈도우 메트릭 {"6h": TimeWindowMetrics, ...}
        """
        history_7d = history_7d or []
        result = AnomalyResult(
            keyword=keyword,
            current_24h=current_24h,
            current_6h=current_6h,
            windows=windows or {},
        )

        # ── 1. 기저선 계산 ──
        if len(history_7d) >= self.min_baseline_days:
            result.baseline_24h_mean = sum(history_7d) / len(history_7d)
            if len(history_7d) >= 2:
                variance = sum((x - result.baseline_24h_mean) ** 2 for x in history_7d) / len(history_7d)
                result.baseline_24h_std = math.sqrt(variance)
            else:
                result.baseline_24h_std = result.baseline_24h_mean * 0.3  # 데이터 부족 시 30% 추정

            # 표준편차가 0이면 (항상 같은 값) 평균의 10% 사용
            effective_std = result.baseline_24h_std if result.baseline_24h_std > 0 else max(result.baseline_24h_mean * 0.1, 1.0)

            # ── 2. z-score ──
            result.z_score = (current_24h - result.baseline_24h_mean) / effective_std

            # ── 3. surprise_score ──
            result.surprise_score = self._z_to_surprise(result.z_score)
        else:
            # 이력 부족: 절대값 기반 추정
            if current_24h >= 50:
                result.surprise_score = 70.0
            elif current_24h >= 20:
                result.surprise_score = 40.0
            else:
                result.surprise_score = 10.0

        # ── 4. day-over-day ──
        if yesterday_24h > 0:
            result.day_over_day = ((current_24h - yesterday_24h) / yesterday_24h) * 100
        elif current_24h > 0:
            result.day_over_day = 100.0  # 어제 0건 → 오늘 발생 = +100%

        # ── 5. 6h velocity (기저선 대비) ──
        baseline_6h = result.baseline_24h_mean / 4  # 24h 평균의 1/4 ≈ 6h 기대값
        if baseline_6h > 0:
            result.velocity_6h = current_6h / baseline_6h
        elif current_6h > 0:
            result.velocity_6h = 5.0  # 기저선 0인데 6h에 발생 → 강한 신호

        # ── 6. 판정 ──
        result.is_anomaly = result.surprise_score >= self.anomaly_threshold
        result.is_surge = result.surprise_score >= self.surge_threshold

        if result.is_surge:
            result.anomaly_reason = f"급등 (z={result.z_score:.1f}, 기저선 {result.baseline_24h_mean:.0f}건 대비 {current_24h}건)"
        elif result.is_anomaly:
            result.anomaly_reason = f"이상 증가 (z={result.z_score:.1f}, 전일대비 {result.day_over_day:+.0f}%)"
        elif result.day_over_day >= 100:
            result.anomaly_reason = f"전일 대비 급증 ({result.day_over_day:+.0f}%)"

        return result

    def analyze_batch(
        self,
        keyword_data: list[dict],
    ) -> list[AnomalyResult]:
        """
        여러 키워드 일괄 분석.

        Args:
            keyword_data: [
                {
                    "keyword": "김경수 경남",
                    "current_24h": 91,
                    "current_6h": 45,
                    "history_7d": [12, 15, 18, 14, 20, 16, 22],
                    "yesterday_24h": 22,
                },
                ...
            ]
        """
        return [
            self.analyze(
                keyword=d["keyword"],
                current_24h=d.get("current_24h", 0),
                current_6h=d.get("current_6h", 0),
                history_7d=d.get("history_7d", []),
                yesterday_24h=d.get("yesterday_24h", 0),
            )
            for d in keyword_data
        ]
