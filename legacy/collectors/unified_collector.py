"""
Election Strategy Engine — 통합 수집기
뉴스 + 블로그 + 카페 + 유튜브 + Google Trends를 한번에 수집하여
이슈별 종합 시그널을 생성합니다.

v2: 병렬 수집 + 캐싱으로 속도 개선
v2.1: reaction intelligence — 반응 볼륨, 커뮤니티 공명도, 자체 채널 활동
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from models.schemas import IssueSignal
from collectors.naver_news import (
    collect_issue_signals as _collect_news,
    analyze_sentiment,
    get_last_collection_meta,
)
from collectors.social_collector import (
    search_blogs,
    search_cafes,
    search_videos,
    SocialSignal,
)
from collectors.youtube_collector import search_youtube
from collectors.trends_collector import get_search_trend

# ── 캐싱 (5분) ──────────────────────────────────────────────
_cache = {}
_CACHE_TTL = 300  # 5분

def _cached(key, fn):
    """5분 캐싱 래퍼"""
    now = time.time()
    if key in _cache and now - _cache[key][1] < _CACHE_TTL:
        return _cache[key][0]
    try:
        result = fn()
        _cache[key] = (result, now)
        return result
    except Exception:
        return _cache[key][0] if key in _cache else None


@dataclass
class ReactionSummary:
    """
    v2: 반응 깊이 종합 — 단순 언급량을 넘어선 반응 인텔리전스.
    UnifiedSignal의 nested dataclass.
    """
    # 뉴스 반응 깊이
    news_tier1_count: int = 0         # 방송/메이저 기사 수
    news_source_diversity: int = 0    # 고유 언론사 수
    news_temporal_cluster: float = 0.0  # 최근 6h 기사 비중
    news_headline_neg_ratio: float = 0.0  # 제목 전용 부정 비율
    news_defense_active: bool = False    # 반박/해명 기사 존재
    news_net_sentiment: float = 0.0      # -1.0~1.0

    # 커뮤니티 공명도
    community_resonance: float = 0.0  # 0~1, 몇 개 커뮤니티에 퍼졌는지
    community_has_viral: bool = False # 인기글/추천글 패턴 감지
    community_derision: float = 0.0   # 조롱 톤 비율
    community_dominant_tone: str = "" # "조롱", "분노", "지지", "무관심"

    # 소셜 테마
    blog_themes: list = field(default_factory=list)    # 블로그 메시지 테마 top3
    cafe_themes: list = field(default_factory=list)    # 카페 메시지 테마 top3
    blog_net_sentiment: float = 0.0
    cafe_net_sentiment: float = 0.0

    # 자체 채널 활동 (있을 경우)
    owned_channel_active: bool = False
    owned_avg_engagement: float = 0.0
    owned_themes: list = field(default_factory=list)

    # 조직 시그널 (있을 경우)
    endorsement_count: int = 0       # 지지선언 기사 수
    withdrawal_count: int = 0        # 지지 철회 기사 수

    # 종합 반응 등급
    reaction_grade: str = ""         # "HOT" | "WARM" | "COOL" | "COLD"


@dataclass
class UnifiedSignal:
    """뉴스 + 소셜 통합 시그널"""
    keyword: str

    # 뉴스
    news_mentions: int = 0
    news_negative: float = 0.0
    news_velocity: float = 0.0
    news_tv_reported: bool = False
    news_portal_trending: bool = False

    # 블로그
    blog_total: int = 0
    blog_recent: int = 0
    blog_negative: float = 0.0
    blog_positive: float = 0.0

    # 카페 (커뮤니티)
    cafe_total: int = 0
    cafe_recent: int = 0
    cafe_negative: float = 0.0
    cafe_positive: float = 0.0

    # 동영상 (네이버)
    video_total: int = 0
    video_recent: int = 0
    video_negative: float = 0.0
    video_positive: float = 0.0

    # 유튜브 (YouTube Data API)
    yt_total: int = 0
    yt_recent_7d: int = 0
    yt_total_views: int = 0
    yt_avg_views: int = 0
    yt_top_videos: list = field(default_factory=list)

    # Google Trends
    trend_interest: int = 0         # 현재 관심도 (0~100)
    trend_change_7d: float = 0.0    # 7일 변화율 (%)
    trend_direction: str = ""       # ↑급상승/↑상승/→유지/↓하락
    trend_related: list = field(default_factory=list)  # 연관 검색어

    # 종합
    total_mentions: int = 0
    combined_negative: float = 0.0
    combined_positive: float = 0.0
    candidate_linked: bool = False
    media_tier: int = 3

    # 원본 시그널 (이슈 스코어링에 전달용)
    issue_signal: IssueSignal = None

    # 24시간 변화량 (이전 수집 대비)
    prev_total: int = 0             # 이전 수집 시 총 언급량
    change_count: int = 0           # 변화량 (현재 - 이전)
    change_pct: float = 0.0         # 등락률 (%)

    # 채널별 상위 항목
    top_articles: list = field(default_factory=list)
    top_blogs: list = field(default_factory=list)
    top_cafe_posts: list = field(default_factory=list)

    # v2: 반응 종합 (nested)
    reaction: ReactionSummary = field(default_factory=ReactionSummary)

    # v3: attribution hints (행동-반응 연결 힌트)
    attribution_hints: list = field(default_factory=list)  # [{"action": str, "confidence": float, "region": str}]

    # v4: 분리 지수
    issue_index: float = 0.0           # Trigger Layer 지수 (0~100)
    issue_index_grade: str = ""        # EXPLOSIVE | HOT | ACTIVE | LOW | DORMANT
    reaction_index: float = 0.0        # Reaction Layer 지수 (0~100)
    reaction_index_grade: str = ""     # VIRAL | ENGAGED | RIPPLE | SILENT
    reaction_direction: str = ""       # positive | negative | mixed | neutral

    # v5: 조직 시그널
    org_endorsement_count: int = 0
    org_withdrawal_count: int = 0
    org_net_sentiment: float = 0.0     # -1 ~ +1
    org_total_influence: float = 0.0
    org_unique_count: int = 0
    org_signals: list = field(default_factory=list)  # [OrgSignal.to_dict()]


def collect_unified_signals(
    keywords: list[str],
    candidate_name: str = "",
    opponents: list[str] = None,
    include_social: bool = True,
    include_youtube: bool = True,
    include_trends: bool = True,
    include_community: bool = False,   # v2: 커뮤니티 심층 수집
    include_owned: bool = False,       # v2: 자체 채널 수집
) -> list[UnifiedSignal]:
    """
    뉴스 + 소셜 + 유튜브 + Google Trends 통합 수집.

    v2: include_community=True → 커뮤니티 공명도 분석
        include_owned=True → 자체 채널 활동 분석

    Parameters:
        keywords: 검색 키워드 리스트
        candidate_name: 우리 후보 이름
        opponents: 상대 후보 이름 리스트
        include_social: 소셜 수집 포함 여부 (False면 뉴스만)

    Returns:
        키워드별 UnifiedSignal 리스트
    """
    opponents = opponents or []

    # 1. 뉴스 수집 (캐싱)
    cache_key = f"news:{','.join(sorted(keywords))}"
    news_signals = _cached(cache_key, lambda: _collect_news(
        keywords,
        candidate_name=candidate_name,
        opponents=opponents,
    ))
    news_signals = news_signals or []
    news_map = {s.keyword: s for s in news_signals}

    # v2: 뉴스 메타데이터 (impact_hints 등)
    news_meta = get_last_collection_meta()

    # v2: 커뮤니티 수집 (선택적, 캐싱)
    community_reports = {}
    if include_community:
        from collectors.community_collector import scan_all_communities
        for kw in keywords:
            cr = _cached(f"comm:{kw}", lambda _kw=kw: scan_all_communities(_kw))
            if cr:
                community_reports[kw] = cr

    # v2: 자체 채널 수집 (한 번만, 키워드 무관)
    owned_metrics = []
    if include_owned:
        from collectors.owned_channels import monitor_all_channels
        owned_metrics = _cached("owned:all", monitor_all_channels) or []

    # ── 키워드별 병렬 수집 ─────────────────────────────────────
    def _collect_one(kw):
        """키워드 1개에 대해 모든 채널 수집 (병렬 실행 단위)"""
        ns = news_map.get(kw)
        u = UnifiedSignal(keyword=kw)

        # 뉴스 데이터
        if ns:
            u.news_mentions = ns.mention_count
            u.news_negative = ns.negative_ratio
            u.news_velocity = ns.velocity
            u.news_tv_reported = ns.tv_reported
            u.news_portal_trending = ns.portal_trending
            u.candidate_linked = ns.candidate_linked
            u.media_tier = ns.media_tier

        # 소셜 데이터 (블로그 + 카페)
        if include_social:
            blog = _cached(f"blog:{kw}", lambda _kw=kw: search_blogs(_kw))
            if blog:
                u.blog_total = blog.total_count
                u.blog_recent = blog.recent_24h
                u.blog_negative = blog.negative_ratio
                u.blog_positive = blog.positive_ratio
                u.top_blogs = blog.top_items[:3]

            cafe = _cached(f"cafe:{kw}", lambda _kw=kw: search_cafes(_kw))
            if cafe:
                u.cafe_total = cafe.total_count
                u.cafe_recent = cafe.recent_24h
                u.cafe_negative = cafe.negative_ratio
                u.cafe_positive = cafe.positive_ratio
                u.top_cafe_posts = cafe.top_items[:3]

        # 유튜브 (선택적)
        if include_youtube:
            yt = _cached(f"yt:{kw}", lambda _kw=kw: search_youtube(_kw, max_results=5))
            if yt:
                u.yt_total = yt.total_results
                u.yt_recent_7d = yt.recent_count
                u.yt_total_views = yt.total_views
                u.yt_avg_views = yt.avg_views
                u.yt_top_videos = [
                    {"title": v.title, "channel": v.channel, "views": v.view_count,
                     "published": v.published}
                    for v in yt.top_videos[:5]
                ]

        # Google Trends (선택적)
        if include_trends:
            tr = _cached(f"tr:{kw}", lambda _kw=kw: get_search_trend(_kw))
            if tr:
                u.trend_interest = tr.interest_now
                u.trend_change_7d = tr.change_7d
                u.trend_direction = tr.trend_direction
                u.trend_related = tr.related_queries[:5]

        return u

    # 병렬 실행 (최대 3 스레드 — 네이버 API rate limit 방지)
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_collect_one, kw): kw for kw in keywords}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception:
                pass

    # 원래 키워드 순서 유지
    kw_order = {kw: i for i, kw in enumerate(keywords)}
    results.sort(key=lambda u: kw_order.get(u.keyword, 999))

    # ── 종합 계산 ─────────────────────────────────────────────
    for u in results:
        # 종합 계산
        channels = []
        if u.news_mentions > 0:
            channels.append(("news", u.news_mentions, u.news_negative))
        if u.blog_total > 0:
            channels.append(("blog", u.blog_recent or u.blog_total, u.blog_negative))
        if u.cafe_total > 0:
            channels.append(("cafe", u.cafe_recent or u.cafe_total, u.cafe_negative))
        if u.yt_total > 0:
            channels.append(("youtube", u.yt_recent_7d or u.yt_total, 0.0))
        if u.video_total > 0:
            channels.append(("video", u.video_recent or u.video_total, u.video_negative))

        u.total_mentions = sum(c[1] for c in channels)

        if channels:
            total_weight = sum(c[1] for c in channels)
            if total_weight > 0:
                u.combined_negative = sum(c[1] * c[2] for c in channels) / total_weight
            # 긍정도 계산
            pos_channels = [
                (u.blog_recent or u.blog_total, u.blog_positive),
                (u.cafe_recent or u.cafe_total, u.cafe_positive),
                (u.video_recent or u.video_total, u.video_positive),
            ]
            pos_weight = sum(c[0] for c in pos_channels)
            if pos_weight > 0:
                u.combined_positive = sum(c[0] * c[1] for c in pos_channels) / pos_weight

        # IssueSignal 생성 (기존 엔진과 호환 + v3 reaction fields)
        ns = news_map.get(u.keyword)
        social_boost = min(u.blog_recent + u.cafe_recent, 50)
        boosted_mentions = (ns.mention_count if ns else 0) + social_boost
        final_negative = u.combined_negative if channels else (ns.negative_ratio if ns else 0)
        social_trending = (u.blog_recent + u.cafe_recent) >= 30

        # v3: reaction_volume = 뉴스 외 전체 반응
        non_news_volume = (u.blog_recent + u.cafe_recent
                          + (u.video_recent or 0) + (u.yt_recent_7d or 0))

        # v3: reaction_velocity = 소셜 변화 속도 추정
        # blog_recent + cafe_recent을 total 대비 비율로 가속도 추정
        non_news_total = (u.blog_total + u.cafe_total
                         + (u.video_total or 0) + (u.yt_total or 0))
        rxn_velocity = 1.0
        if non_news_total > 0 and non_news_volume > 0:
            rxn_velocity = round(non_news_volume / max(non_news_total / 10.0, 1.0), 2)

        # v3: engagement_score = 채널 가중 참여도 종합
        eng_components = []
        blog_sig = _cached(f"blog:{u.keyword}", lambda: None)
        cafe_sig = _cached(f"cafe:{u.keyword}", lambda: None)
        if blog_sig and hasattr(blog_sig, 'engagement_score'):
            eng_components.append(blog_sig.engagement_score)
        if cafe_sig and hasattr(cafe_sig, 'engagement_score'):
            eng_components.append(cafe_sig.engagement_score)
        if u.yt_total_views > 0:
            # 유튜브 참여 추정: 조회수 기반 (10만 조회 = 1.0)
            eng_components.append(min(1.0, u.yt_total_views / 100000.0))
        combined_engagement = round(
            sum(eng_components) / max(len(eng_components), 1), 3
        ) if eng_components else 0.0

        # v3: message_theme 결정 (블로그+카페 테마 중 최빈)
        all_themes = []
        if blog_sig and hasattr(blog_sig, 'theme_tags'):
            all_themes.extend(blog_sig.theme_tags)
        if cafe_sig and hasattr(cafe_sig, 'theme_tags'):
            all_themes.extend(cafe_sig.theme_tags)
        theme_counts = {}
        for t in all_themes:
            theme_counts[t] = theme_counts.get(t, 0) + 1
        top_theme = max(theme_counts, key=theme_counts.get) if theme_counts else ""

        # v3: segment_hint (커뮤니티 기반 추정)
        seg_hint = ""
        cr = community_reports.get(u.keyword) if include_community else None
        if cr and cr.signals:
            # 가장 활발한 커뮤니티의 demographic으로 segment 힌트
            hottest = max(cr.signals, key=lambda s: s.result_count)
            from collectors.community_collector import COMMUNITIES
            comm_info = COMMUNITIES.get(hottest.community_id, {})
            seg_hint = comm_info.get("demographic", "")

        # v3: endorsement_signal 요약
        endorse_sig = ""
        rxn = u.reaction  # ReactionSummary (아래에서 채울 것)
        # rxn은 아래 v2 블록에서 채워지므로 여기서는 미리 참조 불가
        # → endorsement는 ReactionSummary 채운 후 아래에서 별도 설정

        u.issue_signal = IssueSignal(
            keyword=u.keyword,
            mention_count=boosted_mentions,
            velocity=ns.velocity if ns else (u.total_mentions / 10.0),
            negative_ratio=final_negative,
            media_tier=ns.media_tier if ns else 3,
            candidate_linked=u.candidate_linked,
            portal_trending=(ns.portal_trending if ns else False) or social_trending,
            tv_reported=ns.tv_reported if ns else False,
            # v3 fields
            reaction_volume=non_news_volume,
            reaction_velocity=rxn_velocity,
            engagement_score=combined_engagement,
            message_theme=top_theme,
            segment_hint=seg_hint,
        )

        # ── v2: ReactionSummary 생성 ─────────────────────────
        rxn = u.reaction

        # 뉴스 반응 깊이 (impact_hints에서)
        meta = news_meta.get(u.keyword, {})
        hints = meta.get("impact_hints", {})
        if hints:
            rxn.news_tier1_count = hints.get("tier1_count", 0)
            rxn.news_source_diversity = hints.get("source_diversity", 0)
            rxn.news_temporal_cluster = hints.get("temporal_cluster", 0.0)
            rxn.news_headline_neg_ratio = hints.get("headline_neg_ratio", 0.0)
            rxn.news_defense_active = hints.get("defense_active", False)
            rxn.news_net_sentiment = hints.get("net_sentiment", 0.0)

        # 커뮤니티 공명도
        cr = community_reports.get(u.keyword)
        if cr:
            rxn.community_resonance = cr.community_resonance
            rxn.community_has_viral = cr.has_any_viral
            rxn.community_dominant_tone = cr.dominant_tone
            # 평균 조롱 점수
            if cr.signals:
                rxn.community_derision = round(
                    sum(s.derision_score for s in cr.signals) / len(cr.signals), 3
                )

        # 소셜 테마 (blog/cafe SocialSignal의 theme_tags)
        blog_sig = _cached(f"blog:{u.keyword}", lambda: None)
        cafe_sig = _cached(f"cafe:{u.keyword}", lambda: None)
        if blog_sig and hasattr(blog_sig, 'theme_tags'):
            rxn.blog_themes = blog_sig.theme_tags
            rxn.blog_net_sentiment = blog_sig.net_sentiment
        if cafe_sig and hasattr(cafe_sig, 'theme_tags'):
            rxn.cafe_themes = cafe_sig.theme_tags
            rxn.cafe_net_sentiment = cafe_sig.net_sentiment

        # 자체 채널 활동
        if owned_metrics:
            total_eng = sum(m.recent_engagement for m in owned_metrics if m.recent_engagement > 0)
            rxn.owned_channel_active = total_eng > 0
            avg_eng_list = [m.avg_engagement_per_post for m in owned_metrics if m.avg_engagement_per_post > 0]
            rxn.owned_avg_engagement = round(sum(avg_eng_list) / len(avg_eng_list), 1) if avg_eng_list else 0.0
            all_themes = []
            for m in owned_metrics:
                all_themes.extend(m.message_themes)
            rxn.owned_themes = list(set(all_themes))[:5]

        # v3: attribution hints — 자체 채널 게시물과 이슈 키워드 매칭
        if owned_metrics:
            for m in owned_metrics:
                for content in (m.top_content or []):
                    title = content.get("title", "")
                    if not title or not u.keyword:
                        continue
                    # 키워드 매칭: 정확 일치 또는 키워드 내 단어가 제목에 포함
                    matched = u.keyword in title
                    if not matched:
                        kw_words = [w for w in u.keyword.split() if len(w) >= 2]
                        matched = any(w in title for w in kw_words)
                    if matched:
                        # 지역 추출
                        hint_region = ""
                        _RN_LIST = [
                            "창원", "김해", "진주", "거제", "통영", "양산",
                            "밀양", "사천", "함안", "거창",
                        ]
                        for rn in _RN_LIST:
                            if rn in title:
                                hint_region = rn
                                break
                        u.attribution_hints.append({
                            "action": title[:50],
                            "channel": m.channel,
                            "confidence": 0.7 if u.keyword in title else 0.4,
                            "region": hint_region,
                            "engagement": content.get("views", 0) or content.get("engagement", 0),
                            "themes": list(m.message_themes) if hasattr(m, 'message_themes') else [],
                        })

        # 종합 반응 등급 산정
        rxn.reaction_grade = _grade_reaction(u, rxn)

        # v3: endorsement_signal 후처리 (ReactionSummary 채운 후)
        if rxn.endorsement_count > 0 or rxn.withdrawal_count > 0:
            parts = []
            if rxn.endorsement_count > 0:
                parts.append(f"endorse:{rxn.endorsement_count}")
            if rxn.withdrawal_count > 0:
                parts.append(f"withdraw:{rxn.withdrawal_count}")
            u.issue_signal.endorsement_signal = "|".join(parts)

        # v3: region 후처리 — 커뮤니티/뉴스 데이터에서 지역 힌트 추출
        if not u.issue_signal.region and u.keyword:
            # 키워드 자체에 지역명이 포함된 경우
            _REGION_KEYWORDS = [
                "창원", "김해", "진주", "거제", "통영", "양산", "밀양",
                "사천", "함안", "거창", "합천", "하동", "남해", "산청",
                "함양", "의령", "고성", "창녕",
            ]
            for rn in _REGION_KEYWORDS:
                if rn in u.keyword:
                    u.issue_signal.region = rn
                    break

    return results


def _grade_reaction(u: UnifiedSignal, rxn: ReactionSummary) -> str:
    """
    v2: 종합 반응 등급 산정.
    HOT: 뉴스 TV보도 + 커뮤니티 바이럴 + 소셜 고참여
    WARM: 뉴스 다수 + 커뮤니티 공명
    COOL: 뉴스만 존재, 소셜 반응 미약
    COLD: 전체적으로 활동 미미
    """
    score = 0

    # 뉴스 활성도
    if u.news_tv_reported:
        score += 3
    if u.news_portal_trending:
        score += 2
    if rxn.news_tier1_count >= 3:
        score += 2
    if rxn.news_source_diversity >= 5:
        score += 1

    # 커뮤니티 활성도
    if rxn.community_has_viral:
        score += 3
    if rxn.community_resonance >= 0.5:
        score += 2
    elif rxn.community_resonance >= 0.3:
        score += 1

    # 소셜 활성도
    if u.blog_recent >= 20 or u.cafe_recent >= 20:
        score += 2
    if u.yt_total_views >= 10000:
        score += 1

    # 트렌드 활성도
    if u.trend_interest >= 70:
        score += 2
    elif u.trend_interest >= 40:
        score += 1

    if score >= 8:
        return "HOT"
    elif score >= 5:
        return "WARM"
    elif score >= 2:
        return "COOL"
    else:
        return "COLD"


def format_unified_report(signals: list[UnifiedSignal]) -> str:
    """통합 수집 결과 보고서"""
    lines = ["=" * 64, "  통합 수집 보고서 (뉴스 + 블로그 + 카페 + 동영상)", "=" * 64, ""]

    grade_icon = {"HOT": "🔥", "WARM": "🟡", "COOL": "🔵", "COLD": "⚪"}

    for s in sorted(signals, key=lambda x: x.total_mentions, reverse=True):
        g = grade_icon.get(s.reaction.reaction_grade, "")
        lines.append(f"  {g} {s.keyword}  [{s.reaction.reaction_grade}]")
        lines.append(f"    뉴스 {s.news_mentions}건 | 블로그 {s.blog_recent}건"
                     f" | 카페 {s.cafe_recent}건 | 동영상 {s.video_recent}건"
                     f" | 총 {s.total_mentions}건")
        lines.append(f"    부정 {s.combined_negative:.0%} | 긍정 {s.combined_positive:.0%}"
                     f" | {'👤후보' if s.candidate_linked else ''}"
                     f" {'📺TV' if s.news_tv_reported else ''}"
                     f" {'🔥트렌딩' if s.news_portal_trending else ''}")

        # v2: 반응 깊이 표시
        rxn = s.reaction
        if rxn.news_source_diversity > 0:
            lines.append(f"    반응: 언론사 {rxn.news_source_diversity}곳 | "
                         f"제목부정 {rxn.news_headline_neg_ratio:.0%} | "
                         f"시간집중 {rxn.news_temporal_cluster:.0%}"
                         f"{' | 방어기사有' if rxn.news_defense_active else ''}")
        if rxn.community_resonance > 0:
            lines.append(f"    커뮤니티: 공명도 {rxn.community_resonance:.0%} | "
                         f"{'바이럴감지' if rxn.community_has_viral else '미감지'} | "
                         f"톤: {rxn.community_dominant_tone}")
        if rxn.blog_themes or rxn.cafe_themes:
            themes = list(set(rxn.blog_themes + rxn.cafe_themes))[:4]
            lines.append(f"    소셜테마: {', '.join(themes)}")

        if s.top_blogs:
            lines.append(f"    블로그: {s.top_blogs[0].get('title', '')[:50]}")
        if s.top_cafe_posts:
            lines.append(f"    카페: {s.top_cafe_posts[0].get('title', '')[:50]}")
        lines.append("")

    return "\n".join(lines)
