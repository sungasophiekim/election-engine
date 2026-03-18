"""
Election Strategy Engine — Debate Preparation Engine
토론 준비 자료를 생성합니다. Claude API 없이 순수 로직으로 동작합니다.

기존 pledge_comparator.py의 get_debate_prep()을 확장하여
오프닝/클로징, 예상 질문 15개+, 공격/방어 스크립트, 피벗 메시지,
레드라인, 바디랭귀지 팁까지 포함하는 종합 토론 준비 패키지를 생성합니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from config.tenant_config import TenantConfig


# ══════════════════════════════════════════════════════════════════
# Data Classes
# ══════════════════════════════════════════════════════════════════

@dataclass
class DebateQuestion:
    """토론 예상 질문"""
    topic: str                    # 주제
    question: str                 # 예상 질문 원문
    difficulty: str               # "easy" | "medium" | "hard"
    source: str                   # "사회자" | "박완수" | "시민패널"
    recommended_response: str     # 권장 답변 (30초 분량, 3-4문장)
    pivot_to: str                 # 답변 후 전환할 우리 강점 주제
    trap_warning: str             # 함정 경고 (있으면)


@dataclass
class AttackScript:
    """공격 스크립트"""
    target: str                   # 대상 후보
    topic: str                    # 공격 주제
    opening_line: str             # 오프닝 (1문장, 임팩트 있게)
    main_argument: str            # 핵심 논거 (2-3문장)
    killer_question: str          # 상대를 궁지에 몰 질문
    follow_up: str                # 상대가 회피할 때 추격 질문
    evidence: str                 # 근거 데이터/사실


@dataclass
class DebatePrep:
    """토론 준비 종합 패키지"""
    opponent: str
    opening_statement: str        # 오프닝 스테이트먼트 (1분)
    closing_statement: str        # 클로징 스테이트먼트 (1분)
    expected_questions: list[DebateQuestion] = field(default_factory=list)
    attack_scripts: list[AttackScript] = field(default_factory=list)
    defense_scripts: list[dict] = field(default_factory=list)
    pivot_messages: list[str] = field(default_factory=list)
    red_lines: list[str] = field(default_factory=list)
    body_language_tips: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
# Debate Engine
# ══════════════════════════════════════════════════════════════════

class DebateEngine:
    """종합 토론 준비 엔진."""

    def __init__(self, config: TenantConfig):
        self.config = config

    # ── Public API ────────────────────────────────────────────────

    def prepare(self, opponent_name: str = "박완수") -> DebatePrep:
        """Full debate preparation package."""
        return DebatePrep(
            opponent=opponent_name,
            opening_statement=self._generate_opening(),
            closing_statement=self._generate_closing(),
            expected_questions=self._generate_expected_questions(opponent_name),
            attack_scripts=self._generate_attack_scripts(opponent_name),
            defense_scripts=self._generate_defense_scripts(opponent_name),
            pivot_messages=self._get_pivot_messages(),
            red_lines=self._get_red_lines(),
            body_language_tips=self._get_body_language_tips(),
        )

    # ── Opening Statement ─────────────────────────────────────────

    def _generate_opening(self) -> str:
        """
        1분 오프닝 스테이트먼트.
        구조: 인사 → 핵심 비전 → 구체적 약속 → 마무리
        """
        region = self.config.region

        return (
            f"존경하는 {region} 도민 여러분, 김경수입니다.\n\n"
            "'다시 경남, 제대로 한번' — 경남을 경험한 리더십으로 "
            "지방주도 성장을 이끌겠습니다. "
            "부울경 메가시티, 조선·방산 르네상스, 도민 생활지원금... "
            "말이 아닌 경험으로, 약속이 아닌 실행으로 보여드리겠습니다."
        )

    # ── Closing Statement ─────────────────────────────────────────

    def _generate_closing(self) -> str:
        """
        1분 클로징 스테이트먼트.
        구조: 오늘 토론 요약 → 차별화 포인트 → 도민에게 약속 → 투표 호소
        """
        return (
            "도민 여러분, 오늘 토론에서 확인하셨을 것입니다. "
            "경남을 직접 경험한 후보가 누구인지, 변화의 의지가 있는 후보가 누구인지.\n\n"
            "저는 위기 속에서도 경남의 기반을 지킨 사람입니다. "
            "이번에는 위기가 아닌 성장의 시대를 열겠습니다. "
            "부울경 메가시티로 대한민국 제2의 경제권을 만들고, "
            "조선·방산 르네상스로 경남 청년에게 기회를 돌려드리겠습니다.\n\n"
            "안정이라는 이름의 정체가 아닌, "
            "경험에서 나온 진짜 변화가 필요합니다.\n\n"
            "'다시 경남, 제대로 한번' — "
            "김경수에게 경남의 미래를 맡겨주십시오. "
            "반드시 결과로 보답하겠습니다. 감사합니다."
        )

    # ── Expected Questions ────────────────────────────────────────

    def _generate_expected_questions(self, opponent: str) -> list[DebateQuestion]:
        """예상 질문 15개+ 생성."""
        questions: list[DebateQuestion] = []

        # ── 1. 사회자 질문 (공정·정책 비교) ──
        questions.extend([
            DebateQuestion(
                topic="일자리 정책 비교",
                question="두 후보의 일자리 공약 차이는 무엇입니까?",
                difficulty="medium",
                source="사회자",
                recommended_response=(
                    "차이는 명확합니다. 저는 조선·방산 르네상스와 부울경 메가시티를 통해 "
                    "경남 전역에 양질의 일자리를 만듭니다. 경남을 경험한 리더십으로 "
                    "실질적 성과를 만들어 낸 사람과, 4년간 청년 유출을 막지 못한 현 도정, "
                    "도민께서 비교해 주십시오."
                ),
                pivot_to="경남 경험 리더십과 구체적 산업 비전",
                trap_warning="상대 공약을 직접 비방하는 것처럼 보이지 않도록, 우리 비전을 먼저 제시할 것",
            ),
            DebateQuestion(
                topic="부울경 통합",
                question="부울경 행정통합에 대한 입장을 밝혀 주세요.",
                difficulty="medium",
                source="사회자",
                recommended_response=(
                    "부울경 메가시티는 경남 도민의 삶을 바꿀 핵심 과제입니다. "
                    "다만 주민투표로 도민이 직접 결정하는 것이 원칙입니다. "
                    "도민이 원하면 추진하고, 원치 않으면 멈춥니다. "
                    "이것이 민주주의이고, 이것이 제 입장입니다."
                ),
                pivot_to="부울경 메가시티 실질적 협력과 도민 자기결정권",
                trap_warning="'도지사 자리 없어진다'는 프레임에 끌려가지 말 것 — 주민투표 원칙으로 대응",
            ),
            DebateQuestion(
                topic="도민 생활지원금 재원",
                question="도민 생활지원금 10만원, 재원은 어떻게 마련합니까?",
                difficulty="hard",
                source="사회자",
                recommended_response=(
                    "도세 잉여분과 특별교부세를 활용합니다. "
                    "3,300억은 경남 예산의 2% 수준입니다. "
                    "도민 생활 안정이 가장 시급한 지금, "
                    "충분히 감당 가능한 투자입니다."
                ),
                pivot_to="도민 생활 안정 최우선 + 재원 구체성",
                trap_warning="'포퓰리즘' 프레임에 갇히지 말 것 — 재원 구조를 즉시 제시",
            ),
            DebateQuestion(
                topic="재정 건전성",
                question="두 후보 공약을 합산하면 천문학적 예산인데, 경남도 재정으로 감당 가능합니까?",
                difficulty="hard",
                source="사회자",
                recommended_response=(
                    "저의 공약은 단계별 실행과 재원 조달 계획이 명확합니다. "
                    "도민 생활지원금은 도세 잉여분 활용, 산업 투자는 국비와 민간투자 병행. "
                    "오히려 현 도정의 스마트산단 1조 2천억 투자야말로 "
                    "기재부 협의 상황이 불투명하지 않습니까?"
                ),
                pivot_to="우리 공약의 단계적 재원 구조 + 상대 재원 불투명성",
                trap_warning="우리 공약 재원도 공격받을 수 있으므로 구체적 수치를 즉시 제시",
            ),
            DebateQuestion(
                topic="도지사 자질",
                question="경남도지사에게 가장 필요한 자질은 무엇이라 생각하십니까?",
                difficulty="easy",
                source="사회자",
                recommended_response=(
                    "경험과 변화의 의지입니다. 경남을 직접 이끌어 본 경험, "
                    "그리고 정체가 아닌 변화를 만들어낼 의지. "
                    "안정이라는 이름으로 4년을 보낸 것이 아니라, "
                    "위기 속에서도 기반을 지킨 경험이 진짜 리더십입니다."
                ),
                pivot_to="경험 + 변화 의지 = 진짜 리더십",
                trap_warning="사법 리스크 등 다른 자질로 유도될 수 있음 — '경험과 변화'로 고정",
            ),
        ])

        # ── 2. 상대 후보(박완수) 공격 질문 ──
        if opponent in ("박완수", "all"):
            questions.extend([
                DebateQuestion(
                    topic="사법 리스크",
                    question="4년간 사법 리스크로 도정에 공백이 있었는데, 이번에는 어떻게 다릅니까?",
                    difficulty="hard",
                    source="박완수",
                    recommended_response=(
                        "모든 사법 절차가 완료되었습니다. "
                        "저는 경남 발전으로 도민께 보답하는 것에 집중하겠습니다. "
                        "과거가 아닌 미래를 봐주십시오. "
                        "오히려 현 도정 4년간 경남이 얼마나 나아졌는지가 더 중요한 질문입니다."
                    ),
                    pivot_to="사법 절차 완료 → 현 도정 성과 부재 역공",
                    trap_warning="절대 감정적으로 반응하지 말 것 — 차분하게 '사법 절차 완료'로만 대응, '드루킹' 직접 언급 금지",
                ),
                DebateQuestion(
                    topic="도민 10만원 포퓰리즘",
                    question="도민 10만원이 포퓰리즘 아닙니까? 일회성 현금 살포로 뭘 바꿉니까?",
                    difficulty="hard",
                    source="박완수",
                    recommended_response=(
                        "도세 잉여분과 특별교부세를 활용합니다. 3,300억은 경남 예산의 2% 수준. "
                        "도민 생활 안정이 가장 시급합니다. "
                        "지역 경제 순환 효과까지 고려하면 투자 대비 효과가 분명합니다. "
                        "오히려 현 도정의 스마트산단 1조 2천억 재원 조달은 어디까지 왔습니까?"
                    ),
                    pivot_to="재원 구체성 + 상대 재원 불투명성 역공",
                    trap_warning="'포퓰리즘' 프레임에 갇히지 말 것 — 재원 구조 즉시 제시 후 역공",
                ),
                DebateQuestion(
                    topic="조선업 구조조정 대응",
                    question="조선업 구조조정 때 뭘 하셨습니까? 거제 인구가 2만 명이나 줄었는데요.",
                    difficulty="hard",
                    source="박완수",
                    recommended_response=(
                        "코로나 위기와 조선업 구조조정이라는 이중 위기 속에서도 "
                        "경남 경제 기반을 지켰습니다. 거제 인구 감소는 전국적 조선업 구조조정의 결과이지, "
                        "도정 실패가 아닙니다. 이번에는 조선·방산 르네상스로 "
                        "거제에 새로운 기회를 만들겠습니다."
                    ),
                    pivot_to="위기 극복 경험 → 조선·방산 르네상스 비전",
                    trap_warning="과거 방어에 너무 오래 머물지 말 것 — 빠르게 미래 비전으로 전환",
                ),
            ])

        # ── 3. 시민패널 질문 ──
        questions.extend([
            DebateQuestion(
                topic="청년 유출",
                question="청년이 경남을 떠나는 이유가 뭐라고 생각하시나요?",
                difficulty="medium",
                source="시민패널",
                recommended_response=(
                    "일자리와 삶의 질입니다. 양질의 일자리가 부족하고, "
                    "문화·교통 인프라가 열악하기 때문입니다. "
                    "조선·방산 르네상스로 일자리를 만들고, 부울경 메가시티로 "
                    "생활 인프라를 혁신하겠습니다. 경남에 남으면 기회가 있다는 것을 보여드리겠습니다."
                ),
                pivot_to="일자리 + 생활 인프라 혁신",
                trap_warning="추상적 비전이 아닌 구체적 해법으로 답할 것",
            ),
            DebateQuestion(
                topic="거제 경제",
                question="거제 경제를 살릴 구체적 방법이 있습니까?",
                difficulty="medium",
                source="시민패널",
                recommended_response=(
                    "거제는 조선업 의존도를 낮추면서 방위산업과 해양레저 산업을 육성합니다. "
                    "조선 기술 인력을 방산·해양플랜트로 전환하는 재교육 프로그램을 가동하고, "
                    "거제-통영 권역 관광 산업을 활성화하겠습니다. "
                    "경남을 경험한 사람이 거제의 해법도 알고 있습니다."
                ),
                pivot_to="조선·방산 전환 + 관광 활성화",
                trap_warning="조선업 포기로 비칠 수 있음 — '전환'과 '다각화' 강조",
            ),
            DebateQuestion(
                topic="물가 대책",
                question="물가가 너무 올랐습니다. 도지사가 할 수 있는 물가 대책이 있습니까?",
                difficulty="medium",
                source="시민패널",
                recommended_response=(
                    "도민 생활지원금 10만원이 바로 그 대책입니다. "
                    "물가 상승으로 어려운 도민의 생활을 직접 지원하겠습니다. "
                    "또한 지역 농산물 직거래 확대, 공공배달앱 활성화로 "
                    "중간 유통 비용을 줄여 체감 물가를 낮추겠습니다."
                ),
                pivot_to="도민 생활지원금 + 유통 혁신",
                trap_warning="도지사 권한 밖의 거시경제 영역으로 끌려가지 말 것 — 도정 차원 대책으로 한정",
            ),
            DebateQuestion(
                topic="농촌 고령화",
                question="농촌 지역 고령화가 심각한데, 밀양·함안 같은 곳에 대한 대책이 있습니까?",
                difficulty="medium",
                source="시민패널",
                recommended_response=(
                    "농촌 지역은 스마트팜 도입과 6차 산업 육성으로 소득을 높이고, "
                    "공공의료 확충으로 어르신들의 삶의 질을 개선합니다. "
                    "부울경 메가시티 광역교통이 연결되면 농촌 청년들도 도시 일자리에 접근할 수 있습니다. "
                    "경남 전역이 고르게 발전하는 것이 저의 목표입니다."
                ),
                pivot_to="부울경 메가시티 연결성 + 균형발전",
                trap_warning="도시 중심 공약이라는 비판 차단 — 농촌 구체 정책 언급",
            ),
            DebateQuestion(
                topic="환경 문제",
                question="낙동강 수질 문제와 경남 환경 정책은 어떻게 되어 있습니까?",
                difficulty="easy",
                source="시민패널",
                recommended_response=(
                    "낙동강 수질 관리를 위해 산단 폐수 실시간 모니터링 시스템을 구축합니다. "
                    "산업 단지는 친환경 기준을 의무화하여 성장과 환경을 동시에 잡겠습니다. "
                    "경남의 자연은 경남의 미래 자산입니다."
                ),
                pivot_to="친환경 산업 기준 의무화",
                trap_warning="",
            ),
        ])

        return questions

    # ── Attack Scripts ────────────────────────────────────────────

    def _generate_attack_scripts(self, opponent: str) -> list[AttackScript]:
        """공격 스크립트 5개+ 생성."""
        scripts: list[AttackScript] = []

        if opponent in ("박완수", "all"):
            scripts.extend([
                AttackScript(
                    target="박완수",
                    topic="현직 4년 성과 부재",
                    opening_line="4년간 뭘 하셨습니까?",
                    main_argument=(
                        "경남 청년 유출은 더 심해졌고, 도민 체감 경기는 바닥입니다. "
                        "초박빙 여론조사가 도민의 답입니다. "
                        "현직 도지사가 압도적 지지를 받지 못한다는 것은 "
                        "도민이 변화를 원한다는 뜻입니다."
                    ),
                    killer_question=(
                        "4년간 경남 청년 유출이 더 심해졌는데, "
                        "현 도지사로서 책임을 느끼십니까?"
                    ),
                    follow_up=(
                        "초박빙 여론조사가 도민의 심판이 아니라면 "
                        "무엇이라고 해석하십니까?"
                    ),
                    evidence=(
                        "현 도정 기간 경남 청년 순유출 지속, "
                        "도민 체감 경기 하락, 여론조사 초박빙 상황."
                    ),
                ),
                AttackScript(
                    target="박완수",
                    topic="스마트산단 재원 불투명",
                    opening_line="1조 2천억 투자? 재원 조달 계획을 보여주십시오.",
                    main_argument=(
                        "기재부 협의는 어디까지 왔습니까? "
                        "예비타당성 조사도 착수하지 않은 상태에서 "
                        "1조 2천억 투자를 약속하는 것은 빈 수표입니다. "
                        "도민에게 실현 가능성부터 증명하셔야 합니다."
                    ),
                    killer_question=(
                        "스마트산단 1조 2천억, 기재부 협의는 어디까지 왔습니까? "
                        "구체적으로 답변해 주십시오."
                    ),
                    follow_up=(
                        "기재부 협의가 완료되지 않았다면 "
                        "이 공약은 실현 가능성이 없는 것 아닙니까?"
                    ),
                    evidence=(
                        "스마트산단 1조 2천억 투자 공약, "
                        "예비타당성 조사 미착수 상태, "
                        "기재부 공식 협의 결과 미공개."
                    ),
                ),
                AttackScript(
                    target="박완수",
                    topic="BRT 임기 내 불가",
                    opening_line="2028년 개통이면 임기가 끝납니다.",
                    main_argument=(
                        "책임질 수 없는 공약은 공약이 아니라 공수표입니다. "
                        "BRT 2028년 개통 계획은 사실상 다음 도지사에게 떠넘기는 것입니다. "
                        "임기 내 착공조차 불확실한 상황에서 "
                        "도민에게 약속이라고 말할 수 있습니까?"
                    ),
                    killer_question=(
                        "BRT 2028년 개통이면 임기 마지막 해인데, "
                        "임기 내 완공을 책임질 수 있습니까?"
                    ),
                    follow_up=(
                        "착공도 못 하고 임기가 끝나면 "
                        "누가 이 사업을 책임집니까?"
                    ),
                    evidence=(
                        "BRT 3개 노선 2028년 개통 계획, "
                        "도지사 임기 2026~2030 기준 임기 말 개통 구조, "
                        "착공 일정 불확실."
                    ),
                ),
                AttackScript(
                    target="박완수",
                    topic="우주항공 편중",
                    opening_line="사천에만 집중하는 우주항공, 나머지 도민에게는 무슨 의미입니까?",
                    main_argument=(
                        "우주항공 산업이 사천에만 집중되어 있습니다. "
                        "창원·김해·거제 도민에게는 무슨 혜택이 있습니까? "
                        "경남 전체의 균형 발전이 아닌 "
                        "특정 지역 편중 정책은 도민 통합에 해가 됩니다."
                    ),
                    killer_question=(
                        "우주항공 산업이 창원·김해·거제 도민에게 "
                        "어떤 구체적 혜택을 줍니까?"
                    ),
                    follow_up=(
                        "사천 외 지역에 대한 산업 비전을 "
                        "구체적으로 말씀해 주십시오."
                    ),
                    evidence=(
                        "우주항공산업 특화단지 사천 집중, "
                        "창원·김해·거제 등 타 지역 연계 계획 미흡, "
                        "경남 서부·동부권 균형발전 과제."
                    ),
                ),
                AttackScript(
                    target="박완수",
                    topic="행정 안정성 vs 변화",
                    opening_line="안정이라는 이름의 정체, 도민은 변화를 원합니다.",
                    main_argument=(
                        "현 도정은 '안정적 행정'을 내세우지만, "
                        "도민이 체감하는 것은 안정이 아니라 정체입니다. "
                        "변화 없는 4년이 더 계속되어도 괜찮습니까? "
                        "초박빙 여론조사가 도민의 변화 열망을 보여줍니다."
                    ),
                    killer_question=(
                        "4년간의 '안정적 행정'으로 경남이 나아졌다고 "
                        "자신 있게 말씀하실 수 있습니까?"
                    ),
                    follow_up=(
                        "도민이 체감하는 성과를 "
                        "딱 하나만 말씀해 주십시오."
                    ),
                    evidence=(
                        "현 도정 4년간 경남 주요 지표 정체, "
                        "여론조사 초박빙, "
                        "도민 체감 경기 하락."
                    ),
                ),
            ])

        return scripts

    # ── Defense Scripts ───────────────────────────────────────────

    def _generate_defense_scripts(self, opponent: str) -> list[dict]:
        """방어 스크립트 5개+ 생성."""
        return [
            {
                "attack": "도민 10만원 재원은 어디서 나옵니까?",
                "response": (
                    "도세 잉여분과 특별교부세를 활용합니다. "
                    "3,300억은 경남 예산의 2% 수준. "
                    "도민 생활 안정이 가장 시급합니다."
                ),
                "pivot": (
                    "오히려 현 도정의 스마트산단 1조 2천억 재원 조달은 "
                    "어디까지 진행되었습니까? 기재부 협의 결과를 공개해 주십시오."
                ),
            },
            {
                "attack": "부울경 통합하면 경남도지사가 없어지지 않습니까?",
                "response": (
                    "주민투표로 도민이 직접 결정합니다. "
                    "도민이 원하면 추진하고, 원치 않으면 멈춥니다. "
                    "이것이 민주주의입니다."
                ),
                "pivot": (
                    "중요한 것은 경남 도민의 삶이 나아지느냐입니다. "
                    "부울경 메가시티는 경남의 경쟁력을 높이는 선택지이며, "
                    "최종 결정은 도민의 몫입니다."
                ),
            },
            {
                "attack": "사법 리스크가 있지 않습니까?",
                "response": (
                    "모든 사법 절차가 완료되었습니다. "
                    "저는 경남 발전으로 도민께 보답하는 것에 집중하겠습니다. "
                    "과거가 아닌 미래를 봐주십시오."
                ),
                "pivot": (
                    "도민께서 궁금해하시는 것은 과거가 아니라 "
                    "앞으로 경남이 어떻게 달라지느냐입니다. "
                    "경남을 경험한 리더십으로 변화를 만들겠습니다."
                ),
            },
            {
                "attack": "전 도지사 재임 시절 구체적 성과가 무엇입니까?",
                "response": (
                    "코로나 위기 속에서도 경남 경제 기반을 지켰습니다. "
                    "이번에는 위기가 아닌 성장의 시대를 열겠습니다."
                ),
                "pivot": (
                    "위기를 경험한 리더가 성장도 이끌 수 있습니다. "
                    "조선·방산 르네상스, 부울경 메가시티 — "
                    "경남을 아는 사람이 경남을 바꿉니다."
                ),
            },
            {
                "attack": "중앙정부 정권에 의존적인 공약 아닙니까?",
                "response": (
                    "지방시대위원장으로 여야 구분 없이 전국 광역단체와 협력했습니다. "
                    "중앙정부 네트워크는 정권이 아닌 인적 자산입니다."
                ),
                "pivot": (
                    "오히려 현 도정이야말로 여당 프리미엄에 의존하고 있지 않습니까? "
                    "저는 여야를 넘어 경남을 위한 네트워크를 구축해 왔습니다."
                ),
            },
        ]

    # ── Pivot Messages ────────────────────────────────────────────

    def _get_pivot_messages(self) -> list[str]:
        """어떤 질문이든 30초 안에 돌아올 핵심 피벗 메시지 3개."""
        return [
            "'다시 경남, 제대로 한번' — 경남을 경험한 리더십으로 도민의 삶을 바꿉니다.",
            "지방주도 성장 5극3특, 부울경 메가시티 — 경남이 대한민국 성장 엔진이 됩니다.",
            "말이 아닌 경험, 약속이 아닌 실행 — 경남을 아는 사람이 경남을 바꿉니다.",
        ]

    # ── Red Lines ─────────────────────────────────────────────────

    def _get_red_lines(self) -> list[str]:
        """절대 하면 안 되는 발언 목록."""
        return [
            "드루킹 사건을 직접 언급하지 마라 — 상대가 꺼내도 '사법 절차 완료'로만 대응",
            "현직 도지사를 인신공격하지 마라 — '현 도정', '현 도지사'로 지칭",
            "감정적으로 반응하지 마라 — 특히 사법 리스크 질문에 차분하게",
            "검증 안 된 수치 즉흥 발언 금지",
            "전희영 후보 직접 공격 금지 — 진보표 분산 유리",
        ]

    # ── Body Language Tips ────────────────────────────────────────

    def _get_body_language_tips(self) -> list[str]:
        """비언어 커뮤니케이션 팁."""
        return [
            "상대 발언 중 고개를 끄덕이며 경청하는 모습 — 여유와 자신감 표현",
            "공격받을 때 미소 — 감정적으로 흔들리지 않는 모습",
            "숫자를 말할 때 손가락으로 카운트 — 구체성 강조",
            "카메라를 직접 보며 마무리 — 도민에게 직접 호소하는 효과",
            "메모를 자주 확인하지 마라 — 준비된 후보 이미지 손상",
            "상대 발언 중 고개를 젓거나 비웃지 마라 — 도발에 넘어간 것처럼 보임",
            "답변 시 사회자가 아닌 카메라(도민)를 향해 말하라 — 직접 소통 효과",
            "사법 리스크 질문 시 특히 차분한 표정 유지 — 동요하면 약점 노출",
            "오프닝과 클로징에서는 일어서서 인사 — 예의 바른 이미지",
        ]

    # ── Report Formatter ──────────────────────────────────────────

    def format_report(self, prep: DebatePrep) -> str:
        """토론 준비 보고서 출력."""
        lines: list[str] = []
        sep = "=" * 74
        sub_sep = "-" * 74

        lines.append(sep)
        lines.append(f"  토론 준비 종합 보고서 — 상대: {prep.opponent}")
        lines.append(f"  후보: {self.config.candidate_name} ({self.config.slogan})")
        lines.append(f"  선거: {self.config.election_date} {self.config.region} {self.config.election_type}")
        lines.append(sep)

        # ── 1. 오프닝 스테이트먼트 ──
        lines.append("\n[1] 오프닝 스테이트먼트 (1분)")
        lines.append(sub_sep)
        lines.append(prep.opening_statement)

        # ── 2. 클로징 스테이트먼트 ──
        lines.append(f"\n\n[2] 클로징 스테이트먼트 (1분)")
        lines.append(sub_sep)
        lines.append(prep.closing_statement)

        # ── 3. 핵심 피벗 메시지 ──
        lines.append(f"\n\n[3] 핵심 피벗 메시지 (어떤 질문이든 30초 안에 복귀)")
        lines.append(sub_sep)
        for i, msg in enumerate(prep.pivot_messages, 1):
            lines.append(f"  {i}. {msg}")

        # ── 4. 예상 질문 & 권장 답변 ──
        lines.append(f"\n\n[4] 예상 질문 & 권장 답변 ({len(prep.expected_questions)}개)")
        lines.append(sub_sep)

        # 출처별 그룹핑
        source_order = ["사회자", prep.opponent, "시민패널"]
        by_source: dict[str, list[DebateQuestion]] = {}
        for q in prep.expected_questions:
            by_source.setdefault(q.source, []).append(q)

        q_num = 0
        for source in source_order:
            qs = by_source.get(source, [])
            if not qs:
                continue
            lines.append(f"\n  ── {source} 질문 ({len(qs)}개) ──")
            for q in qs:
                q_num += 1
                diff_mark = {"easy": "[쉬움]", "medium": "[보통]", "hard": "[어려움]"}
                lines.append(f"\n  Q{q_num}. {diff_mark.get(q.difficulty, '')} {q.question}")
                lines.append(f"      주제: {q.topic}")
                lines.append(f"      권장 답변: {q.recommended_response}")
                lines.append(f"      피벗: → {q.pivot_to}")
                if q.trap_warning:
                    lines.append(f"      ⚠ 함정: {q.trap_warning}")

        # ── 5. 공격 스크립트 ──
        lines.append(f"\n\n[5] 공격 스크립트 ({len(prep.attack_scripts)}개)")
        lines.append(sub_sep)
        for i, a in enumerate(prep.attack_scripts, 1):
            lines.append(f"\n  공격 {i}: [{a.target}] {a.topic}")
            lines.append(f"    오프닝: \"{a.opening_line}\"")
            lines.append(f"    핵심 논거: {a.main_argument}")
            lines.append(f"    킬러 질문: \"{a.killer_question}\"")
            lines.append(f"    추격 질문: \"{a.follow_up}\"")
            lines.append(f"    근거: {a.evidence}")

        # ── 6. 방어 스크립트 ──
        lines.append(f"\n\n[6] 방어 스크립트 ({len(prep.defense_scripts)}개)")
        lines.append(sub_sep)
        for i, d in enumerate(prep.defense_scripts, 1):
            lines.append(f"\n  방어 {i}: 예상 공격 — \"{d['attack']}\"")
            lines.append(f"    대응: {d['response']}")
            lines.append(f"    피벗: → {d['pivot']}")

        # ── 7. 레드라인 ──
        lines.append(f"\n\n[7] 레드라인 — 절대 하면 안 되는 발언 ({len(prep.red_lines)}개)")
        lines.append(sub_sep)
        for i, rl in enumerate(prep.red_lines, 1):
            lines.append(f"  {i}. {rl}")

        # ── 8. 바디랭귀지 팁 ──
        lines.append(f"\n\n[8] 바디랭귀지 & 비언어 커뮤니케이션 ({len(prep.body_language_tips)}개)")
        lines.append(sub_sep)
        for i, tip in enumerate(prep.body_language_tips, 1):
            lines.append(f"  {i}. {tip}")

        # ── 마무리 ──
        lines.append(f"\n\n{sep}")
        lines.append(f"  토론 준비 보고서 끝 — {self.config.candidate_name} 캠프 내부 자료")
        lines.append(sep)

        return "\n".join(lines)
