"""
Segment Mapper — 프록시 기반 유권자 세그먼트 추론 (v1)
정확한 분류가 아닌 프록시 기반 추정. 반드시 confidence 포함.

입력: 채널(커뮤니티/플랫폼), 키워드, 조직 시그널, 지역
출력: SegmentEstimate (age/gender/leaning/region/org + confidence)

기존 모듈 재사용:
  - reaction_index.py의 COMMUNITY_SEGMENT_MAP → 여기로 통합
  - unified_collector.py의 segment_hint → 이 모듈에서 생성
  - keyword_engine.py의 키워드 → segment_hint 매핑
"""
from __future__ import annotations
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════
# PART 1: COMMUNITY PROXY MAPPING
# ═══════════════════════════════════════════════════════════════

@dataclass
class CommunityProxy:
    """커뮤니티 → 세그먼트 프록시"""
    community_id: str
    name: str
    age_group: str        # "20s" | "30s" | "40s" | "50+" | "mixed"
    gender: str           # "M" | "F" | "mixed"
    leaning: str          # "progressive" | "conservative" | "swing" | "mixed"
    label_ko: str         # "2030 남성"
    confidence: float     # 0~1 (이 프록시의 신뢰도)
    weight: float = 1.0   # 영향력 가중치


COMMUNITY_PROXIES: dict[str, CommunityProxy] = {
    "fmkorea":    CommunityProxy("fmkorea", "에펨코리아", "20s", "M", "conservative", "2030 남성 보수", 0.65, 1.2),
    "dcinside":   CommunityProxy("dcinside", "DC인사이드", "20s", "M", "swing", "2030 남성 스윙", 0.55, 1.0),
    "theqoo":     CommunityProxy("theqoo", "더쿠", "20s", "F", "progressive", "2030 여성 진보", 0.70, 1.1),
    "yeosidae":   CommunityProxy("yeosidae", "여성시대", "30s", "F", "progressive", "2040 여성", 0.65, 0.9),
    "momcafe":    CommunityProxy("momcafe", "맘카페", "30s", "F", "swing", "3040 학부모", 0.75, 1.0),
    "clien":      CommunityProxy("clien", "클리앙", "30s", "M", "progressive", "3040 진보", 0.70, 1.0),
    "mlbpark":    CommunityProxy("mlbpark", "MLB파크", "30s", "M", "swing", "3040 남성 중도", 0.55, 0.8),
    "todayhumor": CommunityProxy("todayhumor", "오늘의유머", "30s", "M", "progressive", "3040 진보 남성", 0.65, 0.9),
    "ppomppu":    CommunityProxy("ppomppu", "뽐뿌", "40s", "M", "swing", "3050 중도", 0.50, 0.7),
    "ruliweb":    CommunityProxy("ruliweb", "루리웹", "20s", "M", "mixed", "2030 일반", 0.45, 0.6),
    "natepann":   CommunityProxy("natepann", "네이트판", "20s", "F", "swing", "2030 여성 감성", 0.55, 0.8),
    # 중도·진보 커뮤니티
    "damoa":      CommunityProxy("damoa", "다모앙", "30s", "M", "progressive", "3050 진보 결집", 0.70, 1.0),
    "ddanzi":     CommunityProxy("ddanzi", "딴지일보", "40s", "M", "progressive", "4050 열성 진보", 0.75, 1.1),
    "bobae":      CommunityProxy("bobae", "보배드림", "30s", "M", "swing", "3050 남성 중도진보", 0.55, 0.9),
    "82cook":     CommunityProxy("82cook", "82쿡", "40s", "F", "progressive", "3050 여성 합리진보", 0.70, 1.0),
    "instiz":     CommunityProxy("instiz", "인스티즈", "20s", "F", "progressive", "1020 여성 진보", 0.50, 0.7),
    "slrclub":    CommunityProxy("slrclub", "SLR클럽", "40s", "M", "progressive", "3050 남성 중도진보", 0.55, 0.8),
    # 경남 맘카페 (지역별 세분화)
    "momcafe_changwon": CommunityProxy("momcafe_changwon", "창원줌마렐라", "30s", "F", "swing", "3040 창원 학부모", 0.80, 1.3),
    "momcafe_gimhae":   CommunityProxy("momcafe_gimhae", "김해줌마렐라", "30s", "F", "swing", "3040 김해 학부모", 0.80, 1.2),
    "momcafe_jinju":    CommunityProxy("momcafe_jinju", "진주아지매", "30s", "F", "swing", "3040 진주 학부모", 0.75, 1.1),
    "momcafe_yangsan":  CommunityProxy("momcafe_yangsan", "러브양산맘", "30s", "F", "swing", "3040 양산 학부모", 0.80, 1.2),
    "momcafe_sacheon":  CommunityProxy("momcafe_sacheon", "우리끼리미수다", "30s", "F", "swing", "3040 사천 학부모", 0.70, 1.0),
}


