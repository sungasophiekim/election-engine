"""
Election Strategy Engine — Reaction Attribution (v3)
후보 행동과 반응 시그널을 연결하는 귀인(attribution) 모듈.

Attribution chain:
  candidate action → issue movement (before/after delta)
  → community/SNS reaction depth → regional concentration
  → poll linkage (실제 여론조사 연동)

기존 모듈 데이터를 최대한 재활용합니다.
"""
from dataclasses import dataclass, field
from datetime import datetime


# ── 모듈 수준 스냅샷 저장소 ───────────────────────────────────────
# 이전 수집 시점의 반응 상태를 저장하여 before/after 비교.
# naver_news.py의 _last_collection_meta 패턴과 동일.
_reaction_snapshots: dict = {}  # {keyword: {"grade": str, "volume": int, "engagement": float, "ts": str}}


def save_reaction_snapshot(keyword: str, grade: str, volume: int, engagement: float):
    """현재 반응 상태를 스냅샷으로 저장. 다음 attribution 실행 시 before로 사용."""
    _reaction_snapshots[keyword] = {
        "grade": grade,
        "volume": volume,
        "engagement": engagement,
        "ts": datetime.now().isoformat(),
    }


def get_reaction_snapshot(keyword: str) -> dict:
    """이전 스냅샷 반환. 없으면 빈 dict."""
    return _reaction_snapshots.get(keyword, {})


# ── 데이터 구조 ───────────────────────────────────────────────────

@dataclass
class CandidateAction:
    """후보의 능동적 행동 (SNS 게시, 현장 방문, 공약 발표 등)"""
    action_type: str          # "sns_post" | "visit" | "speech" | "policy" | "press"
    description: str          # 행동 요약
    region: str = ""          # 행동이 일어난 지역 ("" = 전국/온라인)
    themes: list = field(default_factory=list)   # 관련 테마 ["경제", "교통"]
    keywords: list = field(default_factory=list)  # 관련 키워드 ["일자리", "BRT"]
    timestamp: str = ""       # ISO format 또는 time_slot
    source: str = ""          # "owned_channel" | "schedule" | "strategy"
    engagement: int = 0       # 참여 지표 (조회수, 좋아요 등)


@dataclass
class Attribution:
    """행동-반응 귀인 결과"""
    action: CandidateAction
    keyword: str              # 연결된 이슈 키워드

    # before/after 상태 변화
    reaction_grade_before: str = ""  # 이전 스냅샷의 grade
    reaction_grade_after: str = ""   # 현재 grade
    volume_before: int = 0
    volume_after: int = 0
    reaction_delta: float = 0.0     # volume_after - volume_before (양수=증가)

    # 반응 깊이 (ReactionSummary에서)
    community_resonance: float = 0.0  # 커뮤니티 확산도
    has_viral: bool = False           # 바이럴 감지
    net_sentiment: float = 0.0       # -1~1

    # 지역 집중도
    region_concentration: str = ""   # 반응이 집중된 지역
    region_intensity: float = 0.0    # 0~1, 해당 지역 반응 집중도

    # 신뢰도
    confidence: float = 0.0   # 귀인 신뢰도 0~1

    # 여론조사 연결
    poll_linkage_hint: str = ""       # 텍스트 힌트
    poll_region_delta: float = 0.0    # 실제 여론조사 지역별 변화 (있을 경우)
    poll_validated: bool = False      # 여론조사 데이터로 검증 완료 여부


@dataclass
class AttributionSummary:
    """전체 귀인 분석 요약"""
    total_actions: int = 0
    attributed_count: int = 0     # 반응과 연결된 행동 수
    top_attributions: list = field(default_factory=list)  # list[Attribution]
    unlinked_reactions: list = field(default_factory=list)  # 행동 없이 발생한 반응 키워드
    poll_watch_regions: list = field(default_factory=list)  # 여론조사 주시 지역
    # v3 추가
    movement_detected: list = field(default_factory=list)  # 등급 변화가 감지된 키워드
    strongest_linkage: str = ""  # 가장 강한 귀인 요약 문장


# ── 지역명 추출용 ─────────────────────────────────────────────────
_GYEONGNAM_REGIONS = [
    "창원", "김해", "진주", "거제", "통영", "양산", "밀양",
    "사천", "함안", "거창", "합천", "하동", "남해", "산청",
    "함양", "의령", "고성", "창녕",
]


