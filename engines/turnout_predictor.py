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
    """enrichment_snapshot.json 로드 (캐시)"""
    try:
        import json
        with open("data/enrichment_snapshot.json") as f:
            return json.load(f)
    except Exception:
        return {}


def _auto_president_effect() -> dict:
    """대통령 효과 — 뉴스 감성에서 '이재명/대통령/여당' 키워드 자동 추출"""
    snap = _load_enrichment_snapshot()
    ii = snap.get("issue_indices", {})
    ri = snap.get("reaction_indices", {})
    keywords = ["이재명", "대통령", "여당", "민주당", "정부"]
    scores = []
    sentiments = []
    for kw in keywords:
        for k, v in ii.items():
            if kw in k:
                scores.append(v.get("index", 0))
        for k, v in ri.items():
            if kw in k:
                sentiments.append(v.get("net_sentiment", 0))
    if not scores and not sentiments:
        return {"name": "대통령 효과 전이율", "value": +1.8, "confidence": "high",
                "reason": "갤럽 67%, 정당 +12%p. 경남 할인 적용 (기본값)"}
    avg_score = sum(scores) / len(scores) if scores else 50
    avg_sent = sum(sentiments) / len(sentiments) if sentiments else 0
    # 이슈 활성도 + 감성 방향 → 값 산출
    value = round(max(-3.0, min(3.0, (avg_score - 50) * 0.05 + avg_sent * 3)), 1)
    return {"name": "대통령 효과 전이율", "value": value, "confidence": "high",
            "reason": f"이슈{avg_score:.0f} 감성{avg_sent:+.2f} → 자동산출 {value:+.1f}"}


def _auto_conservative_base() -> dict:
    """보수 기저 — 최신 경남 정당지지율 기반 (동적)"""
    snap = _load_enrichment_snapshot()
    np_data = snap.get("national_poll", {})

    if np_data:
        dem = np_data.get("dem_support", 0)    # 민주당 지지율
        ppp = np_data.get("ppp_support", 0)    # 국힘 지지율
        gap = dem - ppp  # 민주 - 국힘

        if gap and dem > 0 and ppp > 0:
            # 정당 격차 기반: 민주 +12%p면 보수 약세 → 김 유리
            # 국힘 우세면 보수 강세 → 박 유리
            # 경남은 전국 대비 보수 +10~15%p 할인 적용
            gyeongnam_gap = gap - 12  # 경남 보수 할인 (-12%p)
            value = round(max(-2.5, min(1.0, gyeongnam_gap * 0.08)), 1)
            return {
                "name": "보수 기저 (정당지지율)",
                "value": value,
                "confidence": "high",
                "reason": f"민주{dem}% 국힘{ppp}% 격차{gap:+.0f}%p → 경남할인 후 {value:+.1f}",
            }

    # 폴백: 고정값
    return {
        "name": "보수 기저 (정당지지율)",
        "value": -1.0,
        "confidence": "high",
        "reason": "정당지지율 데이터 없음. 역대 보수 평균 57% 기반 (기본값)",
    }


def _auto_ruling_rally() -> dict:
    """여당 결집 — '국정안정/여당/결집' 뉴스 감성 자동"""
    snap = _load_enrichment_snapshot()
    ri = snap.get("reaction_indices", {})
    keywords = ["여당", "결집", "국정", "민주당", "단결"]
    sentiments = []
    for kw in keywords:
        for k, v in ri.items():
            if kw in k:
                sentiments.append(v.get("net_sentiment", 0))
    if not sentiments:
        return {"name": "여당 결집 + 전략적 투표", "value": +0.7, "confidence": "low",
                "reason": "KNN '국정안정 여당' 52.4% (기본값)"}
    avg = sum(sentiments) / len(sentiments)
    value = round(max(-2.0, min(2.0, avg * 3)), 1)
    return {"name": "여당 결집 + 전략적 투표", "value": value, "confidence": "low",
            "reason": f"여당 관련 감성 {avg:+.2f} → 자동산출 {value:+.1f}"}


