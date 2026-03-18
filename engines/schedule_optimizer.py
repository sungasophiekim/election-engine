"""
Election Strategy Engine — Campaign Schedule Optimizer
유세 일정을 자동 최적화합니다.

지역 간 이동 시간, 유권자 우선순위, 이슈 데이터, 요일별 특성을 종합하여
최적의 일일/주간 유세 일정을 생성합니다.
"""
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from itertools import permutations

from config.tenant_config import TenantConfig
from models.schemas import VoterSegment, IssueScore, CrisisLevel


# ── 경남 지역 간 이동 시간 (분) ──────────────────────────────────────
TRAVEL_TIMES = {
    ("창원시", "진주시"): 50,
    ("창원시", "김해시"): 30,
    ("창원시", "거제시"): 60,
    ("창원시", "양산시"): 40,
    ("창원시", "통영시"): 70,
    ("창원시", "사천시"): 60,
    ("창원시", "밀양시"): 50,
    ("진주시", "사천시"): 20,
    ("진주시", "통영시"): 60,
    ("진주시", "밀양시"): 70,
    ("김해시", "양산시"): 25,
    ("김해시", "밀양시"): 40,
    ("거제시", "통영시"): 30,
    ("양산시", "밀양시"): 35,
    ("사천시", "통영시"): 45,
}
# 양방향
for (a, b), t in list(TRAVEL_TIMES.items()):
    TRAVEL_TIMES[(b, a)] = t

# 직접 연결이 없는 경우 경유 추정치 (최대 120분)
_ALL_CITIES = ["창원시", "진주시", "김해시", "거제시", "양산시", "통영시", "사천시", "밀양시"]

def _get_travel_time(city_a: str, city_b: str) -> int:
    """두 도시 간 이동 시간 반환. 직접 경로가 없으면 창원 경유로 추정."""
    if city_a == city_b:
        return 0
    if (city_a, city_b) in TRAVEL_TIMES:
        return TRAVEL_TIMES[(city_a, city_b)]
    # 창원 경유 추정
    via_changwon = (
        TRAVEL_TIMES.get(("창원시", city_a), 90)
        + TRAVEL_TIMES.get(("창원시", city_b), 90)
    )
    return min(via_changwon, 120)


# ── 장소 힌트 데이터 ─────────────────────────────────────────────────
LOCATION_HINTS = {
    "창원시": {
        "유세": "창원 상남동 로터리",
        "간담회": "창원컨벤션센터",
        "방문": "창원 국가산단",
        "기자회견": "경남도청 브리핑룸",
        "시장방문": "마산어시장",
    },
    "김해시": {
        "유세": "김해 활천로터리",
        "간담회": "김해문화의전당",
        "방문": "김해 장유신도시",
        "시장방문": "김해 동상시장",
    },
    "진주시": {
        "유세": "진주 중앙시장 앞",
        "간담회": "경남혁신도시",
        "방문": "진주 평거동",
        "시장방문": "진주 중앙시장",
    },
    "거제시": {
        "유세": "거제 고현시장 앞",
        "간담회": "거제문화예술회관",
        "방문": "대우조선해양",
        "시장방문": "거제 고현시장",
    },
    "양산시": {
        "유세": "양산 중앙시장 앞",
        "간담회": "양산문화예술회관",
        "방문": "양산 물금신도시",
        "시장방문": "양산 중부시장",
    },
    "통영시": {
        "유세": "통영 중앙시장 앞",
        "간담회": "통영시민문화회관",
        "방문": "통영 강구안",
        "시장방문": "통영 서호시장",
    },
    "사천시": {
        "유세": "사천 삼천포시장 앞",
        "간담회": "사천항공우주과학관",
        "방문": "KAI 사천공장",
        "시장방문": "삼천포 용궁수산시장",
    },
    "밀양시": {
        "유세": "밀양역 광장",
        "간담회": "밀양아리나",
        "방문": "밀양 삼랑진",
        "시장방문": "밀양 아리랑시장",
    },
}

# ── 지역별 이슈-토킹포인트 매핑 ──────────────────────────────────────
REGION_TALKING_POINTS = {
    "창원시": {
        "default": ["경남형 스마트산단으로 창원 제조업 부활", "창원 국가산단 디지털 전환 가속"],
        "조선업 일자리": ["조선업 스마트화로 양질의 일자리 창출", "창원 기계산업 + 조선 클러스터 연계"],
    },
    "김해시": {
        "default": ["BRT 3개 노선으로 김해-창원 30분 생활권", "장유신도시 교통 인프라 확충"],
        "교통 인프라": ["김해경전철 연장 추진", "김해-부산 광역교통 개선"],
    },
    "진주시": {
        "default": ["경남혁신도시 2기 사업 유치", "진주를 경남 서부 거점도시로"],
        "혁신도시 2기": ["혁신도시 공공기관 추가 이전", "진주 바이오산업 클러스터 조성"],
    },
    "거제시": {
        "default": ["방산 수출 확대로 거제 경제 살리기", "대우조선 정상화 지원"],
        "방산 산업": ["방산 클러스터 거제 유치", "해양방위산업 특구 지정 추진"],
    },
    "양산시": {
        "default": ["양산-부산 광역교통망 확충", "물금신도시 자족기능 강화"],
        "수도권 연계": ["양산 스마트시티 조성", "부울경 메가시티 양산 거점화"],
    },
    "통영시": {
        "default": ["통영 해양관광 거점도시 육성", "수산업 스마트화 지원"],
        "관광·어업": ["통영 국제관광도시 브랜드화", "어민 소득 안정화 대책"],
    },
    "사천시": {
        "default": ["KAI 중심 항공산업 클러스터 확대", "사천공항 활성화"],
        "항공 산업": ["항공MRO 사업 유치", "사천 우주산업 특구 추진"],
    },
    "밀양시": {
        "default": ["밀양 스마트 농업 혁신", "밀양 관광자원 활성화"],
        "농업·관광": ["스마트팜 단지 조성", "밀양 아리랑 문화관광 벨트"],
    },
}

