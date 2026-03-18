"""
Election Strategy Engine — Engine 6: Pledge Comparator
상대 후보 공약 대비 분석, 공격/방어 포인트, 지역별 유세 메시지, 토론 대비 자료 생성.
"""
from __future__ import annotations

from config.tenant_config import TenantConfig


# ══════════════════════════════════════════════════════════════════
# 상대 후보 공약 데이터
# ══════════════════════════════════════════════════════════════════

OPPONENT_PLEDGES = {
    "박완수": {
        "party": "국민의힘",
        "pledges": [
            {
                "name": "경남형 스마트산단",
                "category": "산업",
                "description": "5개소 조성, 1조 2천억 투자, 일자리 3만 개",
                "numbers": "5개소, 1조 2천억, 3만 일자리",
                "regions": ["창원시", "김해시"],
                "strength": "구체적 수치 제시",
                "weakness": "1조 2천억 재원 조달 방안 불투명, 기재부 협의 미완료",
            },
            {
                "name": "교통 혁신 BRT",
                "category": "교통",
                "description": "창원-진주-김해 BRT 3개 노선, 2028년 개통",
                "numbers": "BRT 3개 노선, 2028년",
                "regions": ["창원시", "진주시", "김해시"],
                "strength": "광역교통 체계 구축",
                "weakness": "2028년 개통이면 임기 내 완료 불가 — 공수표 가능",
            },
            {
                "name": "청년 일자리 2만개",
                "category": "청년",
                "description": "5년간 청년 일자리 2만 개 창출",
                "numbers": "2만 개",
                "regions": ["전체"],
                "strength": "기업 인센티브 + 창업 병행",
                "weakness": "현직 4년간 청년 유출 심화 — 실적 증명 실패",
            },
            {
                "name": "우주항공 허브",
                "category": "산업",
                "description": "사천 우주항공 클러스터, 우주항공산업진흥원 설립",
                "numbers": "",
                "regions": ["사천시"],
                "strength": "누리호 성공 분위기 활용",
                "weakness": "사천 편중 — 다른 지역 소외감, 산업 기반 미약",
            },
            {
                "name": "현직 도정 성과",
                "category": "행정",
                "description": "우주항공 기반 구축, 경남형 일자리 12만개 주장",
                "numbers": "12만 일자리",
                "regions": ["전체"],
                "strength": "현직 경험, 행정 안정성",
                "weakness": "도민 체감 성과 부족, 여론조사 초박빙이 증거",
            },
        ],
    },
    "전희영": {
        "party": "진보당",
        "pledges": [
            {
                "name": "성평등위원회",
                "category": "여성",
                "description": "도지사 직속, 도정 전체 예산에 성인지 관점 반영",
                "numbers": "",
                "regions": ["전체"],
                "strength": "최초 여성 후보 상징성",
                "weakness": "경남 보수 유권자 반감 가능",
            },
            {
                "name": "대학생 3대 생존정책",
                "category": "청년",
                "description": "천원의 밥상, 1만원 공공주택, 경남형 공공일자리",
                "numbers": "월 임대료 1만원, 천원 식사",
                "regions": ["진주시", "창원시"],
                "strength": "청년층 직접 체감",
                "weakness": "재원 확보 방안 미제시",
            },
            {
                "name": "부울경 행정통합",
                "category": "행정",
                "description": "동남권 경제비전, 다핵 분권·주민자치 강화",
                "numbers": "",
                "regions": ["전체"],
                "strength": "진보 진영 통합 논리",
                "weakness": "실현 가능성 낮음",
            },
        ],
    },
}


# ══════════════════════════════════════════════════════════════════
# 우리 공약 카테고리 매핑 및 메타 정보
# ══════════════════════════════════════════════════════════════════

