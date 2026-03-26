"""
Issue Index — Trigger Layer 전용 지수 (v2)
"얼마나 터졌는가"를 측정. 반응(reaction)은 포함하지 않음.

구성요소 (100점 만점):
  1. News Volume     (25) — naver_news + news_deduplicator
  2. Media Tier      (20) — naver_news (방송/메이저/포털)
  3. Spread Velocity  (30) — unified_collector + anomaly_detector
  4. Candidate Linkage(15) — keyword_engine + canonical_mapper + owned_channels
  5. Channel Diversity(10) — 전 채널 동시 확산 여부

기존 issue_scoring.py의 breakdown을 재사용하되, 별도 지수로 산출.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class IssueIndexResult:
    keyword: str
    index: float = 0.0              # 0~100
    grade: str = ""                 # EXPLOSIVE | HOT | ACTIVE | LOW | DORMANT

    # 5-component breakdown
    news_volume: float = 0.0        # 0~25
    media_tier: float = 0.0         # 0~20
    spread_velocity: float = 0.0    # 0~30
    candidate_linkage: float = 0.0  # 0~15
    channel_diversity: float = 0.0  # 0~10

    # 원본 참조 데이터
    raw_mentions: int = 0
    deduped_stories: int = 0
    tier1_count: int = 0
    source_diversity: int = 0
    velocity: float = 0.0
    surprise_score: float = 0.0
    day_over_day: float = 0.0
    is_candidate_linked: bool = False
    contextual_linkage: float = 0.0   # 정책/지역/동맹 연결 강도
    channels_active: list[str] = field(default_factory=list)

    explanation: str = ""
    primary_driver: str = ""

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "index": round(self.index, 1),
            "grade": self.grade,
            "components": {
                "news_volume": round(self.news_volume, 1),
                "media_tier": round(self.media_tier, 1),
                "spread_velocity": round(self.spread_velocity, 1),
                "candidate_linkage": round(self.candidate_linkage, 1),
                "channel_diversity": round(self.channel_diversity, 1),
            },
            "raw_mentions": self.raw_mentions,
            "deduped_stories": self.deduped_stories,
            "channels_active": self.channels_active,
            "primary_driver": self.primary_driver,
            "explanation": self.explanation,
        }


def _grade(score: float) -> str:
    if score >= 80: return "EXPLOSIVE"
    if score >= 60: return "HOT"
    if score >= 40: return "ACTIVE"
    if score >= 20: return "LOW"
    return "DORMANT"


def compute_issue_index(
    keyword: str,
    # ── Source: naver_news + deduplicator ──
    mention_count: int = 0,
    deduped_stories: int = 0,
    # ── Source: naver_news ──
    media_tier: int = 3,
    tier1_count: int = 0,           # Tier1 기사 수 (방송/메이저)
    source_diversity: int = 0,       # 고유 언론사 수
    tv_reported: bool = False,
    portal_trending: bool = False,
    # ── Source: unified_collector + anomaly_detector ──
    velocity: float = 0.0,          # 6h/18h 비율
    surprise_score: float = 0.0,    # anomaly detector
    day_over_day: float = 0.0,      # 전일 대비 변화율 (%)
    # ── Source: keyword_engine + canonical_mapper + owned_channels ──
    candidate_linked: bool = False,
    candidate_action_linked: bool = False,  # 후보 행동과 연결
    message_theme: str = "",                # 공약/정책 테마
    region: str = "",                       # 지역 연결
    # ── Source: 전 채널 ──
    blog_count: int = 0,
    cafe_count: int = 0,
    video_count: int = 0,
    youtube_count: int = 0,
    trend_interest: int = 0,
    community_mentions: int = 0,
    # ── Source: naver_datalab ──
    naver_interest: float = 0.0,        # 네이버 데이터랩 관심도 (0~100)
    naver_change_7d: float = 0.0,       # 네이버 7일 변화율 (%)
    # ── Source: trends_collector (v2 강화) ──
    trend_change_7d: float = 0.0,       # 구글 7일 변화율 (%)
    trend_direction: str = "",          # "↑급상승" | "↑상승" | "→유지" | "↓하락"
    naver_peak_age: str = "",           # "20s" | "30s" | "40s" | "50+"
    naver_gender_skew: str = "",        # "male" | "female" | "balanced"
) -> IssueIndexResult:

    r = IssueIndexResult(
        keyword=keyword,
        raw_mentions=mention_count,
        deduped_stories=deduped_stories,
        tier1_count=tier1_count,
        source_diversity=source_diversity,
        velocity=velocity,
        surprise_score=surprise_score,
        day_over_day=day_over_day,
        is_candidate_linked=candidate_linked,
    )

    # ═══ 1. NEWS VOLUME (0~25) ═══
    # 중복제거 스토리 기준 (없으면 raw)
    ref = deduped_stories if deduped_stories > 0 else mention_count
    # 로그 스케일: log2(ref+1) * 4, 최대 25
    nv = min(25.0, math.log2(ref + 1) * 4.0)
    # 네이버 데이터랩 검색 관심도 점수 제거 — Google Trends와 중복
    r.news_volume = min(25.0, nv)

    # ═══ 2. MEDIA TIER (0~20) ═══
    mt = 0.0
    if tv_reported:
        mt += 8.0
    if portal_trending:
        mt += 4.0
    # Tier1 비중
    if tier1_count >= 5:
        mt += 5.0
    elif tier1_count >= 2:
        mt += 3.0
    elif tier1_count >= 1:
        mt += 1.0
    # 언론사 다양성
    if source_diversity >= 10:
        mt += 3.0
    elif source_diversity >= 5:
        mt += 2.0
    elif source_diversity >= 3:
        mt += 1.0
    r.media_tier = min(20.0, mt)

    # ═══ 3. SPREAD VELOCITY (0~30) ═══
    sv = 0.0
    # velocity (6h/18h 비율) → 0~12
    if velocity >= 4.0:
        sv += 12.0
    elif velocity >= 2.5:
        sv += 9.0
    elif velocity >= 1.5:
        sv += 6.0
    elif velocity >= 1.0:
        sv += 3.0

    # anomaly surprise → 0~10
    if surprise_score >= 80:
        sv += 10.0
    elif surprise_score >= 60:
        sv += 7.0
    elif surprise_score >= 40:
        sv += 4.0
    elif surprise_score >= 20:
        sv += 2.0

    # day-over-day → 0~8
    if day_over_day >= 200:
        sv += 8.0
    elif day_over_day >= 100:
        sv += 6.0
    elif day_over_day >= 50:
        sv += 4.0
    elif day_over_day >= 20:
        sv += 2.0

    # 네이버 데이터랩 변화율 점수 제거 — Google Trends와 중복

    # 구글 트렌드 변화율 → 연속 점수 (0~4)
    if trend_change_7d >= 200:
        sv += 4.0
    elif trend_change_7d >= 100:
        sv += 3.0
    elif trend_change_7d >= 50:
        sv += 2.0
    elif trend_change_7d >= 20:
        sv += 1.0

    # 구글 급상승 키워드 보너스
    if "급상승" in trend_direction:
        sv += 3.0
    elif "상승" in trend_direction:
        sv += 1.0

    r.spread_velocity = min(30.0, sv)

    # ═══ 4. CANDIDATE LINKAGE (0~15) ═══
    cl = 0.0
    # 직접 언급
    if candidate_linked:
        cl += 8.0
    # 후보 행동 연결 (SNS 게시, 현장 방문 등)
    if candidate_action_linked:
        cl += 3.0
    # 정책/공약 테마 연결
    if message_theme:
        cl += 2.0
    # 지역 연결
    if region:
        cl += 2.0
    # 네이버 DataLab 세그먼트 보너스 — 타겟 세대 관심 급등 시 전략적 연결
    if naver_peak_age in ("20s", "30s", "40s"):
        cl += 1.0  # 우리 핵심 타겟층에서 관심 → 전략적 가치

    r.candidate_linkage = min(15.0, cl)
    r.contextual_linkage = cl - (8.0 if candidate_linked else 0.0)

    # ═══ 5. CHANNEL DIVERSITY (0~10) ═══
    channels = []
    if mention_count > 0:
        channels.append("news")
    if blog_count > 0:
        channels.append("blog")
    if cafe_count > 0:
        channels.append("cafe")
    if video_count > 0 or youtube_count > 0:
        channels.append("video")
    if trend_interest > 15:
        channels.append("google_trend")
    # naver_trend 채널 제거 — google_trend와 중복
    if community_mentions > 0:
        channels.append("community")

    r.channels_active = channels
    ch = len(channels)
    if ch >= 5:
        r.channel_diversity = 10.0
    elif ch >= 4:
        r.channel_diversity = 8.0
    elif ch >= 3:
        r.channel_diversity = 6.0
    elif ch >= 2:
        r.channel_diversity = 3.0
    elif ch >= 1:
        r.channel_diversity = 1.0

    # ═══ 합산 ═══
    r.index = min(100, round(
        r.news_volume + r.media_tier + r.spread_velocity +
        r.candidate_linkage + r.channel_diversity, 1
    ))
    r.grade = _grade(r.index)

    # ═══ 설명 ═══
    components = [
        ("뉴스볼륨", r.news_volume, 25),
        ("미디어티어", r.media_tier, 20),
        ("확산속도", r.spread_velocity, 30),
        ("후보연결", r.candidate_linkage, 15),
        ("채널다양성", r.channel_diversity, 10),
    ]
    top = max(components, key=lambda x: x[1])
    r.primary_driver = top[0]
    r.explanation = (
        f"Issue {r.index:.0f} [{r.grade}] "
        f"주요인:{top[0]}({top[1]:.0f}/{top[2]}) "
        f"스토리:{ref} 채널:{ch}개 속도:{velocity:.1f}x"
    )
    return r