# ── 기본 주간 지역 배분 템플릿 ─────────────────────────────────────
DEFAULT_WEEKLY_TEMPLATE = {
    0: ["창원시", "김해시"],     # 월: 인접 대도시
    1: ["진주시", "사천시"],     # 화: 서부권
    2: ["거제시", "통영시"],     # 수: 해안권
    3: ["양산시", "밀양시"],     # 목: 내륙권
    4: ["창원시"],              # 금: 주말 대규모 유세 준비
    5: ["김해시", "양산시"],     # 토: 대규모 유세
    6: ["창원시"],              # 일: 최대 유권자, 대규모 마무리
}


# ── 데이터 클래스 ────────────────────────────────────────────────────

@dataclass
class ScheduleEvent:
    """유세 일정 단위"""
    time_slot: str              # "09:00-11:00"
    region: str                 # "창원시"
    event_type: str             # "유세" | "간담회" | "기자회견" | "방문" | "이동"
    location_hint: str          # "창원 상남동 일대"
    talking_points: list[str]   # 해당 일정에서 강조할 메시지
    priority: str               # "필수" | "권장" | "선택"
    notes: str                  # 참고사항


@dataclass
class DailySchedule:
    """하루 유세 일정"""
    date: str
    day_theme: str              # 오늘의 유세 테마
    events: list[ScheduleEvent]
    total_regions: int          # 방문 지역 수
    total_travel_min: int       # 총 이동 시간
    key_message: str            # 오늘의 핵심 메시지


@dataclass
class WeeklyPlan:
    """주간 유세 계획"""
    week_start: str
    week_end: str
    week_theme: str
    daily_schedules: list[DailySchedule]
    region_coverage: dict       # {"창원시": 3, "김해시": 2, ...}
    uncovered_regions: list[str]


# ── 메인 클래스 ──────────────────────────────────────────────────────