OUR_PLEDGE_CATEGORIES = {
    "지방주도 성장": {
        "category": "경제",
        "regions": ["전체"],
        "strength": "지방시대위원장 경험, 중앙정부 네트워크, 5극3특 설계 주도",
        "weakness": "정권 의존적 구조",
    },
    "부울경 메가시티": {
        "category": "행정",
        "regions": ["전체"],
        "strength": "부울경 1000만 메가시티 비전, 여론조사 기반 민주적 추진",
        "weakness": "경남 정체성 약화 우려, 부산·울산 반발 가능",
    },
    "경남도민 생활지원금": {
        "category": "복지",
        "regions": ["전체"],
        "strength": "즉각적 체감 효과, 지역 경제 활성화",
        "weakness": "3,300억 재원 마련 방안 구체화 필요",
    },
    "조선·방산 르네상스": {
        "category": "산업",
        "regions": ["거제시", "창원시"],
        "strength": "K-방산 수출 호황과 연계, 거제·창원 표심 공략",
        "weakness": "전 도지사 임기 시 조선업 구조조정 경험",
    },
    "청년 정주 패키지": {
        "category": "청년",
        "regions": ["전체"],
        "strength": "월세 30만원 + 장려금 500만원 직접 지원, 체감 효과 높음",
        "weakness": "지속가능성 의문, 재정 부담",
    },
}


# ══════════════════════════════════════════════════════════════════
# Engine 6: Pledge Comparator
# ══════════════════════════════════════════════════════════════════