# ═══════════════════════════════════════════════════════════════
# PART 2: PLATFORM PROXY MAPPING
# ═══════════════════════════════════════════════════════════════

@dataclass
class PlatformProxy:
    """플랫폼 → 세그먼트 프록시"""
    platform: str
    age_group: str
    gender: str
    leaning: str
    label_ko: str
    confidence: float


PLATFORM_PROXIES: dict[str, PlatformProxy] = {
    "youtube":    PlatformProxy("youtube", "30s", "M", "mixed", "3050 남성 편중", 0.45),
    "instagram":  PlatformProxy("instagram", "20s", "F", "mixed", "2030 여성 편중", 0.40),
    "blog":       PlatformProxy("blog", "30s", "mixed", "mixed", "3050 생활층", 0.35),
    "cafe":       PlatformProxy("cafe", "30s", "mixed", "mixed", "3050 생활층", 0.35),
    "news":       PlatformProxy("news", "mixed", "mixed", "mixed", "전 연령", 0.20),
    "trend":      PlatformProxy("trend", "mixed", "mixed", "mixed", "전 국민", 0.15),
}


# ═══════════════════════════════════════════════════════════════
# PART 3: KEYWORD-BASED SEGMENT HINT
# ═══════════════════════════════════════════════════════════════

# 키워드 → 세그먼트 매핑 (부분 매칭)
KEYWORD_SEGMENT_HINTS: list[dict] = [
    # 청년/군대 → 2030 남성
    {"keywords": ["병역", "군대", "입대", "전역", "국방"], "age": "20s", "gender": "M", "label": "청년 남성 (군대)"},
    {"keywords": ["취업", "채용", "인턴", "알바"], "age": "20s", "gender": "mixed", "label": "청년 취업층"},
    {"keywords": ["대학", "등록금", "장학금", "캠퍼스"], "age": "20s", "gender": "mixed", "label": "대학생"},
    # 육아/교육 → 3040 여성
    {"keywords": ["보육", "어린이집", "유치원", "출산", "육아"], "age": "30s", "gender": "F", "label": "3040 학부모"},
    {"keywords": ["학교", "교육", "입시", "수능", "학원"], "age": "30s", "gender": "F", "label": "3040 학부모"},
    {"keywords": ["학부모", "맘카페", "돌봄"], "age": "30s", "gender": "F", "label": "학부모"},
    # 부동산/주거 → 3050 중산층
    {"keywords": ["부동산", "아파트", "전세", "월세", "집값"], "age": "30s", "gender": "mixed", "label": "3050 중산층"},
    {"keywords": ["분양", "재개발", "재건축"], "age": "40s", "gender": "mixed", "label": "4050 자산층"},
    # 노동/산업 → 3050 남성 노동자
    {"keywords": ["일자리", "조선업", "제조업", "공장", "노조"], "age": "40s", "gender": "M", "label": "3050 제조업 노동자"},
    {"keywords": ["방산", "항공", "우주", "산업단지"], "age": "40s", "gender": "M", "label": "4050 산업 종사자"},
    # 복지/연금 → 50+
    {"keywords": ["연금", "건강보험", "노인", "요양", "의료"], "age": "50+", "gender": "mixed", "label": "50+ 고령층"},
    {"keywords": ["복지", "기초생활", "지원금", "수당"], "age": "50+", "gender": "mixed", "label": "50+ 복지 관심"},
    # 여성 이슈
    {"keywords": ["여성", "페미", "성평등", "성범죄", "낙태"], "age": "20s", "gender": "F", "label": "2030 여성"},
    # 농업/어업 → 50+ 농촌
    {"keywords": ["농업", "어업", "수산", "축산", "농촌"], "age": "50+", "gender": "M", "label": "50+ 농어촌"},
]


