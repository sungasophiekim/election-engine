"""
Engine V2 — Weighted Strategy Mode Selector
단순 if-elif 대신 다차원 압력 기반 캠페인 모드 결정.

문제:
  현재: gap < -2 → ATTACK, gap > 3 → DEFENSE, else → INITIATIVE
  이 로직은 위기 이슈가 있어도 격차만 보고 ATTACK을 선택하거나,
  상승세인데도 DEFENSE를 유지하는 등 맥락 없는 결정을 함.

해결:
  4가지 압력(pressure) 벡터를 계산하고,
  가장 강한 압력이 모드를 결정하되,
  각 압력의 구체적 수치와 이유를 기록.
"""
from dataclasses import dataclass, field
from models.schemas import IssueScore, CrisisLevel, OpponentSignal


@dataclass
class PressureVector:
    """4차원 압력 벡터"""
    crisis_pressure: float = 0.0       # 위기 이슈에 의한 압력 (0~100)
    polling_gap_pressure: float = 0.0  # 여론 격차에 의한 압력 (0~100)
    momentum_pressure: float = 0.0     # 모멘텀 변화 압력 (0~100)
    opportunity_pressure: float = 0.0  # 기회 포착 압력 (0~100)

    # 설명
    crisis_reasons: list[str] = field(default_factory=list)
    polling_reasons: list[str] = field(default_factory=list)
    momentum_reasons: list[str] = field(default_factory=list)
    opportunity_reasons: list[str] = field(default_factory=list)


@dataclass
class ModeDecision:
    """캠페인 모드 결정 결과"""
    mode: str                # "CRISIS" | "ATTACK" | "DEFENSE" | "INITIATIVE"
    mode_korean: str         # "위기대응" | "공격" | "수비" | "선점"
    confidence: str          # "high" | "medium" | "low"

    # 결정 근거
    pressures: PressureVector = field(default_factory=PressureVector)
    dominant_pressure: str = ""   # "crisis" | "polling" | "momentum" | "opportunity"
    reasoning: str = ""

    # 세부
    pressure_breakdown: dict = field(default_factory=dict)  # {pressure_name: score}


