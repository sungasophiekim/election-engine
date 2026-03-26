"""
Reaction Index — Reaction Layer 전용 지수 (v3)
"사람들이 어떻게 반응하는가"를 프록시 시그널로 측정.
네이버 댓글 직접 접근 없이, 다층 프록시로 반응을 추정.

5-Layer 구조 (100점 만점):
  1. Community Resonance  (25) — community_collector
  2. Content Creation     (20) — social_collector + youtube_collector
  3. Sentiment Direction  (20) — keyword_analyzer + social + news tone
  4. Search Reaction      (15) — trends_collector
  5. YouTube Comment      (20) — youtube_collector (commentThreads)

+ Velocity Bonus (×1.1~1.15)
+ Cross-Signal Confidence (0~1)

원칙:
  - 네이버 댓글 스크래핑 없음 (API 미제공 + 법적 리스크)
  - 유튜브 댓글이 유일한 직접 반응 시그널
  - 나머지는 프록시 (커뮤니티 확산, 콘텐츠 생산, 검색 급등)
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import datetime


# ── Proxy segmentation — segment_mapper 통합 ──────────────────
# 하위 호환을 위해 COMMUNITY_SEGMENT_MAP 유지 (segment_mapper에서 자동 생성)
try:
    from engines.segment_mapper import COMMUNITY_PROXIES
    COMMUNITY_SEGMENT_MAP = {
        cid: {"segment": p.age_group + "_" + p.gender, "age": p.age_group, "label": p.label_ko}
        for cid, p in COMMUNITY_PROXIES.items()
    }
except ImportError:
    COMMUNITY_SEGMENT_MAP = {
        "fmkorea":    {"segment": "20s_M",     "age": "20s", "label": "2030 남성"},
        "dcinside":   {"segment": "20s_M",     "age": "20s", "label": "남성 전연령"},
        "theqoo":     {"segment": "20s_F",     "age": "20s", "label": "2030 여성"},
        "clien":      {"segment": "30s_M",     "age": "30s", "label": "3040 진보"},
        "natepann":   {"segment": "20s_F",     "age": "20s", "label": "전연령 대중"},
    }


@dataclass
class SegmentReaction:
    """프록시 세그먼트별 반응 (하위 호환)"""
    segment: str
    label: str
    source_community: str
    mention_count: int = 0
    sentiment: float = 0.0
    has_viral: bool = False
    intensity: float = 0.0


@dataclass
class ReactionIndexResult:
    keyword: str
    index: float = 0.0              # 0~100 (velocity bonus 적용 전)
    final_score: float = 0.0        # velocity bonus 적용 후
    grade: str = ""                 # VIRAL | ENGAGED | RIPPLE | SILENT
    direction: str = ""             # positive | negative | mixed | neutral

    # 5-Layer breakdown
    community_resonance: float = 0.0   # 0~25
    content_creation: float = 0.0      # 0~20
    sentiment_direction: float = 0.0   # 0~20
    search_reaction: float = 0.0       # 0~15
    youtube_comment: float = 0.0       # 0~20

    # Cross-signal validation
    confidence: float = 0.0            # 0~1 (active layers / 5)
    layers_active: int = 0
    dominant_channel: str = ""

    # Velocity bonus
    velocity_flag: bool = False
    velocity_multiplier: float = 1.0

    # 감성 상세
    net_sentiment: float = 0.0         # -1.0 ~ +1.0
    sentiment_target: str = ""         # ours | theirs | neutral
    dominant_tone: str = ""
    mobilization_signal: bool = False

    # 유튜브 댓글 상세
    yt_comments_total: int = 0
    yt_comment_sentiment: float = 0.0
    yt_top_positive: str = ""
    yt_top_negative: str = ""

    # 세그먼트 (하위 호환)
    segment_reactions: list[SegmentReaction] = field(default_factory=list)
    hottest_segment: str = ""

    # 조직 시그널 (하위 호환, 독립 component에서 secondary로 이동)
    endorsement_count: int = 0
    withdrawal_count: int = 0

    explanation: str = ""
    primary_driver: str = ""

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "index": round(self.index, 1),
            "final_score": round(self.final_score, 1),
            "grade": self.grade,
            "direction": self.direction,
            "components": {
                "community_resonance": round(self.community_resonance, 1),
                "content_creation": round(self.content_creation, 1),
                "sentiment_direction": round(self.sentiment_direction, 1),
                "search_reaction": round(self.search_reaction, 1),
                "youtube_comment": round(self.youtube_comment, 1),
            },
            "confidence": round(self.confidence, 2),
            "layers_active": self.layers_active,
            "dominant_channel": self.dominant_channel,
            "velocity_flag": self.velocity_flag,
            "velocity_multiplier": self.velocity_multiplier,
            "net_sentiment": round(self.net_sentiment, 3),
            "sentiment_target": self.sentiment_target,
            "dominant_tone": self.dominant_tone,
            "mobilization_signal": self.mobilization_signal,
            "yt_comments_total": self.yt_comments_total,
            "yt_comment_sentiment": round(self.yt_comment_sentiment, 3),
            "yt_top_positive": self.yt_top_positive,
            "yt_top_negative": self.yt_top_negative,
            "hottest_segment": self.hottest_segment,
            "endorsement_count": self.endorsement_count,
            "withdrawal_count": self.withdrawal_count,
            "segment_reactions": [
                {"segment": sr.segment, "label": sr.label, "source": sr.source_community,
                 "mentions": sr.mention_count, "sentiment": round(sr.sentiment, 2),
                 "viral": sr.has_viral, "intensity": round(sr.intensity, 2)}
                for sr in self.segment_reactions[:8]
            ],
            "primary_driver": self.primary_driver,
            "explanation": self.explanation,
        }


def _grade(score: float) -> str:
    if score >= 75: return "VIRAL"
    if score >= 50: return "ENGAGED"
    if score >= 25: return "RIPPLE"
    return "SILENT"


def compute_reaction_index(
    keyword: str,
    # ═══ Layer 1: Community Resonance ═══
    # source: community_collector.py
    community_signals: list = None,     # list[CommunitySignal]
    community_resonance: float = 0.0,   # 0~1 (from CommunityReport)
    community_has_viral: bool = False,
    community_derision: float = 0.0,
    community_dominant_tone: str = "",
    # ═══ Layer 2: Content Creation ═══
    # source: social_collector.py + youtube_collector.py
    blog_count: int = 0,
    cafe_count: int = 0,
    video_count: int = 0,
    youtube_count: int = 0,
    youtube_views: int = 0,
    owned_channel_active: bool = False,
    # ═══ Layer 3: Sentiment Direction ═══
    # source: keyword_analyzer + social + naver_news
    negative_ratio: float = 0.0,
    positive_ratio: float = 0.0,
    news_net_sentiment: float = 0.0,
    blog_net_sentiment: float = 0.0,
    cafe_net_sentiment: float = 0.0,
    tone_distribution: dict = None,
    candidate_linked: bool = False,
    candidate_name: str = "",
    opponents: list[str] = None,
    # ═══ Layer 4: Search Reaction ═══
    # source: trends_collector.py + naver_datalab
    trend_interest: int = 0,            # 구글 (0~100)
    trend_change_7d: float = 0.0,       # 구글 % change
    trend_direction: str = "",          # "↑급상승" etc
    naver_interest: float = 0.0,        # 네이버 (0~100)
    naver_change_7d: float = 0.0,       # 네이버 7일 변화율
    naver_gender_skew: str = "",        # "male" | "female" | "balanced"
    naver_peak_age: str = "",           # "20s" | "30s" | "40s" | "50+"
    # ═══ Layer 5: YouTube Comment + Engagement ═══
    # source: youtube_collector.py (commentThreads + video stats)
    youtube_comments: int = 0,
    yt_comment_net_sentiment: float = 0.0,
    yt_comment_positive_ratio: float = 0.0,
    yt_comment_negative_ratio: float = 0.0,
    yt_comment_mobilization: bool = False,
    yt_top_positive: str = "",
    yt_top_negative: str = "",
    yt_total_likes: int = 0,           # 영상 좋아요 합계 (이미 수집됨)
    yt_total_views: int = 0,           # 영상 조회수 합계
    # ═══ Layer 6 (보조): News Comment Signal ═══
    # source: news_comment_collector.py
    news_comment_count: int = 0,       # 뉴스 댓글 총 수
    news_comment_sentiment: float = 0.0,  # 댓글 감성 (-1~+1)
    news_comment_like_ratio: float = 0.0, # 공감 비율 (0~1)
    news_comment_mobilization: bool = False,  # 동원 키워드 감지
    # ═══ Velocity / Anomaly ═══
    # source: anomaly_detector.py
    surprise_score: float = 0.0,
    day_over_day: float = 0.0,
    is_anomaly: bool = False,
    # ═══ Secondary signals (하위 호환) ═══
    endorsement_count: int = 0,
    withdrawal_count: int = 0,
    org_net_sentiment: float = 0.0,
    org_high_influence: int = 0,
    region: str = "",
    change_pct: float = 0.0,
    **kwargs,  # 하위 호환
) -> ReactionIndexResult:

    community_signals = community_signals or []
    opponents = opponents or []
    tone_distribution = tone_distribution or {}

    r = ReactionIndexResult(
        keyword=keyword,
        endorsement_count=endorsement_count,
        withdrawal_count=withdrawal_count,
        dominant_tone=community_dominant_tone,
        yt_comments_total=youtube_comments,
        yt_comment_sentiment=yt_comment_net_sentiment,
        yt_top_positive=yt_top_positive,
        yt_top_negative=yt_top_negative,
    )

    # ═══════════════════════════════════════════════════════════════
    # LAYER 1: COMMUNITY RESONANCE (0~25)
    # "이슈가 토론 주제가 되었는가?"
    # ═══════════════════════════════════════════════════════════════
    L1 = 0.0
    active_communities = [s for s in community_signals if s.result_count > 0]
    r_communities = len(active_communities)

    # 공명도 (0~1) → 0~10
    L1 += community_resonance * 10

    # 바이럴 감지 (인기글/추천글 패턴)
    if community_has_viral:
        L1 += 4.0

    # 동시 확산 (몇 개 커뮤니티에 동시에)
    if r_communities >= 7:
        L1 += 5.0
    elif r_communities >= 5:
        L1 += 4.0
    elif r_communities >= 3:
        L1 += 3.0
    elif r_communities >= 1:
        L1 += 1.0

    # 반복 빈도 (같은 커뮤니티에 여러 글 = 지속적 관심)
    repeat = sum(1 for s in active_communities if s.result_count >= 5)
    if repeat >= 4:
        L1 += 4.0
    elif repeat >= 2:
        L1 += 2.0

    # 조롱/풍자 시그널 (강한 반응 증거)
    if community_derision > 0.3:
        L1 += 2.0

    r.community_resonance = min(25.0, L1)

    # 세그먼트 프록시 매핑 (secondary)
    for cs in active_communities:
        seg_info = COMMUNITY_SEGMENT_MAP.get(cs.community_id, {})
        if seg_info:
            r.segment_reactions.append(SegmentReaction(
                segment=seg_info.get("segment", "unknown"),
                label=seg_info.get("label", cs.name),
                source_community=cs.community_id,
                mention_count=cs.result_count,
                sentiment=cs.positive_ratio - cs.negative_ratio if hasattr(cs, 'positive_ratio') else 0,
                has_viral=getattr(cs, 'has_viral_signals', False),
                intensity=min(1.0, cs.result_count / 20.0),
            ))
    if r.segment_reactions:
        hottest = max(r.segment_reactions, key=lambda x: x.intensity)
        r.hottest_segment = hottest.label

    # ═══════════════════════════════════════════════════════════════
    # LAYER 2: CONTENT CREATION DEPTH (0~20)
    # "사람들이 콘텐츠를 만들기 시작했는가?"
    # ═══════════════════════════════════════════════════════════════
    L2 = 0.0

    # 블로그 장문 (깊은 참여 — 글 쓰는데 시간 투자)
    if blog_count >= 50:
        L2 += 7.0
    elif blog_count >= 20:
        L2 += 5.0
    elif blog_count >= 5:
        L2 += 3.0
    elif blog_count >= 1:
        L2 += 1.0

    # 카페 토론 (커뮤니티 토론 = 관심)
    if cafe_count >= 50:
        L2 += 6.0
    elif cafe_count >= 20:
        L2 += 4.0
    elif cafe_count >= 5:
        L2 += 2.0
    elif cafe_count >= 1:
        L2 += 1.0

    # 유튜브 영상 (UGC 제작 = 매우 깊은 관여)
    yt = youtube_count or video_count
    if yt >= 10:
        L2 += 5.0
    elif yt >= 5:
        L2 += 3.0
    elif yt >= 1:
        L2 += 1.0

    # 자체 채널 활동
    if owned_channel_active:
        L2 += 2.0

    r.content_creation = min(20.0, L2)

    # ═══════════════════════════════════════════════════════════════
    # LAYER 3: SENTIMENT DIRECTION (0~20)
    # "반응이 긍정인가 부정인가, 누구를 향하는가?"
    # ═══════════════════════════════════════════════════════════════
    L3 = 0.0

    # 채널별 가중 감성 종합
    sentiments = []
    weights = []
    if news_net_sentiment != 0:
        sentiments.append(news_net_sentiment)
        weights.append(0.35)
    if blog_net_sentiment != 0:
        sentiments.append(blog_net_sentiment)
        weights.append(0.25)
    if cafe_net_sentiment != 0:
        sentiments.append(cafe_net_sentiment)
        weights.append(0.20)
    if yt_comment_net_sentiment != 0:
        sentiments.append(yt_comment_net_sentiment)
        weights.append(0.15)
    if news_comment_sentiment != 0:
        sentiments.append(news_comment_sentiment)
        weights.append(0.25)  # 뉴스 댓글 = 가장 대중적 반응

    if sentiments:
        total_w = sum(weights)
        net_sent = sum(s * w for s, w in zip(sentiments, weights)) / total_w
    else:
        net_sent = positive_ratio - negative_ratio

    r.net_sentiment = net_sent

    # 감성 명확도 → 점수 (명확할수록 높음)
    L3 += abs(net_sent) * 12  # 0~12

    # 누구를 향하는가
    is_opp = any(opp in keyword for opp in opponents)
    if is_opp and net_sent < -0.2:
        L3 += 4.0  # 상대 타격
        r.sentiment_target = "theirs"
        r.direction = "positive"
    elif candidate_linked and net_sent < -0.2:
        r.sentiment_target = "ours"
        r.direction = "negative"
    elif net_sent > 0.2:
        r.sentiment_target = "ours" if candidate_linked else "neutral"
        r.direction = "positive"
    elif net_sent < -0.2:
        r.direction = "negative"
        r.sentiment_target = "neutral"
    else:
        r.direction = "mixed" if abs(net_sent) > 0.05 else "neutral"
        r.sentiment_target = "neutral"

    # 톤 분석 (조롱/분노/지지)
    if tone_distribution:
        anger = sum(tone_distribution.get(k, 0) for k in ["분노", "비판", "공분"])
        support = sum(tone_distribution.get(k, 0) for k in ["지지", "기대", "신뢰"])
        if anger > support and anger > 3:
            L3 += 2.0
            r.dominant_tone = r.dominant_tone or "분노"
        elif support > anger and support > 3:
            L3 += 1.0
            r.dominant_tone = r.dominant_tone or "지지"

    if community_derision > 0.3:
        L3 += 2.0
        r.dominant_tone = r.dominant_tone or "조롱"

    r.sentiment_direction = min(20.0, L3)

    # ═══════════════════════════════════════════════════════════════
    # LAYER 4: SEARCH REACTION (0~15)
    # "일반 대중이 관심을 갖기 시작했는가?"
    # ═══════════════════════════════════════════════════════════════
    L4 = 0.0

    # 현재 관심도 (0~100) → 0~6
    if trend_interest >= 80:
        L4 += 6.0
    elif trend_interest >= 50:
        L4 += 4.0
    elif trend_interest >= 30:
        L4 += 2.0
    elif trend_interest >= 10:
        L4 += 1.0

    # 7일 변화율 → 0~6 (급등 감지)
    if trend_change_7d >= 200:
        L4 += 6.0
    elif trend_change_7d >= 100:
        L4 += 4.0
    elif trend_change_7d >= 50:
        L4 += 3.0
    elif trend_change_7d >= 20:
        L4 += 1.0

    # 검색 속도 (급상승 키워드)
    if "급상승" in trend_direction:
        L4 += 3.0
    elif "상승" in trend_direction:
        L4 += 1.0

    # 네이버 데이터랩 검색 관심도 점수 제거 — Google Trends와 중복
    # 데이터랩은 인구통계(성별/연령)만 활용 (segment_mapper에서 사용)

    r.search_reaction = min(15.0, L4)

    # ═══════════════════════════════════════════════════════════════
    # LAYER 5: YOUTUBE ENGAGEMENT + COMMENT (0~20)
    # "직접 반응 시그널 — 댓글 + 좋아요 + 조회수"
    # ═══════════════════════════════════════════════════════════════
    L5 = 0.0

    # 댓글 수 → 0~6 (축소: 좋아요/조회수 공간 확보)
    if youtube_comments >= 200:
        L5 += 6.0
    elif youtube_comments >= 100:
        L5 += 5.0
    elif youtube_comments >= 50:
        L5 += 3.5
    elif youtube_comments >= 20:
        L5 += 2.0
    elif youtube_comments >= 5:
        L5 += 1.0

    # 좋아요 합계 → 0~4 (확산 지표 — 이미 수집되는 데이터)
    if yt_total_likes >= 5000:
        L5 += 4.0
    elif yt_total_likes >= 1000:
        L5 += 3.0
    elif yt_total_likes >= 200:
        L5 += 2.0
    elif yt_total_likes >= 50:
        L5 += 1.0

    # 조회수 → 0~2 (관심 스케일)
    if yt_total_views >= 100000:
        L5 += 2.0
    elif yt_total_views >= 10000:
        L5 += 1.0

    # 댓글 감성 명확도 → 0~4
    if yt_comment_net_sentiment != 0:
        L5 += min(4.0, abs(yt_comment_net_sentiment) * 5)

    # 댓글 극성 (부정 비율 높음 = 강한 반응)
    if yt_comment_negative_ratio >= 0.4:
        L5 += 2.0
    elif yt_comment_positive_ratio >= 0.4:
        L5 += 1.0

    # 동원 키워드 감지 ("투표", "심판" 등)
    if yt_comment_mobilization:
        L5 += 2.0
        r.mobilization_signal = True
    if news_comment_mobilization:
        L5 += 1.0
        r.mobilization_signal = True

    # 뉴스 댓글 보조 점수 (0~3) — 대중 반응 스케일
    if news_comment_count >= 500:
        L5 += 3.0
    elif news_comment_count >= 200:
        L5 += 2.0
    elif news_comment_count >= 50:
        L5 += 1.0

    r.youtube_comment = min(20.0, L5)

    # ═══════════════════════════════════════════════════════════════
    # TOTAL SCORE
    # ═══════════════════════════════════════════════════════════════
    r.index = min(100, round(L1 + L2 + L3 + L4 + L5, 1))

    # ═══════════════════════════════════════════════════════════════
    # VELOCITY BONUS (anomaly_detector 재사용)
    # ═══════════════════════════════════════════════════════════════
    multiplier = 1.0
    if is_anomaly and surprise_score >= 80:
        multiplier = 1.15
        r.velocity_flag = True
    elif is_anomaly or surprise_score >= 60:
        multiplier = 1.1
        r.velocity_flag = True
    elif day_over_day >= 100 or change_pct >= 100:
        multiplier = 1.1
        r.velocity_flag = True

    r.velocity_multiplier = multiplier
    r.final_score = min(100, round(r.index * multiplier, 1))
    r.grade = _grade(r.final_score)

    # ═══════════════════════════════════════════════════════════════
    # CROSS-SIGNAL CONFIDENCE
    # ═══════════════════════════════════════════════════════════════
    active = 0
    if L1 > 3: active += 1   # community
    if L2 > 3: active += 1   # content
    if L3 > 3: active += 1   # sentiment
    if L4 > 2: active += 1   # search
    if L5 > 2: active += 1   # youtube + news comment
    if news_comment_count >= 20: active += 1  # news comment (보조)

    r.layers_active = active
    r.confidence = round(min(1.0, active / 5.0), 2)  # 6개 중 5개면 1.0

    # Dominant channel
    layers = [
        ("community", L1), ("content", L2), ("sentiment", L3),
        ("search", L4), ("youtube", L5),
    ]
    top = max(layers, key=lambda x: x[1])
    r.dominant_channel = top[0]
    r.primary_driver = top[0]

    # ═══════════════════════════════════════════════════════════════
    # EXPLANATION
    # ═══════════════════════════════════════════════════════════════
    dir_ko = {"positive": "긍정", "negative": "부정", "mixed": "혼재", "neutral": "중립"}
    vel_str = f" ×{multiplier}" if r.velocity_flag else ""

    r.explanation = (
        f"Rx {r.final_score:.0f} [{r.grade}] "
        f"방향:{dir_ko.get(r.direction, '?')} "
        f"신뢰:{r.confidence:.0%} ({active}/5 layer){vel_str} "
        f"주요:{top[0]}({top[1]:.0f})"
    )
    return r


# ── Strategic interpretation ──────────────────────────────────

def interpret_reaction(issue_index: float, reaction_result: ReactionIndexResult) -> dict:
    """
    Issue Index + Reaction Index → 전략 해석.

    High Reaction + Positive → Push (밀기)
    High Reaction + Negative → Counter (반박)
    High Issue + Low Reaction → Avoid or Monitor
    """
    rx = reaction_result.final_score
    direction = reaction_result.direction

    if rx >= 50 and direction == "positive":
        stance = "push"
        action = "적극 확산 — 유리한 반응 활용"
    elif rx >= 50 and direction == "negative":
        stance = "counter"
        action = "즉시 반박 — 부정 반응 차단 필요"
    elif issue_index >= 50 and rx < 25:
        stance = "monitor"
        action = "이슈는 크지만 반응 미미 — 관망"
    elif issue_index >= 50 and rx >= 25:
        stance = "pivot"
        action = "이슈 전환 시도 — 반응을 유리한 방향으로"
    else:
        stance = "monitor"
        action = "이슈+반응 모두 낮음 — 모니터링"

    return {
        "recommended_stance": stance,
        "action": action,
        "issue_index": round(issue_index, 1),
        "reaction_score": round(rx, 1),
        "direction": direction,
        "confidence": reaction_result.confidence,
    }


# ── Future hooks (하위 호환) ──────────────────────────────────

def compute_from_comments(news_comments: list[dict], keyword: str = "") -> dict:
    """HOOK: 뉴스 댓글 반응 분석 (미구현 — API 미제공)"""
    return {"keyword": keyword, "comment_sentiment": 0.0, "comment_volume": 0}

def compute_from_youtube_comments(yt_comments: list[dict], keyword: str = "") -> dict:
    """HOOK: 유튜브 댓글 반응 분석 (미구현)"""
    return {"keyword": keyword, "yt_comment_sentiment": 0.0, "yt_comment_volume": 0}

def compute_from_sns_comments(sns_data: list[dict], keyword: str = "") -> dict:
    """HOOK: SNS 댓글/리트윗 분석 (미구현)"""
    return {"keyword": keyword, "sns_reaction_score": 0.0}

def compute_from_action_log(actions: list[dict], keyword: str = "") -> dict:
    """HOOK: 후보 행동 로그 기반 반응 분석 (미구현)"""
    return {"keyword": keyword, "action_triggered_reaction": False}