def _auto_conservative_rally() -> dict:
    """보수 결집 — '국힘/보수/위기감' 뉴스 감성 자동"""
    snap = _load_enrichment_snapshot()
    ri = snap.get("reaction_indices", {})
    keywords = ["국민의힘", "국힘", "보수", "야당", "위기"]
    sentiments = []
    for kw in keywords:
        for k, v in ri.items():
            if kw in k:
                sentiments.append(v.get("net_sentiment", 0))
    if not sentiments:
        return {"name": "보수 결집 (위기감 동원)", "value": -0.8, "confidence": "medium",
                "reason": "여당 압도 시 위기감 동원 (기본값)"}
    avg = sum(sentiments) / len(sentiments)
    # 보수 관련 감성이 부정적이면 → 보수 위기감 강화 → 결집 증가 → 박 유리
    value = round(max(-3.0, min(0.0, avg * -2)), 1)
    return {"name": "보수 결집 (위기감 동원)", "value": value, "confidence": "medium",
            "reason": f"보수 관련 감성 {avg:+.2f} → 위기감 결집 {value:+.1f}"}


def _auto_candidate_negative() -> dict:
    """후보 네거티브 — candidate_buzz에서 김경수 부정 감성 비율 추출"""
    snap = _load_enrichment_snapshot()
    buzz = snap.get("candidate_buzz", {})

    kim_buzz = {k: v for k, v in buzz.items() if "김경수" in k}
    if not kim_buzz:
        return {"name": "후보 네거티브", "value": -1.2, "confidence": "medium",
                "reason": "candidate_buzz 데이터 없음 (기본값)"}

    # 6분류에서 "부정" 비율 추출
    total_neg = 0
    total_all = 0
    total_mentions = 0
    for kw, b in kim_buzz.items():
        s6 = b.get("ai_sentiment", {}).get("sentiment_6way", {})
        neg = s6.get("부정", 0)
        all_s = sum(s6.values()) if s6 else 1
        total_neg += neg
        total_all += all_s
        total_mentions += b.get("mention_count", 0)

    neg_ratio = total_neg / max(total_all, 1)  # 0~1

    # 부정 비율 → 팩터값
    # 0% 부정 → 0 (네거티브 없음)
    # 10% 부정 → -0.5
    # 30%+ 부정 → -2.0 (강한 네거티브)
    value = round(max(-3.0, min(0.0, neg_ratio * -8)), 1)

    return {
        "name": "후보 네거티브",
        "value": value,
        "confidence": "medium" if total_mentions > 10 else "low",
        "reason": f"김경수 {len(kim_buzz)}개 키워드 부정비율 {neg_ratio:.0%} ({total_neg}/{total_all}) → {value:+.1f}",
    }


def _auto_incumbent_premium() -> dict:
    """현직 프리미엄 — '박완수/도정/경남도청' 감성 자동"""
    snap = _load_enrichment_snapshot()
    ri = snap.get("reaction_indices", {})
    keywords = ["박완수", "도정", "경남도청", "도지사"]
    sentiments = []
    for kw in keywords:
        for k, v in ri.items():
            if kw in k:
                sentiments.append(v.get("net_sentiment", 0))
    if not sentiments:
        return {"name": "현직 프리미엄", "value": -1.5, "confidence": "medium",
                "reason": "도정평가 긍정 29% (기본값)"}
    avg = sum(sentiments) / len(sentiments)
    # 현직 감성이 긍정이면 → 현직 프리미엄 강화 (박 유리)
    value = round(max(-3.0, min(0.0, -0.5 + avg * -3)), 1)
    return {"name": "현직 프리미엄", "value": value, "confidence": "medium",
            "reason": f"현직 관련 감성 {avg:+.2f} → 자동산출 {value:+.1f}"}


