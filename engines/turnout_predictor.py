"""
Turnout Predictor — 투표율 예측 + 후보별 예상 득표수 산출
"어느 세대 투표율을 올려야 우리가 이기는가"를 정량화.

모델:
  예상 득표 = Σ(지역) Σ(세대) [유권자수 × 투표율추정 × 지지율추정]

입력 데이터:
  - 세대별 인구 비중 (승리 전략 보고서 표10)
  - 7대/8대 실제 득표율 (config)
  - 현재 여론조사 (polling_tracker)
  - 실시간 보정 시그널 (Leading Index components)

출처:
  - 제9대 경남도지사 선거 승리 전략 보고서 (260315)
  - 한국갤럽 대통령 직무수행 평가
  - KCI 지방선거 투표율 결정요인 연구
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# 경남 세대별 기초 데이터
# tenant_config.age_cohorts 에서 로드. 없으면 하드코딩 폴백.
# ═══════════════════════════════════════════════════════════════

def _load_cohorts() -> tuple[float, dict, dict, dict, dict]:
    """config → (TOTAL_VOTERS, AGE_DISTRIBUTION, BASE_TURNOUT, BASE_SUPPORT_KIM, BASE_SUPPORT_PARK)"""
    try:
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG as cfg
        cohorts = cfg.age_cohorts
        if cohorts:
            total = round(sum(c["voters"] for c in cohorts.values()), 1)
            dist = {k: {"pct": c["pct"], "label": c["label"], "voters": c["voters"]}
                    for k, c in cohorts.items()}
            turnout = {k: c["turnout"] for k, c in cohorts.items()}
            support_kim = {k: c["kim_support"] for k, c in cohorts.items()}
            support_park = {k: c.get("park_support", 100 - c["kim_support"])
                           for k, c in cohorts.items()}
            return total, dist, turnout, support_kim, support_park
    except Exception:
        pass

    # 폴백 — config 로드 실패 시
    dist = {
        "20s": {"pct": 10.0, "label": "20대", "voters": 26.3},
        "30s": {"pct": 11.6, "label": "30대", "voters": 30.5},
        "40s": {"pct": 16.2, "label": "40대", "voters": 42.6},
        "50s": {"pct": 20.9, "label": "50대", "voters": 55.0},
        "60s": {"pct": 20.9, "label": "60대", "voters": 55.0},
        "70+": {"pct": 18.5, "label": "70대+", "voters": 48.7},
    }
    # 7대 지선(2018) 전국 연령별 실제 투표율 (중앙선관위)
    turnout = {"20s": 52.0, "30s": 54.3, "40s": 58.6, "50s": 63.3, "60s": 72.5, "70+": 65.0}
    # NESDC 양자대결 연령별 3개 조사 평균 (리얼미터 26.01 + KNN 26.03 + 여론조사꽃 26.03)
    # kim_support: raw 응답률 (무응답 포함 전체 기준)
    support_kim = {"20s": 29.0, "30s": 42.0, "40s": 61.0, "50s": 53.0, "60s": 37.0, "70+": 27.0}
    # park_support: raw 응답률 (무응답 포함 전체 기준)
    support_park = {"20s": 39.0, "30s": 36.0, "40s": 23.0, "50s": 31.0, "60s": 49.0, "70+": 58.0}
    return 263.0, dist, turnout, support_kim, support_park

TOTAL_VOTERS, AGE_DISTRIBUTION, BASE_TURNOUT, BASE_SUPPORT_KIM, BASE_SUPPORT_PARK = _load_cohorts()


# ═══════════════════════════════════════════════════════════════
# 데이터 구조
# ═══════════════════════════════════════════════════════════════

@dataclass
class AgeGroupResult:
    """세대별 예측 결과"""
    age_group: str
    label: str
    voters: float          # 유권자 수 (만명)
    turnout_pct: float     # 투표율 (%)
    turnout_voters: float  # 투표자 수 (만명)
    kim_support: float     # 김경수 지지율 (%)
    park_support: float    # 박완수 지지율 (%)
    kim_votes: float       # 김경수 예상 득표 (만명)
    park_votes: float      # 박완수 예상 득표 (만명)

    def to_dict(self) -> dict:
        return {
            "age": self.age_group, "label": self.label,
            "voters": round(self.voters, 1),
            "turnout_pct": round(self.turnout_pct, 1),
            "turnout_voters": round(self.turnout_voters, 1),
            "kim_support": round(self.kim_support, 1),
            "park_support": round(self.park_support, 1),
            "kim_votes": round(self.kim_votes, 2),
            "park_votes": round(self.park_votes, 2),
        }


@dataclass
class TurnoutScenario:
    """투표율 시나리오 1개"""
    name: str
    description: str
    total_turnout: float       # 전체 투표율 (%)
    total_voters: float        # 총 투표자 (만명)
    kim_total: float           # 김경수 총 득표 (만명)
    park_total: float          # 박완수 총 득표 (만명)
    kim_pct: float             # 김경수 득표율 (%)
    park_pct: float            # 박완수 득표율 (%)
    gap: float                 # 격차 (%p, +면 김경수 유리)
    result: str                # "김경수 승" | "박완수 승" | "초박빙"
    age_results: list[AgeGroupResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "total_turnout": round(self.total_turnout, 1),
            "kim_pct": round(self.kim_pct, 1),
            "park_pct": round(self.park_pct, 1),
            "gap": round(self.gap, 1),
            "result": self.result,
            "kim_votes": round(self.kim_total, 2),
            "park_votes": round(self.park_total, 2),
            "by_age": [a.to_dict() for a in self.age_results],
        }


@dataclass
class TurnoutPrediction:
    """투표율 예측 전체"""
    base_scenario: TurnoutScenario = None
    scenarios: list[TurnoutScenario] = field(default_factory=list)
    sensitivity: list[dict] = field(default_factory=list)  # 민감도 분석
    correction: dict = field(default_factory=dict)  # 20% 보정모델 결과
    strategic_insight: str = ""
    computed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "base": self.base_scenario.to_dict() if self.base_scenario else None,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "sensitivity": self.sensitivity,
            "correction": self.correction,
            "strategic_insight": self.strategic_insight,
            "computed_at": self.computed_at,
        }


# ═══════════════════════════════════════════════════════════════
# 핵심 계산
# ═══════════════════════════════════════════════════════════════

def _compute_scenario(
    name: str,
    description: str,
    turnout_adjustments: dict = None,   # {"20s": +5, "30s": +3, ...}
    support_adjustments: dict = None,   # {"20s": +2, "30s": +1, ...}
    global_turnout_adj: float = 0.0,    # 전체 투표율 보정
) -> TurnoutScenario:
    """시나리오 1개 계산.

    지지율 모델:
      - kim_raw, park_raw: NESDC 양자대결 연령별 raw 응답률 (무응답 포함)
      - undecided = 100 - kim_raw - park_raw (무응답/기타/없음)
      - 무응답자 중 실제 투표하는 비율: 50% 가정
      - 무응답 투표자의 배분: 김:박 = 50:50 균등 배분
      → 최종 지지율 = (raw + 무응답투표 × 0.5) / (raw합 + 무응답투표)
    """
    turnout_adj = turnout_adjustments or {}
    support_adj = support_adjustments or {}

    age_results = []
    total_voters_sum = 0.0
    kim_total = 0.0
    park_total = 0.0

    for age_key, age_data in AGE_DISTRIBUTION.items():
        voters = age_data["voters"]  # 만명

        # 투표율 = 기저 + 세대별 보정 + 전체 보정
        turnout = BASE_TURNOUT[age_key] + turnout_adj.get(age_key, 0) + global_turnout_adj
        turnout = max(20, min(90, turnout))  # 20~90% 범위

        turnout_count = voters * turnout / 100  # 투표자 수 (만명)

        # 후보 지지율 — raw 응답률 기반 (무응답 별도 처리)
        kim_raw = BASE_SUPPORT_KIM[age_key] + support_adj.get(age_key, 0)
        kim_raw = max(5, min(85, kim_raw))
        park_raw = BASE_SUPPORT_PARK[age_key]  # 보정은 김경수에만 적용
        park_raw = max(5, min(85, park_raw))

        undecided = max(0, 100 - kim_raw - park_raw)

        # 무응답 처리: 무응답자 중 50%가 실제 투표, 그 중 50:50 균등 배분
        undecided_vote_rate = 0.5   # 무응답자 중 투표 참여율
        undecided_kim_share = 0.5   # 무응답 투표자 중 김경수 비율
        undecided_voting = undecided * undecided_vote_rate
        kim_from_undecided = undecided_voting * undecided_kim_share
        park_from_undecided = undecided_voting * (1 - undecided_kim_share)

        # 최종 유효 지지율 (투표하는 사람 중 비율)
        effective_total = kim_raw + park_raw + undecided_voting
        kim_sup = (kim_raw + kim_from_undecided) / effective_total * 100 if effective_total > 0 else 50
        park_sup = (park_raw + park_from_undecided) / effective_total * 100 if effective_total > 0 else 50

        kim_v = turnout_count * kim_sup / 100
        park_v = turnout_count * park_sup / 100

        age_results.append(AgeGroupResult(
            age_group=age_key, label=age_data["label"],
            voters=voters, turnout_pct=turnout, turnout_voters=turnout_count,
            kim_support=round(kim_sup, 1), park_support=round(park_sup, 1),
            kim_votes=kim_v, park_votes=park_v,
        ))

        total_voters_sum += turnout_count
        kim_total += kim_v
        park_total += park_v

    total_votes = kim_total + park_total
    kim_pct = (kim_total / total_votes * 100) if total_votes > 0 else 0
    park_pct = (park_total / total_votes * 100) if total_votes > 0 else 0
    gap = kim_pct - park_pct
    total_turnout = (total_voters_sum / TOTAL_VOTERS * 100)

    if gap > 1:
        result = "김경수 승"
    elif gap < -1:
        result = "박완수 승"
    else:
        result = "초박빙"

    return TurnoutScenario(
        name=name, description=description,
        total_turnout=total_turnout, total_voters=total_voters_sum,
        kim_total=kim_total, park_total=park_total,
        kim_pct=kim_pct, park_pct=park_pct, gap=gap, result=result,
        age_results=age_results,
    )


# ═══════════════════════════════════════════════════════════════
# 후보 프리미엄 — 이슈/리액션 실시간 데이터 기반
# 부울경 메가시티, 경제, 산업, 청년 키워드의 이슈/반응 분석
# ═══════════════════════════════════════════════════════════════

_PREMIUM_KEYWORDS = {
    "부울경": ["부울경", "메가시티", "행정통합"],
    "경제": ["경남 경제", "경남 일자리", "조선업"],
    "산업": ["스마트산단", "우주항공", "경남 AI", "경남 산업"],
    "청년": ["경남 청년", "청년 정책", "청년 일자리"],
}


def _load_enrichment_snapshot() -> dict:
    """enrichment_snapshot.json 로드"""
    try:
        import json
        from pathlib import Path
        p = Path(__file__).resolve().parent.parent / "data" / "enrichment_snapshot.json"
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _auto_president_effect() -> dict:
    """대통령 효과 — 국정지지율 + 뉴스 클러스터에서 대통령 관련 이슈"""
    snap = _load_enrichment_snapshot()
    np_data = snap.get("national_poll", {})
    clusters = snap.get("news_clusters", [])

    approval = np_data.get("president_approval", 0)
    party_gap = np_data.get("party_gap", 0)  # 민주 - 국힘

    # 클러스터에서 대통령/이재명 관련 이슈 감성
    pres_clusters = [c for c in clusters if any(kw in c.get("name", "") for kw in ["이재명", "대통령", "정부", "여당"])]
    pres_sent = sum(c.get("sentiment", 0) for c in pres_clusters) / len(pres_clusters) if pres_clusters else 0

    if approval > 0:
        # 지지율 60%+ → 강한 효과, 50% → 중립, 40%- → 역효과
        # 경남 할인 30% 적용
        base = (approval - 50) * 0.06 * 0.7
        # 정당 격차 보너스
        party_bonus = min(1.0, party_gap * 0.03) if party_gap > 0 else max(-0.5, party_gap * 0.02)
        # 클러스터 감성 보너스
        cluster_bonus = pres_sent * 0.01
        value = round(max(-3.0, min(3.0, base + party_bonus + cluster_bonus)), 1)
        detail = f"지지율{approval}% 정당격차{party_gap:+.0f}%p"
        if pres_clusters:
            detail += f" 클러스터{len(pres_clusters)}건({pres_sent:+.0f})"
        return {"name": "대통령 효과 전이율", "value": value, "confidence": "high",
                "reason": detail}

    return {"name": "대통령 효과 전이율", "value": +1.8, "confidence": "high",
            "reason": "갤럽 67%, 정당 +12%p. 경남 할인 적용 (기본값)"}


def _auto_conservative_base() -> dict:
    """보수 기저 — 최신 경남 정당지지율 기반 (동적)"""
    snap = _load_enrichment_snapshot()
    np_data = snap.get("national_poll", {})

    dem = np_data.get("dem_support", 0)
    ppp = np_data.get("ppp_support", 0)

    if dem > 0 and ppp > 0:
        gap = dem - ppp
        # 경남 보수 할인: 전국 대비 보수 +12%p
        gyeongnam_gap = gap - 12
        value = round(max(-2.5, min(1.5, gyeongnam_gap * 0.08)), 1)
        return {
            "name": "보수 기저 (정당지지율)",
            "value": value,
            "confidence": "high",
            "reason": f"민주{dem}% 국힘{ppp}% 격차{gap:+.0f}%p → 경남할인 후 {value:+.1f}",
        }

    return {
        "name": "보수 기저 (정당지지율)",
        "value": -1.0,
        "confidence": "high",
        "reason": "정당지지율 데이터 없음 (기본값)",
    }


def _auto_ruling_rally() -> dict:
    """여당 결집 — 클러스터 우리유리 비율 + 국정지지율"""
    snap = _load_enrichment_snapshot()
    ci = snap.get("cluster_issue", {})
    np_data = snap.get("national_poll", {})

    issue_idx = ci.get("issue_index", 50)
    approval = np_data.get("president_approval", 0)

    if ci.get("total", 0) > 0:
        # 이슈 우위(>55) + 높은 지지율 → 여당 결집 강화
        issue_bonus = (issue_idx - 50) * 0.04
        approval_bonus = (approval - 50) * 0.02 if approval > 0 else 0
        value = round(max(-2.0, min(2.0, issue_bonus + approval_bonus)), 1)
        return {"name": "여당 결집 + 전략적 투표", "value": value, "confidence": "medium",
                "reason": f"이슈지수{issue_idx:.1f}pt 지지율{approval}% → {value:+.1f}"}

    return {"name": "여당 결집 + 전략적 투표", "value": +0.7, "confidence": "low",
            "reason": "KNN '국정안정 여당' 52.4% (기본값)"}


def _auto_conservative_rally() -> dict:
    """보수 결집 — 상대유리 이슈 비율 + 국힘 지지율"""
    snap = _load_enrichment_snapshot()
    ci = snap.get("cluster_issue", {})
    np_data = snap.get("national_poll", {})
    clusters = snap.get("news_clusters", [])

    ppp = np_data.get("ppp_support", 0)
    opp_count = ci.get("park_count", 0)
    total = ci.get("total", 0)

    # 상대유리 클러스터에서 위기감/네거티브 감지
    opp_clusters = [c for c in clusters if "상대" in c.get("side", "")]
    opp_intensity = sum(abs(c.get("sentiment", 0)) for c in opp_clusters) / len(opp_clusters) if opp_clusters else 0

    if total > 0:
        opp_ratio = opp_count / total  # 상대유리 비율
        # 상대유리 비율 낮으면 → 보수 위기감 ↑ → 결집 ↑ → 박 유리
        # 상대유리 비율 높으면 → 보수 안심 → 결집 약화
        crisis = max(0, 0.5 - opp_ratio)  # 상대 점유 낮을수록 위기감
        ppp_factor = max(0, (30 - ppp) * 0.03) if ppp > 0 else 0.3  # 국힘 지지율 낮을수록 위기감
        value = round(max(-3.0, min(0.0, -(crisis + ppp_factor) * 2)), 1)
        return {"name": "보수 결집 (위기감 동원)", "value": value, "confidence": "medium",
                "reason": f"상대유리{opp_count}/{total}건 국힘{ppp}% 위기감{crisis:.2f} → {value:+.1f}"}

    return {"name": "보수 결집 (위기감 동원)", "value": -0.8, "confidence": "medium",
            "reason": "여당 압도 시 위기감 동원 (기본값)"}


def _auto_candidate_negative() -> dict:
    """후보 네거티브 — 뉴스 클러스터에서 상대유리(김경수 공격) 이슈 강도"""
    snap = _load_enrichment_snapshot()
    clusters = snap.get("news_clusters", [])

    # 상대유리 클러스터 중 네거티브 공격성 분석
    neg_clusters = [c for c in clusters if "상대" in c.get("side", "")]
    if not neg_clusters:
        return {"name": "후보 네거티브", "value": 0.0, "confidence": "medium",
                "reason": "상대유리 클러스터 없음 → 네거티브 없음"}

    total_neg_articles = sum(c.get("count", 0) for c in neg_clusters)
    total_all = sum(c.get("count", 0) for c in clusters)
    neg_ratio = total_neg_articles / max(total_all, 1)
    avg_intensity = sum(abs(c.get("sentiment", 0)) for c in neg_clusters) / len(neg_clusters)

    # 네거티브 비율 × 강도 → 팩터값
    # 10% 비율·낮은 강도 → -0.3, 30%+ 비율·높은 강도 → -2.5
    value = round(max(-3.0, min(0.0, -neg_ratio * avg_intensity * 0.08)), 1)

    return {
        "name": "후보 네거티브",
        "value": value,
        "confidence": "medium" if total_all > 20 else "low",
        "reason": f"상대유리 {len(neg_clusters)}건({total_neg_articles}/{total_all}) 강도{avg_intensity:.0f} → {value:+.1f}",
    }


def _auto_incumbent_premium() -> dict:
    """현직 프리미엄 — 클러스터에서 박완수/도정 관련 이슈 감성"""
    snap = _load_enrichment_snapshot()
    clusters = snap.get("news_clusters", [])

    # 현직 관련 클러스터: 박완수/도정/예산/현직
    inc_clusters = [c for c in clusters if any(kw in c.get("name", "") for kw in ["박완수", "도정", "도청", "추경", "예산", "현직"])]
    # 현직 책임 이슈 (사건사고 등): 우리유리인데 현직 관련
    inc_neg = [c for c in clusters if "우리" in c.get("side", "") and any(kw in c.get("name", "") for kw in ["사고", "사망", "관리", "부실"])]

    if inc_clusters or inc_neg:
        # 상대유리 현직 이슈 → 현직 프리미엄 강화 (박 유리)
        # 우리유리 현직 이슈 (사고 등) → 현직 프리미엄 약화 (김 유리)
        pos_count = sum(c.get("count", 0) for c in inc_clusters if "상대" in c.get("side", ""))
        neg_count = sum(c.get("count", 0) for c in inc_clusters if "우리" in c.get("side", ""))
        neg_count += sum(c.get("count", 0) for c in inc_neg)

        net = pos_count - neg_count
        # 현직 긍정 넘으면 → 박 유리(-), 현직 부정 넘으면 → 김 유리(약화)
        value = round(max(-3.0, min(0.0, -1.0 - net * 0.05)), 1)
        return {"name": "현직 프리미엄", "value": value, "confidence": "medium",
                "reason": f"현직관련: 상대유리{pos_count}건 우리유리{neg_count}건 → {value:+.1f}"}

    return {"name": "현직 프리미엄", "value": -1.5, "confidence": "medium",
            "reason": "현직 관련 클러스터 없음 (기본값)"}


def _auto_poll_inertia() -> dict:
    """여론관성 — 여론조사 격차에서 자동 산출"""
    snap = _load_enrichment_snapshot()
    auto = snap.get("auto_polls", [])

    if auto:
        latest = auto[0] if isinstance(auto[0], dict) else {}
        gap = latest.get("gap", 0)
        if gap != 0:
            value = round(max(-2.0, min(2.0, gap * 0.15)), 1)
            return {"name": "여론관성", "value": value, "confidence": "medium",
                    "reason": f"최신 여론 격차 {gap:+.1f}%p → 관성 {value:+.1f}"}

    return {"name": "여론관성", "value": +0.5, "confidence": "medium",
            "reason": "여론조사 추세 상승 모멘텀 (기본값)"}


def _compute_candidate_premium() -> dict:
    """후보 프리미엄 — 클러스터에서 김경수 관련 우리유리 이슈 감성"""
    snap = _load_enrichment_snapshot()
    clusters = snap.get("news_clusters", [])

    # 우리유리 클러스터의 긍정 감성 강도 = 김경수 브랜드 파워
    our_clusters = [c for c in clusters if "우리" in c.get("side", "")]
    if not our_clusters:
        return {"name": "후보 프리미엄 (정책)", "value": 0.0, "confidence": "low",
                "reason": "우리유리 클러스터 없음"}

    avg_sent = sum(c.get("sentiment", 0) for c in our_clusters) / len(our_clusters)
    avg_count = sum(c.get("count", 0) for c in our_clusters) / len(our_clusters)

    # 높은 긍정 감성 + 높은 커버리지 → 강한 후보 프리미엄
    sent_factor = avg_sent * 0.02  # 감성 50 → +1.0
    volume_factor = min(0.5, avg_count * 0.03)  # 기사수 보너스
    value = round(max(-1.0, min(2.0, sent_factor + volume_factor)), 1)

    return {
        "name": "후보 프리미엄 (정책)",
        "value": value,
        "confidence": "medium" if len(our_clusters) >= 3 else "low",
        "reason": f"우리유리 {len(our_clusters)}건 감성{avg_sent:+.0f} 평균{avg_count:.0f}건 → {value:+.1f}",
    }


def predict_turnout(
    # 실시간 보정 시그널 (현재 미사용 — 7대 실제 투표율 고정)
    honeymoon_score: float = 0.0,
    reaction_index_avg: float = 0.0,
    poll_gap: float = 0.0,
    org_endorsement_count: int = 0,
    momcafe_activity: float = 0.0,
    economic_sentiment: float = 0.0,
) -> TurnoutPrediction:
    """
    투표율 예측 + 후보별 예상 득표수 + 시나리오 분석.

    기저: 7대 지선(2018) 실제 투표율 (중앙선관위) — 보정 없음.
    지지율: NESDC 양자대결 3개 조사 raw data + 무응답 균등배분.
    시나리오는 투표율 변동만 적용 (지지율 보정 없음).
    """
    prediction = TurnoutPrediction(computed_at=datetime.now().isoformat())

    # ── 기저 시나리오: 7대 실제 투표율 그대로 ──
    base = _compute_scenario(
        "현재 추세",
        "7대 지선(2018) 실제 투표율 + NESDC 3개 조사 양자대결 raw data",
    )
    prediction.base_scenario = base

    # ── 시나리오 생성 (투표율 변동만) ──

    # 시나리오 1: 비관 (8대 수준 낮은 투표율)
    s1 = _compute_scenario(
        "비관 (8대 수준)",
        "8대 지선처럼 투표율 하락 — 전체 -8%p",
        turnout_adjustments={"20s": -10, "30s": -8, "40s": -5, "50s": -5, "60s": -3, "70+": -3},
    )

    # 시나리오 2: 3040 집중 동원
    s2 = _compute_scenario(
        "3040 집중 동원",
        "맘카페+신도시 사전투표 캠페인 → 2040 투표율 +5%p",
        turnout_adjustments={"20s": 5, "30s": 5, "40s": 5},
    )

    # 시나리오 3: 전체 투표율 상승
    s3 = _compute_scenario(
        "전체 투표율 상승",
        "접전 보도 + 대통령효과 → 전체 +5%p",
        global_turnout_adj=5,
    )

    # 시나리오 4: 최적 (3040 동원 + 전체 상승)
    s4 = _compute_scenario(
        "최적 (전면 동원)",
        "3040 집중 동원 + 전체 상승 + 60대 이탈 방어",
        turnout_adjustments={"20s": 5, "30s": 5, "40s": 5},
        global_turnout_adj=5,
    )

    prediction.scenarios = [s1, base, s2, s3, s4]

    # ── 민감도 분석 ──
    # "이 세대 투표율 5%p 올리면 결과가 얼마나 바뀌는가"
    for age_key, age_data in AGE_DISTRIBUTION.items():
        test_scenario = _compute_scenario(
            f"{age_data['label']} +5%p",
            f"{age_data['label']} 투표율 5%p 상승 시",
            turnout_adjustments={age_key: 5},
        )
        delta = test_scenario.kim_pct - base.kim_pct
        extra_votes = test_scenario.kim_total - base.kim_total

        prediction.sensitivity.append({
            "age": age_key,
            "label": age_data["label"],
            "turnout_change": "+5%p",
            "kim_pct_change": round(delta, 2),
            "extra_votes": round(extra_votes, 2),
            "strategic_value": "높음" if delta > 0.5 else "중간" if delta > 0.2 else "낮음",
        })

    # 민감도 정렬 (효과 큰 순)
    prediction.sensitivity.sort(key=lambda x: -x["kim_pct_change"])

    # ══════════════════════════════════════════════════════════════
    # 판세지수 — 독립 예측 모델 (9개 팩터)
    # 여론조사/투표율 데이터 없이, 구조적·환경적 변수만으로 독자 예측
    # ══════════════════════════════════════════════════════════════
    # 9개 팩터: 6개 자동 + 2개 고정 + 1개 자동(후보프리미엄)
    PANDSE_FACTORS = [
        _auto_president_effect(),                          # 자동
        _auto_candidate_negative(),                         # 자동 (candidate_buzz 부정 감성)
        _auto_incumbent_premium(),                         # 자동
        _auto_conservative_base(),                         # 자동 (정당지지율)
        _auto_ruling_rally(),                              # 자동
        _auto_conservative_rally(),                        # 자동
        {"name": "투표율 차등 동원", "value": +0.2, "confidence": "medium",
         "reason": "탄핵 후 첫 지선. 진보 동원 미약 순효과"},    # 고정
        _compute_candidate_premium(),                      # 자동
        _auto_poll_inertia(),                              # 자동
    ]
    CONF_WEIGHT = {"high": 1.0, "medium": 0.7, "low": 0.4}

    # 판세지수 산출: 신뢰도 가중합 → 50 기준 지수
    weighted_sum = sum(f["value"] * CONF_WEIGHT.get(f["confidence"], 0.7) for f in PANDSE_FACTORS)
    pandse_index = round(50 + weighted_sum, 1)

    # 판세지수 → 독립 예측 gap (1pt = 0.4%p, 50 = 0%p)
    pandse_gap = round((pandse_index - 50) * 0.4, 2)
    pandse_kim = round(50 + pandse_gap / 2, 1)
    pandse_park = round(50 - pandse_gap / 2, 1)

    # 기본모델 gap
    base_gap = round(base.kim_pct - base.park_pct, 2)

    # ── 다이내믹 예측: D-day 연동 가변 가중치 ──
    # D-90~60: 80:20, D-60~30: 70:30, D-30~14: 55:45, D-14~7: 40:60, D-7~1: 30:70
    from datetime import date
    election_day = date(2026, 6, 3)
    d_day = (election_day - date.today()).days
    if d_day > 60:
        MIX_BASE, MIX_PANDSE = 0.80, 0.20
    elif d_day > 30:
        MIX_BASE, MIX_PANDSE = 0.70, 0.30
    elif d_day > 14:
        MIX_BASE, MIX_PANDSE = 0.55, 0.45
    elif d_day > 7:
        MIX_BASE, MIX_PANDSE = 0.40, 0.60
    else:
        MIX_BASE, MIX_PANDSE = 0.30, 0.70
    dynamic_gap = round(MIX_BASE * base_gap + MIX_PANDSE * pandse_gap, 2)
    dynamic_kim = round(50 + dynamic_gap / 2, 1)
    dynamic_park = round(50 - dynamic_gap / 2, 1)

    prediction.correction = {
        "factors": PANDSE_FACTORS,
        # 판세지수 (독립 모델)
        "pandse_index": pandse_index,
        "pandse_gap": pandse_gap,
        "pandse_kim": pandse_kim,
        "pandse_park": pandse_park,
        # 기본값
        "base_gap": base_gap,
        "base_kim": round(base.kim_pct, 1),
        "base_park": round(base.park_pct, 1),
        # 다이내믹 (가중 평균)
        "dynamic_gap": dynamic_gap,
        "dynamic_kim": dynamic_kim,
        "dynamic_park": dynamic_park,
        "mix": f"기본 {int(MIX_BASE*100)}% + 판세 {int(MIX_PANDSE*100)}%",
        "d_day": d_day,
        "mix_schedule": "D-90~60: 80:20 → D-60~30: 70:30 → D-30~14: 55:45 → D-14~7: 40:60 → D-7~1: 30:70",
    }

    # ── 전략적 인사이트 ──
    top_sens = prediction.sensitivity[0] if prediction.sensitivity else {}
    prediction.strategic_insight = (
        f"기본모델: 김 {base.kim_pct:.1f}% 박 {base.park_pct:.1f}% (gap {base_gap:+.1f}%p). "
        f"판세지수: {pandse_index}pt → 김 {pandse_kim}% 박 {pandse_park}% (gap {pandse_gap:+.1f}%p). "
        f"다이내믹(70:30): 김 {dynamic_kim}% 박 {dynamic_park}% (gap {dynamic_gap:+.1f}%p)."
    )

    return prediction