class ScheduleOptimizer:
    """
    유세 일정 자동 최적화.

    Constraints:
    - 하루 유세 가능 시간: 09:00 ~ 21:00 (12시간)
    - 점심 12:00-13:00, 저녁 18:00-19:00 (식사 겸 간담회 가능)
    - 하루 최대 3개 지역 방문 (이동 피로 고려)
    - 이동 시간 최소화 (인접 지역 묶어서 방문)
    - 주말(토/일): 대규모 유세, 평일: 간담회/방문 중심
    - 후보(현직 도지사)는 창원(도청 소재지)에서 출발
    """

    HOME_BASE = "창원시"

    def __init__(self, config: TenantConfig):
        self.config = config

    # ------------------------------------------------------------------
    # 공개 메서드
    # ------------------------------------------------------------------
    def generate_daily_schedule(
        self,
        target_date: str,
        voter_segments: list[VoterSegment] = None,
        issue_scores: list[IssueScore] = None,
        campaign_mode: str = "선점",
        forced_regions: list[str] = None,
    ) -> DailySchedule:
        """
        하루 유세 일정 생성.

        Algorithm:
        1. Rank regions by priority (voter_segments)
        2. Select top 2-3 regions (considering travel time)
        3. Optimize visit order (nearest-neighbor / brute-force TSP)
        4. Assign time slots (morning/afternoon/evening)
        5. Generate talking points per region
        """
        voter_segments = voter_segments or []
        issue_scores = issue_scores or []
        forced_regions = forced_regions or []

        dt = datetime.strptime(target_date, "%Y-%m-%d").date()
        is_weekend = dt.weekday() >= 5  # 토(5), 일(6)

        # 1. 방문 지역 선택
        all_regions = list(self.config.regions.keys()) if self.config.regions else _ALL_CITIES
        selected = self._select_regions_for_day(
            all_regions, voter_segments, max_regions=3 if not is_weekend else 2, forced=forced_regions
        )

        # 2. 방문 순서 최적화 (창원 출발)
        ordered, total_travel = self._optimize_route(selected)

        # 3. 시간대 배정
        travel_between = []
        prev = self.HOME_BASE
        for r in ordered:
            travel_between.append(_get_travel_time(prev, r))
            prev = r
        events = self._assign_time_slots(ordered, travel_between, is_weekend, issue_scores, campaign_mode)

        # 4. 테마 & 핵심 메시지
        day_theme = self._generate_day_theme(ordered, is_weekend, campaign_mode)
        key_message = self._generate_key_message(ordered, issue_scores, campaign_mode)

        return DailySchedule(
            date=target_date,
            day_theme=day_theme,
            events=events,
            total_regions=len(ordered),
            total_travel_min=total_travel,
            key_message=key_message,
        )

    def generate_weekly_plan(
        self,
        start_date: str,
        voter_segments: list[VoterSegment] = None,
        issue_scores: list[IssueScore] = None,
        campaign_mode: str = "선점",
    ) -> WeeklyPlan:
        """
        주간 유세 계획 생성.

        Algorithm:
        1. Ensure all 8 regions are covered at least once per week
        2. High-priority regions (top 3) get 2+ visits
        3. Weekend: large rally in top region
        4. Weekday: smaller events in 2-3 regions/day
        5. Balance travel vs coverage
        """
        voter_segments = voter_segments or []
        issue_scores = issue_scores or []

        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        # start_date가 월요일이 아닌 경우에도 7일간 생성
        end = start + timedelta(days=6)

        # 지역 우선순위 정렬
        priority_regions = self._rank_regions(voter_segments)
        top3 = priority_regions[:3] if len(priority_regions) >= 3 else priority_regions

        # 주간 지역 배분 계획
        weekly_region_plan = self._build_weekly_region_plan(start, priority_regions, top3)

        # 일별 스케줄 생성
        daily_schedules = []
        for day_offset in range(7):
            current_date = start + timedelta(days=day_offset)
            day_str = current_date.strftime("%Y-%m-%d")
            forced = weekly_region_plan.get(day_offset, [])

            schedule = self.generate_daily_schedule(
                target_date=day_str,
                voter_segments=voter_segments,
                issue_scores=issue_scores,
                campaign_mode=campaign_mode,
                forced_regions=forced,
            )
            daily_schedules.append(schedule)

        # 커버리지 집계
        region_coverage: dict[str, int] = {}
        for ds in daily_schedules:
            visited = set()
            for ev in ds.events:
                if ev.event_type != "이동":
                    visited.add(ev.region)
            for r in visited:
                region_coverage[r] = region_coverage.get(r, 0) + 1

        all_regions = set(self.config.regions.keys()) if self.config.regions else set(_ALL_CITIES)
        uncovered = sorted(all_regions - set(region_coverage.keys()))

        week_theme = self._generate_week_theme(campaign_mode, priority_regions)

        return WeeklyPlan(
            week_start=start_date,
            week_end=end.strftime("%Y-%m-%d"),
            week_theme=week_theme,
            daily_schedules=daily_schedules,
            region_coverage=region_coverage,
            uncovered_regions=uncovered,
        )

    # ------------------------------------------------------------------
    # 내부 메서드: 지역 선택
    # ------------------------------------------------------------------
    def _rank_regions(self, voter_segments: list[VoterSegment]) -> list[str]:
        """유권자 세그먼트 기반 지역 우선순위 정렬."""
        if not voter_segments:
            # 기본: config.regions의 유권자 수 기반
            regions = self.config.regions if self.config.regions else {}
            return sorted(regions.keys(), key=lambda r: regions[r].get("voters", 0), reverse=True)

        sorted_segs = sorted(voter_segments, key=lambda s: s.priority_score, reverse=True)
        return [s.region for s in sorted_segs]

    def _select_regions_for_day(
        self,
        available_regions: list[str],
        voter_segments: list[VoterSegment],
        max_regions: int = 3,
        forced: list[str] = None,
    ) -> list[str]:
        """
        하루 방문 지역 선택.
        - Priority score 기반 선택
        - 이동 시간 최소화 (인접 지역 우선)
        - forced 지역 반드시 포함
        """
        forced = forced or []
        selected = list(forced)

        # 우선순위 정렬
        priority_order = self._rank_regions(voter_segments)

        # forced가 아닌 지역 중 우선순위 높은 순으로 추가
        for region in priority_order:
            if len(selected) >= max_regions:
                break
            if region in selected:
                continue
            if region not in available_regions:
                continue

            # 이동 효율 체크: 이미 선택된 지역과의 평균 이동 시간
            if selected:
                avg_travel = sum(_get_travel_time(region, r) for r in selected) / len(selected)
                # 평균 이동 시간이 80분 초과면 건너뜀 (너무 먼 지역)
                if avg_travel > 80 and len(selected) >= 2:
                    continue

            selected.append(region)

        # 최소 1개 지역 보장
        if not selected and available_regions:
            selected.append(available_regions[0])

        return selected[:max_regions]

    # ------------------------------------------------------------------
    # 내부 메서드: 경로 최적화
    # ------------------------------------------------------------------
    def _optimize_route(self, regions: list[str]) -> tuple[list[str], int]:
        """
        방문 순서 최적화.
        8개 이하 도시이므로 brute-force로 최적 경로 탐색.
        창원(HOME_BASE)에서 출발하는 것을 전제로 함.

        Returns: (ordered_regions, total_travel_minutes)
        """
        if len(regions) <= 1:
            travel = _get_travel_time(self.HOME_BASE, regions[0]) if regions else 0
            return regions, travel

        best_order = None
        best_cost = float("inf")

        for perm in permutations(regions):
            cost = _get_travel_time(self.HOME_BASE, perm[0])
            for i in range(len(perm) - 1):
                cost += _get_travel_time(perm[i], perm[i + 1])
            if cost < best_cost:
                best_cost = cost
                best_order = list(perm)

        return best_order, best_cost

    # ------------------------------------------------------------------
    # 내부 메서드: 시간대 배정
    # ------------------------------------------------------------------
    def _assign_time_slots(
        self,
        regions: list[str],
        travel_times_to: list[int],
        is_weekend: bool,
        issue_scores: list[IssueScore] = None,
        campaign_mode: str = "선점",
    ) -> list[ScheduleEvent]:
        """
        시간대 배정. 평일/주말 템플릿 기반.
        travel_times_to[i] = 이전 위치 -> regions[i]까지 이동 시간
        """
        issue_scores = issue_scores or []
        events: list[ScheduleEvent] = []

        if is_weekend:
            events = self._assign_weekend_slots(regions, travel_times_to, issue_scores, campaign_mode)
        else:
            events = self._assign_weekday_slots(regions, travel_times_to, issue_scores, campaign_mode)

        return events

    def _assign_weekday_slots(
        self,
        regions: list[str],
        travel_times_to: list[int],
        issue_scores: list[IssueScore],
        campaign_mode: str,
    ) -> list[ScheduleEvent]:
        """평일 시간대 배정"""
        events: list[ScheduleEvent] = []
        n = len(regions)

        if n == 1:
            r = regions[0]
            tt = travel_times_to[0]
            tp = self._generate_talking_points(r, issue_scores, campaign_mode)
            # 이동
            depart = "09:00"
            arrive = self._add_minutes(depart, tt)
            if tt > 0 and r != self.HOME_BASE:
                events.append(ScheduleEvent(
                    time_slot=f"09:00-{arrive}",
                    region="", event_type="이동",
                    location_hint=f"{self.HOME_BASE} -> {r}",
                    talking_points=[], priority="필수",
                    notes=f"이동 {tt}분",
                ))
            # 오전 유세
            events.append(ScheduleEvent(
                time_slot=f"{arrive}-12:00", region=r, event_type="현장 방문",
                location_hint=self._get_location_hint(r, "방문"),
                talking_points=tp[:2], priority="필수",
                notes="오전 현장 방문 및 주민 소통",
            ))
            # 점심 간담회
            events.append(ScheduleEvent(
                time_slot="12:00-13:00", region=r, event_type="점심 간담회",
                location_hint=f"{r} 인근 식당",
                talking_points=[tp[0]] if tp else [], priority="권장",
                notes="지역 인사·지지자 오찬 간담회",
            ))
            # 오후 유세
            events.append(ScheduleEvent(
                time_slot="13:00-15:30", region=r, event_type="유세",
                location_hint=self._get_location_hint(r, "유세"),
                talking_points=tp, priority="필수",
                notes="거리 유세 및 시민 악수",
            ))
            # 오후 간담회
            events.append(ScheduleEvent(
                time_slot="15:30-17:30", region=r, event_type="간담회",
                location_hint=self._get_location_hint(r, "간담회"),
                talking_points=tp[1:3] if len(tp) > 1 else tp, priority="권장",
                notes="지역 현안 토론회",
            ))
            # 저녁
            events.append(ScheduleEvent(
                time_slot="18:00-19:00", region=r, event_type="저녁 간담회",
                location_hint=f"{r} 인근 식당",
                talking_points=[], priority="선택",
                notes="지역 지지자 만찬",
            ))
            # 야간 유세
            events.append(ScheduleEvent(
                time_slot="19:00-21:00", region=r, event_type="유세",
                location_hint=self._get_location_hint(r, "유세"),
                talking_points=tp[:2], priority="권장",
                notes="야간 거리 유세",
            ))

        elif n == 2:
            r1, r2 = regions[0], regions[1]
            tt1 = travel_times_to[0]
            tt2 = _get_travel_time(r1, r2)
            tp1 = self._generate_talking_points(r1, issue_scores, campaign_mode)
            tp2 = self._generate_talking_points(r2, issue_scores, campaign_mode)

            # 이동 -> 지역1
            arrive1 = self._add_minutes("09:00", tt1)
            if tt1 > 0 and r1 != self.HOME_BASE:
                events.append(ScheduleEvent(
                    time_slot=f"09:00-{arrive1}", region="", event_type="이동",
                    location_hint=f"{self.HOME_BASE} -> {r1}",
                    talking_points=[], priority="필수",
                    notes=f"이동 {tt1}분",
                ))
            # 지역1 오전
            events.append(ScheduleEvent(
                time_slot=f"{arrive1}-12:00", region=r1, event_type="유세",
                location_hint=self._get_location_hint(r1, "유세"),
                talking_points=tp1, priority="필수",
                notes="오전 거리 유세 및 시장 방문",
            ))
            # 점심 간담회 (지역1)
            events.append(ScheduleEvent(
                time_slot="12:00-13:00", region=r1, event_type="점심 간담회",
                location_hint=f"{r1} 인근 식당",
                talking_points=[tp1[0]] if tp1 else [], priority="권장",
                notes="지역 인사 오찬 간담회",
            ))
            # 이동 -> 지역2
            depart2 = "13:00"
            arrive2 = self._add_minutes(depart2, tt2)
            events.append(ScheduleEvent(
                time_slot=f"13:00-{arrive2}", region="", event_type="이동",
                location_hint=f"{r1} -> {r2}",
                talking_points=[], priority="필수",
                notes=f"이동 {tt2}분",
            ))
            # 지역2 오후
            events.append(ScheduleEvent(
                time_slot=f"{arrive2}-17:30", region=r2, event_type="유세",
                location_hint=self._get_location_hint(r2, "유세"),
                talking_points=tp2, priority="필수",
                notes="오후 거리 유세",
            ))
            # 지역2 저녁 간담회
            events.append(ScheduleEvent(
                time_slot="18:00-19:00", region=r2, event_type="저녁 간담회",
                location_hint=f"{r2} 인근 식당",
                talking_points=[tp2[0]] if tp2 else [], priority="권장",
                notes="지역 지지자 만찬",
            ))
            # 지역2 야간 유세
            events.append(ScheduleEvent(
                time_slot="19:00-21:00", region=r2, event_type="유세",
                location_hint=self._get_location_hint(r2, "유세"),
                talking_points=tp2[:2], priority="권장",
                notes="야간 거리 유세 및 시민 소통",
            ))

        elif n >= 3:
            r1, r2, r3 = regions[0], regions[1], regions[2]
            tt1 = travel_times_to[0]
            tt2 = _get_travel_time(r1, r2)
            tt3 = _get_travel_time(r2, r3)
            tp1 = self._generate_talking_points(r1, issue_scores, campaign_mode)
            tp2 = self._generate_talking_points(r2, issue_scores, campaign_mode)
            tp3 = self._generate_talking_points(r3, issue_scores, campaign_mode)

            # 이동 -> 지역1
            arrive1 = self._add_minutes("09:00", tt1)
            if tt1 > 0 and r1 != self.HOME_BASE:
                events.append(ScheduleEvent(
                    time_slot=f"09:00-{arrive1}", region="", event_type="이동",
                    location_hint=f"{self.HOME_BASE} -> {r1}",
                    talking_points=[], priority="필수",
                    notes=f"이동 {tt1}분",
                ))
            # 지역1 오전
            events.append(ScheduleEvent(
                time_slot=f"{arrive1}-11:00", region=r1, event_type="현장 방문",
                location_hint=self._get_location_hint(r1, "방문"),
                talking_points=tp1[:2], priority="필수",
                notes="현장 방문 및 주민 간담",
            ))
            # 이동 -> 지역2
            arrive2 = self._add_minutes("11:00", tt2)
            events.append(ScheduleEvent(
                time_slot=f"11:00-{arrive2}", region="", event_type="이동",
                location_hint=f"{r1} -> {r2}",
                talking_points=[], priority="필수",
                notes=f"이동 {tt2}분",
            ))
            # 지역2 점심 간담회
            events.append(ScheduleEvent(
                time_slot="12:00-13:00", region=r2, event_type="점심 간담회",
                location_hint=f"{r2} 인근 식당",
                talking_points=[tp2[0]] if tp2 else [], priority="필수",
                notes="지역 인사 오찬 간담회",
            ))
            # 지역2 오후 유세
            events.append(ScheduleEvent(
                time_slot="13:00-15:00", region=r2, event_type="유세",
                location_hint=self._get_location_hint(r2, "유세"),
                talking_points=tp2, priority="필수",
                notes="오후 거리 유세",
            ))
            # 이동 -> 지역3
            arrive3 = self._add_minutes("15:00", tt3)
            events.append(ScheduleEvent(
                time_slot=f"15:00-{arrive3}", region="", event_type="이동",
                location_hint=f"{r2} -> {r3}",
                talking_points=[], priority="필수",
                notes=f"이동 {tt3}분",
            ))
            # 지역3 오후 유세
            events.append(ScheduleEvent(
                time_slot=f"{arrive3}-18:00", region=r3, event_type="유세",
                location_hint=self._get_location_hint(r3, "유세"),
                talking_points=tp3, priority="필수",
                notes="오후 거리 유세",
            ))
            # 지역3 저녁 간담회
            events.append(ScheduleEvent(
                time_slot="18:00-19:00", region=r3, event_type="저녁 간담회",
                location_hint=f"{r3} 인근 식당",
                talking_points=[tp3[0]] if tp3 else [], priority="권장",
                notes="지역 지지자 만찬 간담회",
            ))
            # 지역3 야간 유세
            events.append(ScheduleEvent(
                time_slot="19:00-21:00", region=r3, event_type="유세",
                location_hint=self._get_location_hint(r3, "유세"),
                talking_points=tp3[:2], priority="권장",
                notes="야간 유세 및 시민 만남",
            ))

        return events

    def _assign_weekend_slots(
        self,
        regions: list[str],
        travel_times_to: list[int],
        issue_scores: list[IssueScore],
        campaign_mode: str,
    ) -> list[ScheduleEvent]:
        """주말 시간대 배정 (대규모 유세 중심)"""
        events: list[ScheduleEvent] = []
        n = len(regions)

        if n == 1:
            r = regions[0]
            tt = travel_times_to[0]
            tp = self._generate_talking_points(r, issue_scores, campaign_mode)

            arrive = self._add_minutes("09:00", tt)
            if tt > 0 and r != self.HOME_BASE:
                events.append(ScheduleEvent(
                    time_slot=f"09:00-{arrive}", region="", event_type="이동",
                    location_hint=f"{self.HOME_BASE} -> {r}",
                    talking_points=[], priority="필수",
                    notes=f"이동 {tt}분",
                ))
            events.append(ScheduleEvent(
                time_slot=f"{arrive}-11:30", region=r, event_type="대규모 유세",
                location_hint=self._get_location_hint(r, "유세"),
                talking_points=tp, priority="필수",
                notes="오전 대규모 거리 유세 (지지자 총동원)",
            ))
            events.append(ScheduleEvent(
                time_slot="12:00-14:00", region=r, event_type="시장 방문",
                location_hint=self._get_location_hint(r, "시장방문"),
                talking_points=tp[:2], priority="필수",
                notes="점심시간 전통시장 방문 및 상인 소통",
            ))
            events.append(ScheduleEvent(
                time_slot="14:30-17:00", region=r, event_type="대규모 유세",
                location_hint=self._get_location_hint(r, "유세"),
                talking_points=tp, priority="필수",
                notes="오후 대규모 유세 (핵심 시간대)",
            ))
            events.append(ScheduleEvent(
                time_slot="17:30-19:00", region=r, event_type="시민 소통",
                location_hint=f"{r} 중심 상업지구",
                talking_points=tp[:2], priority="권장",
                notes="시민 자유 소통 및 사진 촬영",
            ))
            events.append(ScheduleEvent(
                time_slot="19:00-21:00", region=r, event_type="야간 유세",
                location_hint=self._get_location_hint(r, "유세"),
                talking_points=tp[:2], priority="권장",
                notes="야간 대규모 마무리 유세",
            ))

        elif n >= 2:
            r1, r2 = regions[0], regions[1]
            tt1 = travel_times_to[0]
            tt2 = _get_travel_time(r1, r2)
            tp1 = self._generate_talking_points(r1, issue_scores, campaign_mode)
            tp2 = self._generate_talking_points(r2, issue_scores, campaign_mode)

            arrive1 = self._add_minutes("09:00", tt1)
            if tt1 > 0 and r1 != self.HOME_BASE:
                events.append(ScheduleEvent(
                    time_slot=f"09:00-{arrive1}", region="", event_type="이동",
                    location_hint=f"{self.HOME_BASE} -> {r1}",
                    talking_points=[], priority="필수",
                    notes=f"이동 {tt1}분",
                ))
            events.append(ScheduleEvent(
                time_slot=f"{arrive1}-11:30", region=r1, event_type="대규모 유세",
                location_hint=self._get_location_hint(r1, "유세"),
                talking_points=tp1, priority="필수",
                notes="오전 대규모 거리 유세",
            ))
            events.append(ScheduleEvent(
                time_slot="12:00-13:30", region=r1, event_type="시장 방문",
                location_hint=self._get_location_hint(r1, "시장방문"),
                talking_points=tp1[:2], priority="필수",
                notes="점심시간 전통시장 방문",
            ))
            # 이동
            arrive2 = self._add_minutes("13:30", tt2)
            events.append(ScheduleEvent(
                time_slot=f"13:30-{arrive2}", region="", event_type="이동",
                location_hint=f"{r1} -> {r2}",
                talking_points=[], priority="필수",
                notes=f"이동 {tt2}분",
            ))
            events.append(ScheduleEvent(
                time_slot=f"{arrive2}-17:00", region=r2, event_type="대규모 유세",
                location_hint=self._get_location_hint(r2, "유세"),
                talking_points=tp2, priority="필수",
                notes="오후 대규모 유세 (핵심 시간대)",
            ))
            events.append(ScheduleEvent(
                time_slot="17:30-19:00", region=r2, event_type="시민 소통",
                location_hint=f"{r2} 중심 상업지구",
                talking_points=tp2[:2], priority="권장",
                notes="시민 소통 및 지지자 만남",
            ))
            events.append(ScheduleEvent(
                time_slot="19:00-21:00", region=r2, event_type="야간 유세",
                location_hint=self._get_location_hint(r2, "유세"),
                talking_points=tp2[:2], priority="권장",
                notes="야간 대규모 마무리 유세",
            ))

        return events

    # ------------------------------------------------------------------
    # 내부 메서드: 토킹포인트 / 장소
    # ------------------------------------------------------------------
    def _generate_talking_points(
        self,
        region: str,
        issue_scores: list[IssueScore],
        campaign_mode: str,
    ) -> list[str]:
        """
        지역별 토킹포인트 생성.
        - 지역 key_issue에 매칭되는 우리 공약
        - 지역별 맞춤 메시지
        - campaign_mode에 따른 톤 조절
        """
        points: list[str] = []
        region_info = self.config.regions.get(region, {})
        key_issue = region_info.get("key_issue", "")

        # 1. 지역별 사전 정의 토킹포인트
        region_tp = REGION_TALKING_POINTS.get(region, {})
        if key_issue and key_issue in region_tp:
            points.extend(region_tp[key_issue])
        else:
            points.extend(region_tp.get("default", []))

        # 2. config의 공약에서 지역 이슈와 매칭
        for pledge_name, pledge_data in self.config.pledges.items():
            desc = pledge_data.get("설명", "")
            number = pledge_data.get("수치", "")
            if key_issue:
                for kw in key_issue.split():
                    if len(kw) >= 2 and (kw in pledge_name or kw in desc):
                        points.append(f"{pledge_name}: {number}")
                        break

        # 3. 이슈 스코어에서 관련 이슈 추가
        for issue in issue_scores:
            if key_issue and any(kw in issue.keyword for kw in key_issue.split() if len(kw) >= 2):
                if issue.level in (CrisisLevel.WATCH, CrisisLevel.NORMAL):
                    points.append(f"'{issue.keyword}' 관련 우리 해법 제시")

        # 4. 모드별 기본 톤 추가
        if campaign_mode == "공격":
            points.append(f"상대 후보의 {key_issue or '핵심 이슈'} 대응 부재 부각")
        elif campaign_mode == "수비":
            points.append(f"현직 도지사로서의 {key_issue or '핵심 분야'} 성과 강조")
        elif campaign_mode == "선점":
            points.append(f"'{key_issue or '핵심 의제'}' 프레임을 우리가 선점")

        # 중복 제거 (순서 유지)
        seen = set()
        unique = []
        for p in points:
            if p not in seen:
                seen.add(p)
                unique.append(p)

        return unique[:4]  # 최대 4개

    def _get_location_hint(self, region: str, event_type: str) -> str:
        """구체적 장소 제안."""
        return LOCATION_HINTS.get(region, {}).get(event_type, f"{region} 중심가")

    # ------------------------------------------------------------------
    # 내부 메서드: 주간 계획 빌더
    # ------------------------------------------------------------------
    def _build_weekly_region_plan(
        self,
        start: date,
        priority_regions: list[str],
        top3: list[str],
    ) -> dict[int, list[str]]:
        """
        주간 지역 배분 계획 생성.
        기본 템플릿을 우선순위에 따라 동적 조정.
        """
        all_regions = set(self.config.regions.keys()) if self.config.regions else set(_ALL_CITIES)
        plan: dict[int, list[str]] = {}

        # 기본 템플릿 복사
        for day_offset in range(7):
            weekday = (start + timedelta(days=day_offset)).weekday()
            plan[day_offset] = list(DEFAULT_WEEKLY_TEMPLATE.get(weekday, []))

        # 동적 조정: top3 지역이 주 2회 이상 방문되도록
        region_visit_count: dict[str, int] = {}
        for day_offset, regions in plan.items():
            for r in regions:
                region_visit_count[r] = region_visit_count.get(r, 0) + 1

        # top3 중 1회만 방문되는 지역 추가 방문
        for r in top3:
            if region_visit_count.get(r, 0) < 2:
                # 가장 여유 있는 평일(지역 수가 적은 날)에 추가
                for day_offset in range(5):  # 평일만
                    if len(plan[day_offset]) < 3 and r not in plan[day_offset]:
                        plan[day_offset].append(r)
                        region_visit_count[r] = region_visit_count.get(r, 0) + 1
                        break

        # 미방문 지역 체크 및 추가
        visited = set()
        for regions in plan.values():
            visited.update(regions)

        missing = all_regions - visited
        for r in missing:
            # 가장 여유 있는 평일에 추가
            for day_offset in range(5):
                if len(plan[day_offset]) < 3 and r not in plan[day_offset]:
                    plan[day_offset].append(r)
                    break

        return plan

    # ------------------------------------------------------------------
    # 내부 메서드: 테마/메시지 생성
    # ------------------------------------------------------------------
    def _generate_day_theme(self, regions: list[str], is_weekend: bool, campaign_mode: str) -> str:
        """오늘의 유세 테마 생성"""
        region_str = "·".join(regions)
        if is_weekend:
            return f"[주말 총력 유세] {region_str} 대규모 유세의 날"

        mode_themes = {
            "공격": "공세 강화",
            "수비": "지지층 결집",
            "선점": "의제 선점",
            "위기대응": "위기 극복",
        }
        theme = mode_themes.get(campaign_mode, "현장 소통")
        return f"[{theme}] {region_str} 집중 유세"

    def _generate_key_message(
        self, regions: list[str], issue_scores: list[IssueScore], campaign_mode: str
    ) -> str:
        """오늘의 핵심 메시지 생성"""
        region_issues = []
        for r in regions:
            info = self.config.regions.get(r, {})
            issue = info.get("key_issue", "")
            if issue:
                region_issues.append(issue)

        if region_issues:
            issue_text = ", ".join(region_issues[:2])
            return f"'{issue_text}' 해결을 위한 구체적 비전 — {self.config.slogan}"
        return f"{self.config.core_message} — {self.config.slogan}"

    def _generate_week_theme(self, campaign_mode: str, priority_regions: list[str]) -> str:
        """주간 테마 생성"""
        top_region = priority_regions[0] if priority_regions else "경남 전역"
        mode_themes = {
            "공격": f"전면 공세 — {top_region} 중심 반격의 한 주",
            "수비": f"리드 수성 — 경남 8개 시 순회로 지지층 결집",
            "선점": f"의제 선점 — 경남의 미래 비전을 먼저 제시하는 한 주",
            "위기대응": f"위기 돌파 — 현장에서 직접 소통하는 한 주",
        }
        return mode_themes.get(campaign_mode, f"경남 전역 순회 유세 — {self.config.slogan}")

    # ------------------------------------------------------------------
    # 유틸리티
    # ------------------------------------------------------------------
    @staticmethod
    def _add_minutes(time_str: str, minutes: int) -> str:
        """시간 문자열에 분을 더함. "09:00" + 30 -> "09:30" """
        h, m = map(int, time_str.split(":"))
        total = h * 60 + m + minutes
        return f"{total // 60:02d}:{total % 60:02d}"

    # ------------------------------------------------------------------
    # 보고서 포맷
    # ------------------------------------------------------------------
    def format_daily_report(self, schedule: DailySchedule) -> str:
        """일일 유세 일정 보고서"""
        sep = "=" * 64
        thin = "-" * 64

        lines = []
        lines.append(sep)
        lines.append(f"  일일 유세 일정 | {schedule.date}")
        lines.append(sep)
        lines.append(f"  테마: {schedule.day_theme}")
        lines.append(f"  방문 지역: {schedule.total_regions}개 | 총 이동: {schedule.total_travel_min}분")
        lines.append(f"  핵심 메시지: {schedule.key_message}")
        lines.append(thin)
        lines.append("")

        for ev in schedule.events:
            if ev.event_type == "이동":
                lines.append(f"  {ev.time_slot}  >>> {ev.location_hint} ({ev.notes})")
            else:
                priority_mark = {"필수": "[필수]", "권장": "[권장]", "선택": "[선택]"}.get(ev.priority, "")
                lines.append(f"  {ev.time_slot}  {ev.region} | {ev.event_type} {priority_mark}")
                lines.append(f"                   장소: {ev.location_hint}")
                if ev.talking_points:
                    for tp in ev.talking_points:
                        lines.append(f"                   > {tp}")
                if ev.notes:
                    lines.append(f"                   * {ev.notes}")
            lines.append("")

        lines.append(sep)
        return "\n".join(lines)

    def format_weekly_report(self, plan: WeeklyPlan) -> str:
        """주간 유세 계획 보고서"""
        sep = "=" * 64
        thin = "-" * 64

        lines = []
        lines.append(sep)
        lines.append(f"  주간 유세 계획 | {plan.week_start} ~ {plan.week_end}")
        lines.append(sep)
        lines.append(f"  주간 테마: {plan.week_theme}")
        lines.append("")

        # 지역 커버리지 요약
        lines.append("  [지역별 방문 횟수]")
        for region, count in sorted(plan.region_coverage.items(), key=lambda x: x[1], reverse=True):
            bar = "#" * count
            lines.append(f"    {region:6s} : {bar} ({count}회)")
        if plan.uncovered_regions:
            lines.append(f"    ** 미방문: {', '.join(plan.uncovered_regions)}")
        lines.append("")
        lines.append(thin)

        # 일별 요약
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        for ds in plan.daily_schedules:
            dt = datetime.strptime(ds.date, "%Y-%m-%d").date()
            day_name = weekday_names[dt.weekday()]
            # 방문 지역 추출
            visited = []
            for ev in ds.events:
                if ev.event_type != "이동" and ev.region and ev.region not in visited:
                    visited.append(ev.region)

            lines.append(f"  [{day_name}] {ds.date} | {' -> '.join(visited)} | 이동 {ds.total_travel_min}분")
            lines.append(f"       테마: {ds.day_theme}")
            lines.append(f"       메시지: {ds.key_message}")
            lines.append("")

        lines.append(thin)
        lines.append("  * 일별 상세 일정은 format_daily_report()로 확인")
        lines.append(sep)
        return "\n".join(lines)