class PledgeComparator:
    """상대 후보 공약 대비 분석 엔진."""

    def __init__(self, config: TenantConfig):
        self.config = config
        self.our_pledges = config.pledges
        self.opponent_pledges = OPPONENT_PLEDGES

    # ── 카테고리별 공약 대비표 ──────────────────────────────────

    def generate_comparison_matrix(self) -> dict:
        """
        카테고리별 공약 대비표 생성.
        Returns dict[category] -> {"우리": [...], "박완수": [...], "전희영": [...]}
        """
        # 모든 카테고리 수집
        categories: set[str] = set()

        # 우리 공약 카테고리 수집
        our_pledge_list = []
        for pledge_name, pledge_data in self.our_pledges.items():
            meta = OUR_PLEDGE_CATEGORIES.get(pledge_name, {})
            category = meta.get("category", "기타")
            categories.add(category)
            our_pledge_list.append({
                "name": pledge_name,
                "category": category,
                "description": pledge_data.get("설명", ""),
                "numbers": pledge_data.get("수치", ""),
                "regions": meta.get("regions", ["전체"]),
                "strength": meta.get("strength", ""),
                "weakness": meta.get("weakness", ""),
            })

        # 상대 공약 카테고리 수집
        for opp_name, opp_info in self.opponent_pledges.items():
            for p in opp_info["pledges"]:
                categories.add(p["category"])

        # 매트릭스 구성
        matrix = {}
        for cat in sorted(categories):
            matrix[cat] = {"우리": [], "우리_후보": self.config.candidate_name}
            # 우리 공약
            for p in our_pledge_list:
                if p["category"] == cat:
                    matrix[cat]["우리"].append(p)
            # 상대 공약
            for opp_name, opp_info in self.opponent_pledges.items():
                matrix[cat][opp_name] = []
                for p in opp_info["pledges"]:
                    if p["category"] == cat:
                        matrix[cat][opp_name].append(p)

        return matrix

    # ── 공격 포인트 생성 ────────────────────────────────────────

    def find_attack_points(self, opponent_name: str = None) -> list[dict]:
        """
        상대 공약의 약점을 분석하여 공격 포인트 생성.
        opponent_name이 None이면 전체 상대에 대해 생성.
        """
        attacks = []
        targets = (
            {opponent_name: self.opponent_pledges[opponent_name]}
            if opponent_name and opponent_name in self.opponent_pledges
            else self.opponent_pledges
        )

        for opp_name, opp_info in targets.items():
            for p in opp_info["pledges"]:
                weakness = p.get("weakness", "")
                if not weakness:
                    continue

                # 공격 각도와 심각도 판정
                attack_angle, severity, talking_point = self._build_attack(
                    opp_name, p
                )

                attacks.append({
                    "target": opp_name,
                    "pledge": p["name"],
                    "attack_angle": attack_angle,
                    "talking_point": talking_point,
                    "severity": severity,
                    "regions": p.get("regions", ["전체"]),
                })

        # severity 우선순위로 정렬
        severity_order = {"high": 0, "medium": 1, "low": 2}
        attacks.sort(key=lambda x: severity_order.get(x["severity"], 3))
        return attacks

    def _build_attack(self, opp_name: str, pledge: dict) -> tuple[str, str, str]:
        """공약 하나에 대해 (attack_angle, severity, talking_point) 반환."""
        weakness = pledge.get("weakness", "")
        numbers = pledge.get("numbers", "")
        name = pledge["name"]

        # ── 박완수 전용 공격 포인트 ──
        if opp_name == "박완수":
            if name == "경남형 스마트산단":
                return (
                    "재원",
                    "high",
                    "스마트산단 1조 2천억 재원은 어디서? 기재부 협의도 안 된 공약, 도민을 속이는 것입니다.",
                )
            if name == "교통 혁신 BRT":
                return (
                    "실행력",
                    "high",
                    "BRT 2028년이면 임기 끝, 공수표 아닌가? 착공도 못 하고 퇴임할 공약입니다.",
                )
            if name == "청년 일자리 2만개":
                return (
                    "실적",
                    "high",
                    "현직 4년 청년 유출 심화 — 뭘 했나? 4년간 기회가 있었는데 청년은 떠났습니다.",
                )
            if name == "우주항공 허브":
                return (
                    "편중",
                    "medium",
                    "우주항공은 사천만을 위한 공약. 나머지 경남 지역은 소외됩니다.",
                )
            if name == "현직 도정 성과":
                return (
                    "실적",
                    "high",
                    "도민 체감 성과 부족, 초박빙이 증거. 12만 일자리? 도민은 체감하지 못합니다.",
                )

        # 재원 관련 약점
        if any(kw in weakness for kw in ["재원", "불투명", "미제시"]):
            angle = "재원"
            severity = "high"
            if numbers:
                tp = f"{numbers}. 재원 조달 방안 없는 표 매수 공약입니다."
            else:
                tp = f"{opp_name} 후보의 '{name}' — 예산은 얼마나 드는지, 돈은 어디서 나오는지 답이 없습니다."

        # 실행력/실적 관련
        elif any(kw in weakness for kw in ["실행력", "성과 미미", "실현 가능성", "실적 증명", "체감 성과"]):
            angle = "실행력"
            severity = "high"
            tp = f"{opp_name} 후보의 '{name}' — 말만 하고 실행은 없었습니다. 과거 실적이 증명합니다."

        # 편중/소외 관련
        elif any(kw in weakness for kw in ["편중", "소외"]):
            angle = "편중"
            severity = "medium"
            tp = f"'{name}' — 특정 지역만을 위한 공약. 경남 전체의 균형발전과는 거리가 멉니다."

        # 임기 내 완료 불가
        elif any(kw in weakness for kw in ["임기", "공수표"]):
            angle = "실행력"
            severity = "high"
            tp = f"'{name}' — 임기 내 완료 불가능한 공약. 도민에게 빈 약속입니다."

        # 반발/반감 가능성
        elif any(kw in weakness for kw in ["반발", "반감"]):
            angle = "민심 이반"
            severity = "medium"
            tp = f"'{name}' — 경남 도민의 정서와 맞지 않는 정책입니다."

        # 로드맵 부재
        elif any(kw in weakness for kw in ["로드맵 부재", "구체적"]):
            angle = "구체성 부족"
            severity = "medium"
            tp = f"'{name}' — 언제, 어떻게, 얼마로? 구체적 실행 계획이 없습니다."

        # 정권 의존
        elif any(kw in weakness for kw in ["정권", "무력화"]):
            angle = "정권 의존"
            severity = "medium"
            tp = f"'{name}' — 정권이 바뀌면 무력화되는 공약. 지속가능한 경남 발전 전략이 아닙니다."

        # 기타
        else:
            angle = "기타"
            severity = "low"
            tp = f"'{name}' — {weakness}"

        return angle, severity, tp

    # ── 방어 포인트 생성 ────────────────────────────────────────

    def find_defense_points(self) -> list[dict]:
        """
        우리 공약이 공격받을 수 있는 약점과 방어 논리 생성.
        """
        defenses = []

        defense_map = {
            "경남도민 생활지원금": {
                "potential_attack": "도민 10만원 3,300억 재원?",
                "defense_logic": (
                    "도세 잉여분 + 특별교부세로 충분. "
                    "도민 생활 안정이 최우선. 지역 경제 활성화로 세수 환류 효과까지 기대."
                ),
                "severity": "high",
            },
            "부울경 메가시티": {
                "potential_attack": "부울경 통합하면 경남도지사 없어지는데?",
                "defense_logic": (
                    "주민투표로 결정. 도민이 원하면 추진, 원치 않으면 중단. "
                    "민주적 절차가 핵심이며, 도민 의사를 무시하는 일은 없을 것."
                ),
                "severity": "medium",
            },
            "지방주도 성장": {
                "potential_attack": "중앙정부 의존적 구조 아닌가?",
                "defense_logic": (
                    "지방시대위원장 경험으로 중앙정부 네트워크를 구축했다. "
                    "의존이 아니라 협력. 경남이 주도하고 중앙이 지원하는 구조."
                ),
                "severity": "medium",
            },
            "조선·방산 르네상스": {
                "potential_attack": "전 도지사 재임 시 조선업 구조조정 아니었나?",
                "defense_logic": (
                    "글로벌 조선 불황기였다. 지금은 K-방산 수출 호황이라는 전혀 다른 환경. "
                    "위기 극복 경험이 오히려 강점. 조선·방산 현장을 가장 잘 아는 후보."
                ),
                "severity": "medium",
            },
            "청년 정주 패키지": {
                "potential_attack": "월세 30만원, 장려금 500만원 — 재정 부담 아닌가?",
                "defense_logic": (
                    "청년 유출이 경남 최대 위기. 청년 1명 유출 시 지역경제 손실이 더 크다. "
                    "청년이 남아야 경남이 산다. 선제 투자 관점에서 충분히 합리적."
                ),
                "severity": "low",
            },
        }

        # 사법 리스크 방어 (드루킹은 forbidden_words이므로 직접 언급 않음)
        defenses.append({
            "our_pledge": "후보 신뢰성",
            "potential_attack": "사법 리스크 — 과거 사건 전과",
            "defense_logic": (
                "사법적 절차 완료, 특별사면. 사법 리스크 해소 완료. "
                "경남 발전으로 도민께 보답하겠다. 과거가 아닌 미래를 선택해 달라."
            ),
            "severity": "high",
        })

        for pledge_name, pledge_data in self.our_pledges.items():
            meta = OUR_PLEDGE_CATEGORIES.get(pledge_name, {})
            dm = defense_map.get(pledge_name)
            if dm:
                defenses.append({
                    "our_pledge": pledge_name,
                    "potential_attack": dm["potential_attack"],
                    "defense_logic": dm["defense_logic"],
                    "severity": dm["severity"],
                })
            elif meta.get("weakness"):
                defenses.append({
                    "our_pledge": pledge_name,
                    "potential_attack": f"'{pledge_name}' 공약의 실효성 의문",
                    "defense_logic": f"{meta['strength']}을 기반으로 단계적 추진.",
                    "severity": "low",
                })

        severity_order = {"high": 0, "medium": 1, "low": 2}
        defenses.sort(key=lambda x: severity_order.get(x["severity"], 3))
        return defenses

    # ── 지역별 유세 메시지 ──────────────────────────────────────

    def get_regional_talking_points(self, region: str) -> list[dict]:
        """
        특정 지역 유세에서 사용할 메시지 생성.
        해당 지역 관련 공약 + 상대 약점을 조합.
        """
        points = []

        # 1) 우리 공약(김경수) 중 해당 지역 관련 홍보 메시지
        for pledge_name, pledge_data in self.our_pledges.items():
            meta = OUR_PLEDGE_CATEGORIES.get(pledge_name, {})
            pledge_regions = meta.get("regions", ["전체"])
            if region in pledge_regions or "전체" in pledge_regions:
                strength = meta.get("strength", "")
                desc = pledge_data.get("설명", "")
                numbers = pledge_data.get("수치", "")
                msg = f"{pledge_name} — {desc}"
                if numbers:
                    msg += f" ({numbers})"
                if strength:
                    msg += f" | 강점: {strength}"
                points.append({
                    "message": msg,
                    "type": "promote",
                    "target_pledge": pledge_name,
                })

        # 2) 상대 공약 중 해당 지역 약점 → 공격 메시지
        for opp_name, opp_info in self.opponent_pledges.items():
            for p in opp_info["pledges"]:
                opp_regions = p.get("regions", [])
                if region not in opp_regions and "전체" not in opp_regions:
                    continue
                weakness = p.get("weakness", "")
                if not weakness:
                    continue

                # 지역 맞춤 공격 메시지 생성
                msg = self._build_regional_attack(opp_name, p, region)
                if msg:
                    points.append({
                        "message": msg,
                        "type": "attack",
                        "target_pledge": p["name"],
                    })

        # 3) 우리 공약 방어 포인트 (해당 지역)
        for defense in self.find_defense_points():
            pledge_name = defense["our_pledge"]
            meta = OUR_PLEDGE_CATEGORIES.get(pledge_name, {})
            pledge_regions = meta.get("regions", ["전체"])
            if region in pledge_regions or "전체" in pledge_regions:
                if defense["severity"] in ("high", "medium"):
                    points.append({
                        "message": f"{defense['potential_attack']} → {defense['defense_logic']}",
                        "type": "defense",
                        "target_pledge": pledge_name,
                    })

        return points

    def _build_regional_attack(self, opp_name: str, pledge: dict, region: str) -> str:
        """지역 맞춤 공격 메시지 생성."""
        name = pledge["name"]
        weakness = pledge["weakness"]
        region_data = self.config.regions.get(region, {})
        key_issue = region_data.get("key_issue", "")

        # ── 박완수 전용 지역 공격 ──
        if opp_name == "박완수":
            if name == "경남형 스마트산단" and region in ("창원시", "김해시"):
                return (
                    f"박완수 후보의 스마트산단 1조 2천억? 기재부 협의도 안 됐습니다. "
                    f"{region} 도민에게 빈 수표를 내미는 것입니다. "
                    f"우리는 K-방산·조선 르네상스로 실질적 일자리를 만듭니다."
                )

            if name == "교통 혁신 BRT" and region in ("창원시", "진주시", "김해시"):
                return (
                    f"BRT 2028년 개통? 임기 마지막 해입니다. 착공도 못 할 수 있습니다. "
                    f"{region} 도민의 교통 문제는 지금 당장 해결해야 합니다."
                )

            if name == "청년 일자리 2만개":
                return (
                    f"현직 4년간 청년 유출이 심화됐습니다. "
                    f"청년 일자리 2만개? 4년간 뭘 했는지부터 답해야 합니다. "
                    f"우리는 월세 30만원 + 장려금 500만원 청년 정주 패키지로 {region} 청년을 지킵니다."
                )

            if name == "우주항공 허브" and region != "사천시":
                return (
                    f"우주항공은 사천만을 위한 공약. {region}에는 뭐가 있습니까? "
                    f"우리는 경남 전체 균형발전을 추진합니다."
                )

            if name == "현직 도정 성과":
                return (
                    f"12만 일자리 창출? {region} 도민이 체감하고 계십니까? "
                    f"여론조사 초박빙이 현직 성과의 민낯입니다."
                )

        # ── 전희영 공격 ──
        if name == "대학생 3대 생존정책" and region in ("진주시", "창원시"):
            return (
                f"천원의 밥상, 1만원 공공주택? 재원 확보 방안 없이 청년에게 빈 약속. "
                f"우리는 {region}에 실질적 일자리를 만들어 청년이 떠나지 않는 경남을 만듭니다."
            )

        if name == "부울경 행정통합" and opp_name == "전희영":
            return (
                f"전희영 후보의 행정통합? 실현 가능성이 없습니다. "
                f"우리는 부울경 메가시티 비전을 주민투표 기반으로 민주적으로 추진합니다."
            )

        # 일반 공격
        if weakness:
            return f"{opp_name} 후보의 '{name}' — {weakness}."

        return ""

    # ── 토론 대비 자료 ──────────────────────────────────────────

    def get_debate_prep(self, opponent_name: str) -> dict:
        """
        특정 상대와의 토론 대비 자료 생성.
        """
        if opponent_name not in self.opponent_pledges:
            return {"expected_attacks": [], "our_attacks": [], "pivot_messages": []}

        opp_info = self.opponent_pledges[opponent_name]
        result = {
            "expected_attacks": [],
            "our_attacks": [],
            "pivot_messages": [],
        }

        # ── 상대가 우리에게 할 예상 공격 ──
        expected_attacks_map = {
            "박완수": [
                {
                    "topic": "도민 생활지원금 재원",
                    "expected_question": "330만 도민 × 10만원 = 3,300억. 재원은 어디서 마련합니까?",
                    "response": (
                        "도세 잉여분과 특별교부세로 충분히 마련 가능합니다. "
                        "도민 생활 안정이 최우선이며, 지역 경제 활성화로 세수 환류 효과까지 기대됩니다. "
                        "현직 도지사는 4년간 도민에게 뭘 해 주셨습니까?"
                    ),
                },
                {
                    "topic": "부울경 메가시티",
                    "expected_question": "부울경 통합하면 경남도지사 자리가 없어지는 것 아닙니까?",
                    "response": (
                        "주민투표로 결정합니다. 도민이 원하면 추진, 원치 않으면 중단. "
                        "1000만 부울경 메가시티는 경남의 미래 경쟁력을 위한 비전이지, "
                        "자리를 위한 정치가 아닙니다."
                    ),
                },
                {
                    "topic": "사법 리스크",
                    "expected_question": "과거 사건으로 유죄 판결을 받으셨는데, 도정을 맡을 자격이 있습니까?",
                    "response": (
                        "사법적 절차가 모두 완료되었고 특별사면을 받았습니다. "
                        "사법 리스크는 완전히 해소되었습니다. "
                        "과거가 아닌 미래를 선택해 주십시오. 경남 발전으로 도민께 보답하겠습니다."
                    ),
                },
                {
                    "topic": "조선업 구조조정",
                    "expected_question": "전 도지사 재임 시 조선업 구조조정으로 거제 인구가 빠졌는데?",
                    "response": (
                        "당시는 글로벌 조선 불황기였습니다. 지금은 K-방산 수출 호황이라는 "
                        "전혀 다른 환경입니다. 위기 극복 경험이 오히려 강점이며, "
                        "조선·방산 현장을 가장 잘 아는 후보가 저입니다."
                    ),
                },
            ],
            "전희영": [
                {
                    "topic": "성평등 정책",
                    "expected_question": "성평등 정책에 대한 입장은 무엇입니까?",
                    "response": (
                        "경남 여성 경제활동 참여율 제고가 핵심입니다. "
                        "청년 정주 패키지에 여성 맞춤 지원을 포함하고, "
                        "실질적 성평등을 구현합니다. 구호가 아니라 실천입니다."
                    ),
                },
                {
                    "topic": "청년 정책 비교",
                    "expected_question": "천원 밥상, 1만원 주택 같은 직접 지원은 왜 안 합니까?",
                    "response": (
                        "우리는 월세 30만원 + 장려금 500만원 청년 정주 패키지로 더 파격적으로 지원합니다. "
                        "일회성이 아니라 청년이 경남에 정착할 수 있는 구조를 만듭니다."
                    ),
                },
            ],
        }

        result["expected_attacks"] = expected_attacks_map.get(opponent_name, [])

        # ── 우리가 공격할 포인트 ──
        for p in opp_info["pledges"]:
            weakness = p.get("weakness", "")
            if not weakness:
                continue

            attack_entry = {
                "topic": p["name"],
                "question": self._build_debate_question(opponent_name, p),
                "follow_up": self._build_follow_up(opponent_name, p),
            }
            result["our_attacks"].append(attack_entry)

        # ── 피벗 메시지 (어떤 질문이든 돌아올 핵심 메시지) ──
        result["pivot_messages"] = [
            self.config.core_message,
            f"지방시대위원장 경험, 중앙정부 네트워크. 경남을 위해 일할 준비가 된 후보입니다.",
            f"부울경 1000만 메가시티로 경남의 미래 경쟁력을 만들겠습니다.",
            f"도민 생활지원금, 청년 정주 패키지 — 도민이 체감하는 정책을 약속합니다.",
            f"조선·방산 르네상스로 거제·창원에 다시 활력을 불어넣겠습니다.",
        ]

        return result

    def _build_debate_question(self, opp_name: str, pledge: dict) -> str:
        """토론용 공격 질문 생성."""
        name = pledge["name"]
        weakness = pledge["weakness"]
        numbers = pledge.get("numbers", "")

        # ── 박완수 전용 질문 ──
        if opp_name == "박완수":
            if name == "경남형 스마트산단":
                return "스마트산단 1조 2천억 재원은 어디서 마련하십니까? 기재부 협의는 완료되었습니까?"
            if name == "교통 혁신 BRT":
                return "BRT 2028년 개통이면 임기 마지막 해입니다. 착공이라도 하실 수 있습니까?"
            if name == "청년 일자리 2만개":
                return "현직 4년간 청년 유출이 심화됐는데, 청년 일자리 정책이 실패한 것 아닙니까?"
            if name == "우주항공 허브":
                return "우주항공은 사천에만 집중되는데, 나머지 경남 지역은 어떻게 하시겠습니까?"
            if name == "현직 도정 성과":
                return "12만 일자리 창출을 주장하시는데, 도민 체감 성과가 부족한 이유는 무엇입니까?"

        if "재원" in weakness or "불투명" in weakness or "미제시" in weakness:
            if numbers:
                return f"'{name}'에 {numbers}이 필요합니다. 재원 조달 방안을 구체적으로 말씀해 주십시오."
            return f"'{name}' 공약의 소요 예산과 재원 조달 방안은 무엇입니까?"

        if "실현 가능성" in weakness:
            return f"'{name}' — 실현 가능성에 대해 구체적으로 설명해 주십시오."

        if "반발" in weakness or "반감" in weakness:
            return f"'{name}'에 대한 도민 반발이 예상됩니다. 어떻게 설득하시겠습니까?"

        if "로드맵 부재" in weakness:
            return f"'{name}'의 구체적 추진 일정과 단계별 계획을 말씀해 주십시오."

        if "정권" in weakness or "무력화" in weakness:
            return f"'{name}'은 중앙정부 의존적입니다. 정권이 바뀌면 어떻게 하시겠습니까?"

        return f"'{name}' 공약에 대해 도민이 의문을 갖고 있습니다. {weakness}"

    def _build_follow_up(self, opp_name: str, pledge: dict) -> str:
        """추가 추궁 질문 생성."""
        name = pledge["name"]
        weakness = pledge["weakness"]

        # ── 박완수 전용 추궁 ──
        if opp_name == "박완수":
            if name == "경남형 스마트산단":
                return "기재부 협의 미완료 상태에서 1조 2천억을 약속하는 것은 도민을 기만하는 것 아닙니까?"
            if name == "교통 혁신 BRT":
                return "임기 내 완료 불가능한 공약을 내건 이유가 무엇입니까? 다음 선거용 아닙니까?"
            if name == "청년 일자리 2만개":
                return "4년간 기회가 있었는데 못한 일을, 왜 이번에는 할 수 있다고 확신하십니까?"
            if name == "우주항공 허브":
                return "사천 외 지역 도민에게는 어떤 산업 비전을 제시하시겠습니까?"
            if name == "현직 도정 성과":
                return "여론조사 초박빙이 현직 성과에 대한 도민 평가 아닙니까?"

        if "재원" in weakness or "불투명" in weakness or "미제시" in weakness:
            return "구체적 수치 없이 약속만 하는 것은 도민을 기만하는 것 아닙니까?"

        if "실현 가능성" in weakness:
            return "실현 불가능한 공약으로 유권자를 현혹하는 것은 아닙니까?"

        if "반발" in weakness or "반감" in weakness:
            return "도민 다수가 반대하는 정책을 강행하시겠습니까?"

        if "정권" in weakness or "무력화" in weakness:
            return "도지사가 자체적으로 추진할 수 있는 대안은 무엇입니까?"

        return f"도민께서 납득할 수 있도록 더 구체적으로 설명해 주십시오."

    # ── 요약 출력 ───────────────────────────────────────────────

    def format_summary(self) -> str:
        """Print-friendly summary of all comparisons."""
        lines = []
        lines.append("=" * 70)
        lines.append("  Pledge Comparator — 공약 대비 분석 요약")
        lines.append("=" * 70)

        # 1. 비교 매트릭스
        matrix = self.generate_comparison_matrix()
        lines.append("\n[1] 카테고리별 공약 대비표")
        lines.append("-" * 50)
        for cat, data in matrix.items():
            lines.append(f"\n  [{cat}]")
            our = data.get("우리", [])
            if our:
                for p in our:
                    lines.append(f"    우리({self.config.candidate_name}): {p['name']} — {p.get('numbers', '')}")
            else:
                lines.append(f"    우리({self.config.candidate_name}): (해당 공약 없음)")

            for opp_name in self.opponent_pledges:
                opp_list = data.get(opp_name, [])
                if opp_list:
                    for p in opp_list:
                        lines.append(f"    {opp_name}: {p['name']} — {p.get('numbers', '')}")
                else:
                    lines.append(f"    {opp_name}: (해당 공약 없음)")

        # 2. 공격 포인트
        attacks = self.find_attack_points()
        lines.append(f"\n\n[2] 공격 포인트 (전체 {len(attacks)}건)")
        lines.append("-" * 50)
        for i, a in enumerate(attacks, 1):
            severity_mark = {"high": "[!!!]", "medium": "[!!]", "low": "[!]"}
            lines.append(f"\n  {i}. {severity_mark.get(a['severity'], '')} {a['target']} — {a['pledge']}")
            lines.append(f"     각도: {a['attack_angle']}")
            lines.append(f"     메시지: {a['talking_point']}")

        # 3. 방어 포인트
        defenses = self.find_defense_points()
        lines.append(f"\n\n[3] 방어 포인트 ({len(defenses)}건)")
        lines.append("-" * 50)
        for i, d in enumerate(defenses, 1):
            lines.append(f"\n  {i}. [{d['severity']}] {d['our_pledge']}")
            lines.append(f"     예상 공격: {d['potential_attack']}")
            lines.append(f"     방어 논리: {d['defense_logic']}")

        return "\n".join(lines)


