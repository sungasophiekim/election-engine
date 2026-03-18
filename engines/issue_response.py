"""
Election Strategy Engine — Issue Response Engine
이슈별 구체적 대응 전략과 메시지를 생성합니다.
Claude 없이 순수 로직/템플릿으로 동작합니다.
"""
from dataclasses import dataclass, field
from typing import Optional

from models.schemas import IssueScore, IssueSignal, CrisisLevel
from config.tenant_config import TenantConfig


@dataclass
class IssueResponse:
    """이슈별 대응 패키지"""
    keyword: str
    score: float
    level: CrisisLevel

    # 분류
    stance: str              # "push" | "counter" | "avoid" | "monitor" | "pivot"
    stance_reason: str       # 왜 이 입장인가

    # 소유권
    owner: str               # "대변인" | "전략팀" | "후보 직접" | "여론분석팀"
    urgency: str             # "즉시" | "당일" | "48시간" | "모니터링"
    golden_time_hours: float # 대응 골든타임

    # 대응 메시지
    response_message: str    # 핵심 대응 메시지 (1-2문장)
    talking_points: list[str]  # 토킹포인트 3개
    do_not_say: list[str]    # 절대 하면 안 되는 발언

    # 이슈 연관 분석
    related_issues: list[str]  # 연관 이슈 키워드
    related_pledges: list[str] # 연관 공약
    pivot_to: str             # 대응 후 전환할 주제

    # 생명주기
    lifecycle: str            # "emerging" | "growing" | "peak" | "declining" | "dormant"
    trend_direction: str      # "↑상승" | "→유지" | "↓하락"
    estimated_duration: str   # "단발성" | "1-2일" | "3-7일" | "장기"

    # 시나리오
    scenario_best: str        # 최선 시나리오
    scenario_worst: str       # 최악 시나리오