# ═══════════════════════════════════════════════════════════════
# PART 5: ORGANIZATION → SEGMENT LINK
# ═══════════════════════════════════════════════════════════════

ORG_SEGMENT_MAP: dict[str, dict] = {
    "labor":     {"age": "40s", "gender": "M", "leaning": "progressive", "label": "조직 노동자"},
    "business":  {"age": "50+", "gender": "M", "leaning": "conservative", "label": "경제인/자영업"},
    "religion":  {"age": "50+", "gender": "mixed", "leaning": "conservative", "label": "종교 조직"},
    "civic":     {"age": "30s", "gender": "mixed", "leaning": "progressive", "label": "시민사회"},
    "education": {"age": "30s", "gender": "F", "leaning": "mixed", "label": "교육/학부모"},
    "local":     {"age": "50+", "gender": "M", "leaning": "mixed", "label": "지역 원로"},
}


# ═══════════════════════════════════════════════════════════════
# CORE: SegmentEstimate
# ═══════════════════════════════════════════════════════════════

@dataclass
class SegmentEstimate:
    """프록시 기반 유권자 세그먼트 추정"""
    region: str = ""
    age_group: str = "unknown"      # 20s | 30s | 40s | 50+ | mixed | unknown
    gender: str = "unknown"         # M | F | mixed | unknown
    leaning: str = "unknown"        # progressive | conservative | swing | mixed | unknown
    organization: str = "none"      # labor | business | religion | civic | education | local | none
    label_ko: str = ""              # "3040 학부모 진보"
    confidence: float = 0.0         # 0~1

    # 구성 근거
    sources: list[str] = field(default_factory=list)  # ["community:theqoo", "keyword:교육", "org:civic"]

    def to_dict(self) -> dict:
        return {
            "region": self.region,
            "age_group": self.age_group,
            "gender": self.gender,
            "leaning": self.leaning,
            "organization": self.organization,
            "label": self.label_ko,
            "confidence": round(self.confidence, 2),
            "sources": self.sources[:5],
        }


@dataclass
class SegmentBreakdown:
    """이슈별 세그먼트 반응 분해"""
    keyword: str
    segments: list[SegmentEstimate] = field(default_factory=list)
    region_distribution: dict = field(default_factory=dict)  # {"창원": 0.6, "김해": 0.3}
    dominant_segment: str = ""        # "3040 학부모"
    dominant_region: str = ""         # "창원"

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "segments": [s.to_dict() for s in self.segments[:10]],
            "region_distribution": {k: round(v, 2) for k, v in self.region_distribution.items()},
            "dominant_segment": self.dominant_segment,
            "dominant_region": self.dominant_region,
        }


# ═══════════════════════════════════════════════════════════════
# CORE: 세그먼트 추론 함수
# ═══════════════════════════════════════════════════════════════

def infer_from_community(community_id: str, mention_count: int = 0) -> SegmentEstimate | None:
    """커뮤니티 → 세그먼트 추론"""
    proxy = COMMUNITY_PROXIES.get(community_id)
    if not proxy:
        return None
    intensity = min(1.0, mention_count / 20.0) if mention_count > 0 else 0.3
    return SegmentEstimate(
        age_group=proxy.age_group,
        gender=proxy.gender,
        leaning=proxy.leaning,
        label_ko=proxy.label_ko,
        confidence=round(proxy.confidence * intensity, 2),
        sources=[f"community:{community_id}({mention_count})"],
    )


def infer_from_platform(platform: str) -> SegmentEstimate | None:
    """플랫폼 → 세그먼트 추론"""
    proxy = PLATFORM_PROXIES.get(platform)
    if not proxy:
        return None
    return SegmentEstimate(
        age_group=proxy.age_group,
        gender=proxy.gender,
        leaning=proxy.leaning,
        label_ko=proxy.label_ko,
        confidence=proxy.confidence,
        sources=[f"platform:{platform}"],
    )


def infer_from_keyword(keyword: str) -> SegmentEstimate | None:
    """키워드 → 세그먼트 추론"""
    kw_lower = keyword.lower()
    for hint in KEYWORD_SEGMENT_HINTS:
        if any(k in kw_lower for k in hint["keywords"]):
            return SegmentEstimate(
                age_group=hint["age"],
                gender=hint["gender"],
                label_ko=hint["label"],
                confidence=0.5,
                sources=[f"keyword:{keyword}"],
            )
    return None