# ── 빠른 테스트 ───────────────────────────────────────────────────
if __name__ == "__main__":
    from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG

    comparator = PledgeComparator(SAMPLE_GYEONGNAM_CONFIG)

    # ── 전체 요약 ──
    print(comparator.format_summary())

    # ── Top 5 공격 포인트 (박완수) ──
    print("\n\n" + "=" * 70)
    print("  Top 5 공격 포인트 — 박완수")
    print("=" * 70)
    attacks_pw = comparator.find_attack_points("박완수")
    for i, a in enumerate(attacks_pw[:5], 1):
        print(f"\n  {i}. [{a['severity'].upper()}] {a['pledge']}")
        print(f"     각도: {a['attack_angle']}")
        print(f"     메시지: {a['talking_point']}")
        print(f"     효과 지역: {', '.join(a['regions'])}")

    # ── Top 3 방어 준비 ──
    print("\n\n" + "=" * 70)
    print("  Top 3 방어 준비")
    print("=" * 70)
    defenses = comparator.find_defense_points()
    for i, d in enumerate(defenses[:3], 1):
        print(f"\n  {i}. [{d['severity'].upper()}] {d['our_pledge']}")
        print(f"     예상 공격: {d['potential_attack']}")
        print(f"     방어 논리: {d['defense_logic']}")

    # ── 지역별 유세 메시지: 창원시 ──
    print("\n\n" + "=" * 70)
    print("  지역별 유세 메시지 — 창원시")
    print("=" * 70)
    cw_points = comparator.get_regional_talking_points("창원시")
    for i, tp in enumerate(cw_points, 1):
        type_tag = {"promote": "[홍보]", "attack": "[공격]", "defense": "[방어]"}
        print(f"\n  {i}. {type_tag.get(tp['type'], '')} {tp['message']}")

    # ── 지역별 유세 메시지: 거제시 ──
    print("\n\n" + "=" * 70)
    print("  지역별 유세 메시지 — 거제시")
    print("=" * 70)
    gj_points = comparator.get_regional_talking_points("거제시")
    for i, tp in enumerate(gj_points, 1):
        type_tag = {"promote": "[홍보]", "attack": "[공격]", "defense": "[방어]"}
        print(f"\n  {i}. {type_tag.get(tp['type'], '')} {tp['message']}")

    # ── 토론 대비 — 박완수 ──
    print("\n\n" + "=" * 70)
    print("  토론 대비 자료 — 박완수")
    print("=" * 70)
    debate = comparator.get_debate_prep("박완수")

    print("\n  [예상 공격 & 대응]")
    for i, ea in enumerate(debate["expected_attacks"], 1):
        print(f"\n  {i}. 주제: {ea['topic']}")
        print(f"     예상 질문: {ea['expected_question']}")
        print(f"     대응: {ea['response']}")

    print("\n  [우리 공격 포인트]")
    for i, oa in enumerate(debate["our_attacks"], 1):
        print(f"\n  {i}. 주제: {oa['topic']}")
        print(f"     질문: {oa['question']}")
        print(f"     추궁: {oa['follow_up']}")

    print("\n  [피벗 메시지]")
    for i, pm in enumerate(debate["pivot_messages"], 1):
        print(f"  {i}. {pm}")

    print("\n" + "=" * 70)
    print("  Engine 6: Pledge Comparator — 테스트 완료")
    print("=" * 70)
