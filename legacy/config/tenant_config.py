"""
Election Strategy Engine — 테넌트 설정 관리
캠프마다 독립된 컨텍스트를 유지합니다.
"""
from dataclasses import dataclass, field


@dataclass
class TenantConfig:
    tenant_id:        str
    candidate_name:   str
    election_type:    str          # "광역단체장" | "국회의원" | ...
    election_date:    str          # "2026-06-03" 형식
    region:           str          # "경상남도"
    slogan:           str
    core_message:     str

    # 공약 DB: {공약명: {수치, 설명}}
    pledges: dict = field(default_factory=dict)

    # 금기어 목록
    forbidden_words: list[str] = field(default_factory=list)

    # 경쟁 후보
    opponents: list[str] = field(default_factory=list)

    # 후보 SNS 계정
    candidate_sns: dict = field(default_factory=dict)
    # {"facebook": "opensky86", "youtube": "김경수", "instagram": "", "twitter": "", "tiktok": ""}

    # 상대 후보 SNS 프로필
    opponent_profiles: dict = field(default_factory=dict)
    # {"박완수": {"facebook": "...", "youtube": "...", "instagram": "..."}, ...}

    # 이슈 스코어링 임계값 (캠프별 조정 가능)
    score_threshold_lv1: float = 30.0
    score_threshold_lv2: float = 56.0
    score_threshold_lv3: float = 80.0

    # 연령 코호트 — 투표율 모델 입력
    # {세대키: {pct, voters, turnout, kim_support, label, note}}
    age_cohorts: dict = field(default_factory=dict)

    # 선거구 지역 목록 (유권자 수 포함)
    regions: dict = field(default_factory=dict)

    # 슬랙 웹훅
    slack_webhook_url: str = ""
    # 카카오 알림 수신자 목록
    kakao_targets: list[str] = field(default_factory=list)


