"""
Index Tracker — 전체 인덱스 일일 측정·저장·추세·액션임팩트·학습
"우리가 만들어낸 지표의 의존도를 높이는 것이 목표"

원칙:
  1. 지표는 데이터 퀄리티와 근거가 충분해야 하고 설명되어야 함
  2. 지표는 처음 보는 사람도 이해할 수 있어야 함
  3. 지표는 매일 측정·저장되고 차트로 추세를 볼 수 있어야 함
  4. 오늘의 액션이 지표에 어떤 영향을 미쳤는지 볼 수 있어야 함
  5. AI 에이전트가 지속 학습하여 예측 인덱스를 정교화해야 함

구조:
  DailySnapshot — 하루 전체 인덱스 값 + 메타
  ActionImpact — 행동 → 인덱스 변화 추적
  LearningEntry — 예측 vs 실제 오차 기록
  PredictionRecord — 예측 인덱스 → 여론조사 결과 비교

저장:
  JSON 파일 기반 (data/index_history/*.json)
  → 추후 DB 마이그레이션 가능한 구조
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# 저장 경로
# ═══════════════════════════════════════════════════════════════

_BASE_DIR = Path(os.path.dirname(os.path.dirname(__file__)))
_DATA_DIR = _BASE_DIR / "data" / "index_history"
_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# 인덱스 정의 — 설명 + 해석 가이드
# ═══════════════════════════════════════════════════════════════

INDEX_DEFINITIONS = {
    "leading_index": {
        "name": "선행지수 (Leading Index)",
        "range": "0~100 (50=중립)",
        "description": "여론조사보다 앞서 유권자 이동을 감지하는 종합 선행지표. 9개 컴포넌트의 가중 합산.",
        "how_to_read": "50 이상이면 우리에게 유리한 이동 감지. 57 이상이면 gaining, 43 이하면 losing.",
        "components": "issue_pressure(15%), anomaly(10%), reaction(15%), social(10%), poll(20%), issue_idx(12%), reaction_idx(13%), honeymoon(8%), economy(5%)",
        "update_freq": "전략 갱신 시 (1~3회/일)",
    },
    "issue_index": {
        "name": "이슈 지수 (Issue Index)",
        "range": "0~100",
        "description": "이슈가 '얼마나 터졌는가'를 측정. 뉴스 볼륨, 미디어 티어, 확산 속도, 후보 연결, 채널 다양성.",
        "how_to_read": "80+ EXPLOSIVE, 60+ HOT, 40+ ACTIVE, 20+ LOW. 키워드별 개별 산출.",
        "components": "news_volume(25), media_tier(20), spread_velocity(30), candidate_linkage(15), channel_diversity(10)",
        "update_freq": "전략 갱신 시",
    },
    "reaction_index": {
        "name": "반응 지수 (Reaction Index)",
        "range": "0~100",
        "description": "사람들이 '어떻게 반응하는가'. 커뮤니티 공명, 콘텐츠 생산, 감성 방향, 검색 반응, 유튜브+뉴스 댓글.",
        "how_to_read": "75+ VIRAL, 50+ ENGAGED, 25+ RIPPLE, 이하 SILENT. direction: positive/negative/mixed.",
        "components": "community(25), content(20), sentiment(20), search(15), youtube+comment(20)",
        "update_freq": "전략 갱신 시",
    },
    "segment_coverage": {
        "name": "세그먼트 커버리지",
        "range": "0~100",
        "description": "이슈가 핵심 타겟 유권자에게 얼마나 도달했는가. 세대별 가중 평균.",
        "how_to_read": "70+ EXCELLENT, 50+ GOOD, 30+ PARTIAL, 이하 WEAK. gap_segment에 주목.",
        "components": "20대(10%), 30대(20%), 40대(25%), 50대(25%), 60대(12%), 70+(5%)",
        "update_freq": "전략 갱신 시",
    },
    "attribution_confidence": {
        "name": "귀인 신뢰도 (Attribution Confidence)",
        "range": "0~1.0",
        "description": "우리 행동이 여론 반응을 만들었는지 연결 신뢰도. 높을수록 '우리 행동 → 여론 변화' 인과 확실.",
        "how_to_read": "0.6+ 강한 귀인, 0.4+ 보통, 0.2+ 약한 귀인, 이하 귀인 불가.",
        "components": "keyword_match(30%), theme_match(15%), region_match(15%), reaction_depth(25%), hint(15%) × time_decay",
        "update_freq": "전략 갱신 시",
    },
    "support_forecast": {
        "name": "지지율 예측",
        "range": "0~100%",
        "description": "현재 시그널 기반 예상 지지율. 여론조사와 비교하여 오차를 줄이는 것이 목표.",
        "how_to_read": "여론조사 결과와 비교. 오차 2%p 이내 = 정확, 5%p 이상 = 모델 재검토.",
        "components": "base_forecast(polling), leading_index, turnout_model, event_impact",
        "update_freq": "일 1회",
    },
    "turnout_prediction": {
        "name": "투표율 예측",
        "range": "김경수 %:박완수 %",
        "description": "세대별 인구×투표율×지지율 교차 모델. 여론조사 38:38이 실제 42:58이 되는 이유.",
        "how_to_read": "gap이 양수면 김경수 유리, 음수면 박완수 유리. 시나리오별 비교.",
        "components": "age_distribution × turnout_rate × support_rate + 실시간 보정",
        "update_freq": "일 1회",
    },
}


# ═══════════════════════════════════════════════════════════════
# 데이터 구조
# ═══════════════════════════════════════════════════════════════

@dataclass
class DailySnapshot:
    """하루 전체 인덱스 스냅샷"""
    date: str                          # "2026-03-21"
    timestamp: str = ""                # ISO format

    # 핵심 인덱스 값
    leading_index: float = 50.0        # 0~100
    leading_direction: str = "stable"

    issue_index_avg: float = 0.0       # 키워드 평균
    issue_top_keyword: str = ""
    issue_top_score: float = 0.0

    reaction_index_avg: float = 0.0
    reaction_top_keyword: str = ""
    reaction_top_score: float = 0.0

    segment_coverage_avg: float = 0.0

    attribution_confidence_avg: float = 0.0
    attribution_count: int = 0         # 귀인 성공 건수

    support_forecast_kim: float = 0.0  # 김경수 예상 %
    support_forecast_park: float = 0.0 # 박완수 예상 %
    support_forecast_gap: float = 0.0  # 격차

    turnout_predicted_gap: float = 0.0 # 투표율 모델 격차

    # 상대후보 인덱스 (비교용)
    opp_issue_avg: float = 0.0         # 상대 키워드 Issue Index 평균
    opp_reaction_avg: float = 0.0      # 상대 키워드 Reaction Index 평균

    # 여론조사 실제값 (있으면)
    poll_actual_kim: float = 0.0
    poll_actual_park: float = 0.0
    poll_source: str = ""

    # 메타
    actions_count: int = 0             # 오늘의 행동 수
    data_quality: str = "low"          # low | medium | high

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ActionImpact:
    """행동 → 인덱스 변화 추적"""
    date: str
    action_description: str
    action_type: str                   # policy | visit | sns_post | debate | ...

    # 행동 전후 인덱스 변화
    leading_before: float = 50.0
    leading_after: float = 50.0
    leading_delta: float = 0.0

    issue_before: float = 0.0
    issue_after: float = 0.0
    issue_delta: float = 0.0

    reaction_before: float = 0.0
    reaction_after: float = 0.0
    reaction_delta: float = 0.0

    # 귀인
    attribution_confidence: float = 0.0
    attributed_keywords: list = field(default_factory=list)

    # 평가
    impact_grade: str = ""             # HIGH | MEDIUM | LOW | NONE
    recommendation: str = ""           # 효과 없으면 전략 재검토 제안

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LearningEntry:
    """예측 vs 실제 오차 — AI 학습용"""
    date: str
    index_name: str                    # "leading_index" | "support_forecast"

    predicted_value: float = 0.0
    actual_value: float = 0.0          # 여론조사 실제값
    error: float = 0.0                 # actual - predicted
    abs_error: float = 0.0

    # 컨텍스트 (오차 원인 분석용)
    context: str = ""                  # "대통령효과 하락 미반영" 등
    correction_applied: bool = False   # AI가 보정 적용했는지

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════
# 저장/조회
# ═══════════════════════════════════════════════════════════════

def _snapshot_path(dt: str) -> Path:
    return _DATA_DIR / f"snapshot_{dt}.json"

def _actions_path(dt: str) -> Path:
    return _DATA_DIR / f"actions_{dt}.json"

def _learning_path() -> Path:
    return _DATA_DIR / "learning_log.json"


def save_daily_snapshot(snapshot: DailySnapshot):
    """일일 스냅샷 저장."""
    snapshot.timestamp = datetime.now().isoformat()
    path = _snapshot_path(snapshot.date)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot.to_dict(), f, ensure_ascii=False, indent=2)


def load_daily_snapshot(dt: str) -> DailySnapshot | None:
    """특정 날짜 스냅샷 로드."""
    path = _snapshot_path(dt)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return DailySnapshot(**{k: v for k, v in data.items() if k in DailySnapshot.__dataclass_fields__})


def get_snapshot_trend(days: int = 30) -> list[dict]:
    """최근 N일간 스냅샷 추세."""
    snapshots = []
    files = sorted(_DATA_DIR.glob("snapshot_*.json"), reverse=True)[:days]
    for fp in reversed(files):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            snapshots.append(data)
        except Exception:
            continue
    return snapshots


def save_action_impact(impact: ActionImpact):
    """액션 임팩트 기록."""
    path = _actions_path(impact.date)
    existing = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    existing.append(impact.to_dict())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def get_action_impacts(dt: str) -> list[dict]:
    """특정 날짜의 액션 임팩트 목록."""
    path = _actions_path(dt)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_learning_entry(entry: LearningEntry):
    """학습 엔트리 추가."""
    path = _learning_path()
    existing = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    existing.append(entry.to_dict())
    # 최근 500건만 유지
    if len(existing) > 500:
        existing = existing[-500:]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def get_learning_log(limit: int = 100) -> list[dict]:
    """학습 로그 조회."""
    path = _learning_path()
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data[-limit:]


# ═══════════════════════════════════════════════════════════════
# 액션 임팩트 분석
# ═══════════════════════════════════════════════════════════════

def analyze_action_impact(
    action_description: str,
    action_type: str,
    leading_before: float,
    leading_after: float,
    issue_before: float = 0.0,
    issue_after: float = 0.0,
    reaction_before: float = 0.0,
    reaction_after: float = 0.0,
    attribution_confidence: float = 0.0,
    attributed_keywords: list = None,
) -> ActionImpact:
    """
    행동의 인덱스 임팩트 분석 + 효과 없으면 전략 재검토 제안.

    원칙 4: "오늘의 액션이 지표에 어떤 영향을 미쳤는지 볼 수 있어야 하고,
    영향을 미치지 않았다면 전략을 재검토하고 빠르게 지표 개선을 위한 활동을 제안"
    """
    today = date.today().isoformat()
    attributed_keywords = attributed_keywords or []

    leading_delta = round(leading_after - leading_before, 1)
    issue_delta = round(issue_after - issue_before, 1)
    reaction_delta = round(reaction_after - reaction_before, 1)

    # 임팩트 등급
    total_delta = abs(leading_delta) + abs(issue_delta) * 0.3 + abs(reaction_delta) * 0.3
    if total_delta >= 5:
        grade = "HIGH"
    elif total_delta >= 2:
        grade = "MEDIUM"
    elif total_delta >= 0.5:
        grade = "LOW"
    else:
        grade = "NONE"

    # 전략 재검토 제안 (효과 없을 때)
    recommendation = ""
    if grade == "NONE":
        if action_type in ("policy", "press"):
            recommendation = (
                f"'{action_description[:30]}' 정책 발표가 지표에 영향 없음. "
                "가능한 원인: ① 미디어 노출 부족 ② 타겟 세그먼트 미도달 ③ 경쟁 이슈에 묻힘. "
                "제안: 맘카페/지역 언론 타겟 2차 확산, 또는 프레임 전환."
            )
        elif action_type in ("visit",):
            recommendation = (
                f"'{action_description[:30]}' 현장 방문이 지표에 영향 없음. "
                "가능한 원인: ① 지역 한정 ② 미디어 미보도. "
                "제안: 방문 콘텐츠 SNS 확산, 주민 증언 영상 제작."
            )
        elif action_type in ("sns_post",):
            recommendation = (
                f"'{action_description[:30]}' SNS 게시 반응 없음. "
                "가능한 원인: ① 도달 부족 ② 메시지 미스매치. "
                "제안: 타겟 세그먼트 재설정, A/B 메시지 테스트."
            )
        else:
            recommendation = (
                f"'{action_description[:30]}' 지표 변화 없음. "
                "전략 재검토 필요 — 타이밍, 채널, 메시지 중 하나를 변경."
            )
    elif grade == "LOW":
        recommendation = f"미약한 효과({leading_delta:+.1f}). 후속 액션으로 모멘텀 유지 필요."
    elif grade == "HIGH":
        recommendation = f"강한 효과({leading_delta:+.1f}). 이 방향의 후속 전략 강화."

    impact = ActionImpact(
        date=today,
        action_description=action_description,
        action_type=action_type,
        leading_before=leading_before,
        leading_after=leading_after,
        leading_delta=leading_delta,
        issue_before=issue_before,
        issue_after=issue_after,
        issue_delta=issue_delta,
        reaction_before=reaction_before,
        reaction_after=reaction_after,
        reaction_delta=reaction_delta,
        attribution_confidence=attribution_confidence,
        attributed_keywords=attributed_keywords,
        impact_grade=grade,
        recommendation=recommendation,
    )

    # 자동 저장
    save_action_impact(impact)

    return impact


# ═══════════════════════════════════════════════════════════════
# 학습 — 예측 vs 실제 비교
# ═══════════════════════════════════════════════════════════════

def record_prediction_vs_actual(
    index_name: str,
    predicted: float,
    actual: float,
    context: str = "",
):
    """
    예측값과 실제값(여론조사) 비교 기록.
    원칙 5: "여론조사 결과와 오차범위를 줄이는 것이 목표"
    """
    error = round(actual - predicted, 2)
    entry = LearningEntry(
        date=date.today().isoformat(),
        index_name=index_name,
        predicted_value=predicted,
        actual_value=actual,
        error=error,
        abs_error=round(abs(error), 2),
        context=context,
    )
    save_learning_entry(entry)
    return entry


def get_prediction_accuracy(index_name: str = "support_forecast") -> dict:
    """
    예측 정확도 리포트.
    원칙 5: "여론조사와 경쟁해서 더 정확한 인덱스를 만드는 것이 목표"
    """
    log = get_learning_log(limit=500)
    entries = [e for e in log if e.get("index_name") == index_name]

    if not entries:
        return {
            "index_name": index_name,
            "total_comparisons": 0,
            "message": "아직 비교 데이터 없음. 여론조사 결과 입력 시 학습 시작.",
        }

    errors = [e["abs_error"] for e in entries]
    recent = entries[-10:] if len(entries) >= 10 else entries
    recent_errors = [e["abs_error"] for e in recent]

    return {
        "index_name": index_name,
        "total_comparisons": len(entries),
        "avg_error": round(sum(errors) / len(errors), 2),
        "recent_avg_error": round(sum(recent_errors) / len(recent_errors), 2),
        "best_error": round(min(errors), 2),
        "worst_error": round(max(errors), 2),
        "within_2pp": round(sum(1 for e in errors if e <= 2.0) / len(errors), 2),
        "within_5pp": round(sum(1 for e in errors if e <= 5.0) / len(errors), 2),
        "trend": "improving" if len(entries) >= 5 and sum(recent_errors) / len(recent_errors) < sum(errors) / len(errors) else "stable",
        "latest": entries[-1] if entries else None,
    }


# ═══════════════════════════════════════════════════════════════
# 일일 리포트 생성
# ═══════════════════════════════════════════════════════════════

def generate_daily_summary(dt: str = "") -> dict:
    """
    일일 인덱스 요약 — 대시보드 + 리포트용.
    원칙 2: "처음 보는 사람도 이해할 수 있어야 함"
    """
    if not dt:
        dt = date.today().isoformat()

    snapshot = load_daily_snapshot(dt)
    actions = get_action_impacts(dt)
    accuracy = get_prediction_accuracy()

    # 전일 비교
    from datetime import timedelta
    yesterday = (date.fromisoformat(dt) - timedelta(days=1)).isoformat()
    prev = load_daily_snapshot(yesterday)

    leading_delta = 0.0
    if snapshot and prev:
        leading_delta = snapshot.leading_index - prev.leading_index

    # 액션 임팩트 요약
    high_impact = [a for a in actions if a.get("impact_grade") == "HIGH"]
    no_impact = [a for a in actions if a.get("impact_grade") == "NONE"]

    return {
        "date": dt,
        "snapshot": snapshot.to_dict() if snapshot else None,
        "vs_yesterday": {
            "leading_delta": round(leading_delta, 1),
            "direction": "상승" if leading_delta > 1 else "하락" if leading_delta < -1 else "보합",
        },
        "actions_summary": {
            "total": len(actions),
            "high_impact": len(high_impact),
            "no_impact": len(no_impact),
            "top_action": high_impact[0] if high_impact else None,
            "failed_actions": no_impact[:3],  # 효과 없는 액션 → 전략 재검토
        },
        "prediction_accuracy": accuracy,
        "index_definitions": INDEX_DEFINITIONS,
    }
