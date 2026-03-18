"""
Election Strategy Engine — 공통 데이터 모델
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class CrisisLevel(Enum):
    NORMAL = 0
    WATCH  = 1   # 관심
    ALERT  = 2   # 경계
    CRISIS = 3   # 위기


class ContentType(Enum):
    PRESS_RELEASE = "보도자료"
    SNS_POST      = "SNS"
    SPEECH        = "연설문"
    STATEMENT     = "논평"


@dataclass
class RawArticle:
    article_id:  str
    title:       str
    content:     str
    source:      str           # 언론사명
    published_at: datetime
    url:         str
    mention_candidate: bool = False


@dataclass
class IssueSignal:
    keyword:          str
    mention_count:    int        # 1시간 내 언급 수
    velocity:         float      # 전 시간 대비 증가율 (1.0 = 동일)
    negative_ratio:   float      # 0.0 ~ 1.0
    media_tier:       int        # 1=방송/메이저, 2=인터넷뉴스, 3=블로그/카페
    candidate_linked: bool       # 후보 이름 직접 연결 여부
    portal_trending:  bool       # 포털 실검 진입 여부
    tv_reported:      bool       # 방송 보도 여부
    collected_at:     datetime = field(default_factory=datetime.now)


@dataclass
class IssueScore:
    keyword:      str
    score:        float          # 0 ~ 100
    level:        CrisisLevel
    breakdown:    dict           # 점수 구성 요소
    estimated_halflife_hours: float  # 예상 이슈 소멸 시간
    scored_at:    datetime = field(default_factory=datetime.now)


@dataclass
class ContentDraft:
    content_type: ContentType
    text:         str
    tenant_id:    str
    created_at:   datetime = field(default_factory=datetime.now)


@dataclass
class ValidationResult:
    is_approved:        bool
    consistency_score:  float       # 0.0 ~ 1.0
    violations:         list[str]   # 위반 항목
    suggestions:        list[str]   # 수정 제안 (최대 3개)
    validated_at:       datetime = field(default_factory=datetime.now)


@dataclass
class VoterSegment:
    region:       str
    voter_count:  int
    swing_index:  float     # 0~1, 높을수록 경합
    online_activity: float  # 0~1
    local_issue_heat: float # 0~1
    priority_score: float = 0.0


@dataclass
class OpponentSignal:
    opponent_name:   str
    recent_mentions: int
    message_shift:   str    # 공약/메시지 변화 감지 텍스트
    attack_prob_72h: float  # 0~1
    recommended_action: str


@dataclass
class StrategicBrief:
    """오케스트레이터 최종 출력"""
    tenant_id:       str
    generated_at:    datetime
    top_issues:      list[IssueScore]
    crisis_level:    CrisisLevel
    response_actions: list[str]
    content_drafts:  list[str]      # 초안 텍스트 목록
    schedule_weights: dict          # 지역별 우선순위
    opponent_alerts: list[str]


@dataclass
class PollingData:
    poll_date: str              # "2026-03-04"
    pollster: str               # 조사기관
    sample_size: int
    margin_of_error: float
    our_support: float          # 우리 후보 지지율 (%)
    opponent_support: dict      # {"김경수": 36.4, "전희영": 2.1}
    undecided: float = 0.0      # 미정 비율
    region_breakdown: dict = field(default_factory=dict)  # {"창원": 45.2, "김해": 38.1}
