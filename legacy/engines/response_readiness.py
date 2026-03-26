"""
Engine V2 — Response Readiness Scoring
"답이 없다"를 구조화하여 stance 결정의 근거를 만듦.

문제:
  현재 issue_response.py에서 "avoid" 스탠스는 직관적 판단.
  "답이 없는 이슈"인지 여부가 측정되지 않음.
  대시보드에서 "왜 이 이슈를 회피하는가?"를 설명 불가.

해결:
  3차원 readiness 스코어:
  1. fact_readiness   — 사실 기반 반박 가능 여부
  2. message_readiness — 준비된 메시지/토킹포인트 존재 여부
  3. legal_readiness   — 법적 리스크 없이 대응 가능 여부

  종합 readiness_score = weighted average
  → stance 결정에 반영:
     readiness < 30 + score ≥ 50 → avoid
     readiness 30~60             → monitor or pivot
     readiness > 60              → counter 가능
"""
from dataclasses import dataclass


@dataclass
class ReadinessScore:
    """이슈 대응 준비도"""
    keyword: str

    # 3차원 readiness (각 0~100)
    fact_readiness: float = 0.0       # 사실 기반 반박 가능
    message_readiness: float = 0.0    # 준비된 메시지 존재
    legal_readiness: float = 0.0      # 법적 리스크 없음

    # 종합
    total_readiness: float = 0.0      # 가중 평균
    readiness_grade: str = ""         # A(강) B(보통) C(약) D(미준비)

    # 판정 근거
    fact_detail: str = ""
    message_detail: str = ""
    legal_detail: str = ""

    # stance 영향
    recommended_stance_override: str = ""  # avoid | monitor | (empty=no override)
    override_reason: str = ""