# ── 경남도지사 캠프 샘플 설정 ─────────────────────────────────────
SAMPLE_GYEONGNAM_CONFIG = TenantConfig(
    tenant_id        = "gyeongnam_2026",
    candidate_name   = "김경수",
    election_type    = "광역단체장",
    election_date    = "2026-06-03",
    region           = "경상남도",
    slogan           = "다시 경남, 제대로 한번",
    core_message     = "경남을 경험한 리더십, 지방주도 성장으로 도민의 삶을 바꿉니다.",

    pledges = {
        "지방주도 성장": {
            "수치": "5극3특 거점 육성, 국비 5조 확보",
            "완료시기": "임기 내",
            "설명": "지방시대위원장 경험을 살려 경남을 지방주도 성장 선도 지역으로"
        },
        "부울경 메가시티": {
            "수치": "부울경 행정통합 로드맵, 주민투표 실시",
            "완료시기": "2027년 주민투표",
            "설명": "부산·울산·경남 통합으로 1,000만 메가시티 실현"
        },
        "경남도민 생활지원금": {
            "수치": "전 도민 10만원 지급, 총 3,300억",
            "완료시기": "취임 100일 내",
            "설명": "물가 안정 및 지역 경제 활성화를 위한 긴급 생활지원"
        },
        "조선·방산 르네상스": {
            "수치": "거제·창원 조선 클러스터 재건, 일자리 2만개",
            "완료시기": "임기 내",
            "설명": "K-방산 수출 호황을 경남 일자리로 연결"
        },
        "청년 정주 패키지": {
            "수치": "청년 월세 30만원 지원, 첫 일자리 장려금 500만원",
            "완료시기": "임기 내",
            "설명": "청년이 떠나지 않는 경남, 정주 여건 혁신"
        },
    },

    forbidden_words = [
        "막장", "내로남불", "적폐", "반드시 당선",
        "드루킹 직접 언급", "상대방 이름 직접 비방", "검증 안 된 수치"
    ],

    opponents = ["박완수", "전희영"],

    candidate_sns = {
        "facebook": "opensky86",
        "youtube": "김경수",
        "instagram": "",
        "twitter": "",
        "tiktok": "",
    },

    opponent_profiles = {
        "박완수": {
            "facebook": "wansu2u",
            "youtube": "박완수",
            "instagram": "",
            "twitter": "",
        },
        "전희영": {
            "facebook": "",
            "youtube": "전희영",
            "instagram": "",
            "twitter": "",
        },
    },

    score_threshold_lv1 = 30.0,   # WATCH
    score_threshold_lv2 = 55.0,   # ALERT
    score_threshold_lv3 = 80.0,   # CRISIS (70→80 상향, 진짜 위기만)

    # ── 연령 코호트 (승리 전략 보고서 표10 + NESDC 양자대결 교차분석) ──
    # voters: 만명
    # turnout: 7대 지선(2018) 전국 연령별 실제 투표율 (중앙선관위)
    #   - 출처: 한국일보 2018.09.18, 경남 전체 65.8%
    # kim_support: NESDC 양자대결 연령별 교차분석 3개 조사 평균
    #   - 리얼미터/경남일보 (2026-01-24, nesdc:17162)
    #   - 서던포스트/KNN (2026-03-03, nesdc:17574)
    #   - 여론조사꽃/톱스타뉴스 (2026-03-19)
    age_cohorts = {
        "20s": {
            "pct": 10.0, "voters": 26.3, "turnout": 52.0,
            "kim_support": 29.0, "park_support": 39.0, "label": "20대",
            "note": "3개 조사 평균: 김 28.7% 박 38.7% 무응답 32.6%. "
                   "무응답 최대 — 잠재 설득층. 대통령 효과 + 청년 정책 필요.",
        },
        "30s": {
            "pct": 11.6, "voters": 30.5, "turnout": 54.3,
            "kim_support": 42.0, "park_support": 36.0, "label": "30대",
            "note": "3개 조사 평균: 김 41.7% 박 36.2% 무응답 22.1%. "
                   "맘카페·신도시 효과. 양산 사송·김해 장유가 핵심.",
        },
        "40s": {
            "pct": 16.2, "voters": 42.6, "turnout": 58.6,
            "kim_support": 61.0, "park_support": 23.0, "label": "40대",
            "note": "3개 조사 평균: 김 60.6% 박 23.3% 무응답 16.1%. "
                   "핵심 지지층. 조선·방산·메가시티 공약이 직접 영향. "
                   "창원 성산(노동계)·감계 신도시가 요충지.",
        },
        "50s": {
            "pct": 20.9, "voters": 55.0, "turnout": 63.3,
            "kim_support": 53.0, "park_support": 31.0, "label": "50대",
            "note": "3개 조사 평균: 김 53.0% 박 30.6% 무응답 16.5%. "
                   "뉴시니어, 유권자 규모 2위. 과반 확보 중이나 이탈 방지 필수. "
                   "지역경제·일자리 공약으로 설득 가능한 최대 풀.",
        },
        "60s": {
            "pct": 20.9, "voters": 55.0, "turnout": 72.5,
            "kim_support": 37.0, "park_support": 49.0, "label": "60대",
            "note": "3개 조사 평균: 김 36.7% 박 49.3% 무응답 13.9%. "
                   "보수 고정층이나 여론조사꽃에서 44.8%까지 상승. 설득 가능성 있음.",
        },
        "70+": {
            "pct": 18.5, "voters": 48.7, "turnout": 65.0,
            "kim_support": 27.0, "park_support": 58.0, "label": "70대 이상",
            "note": "3개 조사 평균: 김 26.7% 박 57.7% 무응답 15.6%. "
                   "보수 강고층. 자원 투입 대비 효과 최저.",
        },
    },

    # ── 경남 전체 시군 ──────────────────────────────────────────
    # 인구: 2025.12 주민등록 기준 (경남빅데이터허브)
    # 유권자: 인구 × 80% 추정 (만 명)
    # 2018: 제7회 도지사 — 김경수(민주) vs 김태호(한국당) → 김경수 52.81% 당선
    # 2022: 제8회 도지사 — 양문석(민주) vs 박완수(국힘) → 박완수 65.70% 당선
    # swing_index: 2018+2022 평균 민주당 득표율 기반 산출
    # 출처: 나무위키/경남신문 개표분석, 중앙선관위
    regions = {
        # ── 대도시 (인구 20만+) ──
        # ── 경남 전체 시군 ──────────────────────────────────────
        # 출처: 제9대 경남도지사 선거 승리 전략 보고서 (260315)
        # 7대: 김경수 52.81% vs 김태호 42.95% (2018)
        # 8대: 양문석 29.43% vs 박완수 65.70% (2022)
        # swing: 7대→8대 민주당 득표율 하락폭 (%p)
        # 인구: 2025.12 주민등록 기준
        "창원시": {
            "voters": 79, "population": 990898, "type": "metro",
            "key_issue": "AX 제조 수도, 창원대 의대",
            "권역": "중부권",
            # 7대 (구별 합산): 의창54.66+성산61.31+진해54.50+회원49.03+합포45.40 ≒ 52.8
            "2018_kim_pct": 52.8, "2018_kim_votes": 296422, "2018_opp_pct": 42.6,
            # 8대 (구별 합산): 의창25.56+성산26.74+진해29.96+회원26.15+합포24.16 ≒ 26.3
            "2022_yang_pct": 26.3, "2022_park_pct": 67.8, "2022_park_votes": 301174,
            "swing_7to8": -26.5,  # 52.8→26.3 = -26.5%p
            "swing_index": 0.62,
            # 핵심 요충지: 성산구(노동계), 의창 북면(감계 신도시)
            "battlegrounds": ["성산 사파동(-37.6)", "성산 상남동(-35.1)", "의창 북면(-30.9)"],
        },
        "김해시": {
            "voters": 43, "population": 533035, "type": "metro",
            "key_issue": "부울경 메가시티, 디지털 물류",
            "권역": "동부권",
            "2018_kim_pct": 65.02, "2018_kim_votes": 161710, "2018_opp_pct": 31.39,
            "2022_yang_pct": 38.87, "2022_park_pct": 57.65, "2022_park_votes": 115747,
            "swing_7to8": -26.15,
            "swing_index": 0.80,
            "battlegrounds": ["장유3동(-29.1)", "장유2동(-28.6)", "장유1동(-27.4)"],
            # 인구격변지: 주촌면 (대규모 아파트 준공)
            "population_surge": "주촌면 — 1만세대+ 신축, 민주당 새 거점",
        },
        "양산시": {
            "voters": 29, "population": 361155, "type": "metro",
            "key_issue": "메가시티 행정중심, 광역교통",
            "권역": "동부권",
            "2018_kim_pct": 57.04, "2018_kim_votes": 94038, "2018_opp_pct": 38.49,
            "2022_yang_pct": 35.93, "2022_park_pct": 61.05, "2022_park_votes": 83209,
            "swing_7to8": -21.11,
            "swing_index": 0.72,
            "battlegrounds": ["물금읍(-25.0)"],
            # 인구격변지: 동면(사송) — 경남 3040 비중 최고
            "population_surge": "동면(사송) — 제2의 물금, 투표인수 폭증",
        },
        "진주시": {
            "voters": 27, "population": 335939, "type": "metro",
            "key_issue": "혁신도시 2.0, 우주항공 클러스터",
            "권역": "서부권",
            "2018_kim_pct": 51.19, "2018_kim_votes": 66991, "2018_opp_pct": 44.54,
            "2022_yang_pct": 27.65, "2022_park_pct": 68.54, "2022_park_votes": 104561,
            "swing_7to8": -23.54,
            "swing_index": 0.58,
            "battlegrounds": ["충무공동(-30.8)"],
            # 인구격변지: 충무공동 — 혁신도시 고학력 젊은층
            "population_surge": "충무공동 — 서부경남 유일 민주당 요새",
        },
        "거제시": {
            "voters": 18, "population": 231178, "type": "city",
            "key_issue": "조선업 본사 유치, 신공항 MICE",
            "권역": "남해안권",
            "2018_kim_pct": 60.05, "2018_kim_votes": 56299, "2018_opp_pct": 35.36,
            "2022_yang_pct": 37.72, "2022_park_pct": 57.61, "2022_park_votes": 56119,
            "swing_7to8": -22.33,
            "swing_index": 0.76,
            "battlegrounds": ["아주동(-26.8)"],
            "population_surge": "상문동 — 조선업 종사자 가족 신규 거점",
        },
        # ── 중도시 ──
        "통영시": {
            "voters": 9, "population": 117667, "type": "city",
            "key_issue": "해양관광, 남해안 아일랜드 하이웨이",
            "권역": "남해안권",
            "2018_kim_pct": 46.16, "2018_opp_pct": 49.78,
            "2022_yang_pct": 30.26, "2022_park_pct": 67.15,
            "swing_7to8": -15.90,
            "swing_index": 0.56,
        },
        "사천시": {
            "voters": 9, "population": 107935, "type": "city",
            "key_issue": "우주항공청 KASA, 항공산단",
            "권역": "서부권",
            "2018_kim_pct": 46.08, "2018_opp_pct": 49.84,
            "2022_yang_pct": 23.86, "2022_park_pct": 71.11,
            "swing_7to8": -22.22,
            "swing_index": 0.50,
            "battlegrounds": ["사남면(-27.1)"],
            "population_surge": "사남면 — 항공우주 연구직/기술직 유입",
        },
        "밀양시": {
            "voters": 8, "population": 99252, "type": "city",
            "key_issue": "나노바이오, 웰니스 관광",
            "권역": "중부권",
            "2018_kim_pct": 45.35, "2018_opp_pct": 50.96,
            "2022_yang_pct": 23.27, "2022_park_pct": 72.43,
            "swing_7to8": -22.08,
            "swing_index": 0.48,
        },
        # ── 군 지역 ──
        "거창군": {
            "voters": 5, "population": 58980, "type": "county",
            "key_issue": "농업·관광",
            "권역": "서부권",
            "2018_kim_pct": 36.29, "2018_opp_pct": 60.03,
            "2022_yang_pct": 22.62, "2022_park_pct": 71.40,
            "swing_7to8": -13.67,
            "swing_index": 0.38,
        },
        "함안군": {
            "voters": 5, "population": 57558, "type": "county",
            "key_issue": "창원 배후 주거지",
            "권역": "중부권",
            "2018_kim_pct": 45.95, "2018_opp_pct": 50.05,
            "2022_yang_pct": 24.72, "2022_park_pct": 69.96,
            "swing_7to8": -21.23,
            "swing_index": 0.52,
        },
        "창녕군": {
            "voters": 4, "population": 54900, "type": "county",
            "key_issue": "우포늪·관광",
            "권역": "중부권",
            "2018_kim_pct": 39.40, "2018_opp_pct": 57.16,
            "2022_yang_pct": 19.35, "2022_park_pct": 75.09,
            "swing_7to8": -20.05,
            "swing_index": 0.38,
        },
        "고성군": {
            "voters": 4, "population": 47099, "type": "county",
            "key_issue": "공룡엑스포·관광",
            "권역": "남해안권",
            "2018_kim_pct": 49.74, "2018_opp_pct": 46.32,
            "2022_yang_pct": 27.01, "2022_park_pct": 68.66,
            "swing_7to8": -22.73,
            "swing_index": 0.55,
        },
        "남해군": {
            "voters": 3, "population": 40770, "type": "county",
            "key_issue": "관광·어업, 아일랜드 하이웨이",
            "권역": "서부권",
            "2018_kim_pct": 46.41, "2018_opp_pct": 49.52,
            "2022_yang_pct": 31.88, "2022_park_pct": 63.55,
            "swing_7to8": -14.53,
            "swing_index": 0.58,
        },
        "하동군": {
            "voters": 3, "population": 39974, "type": "county",
            "key_issue": "녹차·관광, 광양만권",
            "권역": "서부권",
            "2018_kim_pct": 46.88, "2018_opp_pct": 49.03,
            "2022_yang_pct": 29.15, "2022_park_pct": 63.74,
            "swing_7to8": -17.73,
            "swing_index": 0.52,
        },
        "합천군": {
            "voters": 3, "population": 39190, "type": "county",
            "key_issue": "농업·관광",
            "권역": "서부권",
            "2018_kim_pct": 33.35, "2018_opp_pct": 62.64,
            "2022_yang_pct": 17.27, "2022_park_pct": 76.85,
            "swing_7to8": -16.08,
            "swing_index": 0.30,
        },
        "함양군": {
            "voters": 3, "population": 35472, "type": "county",
            "key_issue": "농업·산림",
            "권역": "서부권",
            "2018_kim_pct": 41.42, "2018_opp_pct": 54.21,
            "2022_yang_pct": 24.97, "2022_park_pct": 67.32,
            "swing_7to8": -16.45,
            "swing_index": 0.42,
        },
        "산청군": {
            "voters": 3, "population": 32745, "type": "county",
            "key_issue": "한방·관광",
            "권역": "서부권",
            "2018_kim_pct": 39.88, "2018_opp_pct": 55.68,
            "2022_yang_pct": 23.72, "2022_park_pct": 69.73,
            "swing_7to8": -16.16,
            "swing_index": 0.38,
        },
        "의령군": {
            "voters": 2, "population": 24636, "type": "county",
            "key_issue": "농업",
            "권역": "중부권",
            "2018_kim_pct": 39.18, "2018_opp_pct": 56.42,
            "2022_yang_pct": 20.34, "2022_park_pct": 71.69,
            "swing_7to8": -18.84,
            "swing_index": 0.36,
        },
    },

    slack_webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    kakao_targets     = ["대변인", "전략팀장", "선대위원장"],
)