def _auto_poll_inertia() -> dict:
    """여론관성 — 여론조사 추세/모멘텀/격차에서 자동 산출"""
    snap = _load_enrichment_snapshot()
    # polling history에서 최근 추세 가져오기
    try:
        import json
        with open("data/enrichment_snapshot.json") as f:
            s = json.load(f)
        # auto_polls에서 최신 격차
        auto = s.get("auto_polls", [])
        if auto and len(auto) > 0:
            latest = auto[0]
            gap = latest.get("gap", 0)
            # 격차 기반: +10%p면 강한 여론관성, 0이면 중립
            value = round(max(-2.0, min(2.0, gap * 0.15)), 1)
            return {"name": "여론관성", "value": value, "confidence": "medium",
                    "reason": f"최신 여론 격차 {gap:+.1f}%p → 관성 {value:+.1f}"}
    except Exception:
        pass
    # POLL_DATA에서 최신
    try:
        from lib.pollData import POLL_DATA  # type: ignore
    except Exception:
        pass
    return {"name": "여론관성", "value": +0.5, "confidence": "medium",
            "reason": "여론조사 추세 상승 모멘텀 (기본값)"}


def _compute_candidate_premium() -> dict:
    """후보 프리미엄(김경수 정책 키워드)을 이슈/리액션 데이터에서 실시간 계산."""
    try:
        import json
        with open("data/enrichment_snapshot.json") as f:
            snap = json.load(f)
        ii = snap.get("issue_indices", {})
        ri = snap.get("reaction_indices", {})
    except Exception:
        return {"name": "후보 프리미엄 (정책)", "value": 0.0, "confidence": "low",
                "reason": "데이터 없음", "detail": {}}

    issue_scores = []
    rx_scores = []
    sentiments = []
    matched = []

    for cat, kws in _PREMIUM_KEYWORDS.items():
        for kw in kws:
            # 정확 매칭 → 부분 매칭
            i_match = ii.get(kw)
            r_match = ri.get(kw)
            if not i_match:
                for k, v in ii.items():
                    if kw in k or k in kw:
                        i_match = v
                        break
            if not r_match:
                for k, v in ri.items():
                    if kw in k or k in kw:
                        r_match = v
                        break

            i_score = i_match.get("index", 0) if i_match else 0
            r_score = r_match.get("final_score", 0) if r_match else 0
            r_sent = r_match.get("net_sentiment", 0) if r_match else 0

            if i_score > 0 or r_score > 0:
                issue_scores.append(i_score)
                rx_scores.append(r_score)
                sentiments.append(r_sent)
                matched.append(kw)

    if not matched:
        return {"name": "후보 프리미엄 (정책)", "value": 0.0, "confidence": "low",
                "reason": "매칭 키워드 없음", "detail": {}}

    avg_issue = sum(issue_scores) / len(issue_scores)
    avg_rx = sum(rx_scores) / len(rx_scores)
    avg_sent = sum(sentiments) / len(sentiments)

    # 지표화: 이슈 활성도 + 감성 방향 + 반응 강도
    issue_factor = (avg_issue - 50) * 0.3      # 이슈 50 이상 = 활발한 논의
    sentiment_factor = avg_sent * 15            # 긍정 0.5 → +7.5점
    rx_factor = (avg_rx - 40) * 0.2            # 반응 40 이상 = 관심 높음

    total = round(issue_factor + sentiment_factor + rx_factor, 1)
    # %p 환산: 점수를 직접 사용 (범위 제한)
    value = round(max(-3.0, min(3.0, total * 0.15)), 1)
    confidence = "high" if len(matched) >= 6 and avg_sent > 0.3 else "medium" if len(matched) >= 3 else "low"

    return {
        "name": "후보 프리미엄 (정책)",
        "value": value,
        "confidence": confidence,
        "reason": f"부울경·경제·산업·청년 {len(matched)}개 키워드 이슈{avg_issue:.0f} 감성{avg_sent:+.2f}",
        "detail": {
            "matched_keywords": len(matched),
            "avg_issue": round(avg_issue, 1),
            "avg_reaction": round(avg_rx, 1),
            "avg_sentiment": round(avg_sent, 3),
            "issue_factor": round(issue_factor, 1),
            "sentiment_factor": round(sentiment_factor, 1),
            "rx_factor": round(rx_factor, 1),
            "total_score": total,
        },
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