class IssueResponseEngine:
    """이슈별 대응 전략 생성 엔진"""

    def __init__(self, config: TenantConfig):
        self.config = config
        self._build_knowledge_base()

    def _build_knowledge_base(self):
        """
        이슈 키워드 → 대응 매핑 지식 베이스 구축.
        우리 공약과 상대 약점을 기반으로 이슈별 기본 대응을 미리 준비.
        """
        self.candidate = self.config.candidate_name
        self.opponents = self.config.opponents
        self.main_opponent = self.opponents[0] if self.opponents else ""

        # 이슈 카테고리 매핑 (키워드 → 카테고리)
        self.issue_categories = {
            "선거": "선거일반", "도지사": "선거일반", "공약": "선거일반",
            "일자리": "경제", "조선": "경제", "산업": "경제", "경제": "경제", "방산": "경제",
            "교통": "교통", "BRT": "교통", "도로": "교통",
            "청년": "청년", "대학": "청년", "취업": "청년",
            "부울경": "행정통합", "통합": "행정통합", "메가시티": "행정통합",
            "우주": "산업", "항공": "산업", "스마트": "산업",
            "복지": "복지", "지원금": "복지", "도민": "복지",
            "부동산": "부동산", "집값": "부동산",
            "환경": "환경", "기후": "환경",
            "안전": "안전", "재난": "안전",
        }

        # 카테고리별 기본 대응 템플릿
        # 각 카테고리에 대해: 우리 강점(push), 우리 약점(counter), 전환(pivot) 준비
        self.category_responses = {
            "경제": {
                "our_strength": "조선·방산 르네상스 + 5극3특 지방주도 성장",
                "push_message": (
                    "경남 경제를 살리는 건 경험과 네트워크입니다. "
                    "지방시대위원장 경험으로 국비 5조를 확보하겠습니다."
                ),
                "counter_message": (
                    "코로나 위기 속에서도 경남 경제 기반을 지켰습니다. "
                    "이제 K-방산 수출 호황을 경남 일자리로 연결합니다."
                ),
                "pivot_to": "조선·방산 르네상스",
                "related_pledges": ["지방주도 성장", "조선·방산 르네상스"],
            },
            "교통": {
                "our_strength": "부울경 메가시티 광역교통 체계",
                "push_message": (
                    "부울경 메가시티의 핵심은 교통입니다. "
                    "경남-부산-울산을 하나로 잇는 광역교통 혁신을 추진합니다."
                ),
                "counter_message": (
                    "현 도지사의 BRT는 2028년 개통 — 임기 내 불가. "
                    "저는 임기 내 착공 가능한 현실적 교통 대안을 제시합니다."
                ),
                "pivot_to": "부울경 메가시티",
                "related_pledges": ["부울경 메가시티"],
            },
            "청년": {
                "our_strength": "청년 정주 패키지 (월세 30만 + 장려금 500만)",
                "push_message": (
                    "청년이 떠나지 않는 경남을 만들겠습니다. "
                    "월세 30만원 지원, 첫 일자리 장려금 500만원 — 직접 체감하는 정책입니다."
                ),
                "counter_message": (
                    "현 도정 4년간 청년 인구 유출이 심화되었습니다. "
                    "말이 아닌 실질적 지원이 필요합니다."
                ),
                "pivot_to": "청년 정주 패키지",
                "related_pledges": ["청년 정주 패키지"],
            },
            "행정통합": {
                "our_strength": "부울경 메가시티 — 주민투표 기반 민주적 추진",
                "push_message": (
                    "부울경 1000만 메가시티는 경남의 미래입니다. "
                    "주민투표로 도민이 직접 결정합니다."
                ),
                "counter_message": (
                    "주민투표로 도민이 직접 결정합니다. "
                    "도민이 원하면 추진하고, 원치 않으면 멈춥니다. 이것이 민주주의입니다."
                ),
                "pivot_to": "부울경 메가시티",
                "related_pledges": ["부울경 메가시티"],
                "do_not_say": [
                    "경남도지사 자리가 없어져도 괜찮다 — 이런 식의 자기희생 프레이밍 금지"
                ],
            },
            "복지": {
                "our_strength": "경남도민 생활지원금 10만원 즉시 지급",
                "push_message": (
                    "물가 안정이 최우선입니다. "
                    "취임 100일 내 전 도민 10만원 생활지원금을 지급합니다."
                ),
                "counter_message": (
                    "3,300억은 도세 잉여분과 특별교부세로 충분합니다. "
                    "도민 생활 안정이 가장 시급한 과제입니다."
                ),
                "pivot_to": "경남도민 생활지원금",
                "related_pledges": ["경남도민 생활지원금"],
                "do_not_say": ["포퓰리즘이라는 비판에 감정적으로 반응하지 마라"],
            },
            "선거일반": {
                "our_strength": "경남을 경험한 리더십, 검증된 실행력",
                "push_message": (
                    "다시 경남, 제대로 한번. 경남을 아는 리더가 경남을 바꿉니다."
                ),
                "counter_message": (
                    "경남을 경험한 리더십으로 도민의 삶을 바꿉니다. "
                    "말이 아닌 경험, 약속이 아닌 실행."
                ),
                "pivot_to": "지방주도 성장",
                "related_pledges": ["지방주도 성장"],
            },
            "산업": {
                "our_strength": "5극3특 거점 전략 + K-방산 수출 연계",
                "push_message": (
                    "경남이 대한민국 산업의 심장입니다. "
                    "5극3특 전략으로 경남을 다시 성장 엔진으로 만들겠습니다."
                ),
                "counter_message": (
                    "현 도지사의 우주항공은 사천 편중입니다. "
                    "저는 경남 전체가 수혜받는 균형 발전 전략을 제시합니다."
                ),
                "pivot_to": "지방주도 성장",
                "related_pledges": ["지방주도 성장", "조선·방산 르네상스"],
            },
        }

        # 우리 후보 관련 위기 시나리오 대응 (사전 준비)
        # 주의: "사법" 키워드로 매칭하되, 특정 사건명을 직접 언급하지 않음
        self.crisis_playbook = {
            "사법": {
                "stance": "counter",
                "owner": "대변인",
                "urgency": "즉시",
                "response": (
                    "모든 사법 절차가 완료되었습니다. "
                    "저는 경남 발전으로 도민께 보답하는 것에 집중하겠습니다."
                ),
                "do_not_say": ["댓글", "조작", "유죄", "사면"],
                "pivot_to": "지방주도 성장",
            },
            "재원": {
                "stance": "counter",
                "owner": "정책팀",
                "urgency": "당일",
                "response": (
                    "3,300억은 도세 잉여분과 특별교부세로 충분합니다. "
                    "오히려 현 도지사의 스마트산단 1조 2천억 재원이 불투명합니다."
                ),
                "do_not_say": ["재정 부담이 크지만", "어려울 수 있지만"],
                "pivot_to": "경남도민 생활지원금",
            },
            "포퓰리즘": {
                "stance": "counter",
                "owner": "대변인",
                "urgency": "당일",
                "response": (
                    "도민 생활 안정은 포퓰리즘이 아니라 최우선 과제입니다. "
                    "예산의 2%로 330만 도민의 생활을 지킵니다."
                ),
                "do_not_say": ["다른 시도도 하고 있다 — 비교하지 마라, 우리 논리로"],
                "pivot_to": "경남도민 생활지원금",
            },
            "과거 성과": {
                "stance": "counter",
                "owner": "후보 직접",
                "urgency": "당일",
                "response": (
                    "코로나 위기 속에서도 경남 경제 기반을 지켰습니다. "
                    "이번에는 위기가 아닌 성장의 시대를 열겠습니다."
                ),
                "do_not_say": ["그때는 코로나 때문에 — 핑계로 들림"],
                "pivot_to": "조선·방산 르네상스",
            },
        }

    # ------------------------------------------------------------------
    # 분석 메서드
    # ------------------------------------------------------------------

    def analyze_issue(
        self,
        issue_score: IssueScore,
        signal: IssueSignal = None,
        historical_scores: list[dict] = None,
    ) -> IssueResponse:
        """
        단일 이슈에 대한 완전한 대응 패키지 생성.

        Parameters:
            issue_score: 스코어링된 이슈
            signal: 원본 시그널 (있으면 추가 분석)
            historical_scores: DB에서 가져온 이 키워드의 과거 스코어 (있으면 생명주기 분석)
        """
        keyword = issue_score.keyword
        score = issue_score.score
        level = issue_score.level

        # 1. 카테고리 분류
        category = self._categorize_issue(keyword)

        # 2. 이 이슈가 누구에게 유리/불리한지 판단
        impact = self._assess_impact(keyword, signal)

        # 3. 입장(stance) 결정
        stance, stance_reason = self._determine_stance(
            keyword, score, level, impact, category
        )

        # 4. 대응 메시지 생성
        response_msg, talking_points, do_not_say = self._generate_response(
            keyword, category, stance, impact
        )

        # 5. 소유권 및 긴급도
        owner, urgency, golden_time = self._assign_ownership(level, stance, impact)

        # 6. 연관 이슈/공약 찾기
        related_issues = self._find_related_issues(keyword, category)
        related_pledges = self._find_related_pledges(category)
        pivot_to = self._get_pivot_topic(category)

        # 7. 생명주기 분석
        lifecycle, trend, duration = self._analyze_lifecycle(
            keyword, score, historical_scores
        )

        # 8. 시나리오
        best, worst = self._generate_scenarios(keyword, stance, impact, level)

        return IssueResponse(
            keyword=keyword,
            score=score,
            level=level,
            stance=stance,
            stance_reason=stance_reason,
            owner=owner,
            urgency=urgency,
            golden_time_hours=golden_time,
            response_message=response_msg,
            talking_points=talking_points,
            do_not_say=do_not_say,
            related_issues=related_issues,
            related_pledges=related_pledges,
            pivot_to=pivot_to,
            lifecycle=lifecycle,
            trend_direction=trend,
            estimated_duration=duration,
            scenario_best=best,
            scenario_worst=worst,
        )

    def analyze_all(
        self,
        issue_scores: list[IssueScore],
        signals: list[IssueSignal] = None,
    ) -> list[IssueResponse]:
        """모든 이슈에 대한 대응 패키지 일괄 생성"""
        signal_map: dict[str, IssueSignal] = {}
        if signals:
            for s in signals:
                signal_map[s.keyword] = s

        responses: list[IssueResponse] = []
        for score in issue_scores:
            sig = signal_map.get(score.keyword)
            # DB에서 과거 트렌드 조회 시도
            historical = None
            try:
                from storage.database import ElectionDB
                db = ElectionDB()
                historical = db.get_issue_trend(score.keyword, days=7)
                db.close()
            except Exception:
                pass

            resp = self.analyze_issue(score, sig, historical)
            responses.append(resp)

        return responses

    # ------------------------------------------------------------------
    # 내부 분석 함수
    # ------------------------------------------------------------------

    def _categorize_issue(self, keyword: str) -> str:
        """키워드를 카테고리로 분류"""
        for kw, cat in self.issue_categories.items():
            if kw in keyword:
                return cat
        return "기타"

    def _assess_impact(self, keyword: str, signal: IssueSignal = None) -> dict:
        """이슈가 누구에게 유리/불리한지 판단"""
        mentions_us = self.candidate in keyword
        mentions_opponent = any(opp in keyword for opp in self.opponents)

        # 시그널의 감성 분석 결과 활용
        neg_ratio = 0.0
        if signal:
            neg_ratio = signal.negative_ratio

        if mentions_us and neg_ratio >= 0.3:
            return {"target": "us", "polarity": "negative", "danger": True}
        elif mentions_us and neg_ratio < 0.3:
            return {"target": "us", "polarity": "positive", "danger": False}
        elif mentions_opponent and neg_ratio >= 0.3:
            # 상대에게 부정적 = 우리에게 유리
            return {"target": "opponent", "polarity": "negative", "danger": False}
        elif mentions_opponent:
            return {"target": "opponent", "polarity": "neutral", "danger": False}
        else:
            return {"target": "general", "polarity": "neutral", "danger": False}

    def _determine_stance(
        self, keyword, score, level, impact, category
    ) -> tuple[str, str]:
        """
        5가지 stance 중 결정:
        - push: 우리에게 유리한 이슈 -> 적극 활용
        - counter: 우리에게 불리하지만 대응 필요 -> 반박 후 전환
        - avoid: 우리에게 불리하고 대응해도 손해 -> 침묵
        - monitor: 아직 작아서 지켜보기 -> 확산 시 대응 준비
        - pivot: 이슈 자체보다 우리 의제로 전환이 효과적
        """
        # Crisis playbook 매칭
        for crisis_key, playbook in self.crisis_playbook.items():
            if crisis_key in keyword.lower() or crisis_key in keyword:
                return (
                    playbook["stance"],
                    f"위기 시나리오 '{crisis_key}' 매칭 — 사전 준비된 대응 실행",
                )

        if impact["danger"]:
            if level == CrisisLevel.CRISIS:
                return "counter", "위기 레벨 이슈 + 우리에게 부정적 — 즉시 반박 필요"
            elif score >= 50:
                return "counter", f"고스코어({score:.0f}) + 부정적 — 반박 후 의제 전환"
            else:
                return "monitor", f"아직 낮은 스코어({score:.0f})이지만 부정적 — 확산 모니터링"

        if impact["target"] == "opponent" and impact["polarity"] == "negative":
            return "push", "상대에게 부정적 이슈 — 적극 확산. 우리 공격 포인트로 활용"

        if impact["target"] == "us" and impact["polarity"] == "positive":
            return "push", "우리에게 긍정적 이슈 — 미디어 노출 극대화"

        cat_resp = self.category_responses.get(category)
        if cat_resp and score >= 40:
            pivot_target = cat_resp.get("pivot_to", "")
            return (
                "pivot",
                f"중립 이슈({category}) — 우리 공약 '{pivot_target}' 으로 프레임 전환",
            )

        if score < 30:
            return "monitor", f"낮은 스코어({score:.0f}) — 특별 대응 불요. 모니터링만"

        return "push", "일반 이슈 — 우리 메시지 프레임으로 활용 가능"

    def _generate_response(
        self, keyword, category, stance, impact
    ) -> tuple[str, list[str], list[str]]:
        """대응 메시지, 토킹포인트, 금기 발언 생성"""
        cat_resp = self.category_responses.get(
            category,
            self.category_responses.get("선거일반", {}),
        )

        if stance == "push":
            msg = cat_resp.get(
                "push_message",
                f"'{keyword}' 이슈를 우리 프레임으로 선점하라",
            )
            points = [
                cat_resp.get("our_strength", "우리 강점 강조"),
                f"'{keyword}' 관련 우리 공약의 구체적 수치를 반복 언급",
                f"상대 후보의 이 분야 실적 부재 또는 공수표를 부각",
            ]
        elif stance == "counter":
            # Crisis playbook 매칭 우선
            for crisis_key, pb in self.crisis_playbook.items():
                if crisis_key in keyword.lower() or crisis_key in keyword:
                    msg = pb["response"]
                    points = [
                        msg,
                        f"즉시 '{pb['pivot_to']}' 의제로 전환",
                        "감정적 반응 금지, 차분하게",
                    ]
                    do_not_say = pb.get("do_not_say", [])
                    return msg, points, do_not_say

            msg = cat_resp.get(
                "counter_message",
                f"'{keyword}' 이슈에 대해 팩트로 반박하라",
            )
            pivot_target = cat_resp.get("pivot_to", "핵심 공약")
            points = [
                "팩트 기반 반박 — 검증된 수치만 사용",
                f"반박 후 즉시 '{pivot_target}' 으로 전환",
                "'현 도정의 실적 부재'를 역공 포인트로 활용",
            ]
        elif stance == "avoid":
            msg = "이 이슈에 대한 직접 언급을 피하라. 질문 시 핵심 메시지로 전환."
            points = [
                f"'{self.config.slogan}' 핵심 메시지로 돌아가라",
                "이 이슈에 대한 자발적 언급 금지",
                "기자 질문 시 1문장 응답 후 즉시 우리 의제로",
            ]
        elif stance == "pivot":
            pivot_topic = cat_resp.get("pivot_to", "지방주도 성장")
            msg = f"'{keyword}' 이슈를 '{pivot_topic}' 우리 프레임으로 전환하라"
            points = [
                f"'{keyword}'에 대한 우리의 해법 = '{pivot_topic}'",
                cat_resp.get("push_message", ""),
                "구체적 수치로 마무리",
            ]
        else:  # monitor
            msg = f"'{keyword}' 이슈 모니터링 중. 스코어 50 이상 도달 시 대응 격상."
            points = [
                "뉴스 클리핑 + 소셜 반응 추적",
                "대변인 사전 브리핑 자료 준비",
                "확산 시 counter 또는 pivot 모드로 전환",
            ]

        do_not_say = cat_resp.get("do_not_say", []) + self.config.forbidden_words[:3]

        return msg, [p for p in points if p], do_not_say

    def _assign_ownership(
        self, level: CrisisLevel, stance: str, impact: dict
    ) -> tuple[str, str, float]:
        """담당자, 긴급도, 골든타임"""
        if level == CrisisLevel.CRISIS or impact.get("danger"):
            return "대변인", "즉시", 2.0
        elif level == CrisisLevel.ALERT:
            return "전략팀", "당일", 6.0
        elif stance == "push":
            return "홍보팀", "당일", 12.0
        elif stance == "counter":
            return "대변인", "당일", 6.0
        else:
            return "여론분석팀", "모니터링", 48.0

    def _find_related_issues(self, keyword: str, category: str) -> list[str]:
        """같은 카테고리 내 다른 키워드 반환"""
        related = []
        for kw, cat in self.issue_categories.items():
            if cat == category and kw not in keyword:
                related.append(kw)
        return related[:5]

    def _find_related_pledges(self, category: str) -> list[str]:
        """카테고리에 매핑된 공약 반환"""
        cat_resp = self.category_responses.get(category, {})
        return cat_resp.get("related_pledges", [])

    def _get_pivot_topic(self, category: str) -> str:
        """카테고리별 전환 대상 주제"""
        cat_resp = self.category_responses.get(category, {})
        return cat_resp.get("pivot_to", "지방주도 성장")

    def _analyze_lifecycle(
        self, keyword: str, current_score: float, historical: list[dict] = None
    ) -> tuple[str, str, str]:
        """이슈 생명주기 분석"""
        if not historical or len(historical) < 2:
            if current_score >= 70:
                return "peak", "→유지", "1-2일"
            elif current_score >= 40:
                return "growing", "↑상승", "3-7일"
            else:
                return "emerging", "↑상승", "단발성"

        scores = [h.get("score", 0) for h in historical]
        recent = scores[-3:] if len(scores) >= 3 else scores
        avg_recent = sum(recent) / len(recent)

        if current_score > avg_recent + 5:
            trend = "↑상승"
            if current_score >= 70:
                lifecycle = "peak"
                duration = "3-7일"
            else:
                lifecycle = "growing"
                duration = "1-2일"
        elif current_score < avg_recent - 5:
            trend = "↓하락"
            lifecycle = "declining"
            duration = "1-2일"
        else:
            trend = "→유지"
            if current_score >= 50:
                lifecycle = "peak"
                duration = "3-7일"
            else:
                lifecycle = "dormant"
                duration = "단발성"

        return lifecycle, trend, duration

    def _generate_scenarios(
        self, keyword: str, stance: str, impact: dict, level: CrisisLevel
    ) -> tuple[str, str]:
        """최선/최악 시나리오 생성"""
        if impact.get("danger"):
            best = f"'{keyword}' 이슈가 24시간 내 소멸. 빠른 반박이 효과적이었다."
            worst = f"'{keyword}' 이슈가 TV 토론까지 이어짐. 방송 보도 확대로 1주일간 수세."
        elif stance == "push":
            best = f"'{keyword}' 이슈가 메인 뉴스로 확대. 상대 후보 방어에 밀림."
            worst = f"'{keyword}' 이슈가 관심 못 받고 소멸. 다른 이슈에 묻힘."
        else:
            best = f"'{keyword}' 이슈가 자연 소멸. 특별 대응 불요."
            worst = f"'{keyword}' 이슈가 예상과 달리 확산. 긴급 대응 필요."
        return best, worst

    # ------------------------------------------------------------------
    # 보고서 출력
    # ------------------------------------------------------------------

    def format_report(self, responses: list[IssueResponse]) -> str:
        """이슈 대응 보고서 출력"""
        lines = [
            "=" * 64,
            "  이슈 대응 보고서",
            "=" * 64,
            "",
        ]

        stance_labels = {
            "push": "밀기",
            "counter": "반박",
            "avoid": "회피",
            "monitor": "모니터링",
            "pivot": "전환",
        }
        level_marks = {
            CrisisLevel.CRISIS: "[위기]",
            CrisisLevel.ALERT: "[경계]",
            CrisisLevel.WATCH: "[관심]",
            CrisisLevel.NORMAL: "[정상]",
        }

        for r in sorted(responses, key=lambda x: x.score, reverse=True):
            stance_lbl = stance_labels.get(r.stance, r.stance)
            level_lbl = level_marks.get(r.level, "")

            lines.append(f"  {level_lbl} [{r.score:.1f}] {r.keyword}")
            lines.append(
                f"    입장: {stance_lbl} | 생명주기: {r.lifecycle} "
                f"{r.trend_direction} | 예상: {r.estimated_duration}"
            )
            lines.append(
                f"    담당: {r.owner} | 긴급도: {r.urgency} "
                f"| 골든타임: {r.golden_time_hours}h"
            )
            lines.append(f"    대응: {r.response_message}")
            for tp in r.talking_points:
                lines.append(f"      - {tp}")
            if r.do_not_say:
                lines.append(f"    금지: {', '.join(r.do_not_say[:3])}")
            lines.append(
                f"    -> 전환: {r.pivot_to} | 연관 공약: {', '.join(r.related_pledges)}"
            )
            lines.append(f"    최선: {r.scenario_best}")
            lines.append(f"    최악: {r.scenario_worst}")
            lines.append("")

        return "\n".join(lines)


# ======================================================================
# __main__ — 실제 데이터로 테스트
# ======================================================================
if __name__ == "__main__":
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dotenv import load_dotenv

    load_dotenv(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    )

    from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
    from engines.issue_scoring import calculate_issue_score
    from collectors.naver_news import collect_issue_signals

    config = SAMPLE_GYEONGNAM_CONFIG
    signals = collect_issue_signals(
        [
            "경남도지사 선거",
            f"{config.candidate_name} 경남",
            "부울경 행정통합",
            "경남 조선업 일자리",
            "경남 청년 정책",
            "경남 우주항공",
            "박완수 경남",
        ],
        candidate_name=config.candidate_name,
        opponents=config.opponents,
    )

    scores = sorted(
        [calculate_issue_score(s, config) for s in signals],
        key=lambda x: x.score,
        reverse=True,
    )

    engine = IssueResponseEngine(config)
    responses = engine.analyze_all(scores, signals)
    print(engine.format_report(responses))
