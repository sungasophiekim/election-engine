"""
Election Strategy Engine — Leading Index (v4, rewrite)
기존 엔진 출력을 합성하여 '숨겨진 유권자 이동'을 추정하는 선행지수.

이 모듈은 기존 엔진을 대체하지 않습니다.
issue_scoring, anomaly_detector, unified_collector, polling_tracker의
이미 계산된 출력을 읽어서 하나의 종합 지수로 합성합니다.

Leading Index: 0~100 (50=중립)
  > 50: 우리에게 유리한 이동 감지
  < 50: 우리에게 불리한 이동 감지

Reuse Map:
  issue_scoring.py     → IssueScore.score, .level, .influence_score, .negative_ratio(via signal)
  anomaly_detector.py  → AnomalyResult.surprise_score, .z_score, .is_surge, .day_over_day
  unified_collector.py → ReactionSummary.*, UnifiedSignal.trend_*, .change_pct
  polling_tracker.py   → calculate_trend() → our_trend, momentum
                         calculate_win_probability() → gap, win_prob
  reaction_attribution → AttributionSummary.movement_detected, .attributed_count, .poll_watch_regions

Rewrite fixes:
  Gap 1: negative_ratio로 후보연결 이슈의 실제 감정 방향 판단
  Gap 2: CrisisLevel에 따른 영향력 가중
  Gap 3: 스냅샷 기반 추세 추적 (이전 지수 대비 변화)
  Gap 4: attribution_summary 전체 활용 (ratio, poll_watch, strongest_linkage)
  Gap 5: to_dict() 직렬화 메서드 추가
  Gap 6: message_theme, region 기반 시그널 활용
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LeadingIndex:
    """선행지수 결과 — 기존 ScoreExplanation 패턴과 호환"""
    index: float = 50.0          # 0~100 (50=중립)
    direction: str = "stable"    # "gaining" | "stable" | "losing"
    confidence: str = "low"      # "high" | "medium" | "low"

    # 구성요소 분해 (각각 -50 ~ +50 범위, 합산 후 50 더해서 index 생성)
    components: dict = field(default_factory=dict)

    # ScoreExplanation 호환 필드
    explanation_text: str = ""
    primary_driver: str = ""

    # 개별 시그널 목록
    signals: list = field(default_factory=list)  # [{"type": str, "detail": str, "impact": float}]

    # 여론조사 예측 힌트
    predicted_direction: str = ""    # "상승 예상" | "하락 주의" | "변동 미미"
    predicted_magnitude: float = 0.0  # 예상 변화폭 (±%p, rough)

    # Gap 3: 추세 추적
    previous_index: float = 50.0     # 직전 지수 (스냅샷 비교)
    index_delta: float = 0.0         # 현재 - 직전
    trend_description: str = ""      # "상승 전환", "하락 가속" 등

    computed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """대시보드/API 전달용 dict — ScoreExplanation.to_dict() 패턴 호환"""
        return {
            "index": round(self.index, 1),
            "direction": self.direction,
            "confidence": self.confidence,
            "components": self.components,
            "explanation_text": self.explanation_text,
            "primary_driver": self.primary_driver,
            "signals": self.signals[:10],
            "predicted_direction": self.predicted_direction,
            "predicted_magnitude": round(self.predicted_magnitude, 1),
            "previous_index": round(self.previous_index, 1),
            "index_delta": round(self.index_delta, 1),
            "trend_description": self.trend_description,
        }


# ── 가중치 (v2: Issue/Reaction Index 반영) ─────────────────────────
# 기존 5-component (하위 호환)
W_ISSUE_PRESSURE     = 0.15  # 축소 (Issue Index가 대체)
W_ANOMALY_SIGNAL     = 0.10  # 축소 (Issue Index velocity에 포함)
W_REACTION_MOMENTUM  = 0.15  # 축소 (Reaction Index가 대체)
W_SOCIAL_VELOCITY    = 0.10  # 축소 (네이버+구글 분리)
W_POLL_INERTIA       = 0.20  # 유지

# v2 신규 component
W_ISSUE_INDEX        = 0.12  # Issue Index 직접 반영
W_REACTION_INDEX     = 0.13  # Reaction Index 직접 반영

# v3 신규 component
W_HONEYMOON          = 0.08  # 대통령/정당 지지율 (대통령 효과)
W_ECONOMY            = 0.05  # 경제 체감 (현직 평가)

# Gap 2: CrisisLevel → 영향 가중치
_LEVEL_WEIGHT = {
    "CRISIS": 2.0,
    "ALERT":  1.5,
    "WATCH":  1.0,
    "NORMAL": 0.5,
}

# ── Gap 3: 스냅샷 저장소 ──────────────────────────────────────────
_leading_index_snapshots: dict = {}  # tenant_id → LeadingIndex


def save_leading_snapshot(tenant_id: str, li: "LeadingIndex"):
    """현재 선행지수를 스냅샷으로 저장"""
    _leading_index_snapshots[tenant_id] = li


def get_leading_snapshot(tenant_id: str) -> "LeadingIndex | None":
    """직전 스냅샷 조회"""
    return _leading_index_snapshots.get(tenant_id)


def compute_leading_index(
    issue_scores: list = None,       # list[IssueScore]
    anomaly_results: list = None,    # list[AnomalyResult]
    unified_signals: list = None,    # list[UnifiedSignal]
    polling_data: dict = None,       # from PollingTracker
    attribution_summary: dict = None,  # from ReactionAttributor.build_summary()
    candidate_name: str = "",
    opponents: list = None,
    issue_signals: list = None,      # list[IssueSignal] — negative_ratio 참조용
    tenant_id: str = "",             # 스냅샷 키
    # v2: 분리 인덱스 입력
    issue_index_map: dict = None,    # {keyword: IssueIndexResult}
    reaction_index_map: dict = None, # {keyword: ReactionIndexResult}
    naver_trend_data: dict = None,   # {keyword: NaverTrendSignal}
    ai_sentiment_data: dict = None,  # {keyword: AISentimentResult}
    national_poll: dict = None,      # v3: NationalPollData.to_dict()
    economic_data: dict = None,      # v3: EconomicIndicator.to_dict()
    event_context: dict = None,      # v4: {"event_type": str, "severity": str} — 이벤트 감지 시 issue_pressure 가중
) -> LeadingIndex:
    """
    기존 엔진 출력만으로 선행지수를 계산합니다.
    새로운 데이터 수집 없이 이미 있는 값만 읽습니다.

    Returns:
        LeadingIndex with index 0~100 (50=neutral)
    """
    issue_scores = issue_scores or []
    anomaly_results = anomaly_results or []
    unified_signals = unified_signals or []
    polling_data = polling_data or {}
    attribution_summary = attribution_summary or {}
    opponents = opponents or []
    issue_signals = issue_signals or []

    signals = []

    # negative_ratio 매핑 (keyword → ratio)
    neg_ratio_map = {}
    for sig in issue_signals:
        neg_ratio_map[sig.keyword] = sig.negative_ratio

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 1. ISSUE PRESSURE (-50 ~ +50)
    #    뜨거운 이슈가 우리에게 유리한가, 불리한가?
    #    Gap 1: negative_ratio 기반 실제 감정 판단
    #    Gap 2: CrisisLevel 기반 가중
    #    Gap 6: message_theme 활용
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    issue_pressure = 0.0
    if issue_scores:
        for iss in issue_scores[:5]:
            kw = iss.keyword
            base_weight = iss.score / 100.0
            # Gap 2: crisis level로 가중
            level_name = iss.level.name if hasattr(iss.level, 'name') else str(iss.level)
            level_w = _LEVEL_WEIGHT.get(level_name, 1.0)
            weight = base_weight * level_w

            candidate_linked = candidate_name and candidate_name in kw
            opponent_linked = any(opp in kw for opp in opponents)

            # Gap 1: negative_ratio로 실제 감정 판단
            neg_ratio = neg_ratio_map.get(kw, 0.5)  # 기본 0.5 (중립)

            if candidate_linked:
                if neg_ratio > 0.6:
                    # 후보 연결 + 부정적 → 불리
                    impact = -weight * 15
                    issue_pressure += impact
                    signals.append({
                        "type": "issue_pressure",
                        "detail": f"후보 연결 이슈 '{kw}' ({iss.score:.0f}점, 부정 {neg_ratio:.0%}) — 부담",
                        "impact": impact,
                    })
                elif neg_ratio < 0.3:
                    # 후보 연결 + 긍정적 → 유리
                    impact = weight * 10
                    issue_pressure += impact
                    signals.append({
                        "type": "issue_pressure",
                        "detail": f"후보 연결 이슈 '{kw}' ({iss.score:.0f}점, 긍정) — 유리",
                        "impact": impact,
                    })
                else:
                    # 중립적 노출 — 약한 부담 (노출 자체가 리스크)
                    impact = -weight * 5
                    issue_pressure += impact

            elif opponent_linked:
                if neg_ratio > 0.5:
                    # 상대 이름 연결 + 부정적 → 우리에게 유리
                    impact = weight * 12
                    issue_pressure += impact
                    signals.append({
                        "type": "issue_pressure",
                        "detail": f"상대 연결 이슈 '{kw}' ({iss.score:.0f}점, 부정 {neg_ratio:.0%}) — 유리",
                        "impact": impact,
                    })
                elif neg_ratio < 0.3:
                    # 상대가 긍정적 노출 → 불리
                    impact = -weight * 8
                    issue_pressure += impact
                    signals.append({
                        "type": "issue_pressure",
                        "detail": f"상대 긍정 노출 '{kw}' ({iss.score:.0f}점) — 우리에게 불리",
                        "impact": impact,
                    })

            else:
                # Gap 6: 중립 이슈 + message_theme 기반 기회 판단
                if iss.influence_score > 60:
                    theme = getattr(iss, 'message_theme', '') or ''
                    region = getattr(iss, 'region', '') or ''
                    detail = f"고영향 중립이슈 '{kw}' (영향력 {iss.influence_score:.0f})"
                    if theme:
                        detail += f" 테마={theme}"
                    if region:
                        detail += f" 지역={region}"
                    issue_pressure += 3
                    signals.append({
                        "type": "issue_pressure",
                        "detail": detail + " — 선점 기회",
                        "impact": 3,
                    })

    issue_pressure = max(-50, min(50, issue_pressure))

    # v4: 이벤트 컨텍스트가 있으면 issue_pressure에 가중치 적용
    event_context = event_context or {}
    if event_context.get("event_type"):
        try:
            from engines.event_impact import get_event_impact_for_leading_index
            ev_weight = get_event_impact_for_leading_index(
                event_context["event_type"],
                event_context.get("severity", "standard"),
            )
            issue_pressure = max(-50, min(50, issue_pressure * ev_weight))
            signals.append({
                "type": "event_impact",
                "detail": f"이벤트 '{event_context['event_type']}' 감지 → issue_pressure ×{ev_weight}",
                "impact": round(issue_pressure * (ev_weight - 1), 1),
            })
        except Exception:
            pass

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 2. ANOMALY SIGNAL (-50 ~ +50)
    #    급등이 우리에게 유리한 방향인가?
    #    Gap 1: negative_ratio 반영
    #    Gap 2: day_over_day 변화율 활용
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    anomaly_signal = 0.0
    for ar in anomaly_results:
        if not ar.is_anomaly:
            continue
        kw = ar.keyword
        surprise = ar.surprise_score / 100.0  # 0~1
        candidate_linked = candidate_name and candidate_name in kw
        opponent_linked = any(opp in kw for opp in opponents)
        neg_ratio = neg_ratio_map.get(kw, 0.5)

        if candidate_linked:
            if neg_ratio > 0.5:
                # 우리 이슈 급등 + 부정 = 불리
                impact = -surprise * 20
                anomaly_signal += impact
                signals.append({
                    "type": "anomaly",
                    "detail": f"급등 '{kw}' (surprise {ar.surprise_score:.0f}, 부정 {neg_ratio:.0%}) — 후보 부담",
                    "impact": impact,
                })
            elif neg_ratio < 0.3:
                # 우리 이슈 급등 + 긍정 = 유리
                impact = surprise * 15
                anomaly_signal += impact
                signals.append({
                    "type": "anomaly",
                    "detail": f"급등 '{kw}' (surprise {ar.surprise_score:.0f}, 긍정) — 후보 노출 기회",
                    "impact": impact,
                })
        elif opponent_linked:
            if neg_ratio > 0.4:
                # 상대 이슈 급등 + 부정 = 유리
                impact = surprise * 18
                anomaly_signal += impact
                signals.append({
                    "type": "anomaly",
                    "detail": f"급등 '{kw}' (surprise {ar.surprise_score:.0f}) — 상대 부담",
                    "impact": impact,
                })
            elif neg_ratio < 0.3:
                # 상대 긍정 급등 = 불리
                impact = -surprise * 12
                anomaly_signal += impact
                signals.append({
                    "type": "anomaly",
                    "detail": f"상대 긍정 급등 '{kw}' — 우리에게 불리",
                    "impact": impact,
                })
        elif ar.is_surge:
            # 무관 이슈 서지 → 약간 부정적 (불확실성)
            impact = -surprise * 5
            anomaly_signal += impact
            signals.append({
                "type": "anomaly",
                "detail": f"비관련 급등 '{kw}' — 불확실성",
                "impact": impact,
            })

    anomaly_signal = max(-50, min(50, anomaly_signal))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 3. REACTION MOMENTUM (-50 ~ +50)
    #    커뮤니티/SNS 반응 방향 — 여론조사보다 빠른 체감 지표
    #    Gap 4: attribution_summary 전체 활용
    #    Gap 6: region 기반 시그널
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    reaction_momentum = 0.0
    hot_count = 0
    total_resonance = 0.0
    net_sentiment_sum = 0.0
    endorsement_net = 0
    region_heat_map = {}  # region → heat accumulator

    for sig in unified_signals:
        rxn = getattr(sig, 'reaction', None)
        if not rxn:
            continue

        # 반응 등급 집계
        if rxn.reaction_grade == "HOT":
            hot_count += 1
        total_resonance += rxn.community_resonance

        # 감정 방향 (전 채널 합산)
        net_sentiment_sum += rxn.news_net_sentiment
        net_sentiment_sum += rxn.blog_net_sentiment * 0.5
        net_sentiment_sum += rxn.cafe_net_sentiment * 0.5

        # Gap 6: 지역별 반응 열기 집계
        sig_region = getattr(sig, 'region', '') or ''
        if sig_region:
            region_heat_map[sig_region] = region_heat_map.get(sig_region, 0) + rxn.community_resonance

        # 바이럴 감지 — 바이럴이 상대에게 불리한 톤이면 우리에게 유리
        if rxn.community_has_viral:
            kw = sig.keyword
            opponent_linked = any(opp in kw for opp in opponents)
            candidate_linked = candidate_name and candidate_name in kw
            if opponent_linked and rxn.community_dominant_tone in ("조롱", "분노"):
                reaction_momentum += 8
                signals.append({
                    "type": "reaction",
                    "detail": f"'{kw}' 바이럴 (톤: {rxn.community_dominant_tone}) — 상대 부담",
                    "impact": 8,
                })
            elif candidate_linked and rxn.community_dominant_tone in ("조롱", "분노"):
                reaction_momentum -= 10
                signals.append({
                    "type": "reaction",
                    "detail": f"'{kw}' 바이럴 (톤: {rxn.community_dominant_tone}) — 우리 부담",
                    "impact": -10,
                })

        # 조직 시그널 (지지선언 vs 이탈)
        endorsement_net += rxn.endorsement_count - rxn.withdrawal_count

    # 커뮤니티 공명 집계 (시그널이 있을 때만)
    if unified_signals:
        avg_resonance = total_resonance / len(unified_signals)
        if avg_resonance > 0.5:
            reaction_momentum += 5  # 이슈가 깊이 퍼지고 있음
        elif avg_resonance < 0.2 and total_resonance > 0:
            reaction_momentum -= 3  # 반응 미미

    # 전체 감정 방향
    if net_sentiment_sum > 1.0:
        impact = min(10, net_sentiment_sum * 5)
        reaction_momentum += impact
        signals.append({
            "type": "reaction",
            "detail": f"전체 감정 긍정 (합산 {net_sentiment_sum:.1f})",
            "impact": impact,
        })
    elif net_sentiment_sum < -1.0:
        impact = max(-10, net_sentiment_sum * 5)
        reaction_momentum += impact
        signals.append({
            "type": "reaction",
            "detail": f"전체 감정 부정 (합산 {net_sentiment_sum:.1f})",
            "impact": impact,
        })

    # 조직 지지/이탈
    if endorsement_net > 0:
        impact = min(8, endorsement_net * 4)
        reaction_momentum += impact
        signals.append({
            "type": "endorsement",
            "detail": f"순지지 +{endorsement_net} (지지선언 우세)",
            "impact": impact,
        })
    elif endorsement_net < 0:
        impact = max(-8, endorsement_net * 4)
        reaction_momentum += impact
        signals.append({
            "type": "endorsement",
            "detail": f"순이탈 {endorsement_net} (지지 철회 우세)",
            "impact": impact,
        })

    # Gap 4: attribution_summary 전체 활용
    movements = attribution_summary.get("movement_detected", [])
    if movements:
        impact = min(6, len(movements) * 3)
        reaction_momentum += impact
        signals.append({
            "type": "attribution",
            "detail": f"행동-반응 이동 {len(movements)}건 감지",
            "impact": impact,
        })

    # Gap 4: 귀인 효율 (attributed / total actions)
    total_actions = attribution_summary.get("total_actions", 0)
    attributed_count = attribution_summary.get("attributed_count", 0)
    if total_actions > 0:
        attr_ratio = attributed_count / total_actions
        if attr_ratio > 0.5:
            # 행동 절반 이상이 반응을 만들었다 = 캠페인 효과적
            impact = min(5, attr_ratio * 8)
            reaction_momentum += impact
            signals.append({
                "type": "attribution",
                "detail": f"귀인 효율 {attr_ratio:.0%} (행동→반응 연결 높음)",
                "impact": round(impact, 1),
            })
        elif attr_ratio < 0.2 and total_actions >= 3:
            # 많은 행동이 반응을 만들지 못함 = 메시지 미스매치
            reaction_momentum -= 3
            signals.append({
                "type": "attribution",
                "detail": f"귀인 효율 {attr_ratio:.0%} (행동→반응 미연결)",
                "impact": -3,
            })

    # Gap 4: poll_watch_regions — 여론 변동 감시 지역이 있으면 불확실성 시그널
    poll_watch = attribution_summary.get("poll_watch_regions", [])
    if poll_watch:
        # 감시 지역이 있다는 것은 반응과 여론이 함께 움직이는 곳이 있다는 의미
        # 방향은 movement와 같이 판단 (있으면 이미 우리에게 유리한 쪽)
        signals.append({
            "type": "attribution",
            "detail": f"여론 감시 지역 {len(poll_watch)}곳: {', '.join(poll_watch[:3])}",
            "impact": 0,  # 정보 시그널 (방향 중립)
        })

    # Gap 6: 지역별 반응 집중도 시그널
    if region_heat_map:
        top_region = max(region_heat_map, key=region_heat_map.get)
        if region_heat_map[top_region] > 1.5:
            signals.append({
                "type": "reaction",
                "detail": f"반응 집중 지역: {top_region} (열기 {region_heat_map[top_region]:.1f})",
                "impact": 0,  # 정보 시그널
            })

    reaction_momentum = max(-50, min(50, reaction_momentum))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 4. SOCIAL VELOCITY (-50 ~ +50)
    #    Google Trends + 소셜 변화율 — 관심도 방향
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    social_velocity = 0.0
    for sig in unified_signals:
        kw = sig.keyword
        opponent_linked = any(opp in kw for opp in opponents)
        candidate_linked = candidate_name and candidate_name in kw
        neg_ratio = neg_ratio_map.get(kw, 0.5)

        # Google Trends 관심도 변화
        if sig.trend_change_7d > 20:
            if candidate_linked:
                # 후보 관심 증가 — 감정에 따라 방향 결정
                if neg_ratio > 0.6:
                    social_velocity -= 5
                elif neg_ratio < 0.3:
                    social_velocity += 4
                else:
                    social_velocity -= 2  # 약한 부담
            elif opponent_linked:
                social_velocity += 5  # 상대 검색 증가 = 스캔들/이슈
        elif sig.trend_change_7d < -20:
            # 관심 급감 — 이슈 소멸
            pass

        # 24시간 변화율 (change_pct)
        if sig.change_pct > 50:
            if opponent_linked:
                social_velocity += 4
                signals.append({
                    "type": "social_velocity",
                    "detail": f"'{kw}' 24h 변화 {sig.change_pct:+.0f}% — 상대 관련",
                    "impact": 4,
                })
            elif candidate_linked:
                # Gap 1: 감정에 따라 방향
                if neg_ratio > 0.6:
                    social_velocity -= 4
                    signals.append({
                        "type": "social_velocity",
                        "detail": f"'{kw}' 24h 변화 {sig.change_pct:+.0f}% — 부정 노출",
                        "impact": -4,
                    })
                elif neg_ratio < 0.3:
                    social_velocity += 3
                    signals.append({
                        "type": "social_velocity",
                        "detail": f"'{kw}' 24h 변화 {sig.change_pct:+.0f}% — 긍정 관심",
                        "impact": 3,
                    })

    social_velocity = max(-50, min(50, social_velocity))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 5. POLL INERTIA (-50 ~ +50)
    #    기존 여론조사 추세 — 관성 + 현재 위치
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    poll_inertia = 0.0
    our_trend = polling_data.get("our_trend", 0.0)    # 일별 %p 변화
    momentum = polling_data.get("momentum", "stable")  # "gaining"|"stable"|"losing"
    gap = polling_data.get("gap", 0.0)                # 우리 - 상대 (%p)

    # 추세 반영 (일별 기울기 × 확대)
    poll_inertia += max(-20, min(20, our_trend * 50))

    # 모멘텀 보너스
    if momentum == "gaining":
        poll_inertia += 8
        signals.append({"type": "poll", "detail": "여론 상승 모멘텀", "impact": 8})
    elif momentum == "losing":
        poll_inertia -= 8
        signals.append({"type": "poll", "detail": "여론 하락 모멘텀", "impact": -8})

    # 현재 격차 반영 (± 방향)
    gap_impact = max(-15, min(15, gap * 3))
    poll_inertia += gap_impact
    if abs(gap) > 2:
        signals.append({
            "type": "poll",
            "detail": f"여론 격차 {gap:+.1f}%p",
            "impact": gap_impact,
        })

    poll_inertia = max(-50, min(50, poll_inertia))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 6. ISSUE INDEX COMPONENT (-50 ~ +50)
    #    Issue Index 직접 반영 — 기존 issue_pressure를 보완
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    issue_index_component = 0.0
    issue_index_map = issue_index_map or {}
    if issue_index_map:
        for kw, ii_result in list(issue_index_map.items())[:5]:
            idx_val = ii_result.index if hasattr(ii_result, 'index') else (ii_result.get('index', 50) if isinstance(ii_result, dict) else 50)
            candidate_linked = candidate_name and candidate_name in kw
            opponent_linked = any(opp in kw for opp in opponents)
            neg_ratio = neg_ratio_map.get(kw, 0.5)

            # Issue가 크고(index 높고) 우리에게 불리하면 부정, 상대에게 불리하면 긍정
            normalized = (idx_val - 50) / 50  # -1 ~ +1
            if candidate_linked and neg_ratio > 0.5:
                issue_index_component -= abs(normalized) * 15  # 큰 이슈 + 우리 부정
            elif opponent_linked and neg_ratio > 0.5:
                issue_index_component += abs(normalized) * 12  # 큰 이슈 + 상대 부정
            elif candidate_linked and neg_ratio < 0.3:
                issue_index_component += abs(normalized) * 10  # 큰 이슈 + 우리 긍정

        signals.append({
            "type": "issue_index",
            "detail": f"Issue Index 기반 영향 {issue_index_component:+.1f}",
            "impact": round(issue_index_component, 1),
        })
    issue_index_component = max(-50, min(50, issue_index_component))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 7. REACTION INDEX COMPONENT (-50 ~ +50)
    #    Reaction Index 직접 반영 — 기존 reaction_momentum을 보완
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    reaction_index_component = 0.0
    reaction_index_map = reaction_index_map or {}
    if reaction_index_map:
        for kw, ri_result in list(reaction_index_map.items())[:5]:
            if isinstance(ri_result, dict):
                rx_score = ri_result.get('final_score', ri_result.get('index', 0))
                rx_dir = ri_result.get('direction', 'neutral')
                rx_conf = ri_result.get('confidence', 0)
            else:
                rx_score = getattr(ri_result, 'final_score', getattr(ri_result, 'index', 0))
                rx_dir = getattr(ri_result, 'direction', 'neutral')
                rx_conf = getattr(ri_result, 'confidence', 0)

            if rx_score < 25:
                continue  # SILENT → 무시

            # 반응 방향에 따라 Leading Index에 영향
            normalized = (rx_score - 25) / 75  # 0~1 (25 이하는 이미 필터)
            if rx_dir == "positive":
                reaction_index_component += normalized * 15 * rx_conf
            elif rx_dir == "negative":
                reaction_index_component -= normalized * 15 * rx_conf
            # mixed/neutral → 약한 영향만
            elif rx_score >= 50:
                reaction_index_component += normalized * 5 * rx_conf  # 강한 반응 자체가 시그널

        signals.append({
            "type": "reaction_index",
            "detail": f"Reaction Index 기반 영향 {reaction_index_component:+.1f}",
            "impact": round(reaction_index_component, 1),
        })
    reaction_index_component = max(-50, min(50, reaction_index_component))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 네이버 검색 트렌드 보정 (social_velocity에 추가)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    naver_trend_data = naver_trend_data or {}
    for kw, nv in naver_trend_data.items():
        nv_interest = nv.interest_now if hasattr(nv, 'interest_now') else (nv.get('interest_now', 0) if isinstance(nv, dict) else 0)
        nv_change = nv.change_7d if hasattr(nv, 'change_7d') else (nv.get('change_7d', 0) if isinstance(nv, dict) else 0)

        candidate_linked = candidate_name and candidate_name in kw
        opponent_linked = any(opp in kw for opp in opponents)

        if nv_change > 30:
            if candidate_linked:
                social_velocity += 3
                signals.append({"type": "naver_trend", "detail": f"네이버 '{kw}' 급상승 {nv_change:+.0f}%", "impact": 3})
            elif opponent_linked:
                social_velocity -= 2
                signals.append({"type": "naver_trend", "detail": f"네이버 상대 '{kw}' 급상승", "impact": -2})

    # AI 감성 분석 보정
    ai_sentiment_data = ai_sentiment_data or {}
    for kw, ai_sent in ai_sentiment_data.items():
        if isinstance(ai_sent, dict):
            net = ai_sent.get('net_sentiment', 0)
            about_us_neg = ai_sent.get('about_us', {}).get('negative', 0)
            about_us_pos = ai_sent.get('about_us', {}).get('positive', 0)
        else:
            net = getattr(ai_sent, 'net_sentiment', 0)
            about_us_neg = getattr(ai_sent, 'about_us_negative', 0)
            about_us_pos = getattr(ai_sent, 'about_us_positive', 0)

        if about_us_pos > about_us_neg:
            social_velocity += 2
        elif about_us_neg > about_us_pos:
            social_velocity -= 3

    social_velocity = max(-50, min(50, social_velocity))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 8. HONEYMOON EFFECT (-50 ~ +50)
    #    대통령/정당 지지율 → 지방선거 연동
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    honeymoon_component = 0.0
    national_poll = national_poll or {}
    if national_poll:
        honeymoon_score = national_poll.get("honeymoon_score", 0)
        honeymoon_component = honeymoon_score  # 이미 -50~+50 범위
        approval = national_poll.get("president_approval", 0)
        party_gap = national_poll.get("party_gap", 0)
        signals.append({
            "type": "honeymoon",
            "detail": f"대통령 지지율 {approval}%, 정당 격차 민주+{party_gap}%p → 대통령효과 {honeymoon_score:+.1f}",
            "impact": round(honeymoon_component, 1),
        })
    honeymoon_component = max(-50, min(50, honeymoon_component))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 9. ECONOMIC SENTIMENT (-50 ~ +50)
    #    경남 경제 체감 → 도전자(김경수) 관점
    #    경제 나쁘면 현직 불리 = 도전자 유리 (+)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    economy_component = 0.0
    economic_data = economic_data or {}
    if economic_data:
        # incumbent_effect는 이미 도전자 관점 (현직 유리 = 마이너스)
        economy_component = economic_data.get("incumbent_effect", 0)
        emp_rate = economic_data.get("employment_rate", 0)
        cpi = economic_data.get("cpi_change", 0)
        sentiment = economic_data.get("economic_sentiment", 0)
        signals.append({
            "type": "economy",
            "detail": f"경남 경제 체감 {sentiment:+.1f} (고용률 {emp_rate}%, 물가 {cpi}%) → 도전자 영향 {economy_component:+.1f}",
            "impact": round(economy_component, 1),
        })
    economy_component = max(-50, min(50, economy_component))

    # COMPOSITE INDEX (v3: 9-component)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    weighted_sum = (
        issue_pressure          * W_ISSUE_PRESSURE
        + anomaly_signal        * W_ANOMALY_SIGNAL
        + reaction_momentum     * W_REACTION_MOMENTUM
        + social_velocity       * W_SOCIAL_VELOCITY
        + poll_inertia          * W_POLL_INERTIA
        + issue_index_component * W_ISSUE_INDEX
        + reaction_index_component * W_REACTION_INDEX
        + honeymoon_component   * W_HONEYMOON
        + economy_component     * W_ECONOMY
    )

    index = max(0, min(100, 50 + weighted_sum))

    # ── 방향 판정 ──
    if index >= 57:
        direction = "gaining"
    elif index <= 43:
        direction = "losing"
    else:
        direction = "stable"

    # ── 신뢰도 ──
    data_sources = 0
    if issue_scores:
        data_sources += 1
    if anomaly_results:
        data_sources += 1
    if unified_signals:
        data_sources += 1
    if polling_data.get("our_trend") is not None:
        data_sources += 1

    if data_sources >= 4:
        confidence = "high"
    elif data_sources >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    # ── 구성요소 dict ──
    components = {
        "issue_pressure":    round(issue_pressure, 1),
        "anomaly_signal":    round(anomaly_signal, 1),
        "reaction_momentum": round(reaction_momentum, 1),
        "social_velocity":   round(social_velocity, 1),
        "poll_inertia":      round(poll_inertia, 1),
        "issue_index":       round(issue_index_component, 1),
        "reaction_index":    round(reaction_index_component, 1),
        "honeymoon":         round(honeymoon_component, 1),
        "economy":           round(economy_component, 1),
    }
    if event_context.get("event_type"):
        components["event_context"] = event_context["event_type"]

    # ── primary_driver ──
    abs_components = {k: abs(v) for k, v in components.items()}
    primary_driver = max(abs_components, key=abs_components.get) if abs_components else ""

    # ── 예측 힌트 ──
    if direction == "gaining":
        predicted_direction = "우리 지지율 상승 예상"
        predicted_magnitude = round(max(0.5, min(3.0, (index - 50) * 0.15)), 1)
    elif direction == "losing":
        predicted_direction = "하락 주의"
        predicted_magnitude = round(max(0.5, min(3.0, (50 - index) * 0.15)), 1)
    else:
        predicted_direction = "변동 미미"
        predicted_magnitude = 0.0

    # ── Gap 3: 스냅샷 비교 ──
    previous_index = 50.0
    index_delta = 0.0
    trend_description = ""

    prev_snapshot = get_leading_snapshot(tenant_id) if tenant_id else None
    if prev_snapshot:
        previous_index = prev_snapshot.index
        index_delta = round(index - previous_index, 1)
        prev_dir = prev_snapshot.direction

        if index_delta > 5:
            if prev_dir == "losing":
                trend_description = "하락→반등 전환"
            else:
                trend_description = "상승 가속"
        elif index_delta < -5:
            if prev_dir == "gaining":
                trend_description = "상승→하락 전환"
            else:
                trend_description = "하락 가속"
        elif abs(index_delta) <= 2:
            trend_description = "횡보 유지"
        else:
            trend_description = "소폭 변동"

        # 추세 전환 감지 시그널
        if "전환" in trend_description:
            signals.append({
                "type": "trend",
                "detail": f"선행지수 추세 전환: {previous_index:.0f}→{index:.0f} ({trend_description})",
                "impact": index_delta,
            })

    # ── explanation_text ──
    _DRIVER_NAMES = {
        "issue_pressure": "이슈 압력",
        "anomaly_signal": "이상 급등",
        "reaction_momentum": "반응 모멘텀",
        "social_velocity": "소셜 변화",
        "poll_inertia": "여론 관성",
    }
    driver_name = _DRIVER_NAMES.get(primary_driver, primary_driver)
    driver_value = components.get(primary_driver, 0)
    driver_dir = "긍정" if driver_value > 0 else "부정"

    top_signals_text = ""
    sorted_sigs = sorted(signals, key=lambda s: abs(s.get("impact", 0)), reverse=True)
    if sorted_sigs:
        top_details = [s["detail"] for s in sorted_sigs[:2]]
        top_signals_text = " + ".join(top_details)

    explanation_text = (
        f"선행지수 {index:.0f} ({direction}): "
        f"주요인 {driver_name}({driver_dir}) "
    )
    if top_signals_text:
        explanation_text += f"| {top_signals_text}"
    if predicted_magnitude > 0:
        explanation_text += f" → {predicted_direction} (±{predicted_magnitude}%p)"
    if trend_description:
        explanation_text += f" [{trend_description}]"

    result = LeadingIndex(
        index=round(index, 1),
        direction=direction,
        confidence=confidence,
        components=components,
        explanation_text=explanation_text,
        primary_driver=primary_driver,
        signals=sorted_sigs[:10],
        predicted_direction=predicted_direction,
        predicted_magnitude=predicted_magnitude,
        previous_index=round(previous_index, 1),
        index_delta=index_delta,
        trend_description=trend_description,
    )

    # Gap 3: 스냅샷 자동 업데이트
    if tenant_id:
        save_leading_snapshot(tenant_id, result)

    return result