def infer_from_org(org_type: str) -> SegmentEstimate | None:
    """조직 유형 → 세그먼트 추론"""
    mapping = ORG_SEGMENT_MAP.get(org_type)
    if not mapping:
        return None
    return SegmentEstimate(
        age_group=mapping["age"],
        gender=mapping["gender"],
        leaning=mapping["leaning"],
        organization=org_type,
        label_ko=mapping["label"],
        confidence=0.6,
        sources=[f"org:{org_type}"],
    )


# ═══════════════════════════════════════════════════════════════
# MAIN: 다층 세그먼트 분석
# ═══════════════════════════════════════════════════════════════

def analyze_segments(
    keyword: str,
    # community_collector 결과
    community_signals: list = None,
    # platform 정보
    active_platforms: list[str] = None,   # ["blog", "cafe", "youtube"]
    # 조직 시그널
    org_type: str = "",
    # 지역 정보
    region_hints: dict = None,            # {"창원": 3, "김해": 1} (언급 횟수)
    # 네이버 데이터랩 — 실제 성별/연령 데이터
    naver_gender_skew: str = "",          # "male" | "female" | "balanced"
    naver_peak_age: str = "",             # "20s" | "30s" | "40s" | "50+"
    naver_age_breakdown: dict = None,     # {"20s": 22.0, "30s": 20.7, ...}
    naver_male_interest: float = 0.0,
    naver_female_interest: float = 0.0,
) -> SegmentBreakdown:
    """
    다층 프록시를 결합하여 이슈별 세그먼트 반응을 분석합니다.

    Args:
        keyword: 분석 대상 키워드
        community_signals: CommunitySignal 리스트 (community_collector 출력)
        active_platforms: 활성 플랫폼 목록
        org_type: 조직 시그널 유형
        region_hints: 지역별 언급 횟수

    Returns:
        SegmentBreakdown with segment estimates + region distribution
    """
    community_signals = community_signals or []
    active_platforms = active_platforms or []
    region_hints = region_hints or {}

    breakdown = SegmentBreakdown(keyword=keyword)
    all_estimates: list[SegmentEstimate] = []

    # ── Layer 1: Community proxy ──
    for cs in community_signals:
        cid = cs.community_id if hasattr(cs, 'community_id') else ""
        count = cs.result_count if hasattr(cs, 'result_count') else 0
        if count > 0:
            est = infer_from_community(cid, count)
            if est:
                all_estimates.append(est)

    # ── Layer 2: Platform proxy ──
    for platform in active_platforms:
        est = infer_from_platform(platform)
        if est:
            all_estimates.append(est)

    # ── Layer 3: Keyword proxy ──
    kw_est = infer_from_keyword(keyword)
    if kw_est:
        all_estimates.append(kw_est)

    # ── Layer 4: Organization proxy ──
    if org_type:
        org_est = infer_from_org(org_type)
        if org_est:
            all_estimates.append(org_est)

    # ── Layer 5: 네이버 데이터랩 (실제 성별/연령 검증) ──
    naver_age_breakdown = naver_age_breakdown or {}
    if naver_peak_age or naver_gender_skew:
        gender = "F" if naver_gender_skew == "female" else "M" if naver_gender_skew == "male" else "mixed"
        age = naver_peak_age or "mixed"
        # 네이버 실데이터 → 높은 confidence
        naver_est = SegmentEstimate(
            age_group=age,
            gender=gender,
            label_ko=f"네이버검색 {age} {'여성' if gender == 'F' else '남성' if gender == 'M' else ''}",
            confidence=0.85,  # 실데이터이므로 높은 신뢰도
            sources=[f"naver_datalab:gender={naver_gender_skew},peak={naver_peak_age}"],
        )
        all_estimates.append(naver_est)

        # 연령별 세부 — 관심도가 높은 연령대별로 추가
        for age_grp, interest in sorted(naver_age_breakdown.items(), key=lambda x: -x[1]):
            if interest > 15:  # 의미 있는 관심도만
                age_est = SegmentEstimate(
                    age_group=age_grp,
                    gender=gender,
                    label_ko=f"네이버 {age_grp} (관심도 {interest:.0f})",
                    confidence=round(min(0.9, interest / 100 + 0.5), 2),
                    sources=[f"naver_age:{age_grp}={interest:.0f}"],
                )
                all_estimates.append(age_est)

    # ── Region distribution ──
    total_region = sum(region_hints.values()) or 1
    breakdown.region_distribution = {
        region: round(count / total_region, 2)
        for region, count in sorted(region_hints.items(), key=lambda x: -x[1])
    }
    if region_hints:
        breakdown.dominant_region = max(region_hints, key=region_hints.get)
        # 지역 정보를 estimates에 반영
        for est in all_estimates:
            if not est.region:
                est.region = breakdown.dominant_region

    # ── 가중 집계 ──
    # confidence 기준 상위 세그먼트 선택
    all_estimates.sort(key=lambda x: x.confidence, reverse=True)
    breakdown.segments = all_estimates[:10]

    # dominant segment 결정
    if all_estimates:
        # age_group별 가중 투표
        age_votes: dict[str, float] = {}
        for est in all_estimates:
            if est.age_group != "unknown" and est.age_group != "mixed":
                age_votes[est.age_group] = age_votes.get(est.age_group, 0) + est.confidence

        gender_votes: dict[str, float] = {}
        for est in all_estimates:
            if est.gender != "unknown" and est.gender != "mixed":
                gender_votes[est.gender] = gender_votes.get(est.gender, 0) + est.confidence

        top_age = max(age_votes, key=age_votes.get) if age_votes else "mixed"
        top_gender = max(gender_votes, key=gender_votes.get) if gender_votes else "mixed"
        top_label = all_estimates[0].label_ko if all_estimates else ""

        breakdown.dominant_segment = top_label or f"{top_age} {top_gender}"

    return breakdown