# ── 의미적 테마 그룹 (v4) ────────────────────────────────────────
# 같은 그룹 내 테마는 매칭 가능 (예: "경제" action → "일자리" reaction)
THEME_GROUPS = {
    "경제": ["경제", "일자리", "고용", "물가", "부동산", "조선업", "방산", "산업", "투자", "성장"],
    "복지": ["복지", "지원금", "의료", "간병", "보육", "돌봄", "노인", "저출생", "연금"],
    "교통": ["교통", "BRT", "철도", "KTX", "광역교통", "도로", "버스"],
    "청년": ["청년", "대학", "취업", "주거", "인구", "정주", "청년층"],
    "교육": ["교육", "학교", "입시", "교육청", "대학", "유치원"],
    "환경": ["환경", "기후", "탄소", "에너지", "재생", "오염"],
    "안전": ["안전", "재난", "범죄", "치안", "소방"],
    "행정": ["행정", "도정", "공무원", "예산", "재정", "세금"],
    "지역": ["지역", "균형", "소외", "격차", "분권", "자치"],
}

# 테마 → 그룹 역방향 매핑 (빠른 조회용)
_THEME_TO_GROUP = {}
for _grp, _themes in THEME_GROUPS.items():
    for _t in _themes:
        _THEME_TO_GROUP[_t] = _grp


def _semantic_theme_match(action_themes: set, reaction_themes: set) -> float:
    """의미적 테마 매칭 (같은 그룹이면 매칭)."""
    if not action_themes or not reaction_themes:
        return 0.0

    # 직접 매칭
    direct = len(action_themes & reaction_themes)
    if direct > 0:
        return min(1.0, direct / max(len(action_themes), 1))

    # 같은 그룹 매칭
    action_groups = {_THEME_TO_GROUP.get(t, t) for t in action_themes}
    reaction_groups = {_THEME_TO_GROUP.get(t, t) for t in reaction_themes}
    group_overlap = len(action_groups & reaction_groups)
    if group_overlap > 0:
        return min(0.8, group_overlap / max(len(action_groups), 1))  # 직접보다 약간 낮게

    return 0.0


def _time_decay_weight(action_timestamp: str, snapshot_ts: str = "") -> float:
    """행동-반응 시간 차이에 따른 가중치 (72시간 이내만 유효)."""
    if not action_timestamp:
        return 0.7  # 타임스탬프 없으면 중간값

    try:
        from datetime import timezone
        now = datetime.now()

        # 다양한 포맷 파싱
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                action_dt = datetime.strptime(action_timestamp[:19], fmt[:len(action_timestamp[:19])])
                break
            except ValueError:
                continue
        else:
            return 0.7

        hours = (now - action_dt).total_seconds() / 3600
        if hours < 0:
            hours = 0

        # 0h → 1.0, 24h → 0.67, 48h → 0.33, 72h+ → 0.2
        weight = max(0.2, 1.0 - (hours / 72))
        return round(weight, 2)

    except Exception:
        return 0.7


