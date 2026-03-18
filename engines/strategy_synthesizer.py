"""
Election Strategy Engine — Engine 7: Strategy Synthesizer
모든 엔진 결과를 종합하여 일일 전략을 산출합니다.
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum

from config.tenant_config import TenantConfig
from models.schemas import IssueScore, CrisisLevel, OpponentSignal, VoterSegment


class CampaignMode(Enum):
    ATTACK = "공격"       # We're behind -> aggressive messaging, highlight opponent weaknesses
    DEFENSE = "수비"      # We're ahead -> protect lead, avoid mistakes, stay on message
    INITIATIVE = "선점"   # Too close to call -> seize agenda, define the narrative
    CRISIS = "위기대응"   # Crisis issue detected -> all hands on crisis management


@dataclass
class DailyStrategy:
    """일일 전략 산출물"""
    date: str
    campaign_mode: CampaignMode
    mode_reasoning: str              # why this mode

    # 핵심 지시
    top_priority: str                # 오늘의 최우선 과제 (1문장)
    key_messages: list[str]          # 오늘 반복할 핵심 메시지 3개

    # 자원 배분
    region_schedule: list[dict]      # [{"region": "창원시", "priority": 1, "reason": "...", "talking_points": [...]}]

    # 상대 대응
    opponent_actions: list[dict]     # [{"opponent": "김경수", "action": "모니터링"|"반박"|"선제공격", "detail": "..."}]

    # 이슈 대응
    issues_to_push: list[str]        # 우리가 밀어야 할 이슈
    issues_to_avoid: list[str]       # 피해야 할 이슈
    issues_to_counter: list[str]     # 반박해야 할 이슈

    # 리스크
    risk_level: str                  # "낮음" | "보통" | "높음" | "매우높음"
    risk_factors: list[str]

    # 메타
    win_probability: float           # 0.0~1.0
    days_left: int
    confidence: str                  # "high" | "medium" | "low"


class StrategySynthesizer:
    """
    모든 엔진 결과를 종합하여 일일 전략을 생성합니다.
    Claude API 없이 순수 로직으로 작동합니다.
    """

    def __init__(self, config: TenantConfig):
        self.config = config

    # ------------------------------------------------------------------
    # 유틸리티
    # ------------------------------------------------------------------
    def _days_until_election(self) -> int:
        try:
            election_date = datetime.strptime(self.config.election_date, "%Y-%m-%d").date()
            return max(0, (election_date - date.today()).days)
        except Exception:
            return 90

    # ------------------------------------------------------------------
    # 핵심 메서드
    # ------------------------------------------------------------------
    def synthesize(
        self,
        issue_scores: list[IssueScore] = None,
        opponent_signals: list[OpponentSignal] = None,
        voter_segments: list[VoterSegment] = None,
        polling_data: dict = None,       # from PollingTracker.calculate_win_probability()
        attack_points: list[dict] = None,  # from PledgeComparator.find_attack_points()
        defense_points: list[dict] = None, # from PledgeComparator.find_defense_points()
    ) -> DailyStrategy:
        """
        핵심 메서드: 모든 입력을 종합하여 DailyStrategy를 생성.
        """
        issue_scores = issue_scores or []
        opponent_signals = opponent_signals or []
        voter_segments = voter_segments or []
        polling_data = polling_data or {}
        attack_points = attack_points or []
        defense_points = defense_points or []

        days_left = self._days_until_election()

        # 1. 캠페인 모드 결정 — 가장 중요한 의사결정
        mode, mode_reasoning = self._determine_campaign_mode(
            polling_data, issue_scores, days_left
        )

        # 2. 핵심 메시지 생성
        key_messages = self._generate_key_messages(
            mode, issue_scores, attack_points, defense_points
        )

        # 3. 지역별 유세 배분
        region_schedule = self._allocate_regions(
            voter_segments, mode, attack_points, days_left
        )

        # 4. 이슈 전략 분류
        issues_to_push, issues_to_avoid, issues_to_counter = self._determine_issue_strategy(
            issue_scores, mode
        )

        # 5. 상대 대응 전략
        opponent_actions = self._determine_opponent_actions(
            opponent_signals, mode, attack_points
        )

        # 6. 리스크 평가
        risk_level, risk_factors = self._assess_risk(
            issue_scores, opponent_signals, polling_data
        )

        # 7. 최우선 과제 결정
        top_priority = self._determine_top_priority(
            mode, risk_level, region_schedule, issues_to_push, days_left
        )

        # 8. 승률 / 신뢰도
        win_prob = polling_data.get("win_prob", 0.5)
        confidence = polling_data.get("confidence", "low")

        return DailyStrategy(
            date=datetime.now().strftime("%Y-%m-%d"),
            campaign_mode=mode,
            mode_reasoning=mode_reasoning,
            top_priority=top_priority,
            key_messages=key_messages,
            region_schedule=region_schedule,
            opponent_actions=opponent_actions,
            issues_to_push=issues_to_push,
            issues_to_avoid=issues_to_avoid,
            issues_to_counter=issues_to_counter,
            risk_level=risk_level,
            risk_factors=risk_factors,
            win_probability=win_prob,
            days_left=days_left,
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # 캠페인 모드 결정
    # ------------------------------------------------------------------
    def _determine_campaign_mode(
        self,
        polling_data: dict,
        issue_scores: list[IssueScore],
        days_left: int,
    ) -> tuple[CampaignMode, str]:
        """
        캠페인 모드 결정 로직:

        1. CRISIS: 이슈 중 CRISIS 레벨이 있고, candidate_linked인 경우
        2. ATTACK: 여론조사에서 뒤지고 있을 때 (gap < -2)
        3. DEFENSE: 여론조사에서 앞서고 있을 때 (gap > 3)
        4. INITIATIVE: 초박빙 (-2 <= gap <= 3) 또는 데이터 불확실

        D-14 이내: 더 공격적으로 조정
        - DEFENSE -> INITIATIVE (리드가 5%p 이상이 아니면)
        - INITIATIVE -> ATTACK (뒤지고 있으면 무조건)
        """
        # 1. CRISIS 체크 — 후보에게 부정적인 위기 이슈만 해당
        # 단순히 후보 이름이 뉴스에 나오는 것은 위기가 아님.
        # 후보 이름 + 높은 부정 비율(30%+) = 진짜 위기
        candidate_name = self.config.candidate_name
        for issue in issue_scores:
            if issue.level == CrisisLevel.CRISIS and candidate_name in issue.keyword:
                neg_ratio = issue.breakdown.get("sentiment_score", 0) / 15.0  # 0~1 복원
                if neg_ratio >= 0.30:
                    return (
                        CampaignMode.CRISIS,
                        f"위기 이슈 감지: '{issue.keyword}' (점수 {issue.score:.1f},"
                        f" 부정 {neg_ratio:.0%}) — 즉시 위기대응 모드 진입."
                    )

        gap = polling_data.get("gap", 0.0)
        our_avg = polling_data.get("our_avg", 0.0)
        assessment = polling_data.get("assessment", "")

        # 2~4. 여론조사 기반 모드 결정
        if gap < -2:
            mode = CampaignMode.ATTACK
            reasoning = (
                f"여론조사 {abs(gap):.1f}%p 열세 — 공격 모드. "
                f"우리 {our_avg:.1f}% 상대 선두와 격차를 줄여야 함."
            )
        elif gap > 3:
            mode = CampaignMode.DEFENSE
            reasoning = (
                f"여론조사 {gap:.1f}%p 리드 — 수비 모드. "
                f"실점 방지, 안정적 메시지 반복으로 리드 유지."
            )
        else:
            mode = CampaignMode.INITIATIVE
            reasoning = (
                f"초박빙 접전 (격차 {gap:+.1f}%p) — 선점 모드. "
                f"의제를 선점하여 유리한 프레임을 만들어야 함."
            )

        # D-14 이내: 공격적 조정
        if days_left <= 14:
            if mode == CampaignMode.DEFENSE and gap < 5:
                mode = CampaignMode.INITIATIVE
                reasoning += (
                    f" [D-{days_left} 조정] 리드가 5%p 미만이므로 "
                    f"수비에서 선점으로 상향. 막판에는 적극적으로."
                )
            elif mode == CampaignMode.INITIATIVE and gap < 0:
                mode = CampaignMode.ATTACK
                reasoning += (
                    f" [D-{days_left} 조정] 뒤지고 있으므로 "
                    f"선점에서 공격으로 전환. 반전이 필요한 시점."
                )

        return mode, reasoning

    # ------------------------------------------------------------------
    # 핵심 메시지 생성
    # ------------------------------------------------------------------
    def _generate_key_messages(
        self,
        mode: CampaignMode,
        issue_scores: list[IssueScore],
        attack_points: list[dict],
        defense_points: list[dict],
    ) -> list[str]:
        """
        모드별 핵심 메시지 3개 생성.

        ATTACK mode:
          1. 상대 약점 공격 메시지
          2. 우리 차별화 포인트
          3. 변화/비전 메시지

        DEFENSE mode:
          1. 현 성과 강조
          2. 안정/지속 메시지
          3. 우리 핵심 공약 반복

        INITIATIVE mode:
          1. 의제 선점 메시지 (가장 유리한 이슈)
          2. 우리 핵심 공약
          3. 비전/미래 메시지

        CRISIS mode:
          1. 위기 이슈 직접 대응
          2. 이슈 전환 메시지
          3. 핵심 메시지 반복 (흔들리지 않음)
        """
        messages = []
        candidate = self.config.candidate_name
        slogan = self.config.slogan
        core_msg = self.config.core_message

        # 가장 유리한 공격 포인트
        best_attack = attack_points[0] if attack_points else None
        # 가장 큰 방어 필요 포인트
        best_defense = defense_points[0] if defense_points else None
        # 가장 뜨거운 이슈 (후보 무관)
        hottest_issue = issue_scores[0] if issue_scores else None

        # 우리 핵심 공약 중 첫 번째
        pledge_names = list(self.config.pledges.keys())
        top_pledge = pledge_names[0] if pledge_names else "핵심 공약"
        top_pledge_detail = ""
        if pledge_names:
            p = self.config.pledges[top_pledge]
            top_pledge_detail = p.get("수치", "")

        if mode == CampaignMode.ATTACK:
            # 1. 공격
            if best_attack:
                messages.append(
                    f"[공격] {best_attack['target']}의 '{best_attack['pledge']}' — "
                    f"{best_attack['talking_point']}"
                )
            else:
                messages.append(f"[공격] 상대 후보의 실적 부재를 부각하라")
            # 2. 차별화
            messages.append(
                f"[차별화] {candidate}의 {top_pledge}: {top_pledge_detail} — "
                f"구체적 수치로 차이를 보여라"
            )
            # 3. 비전
            messages.append(
                f"[비전] '{slogan}' — 변화가 필요한 이유를 도민 삶으로 설명하라"
            )

        elif mode == CampaignMode.DEFENSE:
            # 1. 성과
            messages.append(
                f"[성과] {candidate}의 현장 경험과 준비된 리더십을 강조하라"
            )
            # 2. 안정
            messages.append(
                f"[안정] 흔들림 없는 정책 실행력 — '{core_msg}'"
            )
            # 3. 공약 반복
            messages.append(
                f"[공약] {top_pledge} ({top_pledge_detail}) — 반복하여 각인시켜라"
            )

        elif mode == CampaignMode.INITIATIVE:
            # 1. 의제 선점
            if hottest_issue and candidate not in hottest_issue.keyword:
                messages.append(
                    f"[선점] '{hottest_issue.keyword}' 이슈를 우리 프레임으로 — "
                    f"먼저 해법을 제시하라"
                )
            else:
                messages.append(
                    f"[선점] 가장 뜨거운 의제를 우리가 먼저 정의하라 — "
                    f"프레임 싸움에서 이겨야 한다"
                )
            # 2. 핵심 공약
            messages.append(
                f"[공약] {top_pledge} ({top_pledge_detail}) — "
                f"숫자로 말하고 비전으로 마무리하라"
            )
            # 3. 미래 비전
            messages.append(
                f"[비전] '{slogan}' — 도민의 미래를 우리가 책임진다는 확신을 줘라"
            )

        elif mode == CampaignMode.CRISIS:
            # 1. 위기 직접 대응
            crisis_issues = [i for i in issue_scores if i.level == CrisisLevel.CRISIS]
            if crisis_issues:
                ci = crisis_issues[0]
                messages.append(
                    f"[대응] '{ci.keyword}' 이슈에 대해 즉시 입장을 밝혀라 — "
                    f"침묵은 인정이다"
                )
            else:
                messages.append("[대응] 위기 이슈에 대해 선제적으로 입장을 밝혀라")
            # 2. 이슈 전환
            messages.append(
                f"[전환] 위기 대응 후 즉시 {top_pledge} 의제로 전환하라 — "
                f"우리의 강점 영역으로 돌아와야 한다"
            )
            # 3. 핵심 반복
            messages.append(
                f"[일관] '{core_msg}' — 흔들리지 않는 모습을 보여라. "
                f"위기에도 원칙은 변하지 않는다"
            )

        return messages

    # ------------------------------------------------------------------
    # 지역 배분
    # ------------------------------------------------------------------
    def _allocate_regions(
        self,
        voter_segments: list[VoterSegment],
        mode: CampaignMode,
        attack_points: list[dict],
        days_left: int,
    ) -> list[dict]:
        """
        지역별 유세 우선순위 + 토킹포인트.
        상위 3개 지역에 대해:
        - region, priority rank, reason
        - talking_points: 해당 지역 key_issue와 연관된 공약/공격 포인트
        """
        if not voter_segments:
            return []

        # 우선순위 정렬 (priority_score 내림차순)
        sorted_segments = sorted(voter_segments, key=lambda s: s.priority_score, reverse=True)
        top_regions = sorted_segments[:3]

        # 지역 설정 정보 참조
        region_config = self.config.regions

        # 공격 포인트를 지역별로 매핑
        region_attacks: dict[str, list[str]] = {}
        for ap in attack_points:
            for r in ap.get("regions", []):
                if r == "전체":
                    for rn in region_config:
                        region_attacks.setdefault(rn, []).append(ap["talking_point"])
                else:
                    region_attacks.setdefault(r, []).append(ap["talking_point"])

        schedule = []
        for rank, seg in enumerate(top_regions, 1):
            region_name = seg.region
            r_info = region_config.get(region_name, {})
            key_issue = r_info.get("key_issue", "")
            voters = r_info.get("voters", seg.voter_count)

            # 이유 생성
            reasons = []
            if rank == 1:
                reasons.append(f"최우선: 유권자 {voters}만명")
            else:
                reasons.append(f"유권자 {voters}만명")

            if seg.swing_index >= 0.6:
                reasons.append("경합지역")
            if seg.local_issue_heat >= 0.5:
                reasons.append(f"'{key_issue}' 이슈 활성")
            if days_left <= 14 and seg.swing_index >= 0.5:
                reasons.append("막판 스윙보터 집중 공략")

            reason = " + ".join(reasons) if reasons else "전략적 중요 지역"

            # 토킹포인트 생성
            talking_points = []

            # 해당 지역 핵심 이슈와 연결된 공약 찾기
            for pledge_name, pledge_data in self.config.pledges.items():
                desc = pledge_data.get("설명", "")
                number = pledge_data.get("수치", "")
                # 공약이 지역 핵심 이슈와 관련되는지 간단 매칭
                if key_issue:
                    key_words = key_issue.replace(" ", "")
                    pledge_text = (pledge_name + desc).replace(" ", "")
                    # 키워드 겹침 체크
                    for kw in key_issue.split():
                        if len(kw) >= 2 and kw in pledge_text:
                            talking_points.append(f"{pledge_name}: {number}")
                            break

            # 해당 지역 공격 포인트 추가
            for tp in region_attacks.get(region_name, [])[:2]:
                talking_points.append(tp)

            # 모드별 기본 토킹포인트 보충
            if not talking_points:
                if mode == CampaignMode.ATTACK:
                    talking_points.append(f"'{key_issue}' 문제 해결 의지 어필 + 상대 실적 부재 부각")
                elif mode == CampaignMode.DEFENSE:
                    talking_points.append(f"'{key_issue}'에 대한 구체적 해법 + 실행 경험 강조")
                elif mode == CampaignMode.INITIATIVE:
                    talking_points.append(f"'{key_issue}' 의제를 선점하는 정책 비전 제시")
                elif mode == CampaignMode.CRISIS:
                    talking_points.append(f"위기 이슈 해명 + '{key_issue}' 민생 의제 전환")

            schedule.append({
                "region": region_name,
                "priority": rank,
                "reason": reason,
                "talking_points": talking_points[:4],  # 최대 4개
            })

        return schedule

    # ------------------------------------------------------------------
    # 리스크 평가
    # ------------------------------------------------------------------
    def _assess_risk(
        self,
        issue_scores: list[IssueScore],
        opponent_signals: list[OpponentSignal],
        polling_data: dict,
    ) -> tuple[str, list[str]]:
        """
        리스크 종합 평가.
        - CRISIS 이슈 존재 -> "매우높음"
        - 공격확률 70%+ 상대 존재 -> "높음"
        - 여론조사 하락 추세 -> "높음"
        - 그 외 -> "보통" 또는 "낮음"

        Returns: (risk_level, [risk_factor_descriptions])
        """
        risk_factors = []
        severity = 0  # 0=낮음, 1=보통, 2=높음, 3=매우높음

        # CRISIS 이슈 체크
        crisis_issues = [i for i in issue_scores if i.level == CrisisLevel.CRISIS]
        if crisis_issues:
            severity = max(severity, 3)
            for ci in crisis_issues:
                risk_factors.append(
                    f"위기 이슈: '{ci.keyword}' (점수 {ci.score:.1f}) — 즉시 대응 필요"
                )

        # ALERT 이슈 체크
        alert_issues = [i for i in issue_scores if i.level == CrisisLevel.ALERT]
        if alert_issues:
            severity = max(severity, 2)
            for ai in alert_issues[:2]:
                risk_factors.append(
                    f"경계 이슈: '{ai.keyword}' (점수 {ai.score:.1f}) — 확산 모니터링 필요"
                )

        # 상대 공격 확률 체크
        for opp in opponent_signals:
            if opp.attack_prob_72h >= 0.7:
                severity = max(severity, 2)
                risk_factors.append(
                    f"공격 위협: {opp.opponent_name} 72시간 내 공격 확률 "
                    f"{opp.attack_prob_72h*100:.0f}%"
                )

        # 여론조사 격차 체크
        gap = polling_data.get("gap", 0.0)
        if gap < -3:
            severity = max(severity, 2)
            risk_factors.append(
                f"여론 열세: {abs(gap):.1f}%p 뒤처짐 — 반등 전략 시급"
            )
        elif gap < 0:
            severity = max(severity, 1)
            risk_factors.append(
                f"소폭 열세: {abs(gap):.1f}%p 차이 — 부동층 공략 집중"
            )

        # 신뢰도 낮은 데이터
        confidence = polling_data.get("confidence", "low")
        if confidence == "low":
            severity = max(severity, 1)
            risk_factors.append(
                "데이터 신뢰도 낮음: 여론조사 데이터 부족 — 판단 근거 불확실"
            )

        if not risk_factors:
            risk_factors.append("특이 리스크 없음 — 현 전략 유지")

        level_map = {0: "낮음", 1: "보통", 2: "높음", 3: "매우높음"}
        return level_map[severity], risk_factors

    # ------------------------------------------------------------------
    # 이슈 전략 분류
    # ------------------------------------------------------------------
    def _determine_issue_strategy(
        self,
        issue_scores: list[IssueScore],
        mode: CampaignMode,
    ) -> tuple[list[str], list[str], list[str]]:
        """
        이슈별 전략 분류: 밀기 / 피하기 / 반박하기

        Rules:
        - 우리에게 유리한 이슈 (not candidate_linked, low score): push
        - 우리에게 불리한 이슈 (candidate_linked, high score): counter or avoid
        - CRISIS인데 candidate_linked: must counter
        - 상대에게 불리한 이슈: push harder
        """
        issues_to_push = []
        issues_to_avoid = []
        issues_to_counter = []

        candidate_name = self.config.candidate_name
        opponent_names = self.config.opponents

        for issue in issue_scores:
            keyword = issue.keyword
            candidate_linked = candidate_name in keyword
            opponent_linked = any(opp in keyword for opp in opponent_names)
            neg_ratio = issue.breakdown.get("sentiment_score", 0) / 15.0 if issue.breakdown else 0

            if candidate_linked and neg_ratio >= 0.30:
                # 후보 연결 + 부정적 = 반박 필요
                issues_to_counter.append(keyword)
            elif candidate_linked and neg_ratio < 0.30:
                # 후보 이름이 나오지만 긍정적/중립 = 활용 가능
                issues_to_push.append(keyword)
            elif opponent_linked:
                # 상대 후보 연결 이슈 = 적극 활용
                issues_to_push.append(keyword)
            elif not candidate_linked and issue.score < 50:
                # 후보 무관 + 낮은 점수 = 우리가 선점 가능
                issues_to_push.append(keyword)
            elif not candidate_linked and issue.score >= 50:
                # 후보 무관 + 높은 점수 = 조심스럽게 접근
                if mode == CampaignMode.INITIATIVE:
                    issues_to_push.append(keyword)  # 선점 모드면 과감하게
                else:
                    issues_to_avoid.append(keyword)

        return issues_to_push, issues_to_avoid, issues_to_counter

    # ------------------------------------------------------------------
    # 상대 대응 전략
    # ------------------------------------------------------------------
    def _determine_opponent_actions(
        self,
        opponent_signals: list[OpponentSignal],
        mode: CampaignMode,
        attack_points: list[dict],
    ) -> list[dict]:
        """
        상대 후보별 대응 전략.

        Rules:
        - attack_prob >= 0.7: 선제 반박 준비
        - attack_prob >= 0.4 AND mode == ATTACK: 우리가 먼저 공격
        - attack_prob < 0.4: 모니터링
        - 김경수(주적)에 집중, 전희영은 무시 전략 (3자 구도에서 진보표 분산은 우리에게 유리)
        """
        actions = []

        # 주적 판별: 상대 중 가장 위협적인 후보
        main_opponent = None
        if opponent_signals:
            main_opponent = max(opponent_signals, key=lambda o: o.attack_prob_72h).opponent_name

        # 해당 상대에 대한 공격 포인트 매핑
        opponent_attacks: dict[str, list[dict]] = {}
        for ap in attack_points:
            target = ap.get("target", "")
            opponent_attacks.setdefault(target, []).append(ap)

        for opp in opponent_signals:
            name = opp.opponent_name
            prob = opp.attack_prob_72h
            is_main = (name == main_opponent)

            # 비주적 후보: 무시 전략 (진보표 분산은 유리)
            if not is_main and prob < 0.7:
                actions.append({
                    "opponent": name,
                    "action": "무시",
                    "detail": (
                        f"{name} 후보는 비주적 — 관심을 주지 마라. "
                        f"진보 진영 표 분산은 우리에게 유리하다."
                    ),
                })
                continue

            # 주적 또는 위협적 비주적 후보
            if prob >= 0.7:
                # 선제 반박 준비
                available_attacks = opponent_attacks.get(name, [])
                if available_attacks:
                    best = available_attacks[0]
                    detail = (
                        f"공격 확률 {prob*100:.0f}% — 선제 반박 준비. "
                        f"역공 포인트: '{best['pledge']}' → {best['talking_point']}"
                    )
                else:
                    detail = (
                        f"공격 확률 {prob*100:.0f}% — 선제 반박 자료 준비. "
                        f"대변인 방어 논리 사전 배포."
                    )
                actions.append({
                    "opponent": name,
                    "action": "선제반박",
                    "detail": detail,
                })
            elif prob >= 0.4 and mode == CampaignMode.ATTACK:
                # 공격 모드 + 중간 위협: 우리가 먼저 친다
                available_attacks = opponent_attacks.get(name, [])
                if available_attacks:
                    best = available_attacks[0]
                    detail = (
                        f"공격 모드 — {name} 약점 선제공격. "
                        f"공격 포인트: '{best['pledge']}' → {best['talking_point']}"
                    )
                else:
                    detail = (
                        f"공격 모드 — {name}에 대한 공세 강화. "
                        f"실적 부재와 공약 허구성 부각."
                    )
                actions.append({
                    "opponent": name,
                    "action": "선제공격",
                    "detail": detail,
                })
            elif prob >= 0.4:
                actions.append({
                    "opponent": name,
                    "action": "모니터링",
                    "detail": (
                        f"공격 확률 {prob*100:.0f}% — 동향 모니터링 강화. "
                        f"대응 초안 사전 준비. 메시지 변화: {opp.message_shift}"
                    ),
                })
            else:
                actions.append({
                    "opponent": name,
                    "action": "모니터링",
                    "detail": f"특이 동향 없음. 정상 모니터링 유지.",
                })

        return actions

    # ------------------------------------------------------------------
    # 최우선 과제 결정
    # ------------------------------------------------------------------
    def _determine_top_priority(
        self,
        mode: CampaignMode,
        risk_level: str,
        region_schedule: list[dict],
        issues_to_push: list[str],
        days_left: int,
    ) -> str:
        """오늘의 최우선 과제 1문장 생성"""

        if mode == CampaignMode.CRISIS:
            return "위기 이슈에 대한 즉각 대응 — 1시간 내 공식 입장 발표하라."

        top_region = region_schedule[0]["region"] if region_schedule else "핵심 지역"
        top_issue = issues_to_push[0] if issues_to_push else "핵심 의제"

        if mode == CampaignMode.ATTACK:
            if days_left <= 7:
                return (
                    f"D-{days_left} 반전 공세: {top_region}에서 상대 약점을 집중 부각하고 "
                    f"부동층 결집을 유도하라."
                )
            return (
                f"{top_region} 방문 유세 + 상대 후보 '{top_issue}' 공약 허구성 부각 — "
                f"공격 메시지를 전 채널에 배포하라."
            )

        if mode == CampaignMode.DEFENSE:
            return (
                f"{top_region} 현장 방문으로 지지층 결집 + "
                f"핵심 공약 반복으로 안정적 리드 유지하라."
            )

        # INITIATIVE
        if days_left <= 14:
            return (
                f"D-{days_left} 의제 선점: '{top_issue}' 관련 정책 발표 + "
                f"{top_region} 현장 유세로 모멘텀을 잡아라."
            )
        return (
            f"'{top_issue}' 의제를 우리 프레임으로 선점하라 — "
            f"{top_region}에서 정책 비전을 발표하고 여론을 주도하라."
        )

    # ------------------------------------------------------------------
    # 보고서 포맷
    # ------------------------------------------------------------------
    def format_strategy_report(self, strategy: DailyStrategy) -> str:
        """
        선대위 보고용 텍스트 포맷.
        깔끔하게 읽을 수 있는 형식으로 DailyStrategy를 출력합니다.
        """
        sep = "=" * 64
        thin = "-" * 64

        lines = []
        lines.append(sep)
        lines.append(f"  일일 전략 보고서 | {strategy.date} | D-{strategy.days_left}")
        lines.append(sep)
        lines.append("")

        # 캠페인 모드
        mode_icon = {
            CampaignMode.ATTACK: "[공격]",
            CampaignMode.DEFENSE: "[수비]",
            CampaignMode.INITIATIVE: "[선점]",
            CampaignMode.CRISIS: "[위기]",
        }
        lines.append(f"  캠페인 모드: {mode_icon.get(strategy.campaign_mode, '')} {strategy.campaign_mode.value}")
        lines.append(f"  근거: {strategy.mode_reasoning}")
        lines.append(f"  승률: {strategy.win_probability*100:.1f}% (신뢰도: {strategy.confidence})")
        lines.append(f"  리스크: {strategy.risk_level}")
        lines.append("")

        # 최우선 과제
        lines.append(thin)
        lines.append(f"  >>> 오늘의 최우선 과제")
        lines.append(f"  {strategy.top_priority}")
        lines.append(thin)
        lines.append("")

        # 핵심 메시지
        lines.append("  [핵심 메시지 — 오늘 반복할 3가지]")
        for i, msg in enumerate(strategy.key_messages, 1):
            lines.append(f"    {i}. {msg}")
        lines.append("")

        # 지역 유세 일정
        lines.append("  [지역 유세 우선순위]")
        for r in strategy.region_schedule:
            lines.append(f"    {r['priority']}순위: {r['region']} — {r['reason']}")
            for tp in r.get("talking_points", []):
                lines.append(f"       > {tp}")
        lines.append("")

        # 상대 대응
        lines.append("  [상대 후보 대응]")
        for oa in strategy.opponent_actions:
            lines.append(f"    {oa['opponent']}: [{oa['action']}]")
            lines.append(f"       {oa['detail']}")
        lines.append("")

        # 이슈 전략
        lines.append("  [이슈 전략]")
        if strategy.issues_to_push:
            lines.append(f"    밀어야 할 이슈: {', '.join(strategy.issues_to_push)}")
        if strategy.issues_to_avoid:
            lines.append(f"    피해야 할 이슈: {', '.join(strategy.issues_to_avoid)}")
        if strategy.issues_to_counter:
            lines.append(f"    반박해야 할 이슈: {', '.join(strategy.issues_to_counter)}")
        lines.append("")

        # 리스크 팩터
        if strategy.risk_factors:
            lines.append("  [리스크 요인]")
            for rf in strategy.risk_factors:
                lines.append(f"    ! {rf}")
            lines.append("")

        lines.append(sep)
        return "\n".join(lines)