class StrategyModeSelector:
    """
    다차원 압력 기반 캠페인 모드 결정기.

    사용법:
        selector = StrategyModeSelector()
        decision = selector.decide(
            issue_scores=[...],
            polling_gap=-1.2,
            momentum="losing",
            our_trend=-0.3,
            opponent_signals=[...],
            days_left=76,
        )
        print(decision.mode)      # "INITIATIVE"
        print(decision.reasoning) # "초박빙 접전 + 하락세 → 의제 선점 필요"
    """

    # 모드 매핑
    MODE_MAP = {
        "CRISIS": "위기대응",
        "ATTACK": "공격",
        "DEFENSE": "수비",
        "INITIATIVE": "선점",
    }

    def decide(
        self,
        issue_scores: list[IssueScore] = None,
        polling_gap: float = 0.0,          # 우리 - 상대 (%p)
        momentum: str = "stable",          # "gaining" | "stable" | "losing"
        our_trend: float = 0.0,            # 일일 변화 %p
        opponent_signals: list[OpponentSignal] = None,
        days_left: int = 90,
        candidate_linked_crisis: bool = False,
    ) -> ModeDecision:

        issue_scores = issue_scores or []
        opponent_signals = opponent_signals or []

        pv = PressureVector()

        # ═══ 1. CRISIS PRESSURE ═══
        crisis_issues = [s for s in issue_scores if s.level == CrisisLevel.CRISIS]
        alert_issues = [s for s in issue_scores if s.level == CrisisLevel.ALERT]
        candidate_crisis = [s for s in crisis_issues if getattr(s, 'breakdown', {}).get('candidate_linked', False) or candidate_linked_crisis]

        if candidate_crisis:
            pv.crisis_pressure += 50
            pv.crisis_reasons.append(f"후보 직접 연결 위기 이슈 {len(candidate_crisis)}건")

        pv.crisis_pressure += min(30, len(crisis_issues) * 10)
        if crisis_issues:
            pv.crisis_reasons.append(f"CRISIS 이슈 {len(crisis_issues)}건 (최고 {max(s.score for s in crisis_issues):.0f}점)")

        pv.crisis_pressure += min(15, len(alert_issues) * 3)
        if alert_issues:
            pv.crisis_reasons.append(f"ALERT 이슈 {len(alert_issues)}건")

        # D-14 이내 위기는 가중
        if days_left <= 14 and crisis_issues:
            pv.crisis_pressure = min(100, pv.crisis_pressure * 1.3)
            pv.crisis_reasons.append(f"D-{days_left} 선거 임박 위기 가중")

        pv.crisis_pressure = min(100, pv.crisis_pressure)

        # ═══ 2. POLLING GAP PRESSURE ═══
        # 뒤질수록 공격 압력 ↑, 앞설수록 수비 압력 ↑
        if polling_gap < 0:
            # 열세: 격차가 클수록 공격 압력
            pv.polling_gap_pressure = min(100, abs(polling_gap) * 15)
            pv.polling_reasons.append(f"격차 {polling_gap:+.1f}%p 열세")
            if polling_gap < -5:
                pv.polling_reasons.append("5%p 이상 열세 — 강공 필요")
        else:
            # 우세: 격차가 클수록 수비 압력 (음수 표현으로 DEFENSE 방향)
            pv.polling_gap_pressure = -min(80, polling_gap * 12)
            pv.polling_reasons.append(f"격차 {polling_gap:+.1f}%p 우세")
            if polling_gap > 5:
                pv.polling_reasons.append("5%p 이상 리드 — 실점 방지 집중")

        # ═══ 3. MOMENTUM PRESSURE ═══
        if momentum == "losing":
            pv.momentum_pressure = min(80, 40 + abs(our_trend) * 30)
            pv.momentum_reasons.append(f"하락세 ({our_trend:+.2f}%p/일)")
            if our_trend < -0.5:
                pv.momentum_reasons.append("급속 하락 — 프레임 전환 시급")
        elif momentum == "gaining":
            pv.momentum_pressure = -min(60, 30 + our_trend * 20)
            pv.momentum_reasons.append(f"상승세 ({our_trend:+.2f}%p/일)")
        else:
            pv.momentum_pressure = 0
            pv.momentum_reasons.append("모멘텀 유지")

        # ═══ 4. OPPORTUNITY PRESSURE ═══
        # 상대 약점 기회
        high_attack_prob = [o for o in opponent_signals if o.attack_prob_72h >= 0.6]
        if high_attack_prob:
            pv.opportunity_pressure += 30
            pv.opportunity_reasons.append(f"상대 공격 확률 높음 ({len(high_attack_prob)}건)")

        # 초박빙이면 의제 선점 기회
        if abs(polling_gap) <= 2:
            pv.opportunity_pressure += 25
            pv.opportunity_reasons.append("초박빙 — 의제 선점 기회")

        # 상승세 + 우세면 마무리 기회
        if momentum == "gaining" and polling_gap > 0:
            pv.opportunity_pressure += 20
            pv.opportunity_reasons.append("상승세 + 우세 — 마무리 공세 기회")

        # D-Day 근접 시 기회 가중
        if days_left <= 30:
            pv.opportunity_pressure = min(100, pv.opportunity_pressure * 1.2)
            pv.opportunity_reasons.append(f"D-{days_left} 최종 국면")

        pv.opportunity_pressure = min(100, max(0, pv.opportunity_pressure))

        # ═══ MODE DECISION ═══
        # 양수 = 공격적, 음수 = 수비적
        scores = {
            "CRISIS": pv.crisis_pressure,
            "ATTACK": max(0, pv.polling_gap_pressure) + max(0, pv.momentum_pressure) * 0.5,
            "DEFENSE": abs(min(0, pv.polling_gap_pressure)) + abs(min(0, pv.momentum_pressure)) * 0.3,
            "INITIATIVE": pv.opportunity_pressure + (20 if abs(polling_gap) <= 2 else 0),
        }

        # CRISIS는 절대 우선 (60점 이상이면 무조건)
        if scores["CRISIS"] >= 60:
            mode = "CRISIS"
            dominant = "crisis"
        else:
            # 나머지 중 최고 점수 선택
            mode = max(["ATTACK", "DEFENSE", "INITIATIVE"], key=lambda m: scores[m])
            dominant = {
                "ATTACK": "polling",
                "DEFENSE": "polling",
                "INITIATIVE": "opportunity",
            }[mode]

        # D-14 보정
        if days_left <= 14:
            if mode == "DEFENSE" and polling_gap < 5:
                mode = "INITIATIVE"
                dominant = "opportunity"
                pv.opportunity_reasons.append("D-14 보정: 리드 5%p 미만 → 선점으로 전환")
            if mode == "INITIATIVE" and polling_gap < -2:
                mode = "ATTACK"
                dominant = "polling"
                pv.polling_reasons.append("D-14 보정: 열세 2%p 이상 → 공격으로 전환")

        # Confidence (with learning feedback adjustment)
        top_score = scores[mode]
        second_score = sorted(scores.values(), reverse=True)[1]
        gap = top_score - second_score
        confidence = "high" if gap >= 20 else "medium" if gap >= 8 else "low"

        try:
            from engines.learning_feedback import adjust_confidence
            confidence = adjust_confidence(confidence, "campaign_mode", mode)
        except Exception:
            pass

        # Reasoning 생성
        reasons = {
            "crisis": pv.crisis_reasons,
            "polling": pv.polling_reasons,
            "momentum": pv.momentum_reasons,
            "opportunity": pv.opportunity_reasons,
        }
        primary_reasons = reasons.get(dominant, [])
        reasoning = " / ".join(primary_reasons[:3]) if primary_reasons else f"{mode} 모드 선택"

        return ModeDecision(
            mode=mode,
            mode_korean=self.MODE_MAP[mode],
            confidence=confidence,
            pressures=pv,
            dominant_pressure=dominant,
            reasoning=reasoning,
            pressure_breakdown={k: round(v, 1) for k, v in scores.items()},
        )