class ReactionAttributor:
    """
    후보 행동 → 반응 시그널 귀인 엔진.
    기존 모듈의 데이터를 받아서 action-reaction 연결을 수행.

    v4: 시간 가중(time_decay) + 의미적 테마 매칭(semantic_theme) 추가.
    """

    def __init__(self, candidate_name: str = "", regions: dict = None):
        self.candidate_name = candidate_name
        self.regions = regions or {}

    # ── 행동 추출 ─────────────────────────────────────────────────

    def extract_actions_from_channels(self, channel_metrics: list) -> list[CandidateAction]:
        """
        owned_channels.py의 ChannelMetrics에서 후보 행동 추출.
        top_content의 각 항목이 하나의 action.
        """
        actions = []
        for m in channel_metrics:
            if not m.top_content:
                continue

            channel_themes = list(m.message_themes) if hasattr(m, 'message_themes') and m.message_themes else []

            for content in m.top_content:
                title = content.get("title", "")
                if not title:
                    continue

                # 지역 추출: 제목에서 경남 지역명 검색
                action_region = ""
                for rn in _GYEONGNAM_REGIONS:
                    if rn in title:
                        action_region = rn
                        break

                actions.append(CandidateAction(
                    action_type="sns_post",
                    description=title,
                    region=action_region,
                    themes=channel_themes,
                    keywords=[w for w in title.split() if len(w) >= 2][:5],
                    source="owned_channel",
                    engagement=content.get("views", 0) or content.get("engagement", 0),
                    timestamp=m.last_updated or "",
                ))

        return actions

    def extract_actions_from_schedule(self, schedule_events: list) -> list[CandidateAction]:
        """
        schedule_optimizer.py의 ScheduleEvent에서 후보 행동 추출.
        이동 이벤트 제외.
        """
        actions = []
        for ev in schedule_events:
            if ev.event_type == "이동":
                continue

            keywords = []
            for tp in (ev.talking_points or []):
                keywords.extend([w for w in tp.split() if len(w) >= 2][:3])

            # event_type → action_type 매핑
            if "방문" in ev.event_type or "시장" in ev.event_type:
                atype = "visit"
            elif "간담회" in ev.event_type:
                atype = "speech"
            elif "기자회견" in ev.event_type:
                atype = "press"
            else:
                atype = "speech"

            actions.append(CandidateAction(
                action_type=atype,
                description=f"{ev.region} {ev.event_type}: {ev.notes or ''}",
                region=ev.region.replace("시", "") if ev.region else "",  # "창원시" → "창원"
                themes=[],
                keywords=keywords[:5],
                source="schedule",
                timestamp=ev.time_slot,
            ))

        return actions

    def extract_actions_from_strategy(self, daily_strategy) -> list[CandidateAction]:
        """
        strategy_synthesizer.py의 DailyStrategy에서 전략적 행동 추출.
        issues_to_push, region_schedule → 의도된 행동.
        """
        actions = []

        for issue_kw in (daily_strategy.issues_to_push or []):
            actions.append(CandidateAction(
                action_type="policy",
                description=f"이슈 선점: {issue_kw}",
                keywords=[issue_kw],
                source="strategy",
            ))

        for r in (daily_strategy.region_schedule or []):
            region = r.get("region", "")
            tps = r.get("talking_points", [])
            keywords = []
            for tp in tps:
                keywords.extend([w for w in tp.split() if len(w) >= 2][:2])
            actions.append(CandidateAction(
                action_type="visit",
                description=f"{region} 유세 ({r.get('reason', '')})",
                region=region.replace("시", "") if region else "",
                keywords=keywords[:5],
                source="strategy",
            ))

        return actions

    # ── 귀인 매칭 ─────────────────────────────────────────────────

    def attribute_reactions(
        self,
        actions: list[CandidateAction],
        unified_signals: list,    # list[UnifiedSignal]
        polling_data: dict = None,  # from PollingTracker.calculate_win_probability()
        opponent_actions: list[CandidateAction] = None,  # v4: 상대 행동 (동시 발생 할인용)
    ) -> list[Attribution]:
        """
        행동과 반응 시그널을 매칭하여 귀인 생성.

        신뢰도 계산:
          keyword_match  * 0.30  — 키워드 겹침
          theme_match    * 0.15  — 테마 겹침
          region_match   * 0.15  — 지역 일치
          reaction_depth * 0.25  — 반응 깊이 (community_resonance, viral, sentiment)
          hint_match     * 0.15  — attribution_hints 사전 매칭

        threshold: 0.25 이상이어야 귀인 생성
        """
        polling_data = polling_data or {}
        opponent_actions = opponent_actions or []
        region_breakdown = polling_data.get("region_breakdown", {})
        attributions = []

        # v4: 상대 행동 키워드 집합 (동시 발생 할인용)
        opponent_keyword_set = set()
        for opp_act in opponent_actions:
            opponent_keyword_set.update(opp_act.keywords)
            for t in opp_act.themes:
                opponent_keyword_set.add(t)

        for action in actions:
            action_theme_set = set(action.themes)

            for sig in unified_signals:
                # ── 1. keyword match ──
                kw_match = 0.0
                if action.keywords:
                    for akw in action.keywords:
                        if akw in sig.keyword or sig.keyword in akw:
                            kw_match = 1.0
                            break

                # ── 2. theme match (v4: 의미적 그룹 매칭) ──
                sig_themes = set()
                rxn = getattr(sig, 'reaction', None)
                if rxn:
                    sig_themes.update(rxn.blog_themes or [])
                    sig_themes.update(rxn.cafe_themes or [])
                    sig_themes.update(rxn.owned_themes or [])
                theme_match = _semantic_theme_match(action_theme_set, sig_themes)

                # ── 3. region match ──
                sig_region = ""
                if sig.issue_signal and sig.issue_signal.region:
                    sig_region = sig.issue_signal.region
                region_match = 0.0
                if action.region and sig_region:
                    if action.region in sig_region or sig_region in action.region:
                        region_match = 1.0

                # ── 4. reaction depth ──
                depth_score = 0.0
                community_res = 0.0
                has_viral = False
                net_sent = 0.0
                if rxn:
                    # 커뮤니티 공명도 (0~1) → 깊이 기여
                    community_res = rxn.community_resonance
                    depth_score += min(0.4, community_res)
                    # 바이럴 감지 → +0.2
                    has_viral = rxn.community_has_viral
                    if has_viral:
                        depth_score += 0.2
                    # 뉴스 다양성 (5곳 이상 → 0.2)
                    if rxn.news_source_diversity >= 5:
                        depth_score += 0.2
                    elif rxn.news_source_diversity >= 3:
                        depth_score += 0.1
                    # 시간 집중도 (최근 6h 비중 높으면 → 방금 터진 이슈)
                    if rxn.news_temporal_cluster >= 0.5:
                        depth_score += 0.1
                    # 방어기사 존재 → 논쟁 활성화
                    if rxn.news_defense_active:
                        depth_score += 0.1
                    # net_sentiment 극단값
                    net_sent = rxn.news_net_sentiment
                    if abs(net_sent) >= 0.5:
                        depth_score += 0.1

                    depth_score = min(1.0, depth_score)

                # ── 5. attribution_hints 사전 매칭 ──
                hint_match = 0.0
                for hint in getattr(sig, 'attribution_hints', []):
                    hint_action = hint.get("action", "")
                    # 힌트의 action 텍스트가 현재 action과 겹치면 가중
                    if hint_action and action.description:
                        if hint_action in action.description or action.description[:20] in hint_action:
                            hint_match = max(hint_match, hint.get("confidence", 0.5))

                # ── 종합 신뢰도 (v4: 시간 가중 적용) ──
                raw_confidence = (
                    kw_match    * 0.30
                    + theme_match * 0.15
                    + region_match * 0.15
                    + depth_score * 0.25
                    + hint_match  * 0.15
                )

                # 시간 가중: 행동 직후 반응일수록 귀인 신뢰도 높음
                time_weight = _time_decay_weight(action.timestamp)
                confidence = raw_confidence * time_weight

                # v4: Counter-Attribution — 상대 행동과 동시 발생 시 할인
                counter_discount = 1.0
                if opponent_keyword_set:
                    # 이 반응 키워드가 상대 행동과도 연관되면 귀인 불확실
                    opp_overlap = any(
                        okw in sig.keyword or sig.keyword in okw
                        for okw in opponent_keyword_set
                    )
                    if opp_overlap:
                        counter_discount = 0.6  # 40% 할인
                        # 상대 테마와도 겹치면 추가 할인
                        sig_themes_flat = set()
                        if rxn:
                            sig_themes_flat.update(rxn.blog_themes or [])
                            sig_themes_flat.update(rxn.cafe_themes or [])
                        opp_theme_overlap = any(t in opponent_keyword_set for t in sig_themes_flat)
                        if opp_theme_overlap:
                            counter_discount = 0.4  # 60% 할인

                confidence *= counter_discount

                # 최소 기준: 신뢰도 0.20 이상 AND 키워드/테마/지역 중 1개 이상 매칭
                direct_match = kw_match + theme_match + region_match
                if confidence < 0.20 or direct_match == 0:
                    continue

                # ── before/after 비교 ──
                snapshot = get_reaction_snapshot(sig.keyword)
                grade_before = snapshot.get("grade", "")
                volume_before = snapshot.get("volume", 0)

                grade_after = rxn.reaction_grade if rxn else ""
                volume_after = sig.issue_signal.reaction_volume if sig.issue_signal else 0

                reaction_delta = float(volume_after - volume_before)

                # ── 지역 집중도 ──
                region_intensity = 0.0
                if sig_region:
                    # 커뮤니티 공명도를 지역 집중도 프록시로 사용
                    region_intensity = community_res
                    # 해당 지역의 반응이 전체 대비 높으면 가중
                    if sig.issue_signal and sig.issue_signal.reaction_volume > 0:
                        region_intensity = min(1.0, region_intensity + 0.3)

                # ── poll linkage ──
                poll_hint = ""
                poll_delta = 0.0
                poll_validated = False
                target_region = action.region or sig_region
                if target_region and confidence >= 0.4:
                    poll_hint = (
                        f"'{action.description[:30]}' 이후 "
                        f"{target_region} 지지율 변화 관찰 필요"
                    )
                    # 실제 여론조사 지역 데이터가 있으면 검증
                    if region_breakdown and target_region in str(region_breakdown):
                        for rk, rv in region_breakdown.items():
                            if target_region in rk:
                                # rv가 우리 지지율이면 gap과 비교
                                our_avg = polling_data.get("our_avg", 0)
                                if our_avg > 0 and rv > 0:
                                    poll_delta = round(rv - our_avg, 2)
                                    poll_validated = True
                                    poll_hint = (
                                        f"'{action.description[:30]}' → "
                                        f"{target_region} 지지율 {rv}% "
                                        f"(전체 평균 대비 {poll_delta:+.1f}%p)"
                                    )
                                break

                attributions.append(Attribution(
                    action=action,
                    keyword=sig.keyword,
                    reaction_grade_before=grade_before,
                    reaction_grade_after=grade_after,
                    volume_before=volume_before,
                    volume_after=volume_after,
                    reaction_delta=reaction_delta,
                    community_resonance=community_res,
                    has_viral=has_viral,
                    net_sentiment=net_sent,
                    region_concentration=sig_region,
                    region_intensity=round(region_intensity, 2),
                    confidence=round(confidence, 2),
                    poll_linkage_hint=poll_hint,
                    poll_region_delta=poll_delta,
                    poll_validated=poll_validated,
                ))

        # 신뢰도 내림차순 정렬
        attributions.sort(key=lambda a: a.confidence, reverse=True)

        # ── 스냅샷 갱신 (다음 실행의 before 용도) ──
        for sig in unified_signals:
            rxn = getattr(sig, 'reaction', None)
            vol = sig.issue_signal.reaction_volume if sig.issue_signal else 0
            grade = rxn.reaction_grade if rxn else ""
            eng = sig.issue_signal.engagement_score if sig.issue_signal else 0.0
            save_reaction_snapshot(sig.keyword, grade, vol, eng)

        return attributions

    # ── 요약 생성 ─────────────────────────────────────────────────

    def build_summary(
        self,
        actions: list[CandidateAction],
        attributions: list[Attribution],
        unified_signals: list,
    ) -> AttributionSummary:
        """전체 귀인 분석 요약 생성."""
        attributed_keywords = {a.keyword for a in attributions}

        # 행동 없이 발생한 HOT/WARM 반응
        unlinked = []
        for sig in unified_signals:
            if sig.keyword not in attributed_keywords:
                rxn = getattr(sig, 'reaction', None)
                if rxn and rxn.reaction_grade in ("HOT", "WARM"):
                    unlinked.append(sig.keyword)

        # 등급 변화 감지
        movement = []
        _GRADE_RANK = {"COLD": 0, "COOL": 1, "WARM": 2, "HOT": 3}
        for a in attributions:
            before_rank = _GRADE_RANK.get(a.reaction_grade_before, -1)
            after_rank = _GRADE_RANK.get(a.reaction_grade_after, -1)
            if before_rank >= 0 and after_rank > before_rank:
                movement.append(
                    f"{a.keyword}: {a.reaction_grade_before}→{a.reaction_grade_after}"
                )

        # poll watch regions
        poll_regions = set()
        for a in attributions:
            if a.confidence >= 0.4 and a.region_concentration:
                poll_regions.add(a.region_concentration)

        # 가장 강한 귀인 요약
        strongest = ""
        if attributions:
            top = attributions[0]
            parts = [f"'{top.action.description[:30]}' → '{top.keyword}'"]
            parts.append(f"신뢰도 {top.confidence:.0%}")
            if top.reaction_delta > 0:
                parts.append(f"반응 +{top.reaction_delta:.0f}")
            if top.region_concentration:
                parts.append(f"집중: {top.region_concentration}")
            if top.poll_validated:
                parts.append(f"여론조사 검증됨")
            strongest = " | ".join(parts)

        return AttributionSummary(
            total_actions=len(actions),
            attributed_count=len(attributed_keywords),
            top_attributions=attributions[:10],
            unlinked_reactions=unlinked,
            poll_watch_regions=sorted(poll_regions),
            movement_detected=movement,
            strongest_linkage=strongest,
        )