# ═══════════════════════════════════════════════════════════════
# Segment Coverage Score (v2) — "이슈가 타겟층에 도달했는가"
# ═══════════════════════════════════════════════════════════════

# 세대별 전략적 중요도 가중치
# 투표율 × 인구 비중 × 이탈 가능성 기반 (turnout_predictor 연동)
AGE_STRATEGIC_WEIGHT = {
    "20s": 0.10,  # 인구 10%, 투표율 낮음, 변심 적음
    "30s": 0.20,  # 인구 11.6%, 신도시 핵심, 투표율 관건
    "40s": 0.25,  # 인구 16.2%, 핵심 허리층
    "50s": 0.25,  # 인구 20.9%, 최대 유권자, 스윙 가능
    "50+": 0.20,  # 50s와 60+를 합친 카테고리 (호환)
    "60s": 0.12,  # 인구 20.9%, 보수 고정, 변심 적음
    "70+": 0.05,  # 인구 18.5%, 보수 강고
    "mixed": 0.10,
    "unknown": 0.05,
}


@dataclass
class SegmentCoverageResult:
    """세그먼트 커버리지 점수"""
    keyword: str
    score: float = 0.0              # 0~100
    grade: str = ""                 # EXCELLENT | GOOD | PARTIAL | WEAK

    # 세대별 도달도
    age_reach: dict = field(default_factory=dict)   # {"20s": 45.2, "30s": 62.1, ...}
    age_weighted: dict = field(default_factory=dict) # 가중 점수

    # 타겟 분석
    target_reached: bool = False     # 핵심 타겟(3040) 도달 여부
    gap_segment: str = ""            # 가장 부족한 세그먼트
    strongest_segment: str = ""      # 가장 강한 세그먼트

    # 전략 시사점
    insight: str = ""

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "score": round(self.score, 1),
            "grade": self.grade,
            "age_reach": {k: round(v, 1) for k, v in self.age_reach.items()},
            "age_weighted": {k: round(v, 1) for k, v in self.age_weighted.items()},
            "target_reached": self.target_reached,
            "gap_segment": self.gap_segment,
            "strongest_segment": self.strongest_segment,
            "insight": self.insight,
        }


