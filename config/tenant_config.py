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

    # 이슈 스코어링 임계값 (캠프별 조정 가능)
    score_threshold_lv1: float = 30.0
    score_threshold_lv2: float = 56.0
    score_threshold_lv3: float = 80.0

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

    score_threshold_lv1 = 25.0,
    score_threshold_lv2 = 50.0,
    score_threshold_lv3 = 70.0,

    # 경남 주요 시군 (유권자 수 단위: 만 명)
    regions = {
        "창원시": {"voters": 87, "swing_index": 0.62, "key_issue": "조선업 일자리"},
        "진주시": {"voters": 28, "swing_index": 0.55, "key_issue": "혁신도시 2기"},
        "김해시": {"voters": 37, "swing_index": 0.70, "key_issue": "교통 인프라"},
        "거제시": {"voters": 18, "swing_index": 0.58, "key_issue": "방산 산업"},
        "양산시": {"voters": 23, "swing_index": 0.65, "key_issue": "수도권 연계"},
        "통영시": {"voters": 11, "swing_index": 0.45, "key_issue": "관광·어업"},
        "사천시": {"voters": 10, "swing_index": 0.50, "key_issue": "항공 산업"},
        "밀양시": {"voters": 9,  "swing_index": 0.40, "key_issue": "농업·관광"},
    },

    slack_webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    kakao_targets     = ["대변인", "전략팀장", "선대위원장"],
)