class ResponseReadinessScorer:
    """
    이슈별 대응 준비도를 채점.

    config의 crisis_playbook, category_responses, forbidden_words 등을 활용하여
    각 이슈에 대해 우리가 얼마나 준비되어 있는지를 정량화.
    """

    # readiness → stance override 규칙
    AVOID_THRESHOLD = 30     # readiness < 30 이고 score ≥ 50 → avoid 권고
    MONITOR_THRESHOLD = 60   # readiness < 60 → counter 불가, monitor/pivot 권고
    COUNTER_THRESHOLD = 60   # readiness ≥ 60 → counter 가능

    # 가중치
    FACT_WEIGHT = 0.4
    MESSAGE_WEIGHT = 0.35
    LEGAL_WEIGHT = 0.25

    def __init__(self, config):
        self.config = config
        self._build_readiness_base()

    def _build_readiness_base(self):
        """config에서 준비도 기반 데이터 추출"""
        self.candidate = self.config.candidate_name
        self.forbidden = set(self.config.forbidden_words or [])

        # 공약 키워드 (우리가 준비된 메시지가 있는 영역)
        self.pledge_keywords = set()
        for name, info in (self.config.pledges or {}).items():
            self.pledge_keywords.add(name)
            if isinstance(info, dict):
                for v in info.values():
                    if isinstance(v, str):
                        for word in v.split():
                            if len(word) >= 2:
                                self.pledge_keywords.add(word)

        # 위기 플레이북 키워드 (사전 준비된 대응)
        self.playbook_keywords = {
            "사법", "재판", "유죄", "수사", "구속",    # 사법 리스크
            "재원", "예산", "세금", "재정",             # 재원 논란
            "포퓰리즘", "퍼주기", "선심",               # 포퓰리즘
            "강남", "발언", "실언", "막말",             # 발언 논란
        }

        # 법적 리스크 키워드
        self.legal_risk_keywords = {
            "고발", "소송", "재판", "기소", "유죄", "판결",
            "위증", "위법", "불법", "탈세", "횡령", "뇌물",
        }

    def score(self, keyword: str, issue_score: float = 0, issue_type: str = "", target_side: str = "") -> ReadinessScore:
        """
        키워드 1개에 대한 대응 준비도 채점.

        Args:
            keyword: 이슈 키워드
            issue_score: 현재 이슈 스코어 (0~100)
            issue_type: canonical_issue_mapper의 issue_type
            target_side: "ours" | "theirs" | "neutral"
        """
        result = ReadinessScore(keyword=keyword)

        # ── 1. Fact Readiness ──
        # 우리 공약 영역 = 사실 준비 높음
        # 상대 관련 = 우리가 사실 확인 어려움
        # 스캔들 = 사실 관계 복잡

        fact = 50.0  # 기본값

        # 우리 공약/정책 영역이면 사실 근거 풍부
        if any(pk in keyword for pk in self.pledge_keywords):
            fact = 80.0
            result.fact_detail = "우리 공약 영역 — 수치 근거 보유"

        # 위기 플레이북에 해당하면 사전 팩트체크 완료
        elif any(pk in keyword for pk in self.playbook_keywords):
            fact = 65.0
            result.fact_detail = "위기 플레이북 대상 — 사전 대응 준비됨"

        # 스캔들/의혹 유형은 사실 확인 어려움
        elif issue_type in ("candidate_scandal", "general_scandal"):
            fact = 25.0
            result.fact_detail = "스캔들/의혹 — 사실 반박 근거 부족"

        # 상대 관련 이슈는 우리가 사실 주장 가능
        elif target_side == "theirs":
            fact = 70.0
            result.fact_detail = "상대 관련 — 우리 측 공격 자료 활용 가능"

        else:
            result.fact_detail = "일반 이슈 — 기본 대응"

        result.fact_readiness = fact

        # ── 2. Message Readiness ──
        msg = 50.0

        if any(pk in keyword for pk in self.pledge_keywords):
            msg = 85.0
            result.message_detail = "공약 메시지/토킹포인트 사전 준비됨"
        elif any(pk in keyword for pk in self.playbook_keywords):
            msg = 70.0
            result.message_detail = "위기 대응 메시지 준비됨"
        elif target_side == "theirs":
            msg = 60.0
            result.message_detail = "상대 공격용 메시지 활용 가능"
        elif issue_type in ("candidate_scandal",):
            msg = 20.0
            result.message_detail = "후보 스캔들 — 적절한 메시지 부재"
        else:
            msg = 40.0
            result.message_detail = "범용 대응 필요"

        result.message_readiness = msg

        # ── 3. Legal Readiness ──
        legal = 80.0  # 기본적으로 법적 리스크 낮음

        if any(lk in keyword for lk in self.legal_risk_keywords):
            legal = 30.0
            result.legal_detail = "법적 리스크 키워드 포함 — 법률팀 검토 필요"
        elif self.candidate in keyword and issue_type in ("candidate_scandal",):
            legal = 40.0
            result.legal_detail = "후보 직접 연관 스캔들 — 발언 주의"
        elif any(fw in keyword for fw in self.forbidden):
            legal = 50.0
            result.legal_detail = "금기 표현 관련 — 표현 제한"
        else:
            result.legal_detail = "법적 리스크 낮음"

        result.legal_readiness = legal

        # ── 4. 종합 ──
        result.total_readiness = (
            result.fact_readiness * self.FACT_WEIGHT +
            result.message_readiness * self.MESSAGE_WEIGHT +
            result.legal_readiness * self.LEGAL_WEIGHT
        )

        # Grade
        r = result.total_readiness
        if r >= 70:
            result.readiness_grade = "A"
        elif r >= 50:
            result.readiness_grade = "B"
        elif r >= 30:
            result.readiness_grade = "C"
        else:
            result.readiness_grade = "D"

        # ── 5. Stance Override ──
        if result.total_readiness < self.AVOID_THRESHOLD and issue_score >= 50:
            result.recommended_stance_override = "avoid"
            result.override_reason = f"준비도 {result.total_readiness:.0f} (D등급) — 고점수 이슈이나 대응 수단 부족"
        elif result.total_readiness < self.MONITOR_THRESHOLD and issue_score >= 40:
            result.recommended_stance_override = "monitor"
            result.override_reason = f"준비도 {result.total_readiness:.0f} (C등급) — counter 불가, 모니터링 권고"

        return result

    def score_batch(self, issues: list[dict]) -> list[ReadinessScore]:
        """
        여러 이슈 일괄 채점.

        Args:
            issues: [{"keyword": str, "score": float, "issue_type": str, "target_side": str}, ...]
        """
        return [
            self.score(
                keyword=iss["keyword"],
                issue_score=iss.get("score", 0),
                issue_type=iss.get("issue_type", ""),
                target_side=iss.get("target_side", ""),
            )
            for iss in issues
        ]