def compute_segment_coverage(
    breakdown: SegmentBreakdown,
    naver_age_breakdown: dict = None,
) -> SegmentCoverageResult:
    """
    세그먼트 분석 결과 → 커버리지 점수 (0~100).
    "이 이슈가 우리 타겟 유권자에게 얼마나 도달했는가"

    Args:
        breakdown: analyze_segments()의 결과
        naver_age_breakdown: 네이버 DataLab 연령별 관심도 (있으면 정확도 ↑)

    Returns:
        SegmentCoverageResult with score 0~100
    """
    naver_age_breakdown = naver_age_breakdown or {}
    result = SegmentCoverageResult(keyword=breakdown.keyword)

    # ── Step 1: 세대별 도달도 집계 ──
    # 프록시 세그먼트 + 네이버 실데이터를 결합
    age_intensity: dict[str, float] = {}  # 0~100 스케일

    # 프록시 기반 (커뮤니티 반응 → 세대 추론)
    for seg in breakdown.segments:
        age = seg.age_group
        if age in ("unknown", "mixed"):
            continue
        # confidence × 100 → 도달 강도
        current = age_intensity.get(age, 0)
        age_intensity[age] = min(100, current + seg.confidence * 60)

    # 네이버 DataLab 실데이터 (있으면 덮어쓰기 — 더 정확)
    for age, interest in naver_age_breakdown.items():
        if interest > 5:
            # 네이버 관심도를 도달 강도로 변환 (0~100 → 0~100)
            naver_reach = min(100, interest * 1.2)
            current = age_intensity.get(age, 0)
            # 프록시와 평균 (프록시 30% + 네이버 70%)
            age_intensity[age] = current * 0.3 + naver_reach * 0.7

    result.age_reach = age_intensity

    # ── Step 2: 가중 점수 계산 ──
    total_score = 0.0
    total_weight = 0.0

    # 실제 데이터가 있는 세대만 계산 (없는 세대는 패널티 없음)
    active_ages = set(age_intensity.keys()) | set(naver_age_breakdown.keys())
    for age in active_ages:
        weight = AGE_STRATEGIC_WEIGHT.get(age, 0.05)
        reach = age_intensity.get(age, 0)
        weighted = reach * weight
        result.age_weighted[age] = weighted
        total_score += weighted
        total_weight += weight

    # 정규화 (0~100) — 도달한 세대의 가중 평균
    result.score = min(100, total_score / total_weight) if total_weight > 0 else 0

    # ── Step 3: 등급 ──
    if result.score >= 70:
        result.grade = "EXCELLENT"
    elif result.score >= 50:
        result.grade = "GOOD"
    elif result.score >= 30:
        result.grade = "PARTIAL"
    else:
        result.grade = "WEAK"

    # ── Step 4: 타겟 분석 ──
    reach_30s = age_intensity.get("30s", 0)
    reach_40s = age_intensity.get("40s", 0)
    result.target_reached = (reach_30s >= 30 and reach_40s >= 30)

    # 가장 강한/약한 세그먼트
    strategic_ages = ["20s", "30s", "40s", "50s"]
    filled = {a: age_intensity.get(a, 0) for a in strategic_ages}
    if filled:
        result.strongest_segment = max(filled, key=filled.get)
        result.gap_segment = min(filled, key=filled.get)

    # ── Step 5: 전략 시사점 ──
    parts = []
    if result.score >= 70:
        parts.append("타겟 세그먼트 전반에 이슈 도달 양호.")
    elif result.score >= 50:
        parts.append(f"부분 도달. {result.gap_segment} 세대 확산 부족.")
    else:
        parts.append(f"도달 취약. 핵심 타겟 미도달 — {result.gap_segment} 집중 필요.")

    if not result.target_reached:
        parts.append("3040 핵심층 도달 미흡 — 맘카페/신도시 확산 전략 필요.")

    if reach_30s >= 50:
        parts.append("30대 반응 활발 — 맘카페/SNS 2차 확산 유도.")
    if age_intensity.get("50s", 0) < 20:
        parts.append("50대 이탈 위험 — 뉴시니어 타겟 메시지 필요.")

    result.insight = " ".join(parts)

    return result


def get_segment_hint(keyword: str, community_id: str = "", platform: str = "") -> str:
    """
    간단한 segment_hint 문자열 반환 (기존 코드 호환용).
    unified_collector, issue_scoring에서 사용.
    """
    # 커뮤니티 우선
    proxy = COMMUNITY_PROXIES.get(community_id)
    if proxy:
        return proxy.label_ko

    # 키워드 기반
    kw_lower = keyword.lower()
    for hint in KEYWORD_SEGMENT_HINTS:
        if any(k in kw_lower for k in hint["keywords"]):
            return hint["label"]

    # 플랫폼 기반
    pp = PLATFORM_PROXIES.get(platform)
    if pp:
        return pp.label_ko

    return ""
