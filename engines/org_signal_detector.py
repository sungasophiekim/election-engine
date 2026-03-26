"""
Organization Signal Detector v2 — 경남 조직 시그널 추출
뉴스 제목 + 검색 결과에서 조직적 움직임을 감지합니다.

기존 naver_news.py, community_collector.py, owned_channels.py 재사용.
새 수집은 하지 않음 — 기존 수집 결과에서 패턴 추출만 수행.

6대 조직 카테고리:
  1. 노동 (labor)
  2. 경제/산업 (business)
  3. 종교 (religion)
  4. 시민/NGO (civic)
  5. 교육/학부모 (education)
  6. 지역 기반 (local)
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# 조직 데이터베이스 — 경남 정치적 유의미 단체
# ═══════════════════════════════════════════════════════════════

@dataclass
class OrgProfile:
    """단체 프로필"""
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    org_type: str = ""          # labor | business | religion | civic | education | local
    region: str = ""            # "창원" | "경남" | "" (전국)
    influence_tier: str = "low" # high | medium | low
    historical_leaning: str = "" # progressive | conservative | neutral | unknown
    member_estimate: int = 0    # 추정 조합원/회원 수


# 경남 핵심 조직 DB
ORG_DATABASE: list[OrgProfile] = [
    # ── 노동 ──
    OrgProfile("민주노총 경남본부", ["민주노총 경남", "민노총 경남"], "labor", "경남", "high", "progressive", 50000),
    OrgProfile("한국노총 경남본부", ["한국노총 경남", "한노총 경남"], "labor", "경남", "high", "neutral", 40000),
    OrgProfile("금속노조 경남지부", ["금속노조 경남", "금속노련"], "labor", "창원", "high", "progressive", 30000),
    OrgProfile("조선업 노동조합", ["조선노조", "대우조선 노조", "삼성중공업 노조", "한화오션 노조"], "labor", "거제", "medium", "progressive", 15000),
    OrgProfile("공공운수노조 경남", ["공공노조 경남"], "labor", "경남", "medium", "progressive", 8000),
    # ── 경제/산업 ──
    OrgProfile("창원상공회의소", ["창원상의"], "business", "창원", "high", "conservative", 5000),
    OrgProfile("경남상공회의소", ["경남상의", "경남경제인"], "business", "경남", "high", "conservative", 3000),
    OrgProfile("경남경영자총협회", ["경남경총"], "business", "경남", "medium", "conservative", 1000),
    OrgProfile("경남중소기업중앙회", ["경남중기중앙회", "중소기업 경남"], "business", "경남", "medium", "neutral", 2000),
    # ── 종교 ──
    OrgProfile("경남기독교총연합회", ["경남기총", "경남 교회 연합", "개신교 경남"], "religion", "경남", "medium", "conservative", 0),
    OrgProfile("마산교구", ["천주교 마산교구", "천주교 경남"], "religion", "창원", "medium", "neutral", 0),
    OrgProfile("통도사", ["통도사 경남", "불교 경남"], "religion", "양산", "low", "neutral", 0),
    # ── 시민/NGO ──
    OrgProfile("경남시민사회단체연대", ["경남시민단체", "시민사회 경남"], "civic", "경남", "medium", "progressive", 0),
    OrgProfile("경남여성단체연합", ["경남여성회", "경남 여성단체"], "civic", "경남", "medium", "progressive", 0),
    OrgProfile("경남청년회", ["경남 청년단체", "경남청년연대"], "civic", "경남", "low", "progressive", 0),
    OrgProfile("환경운동연합 경남", ["환경연합 경남", "경남환경"], "civic", "경남", "low", "progressive", 0),
    OrgProfile("경실련 경남", ["경실련 경남지부"], "civic", "경남", "low", "neutral", 0),
    # ── 교육/학부모 ──
    OrgProfile("교총 경남", ["한국교원단체총연합회 경남", "교총 경남지부"], "education", "경남", "medium", "neutral", 0),
    OrgProfile("전교조 경남지부", ["전교조 경남", "전국교직원노동조합 경남"], "education", "경남", "medium", "progressive", 0),
    OrgProfile("경남학부모회", ["경남 학부모단체", "학부모 경남"], "education", "경남", "low", "neutral", 0),
    # ── 지역 기반 ──
    OrgProfile("경남도의회", ["도의회 경남", "경남 도의원"], "local", "경남", "high", "neutral", 0),
    OrgProfile("창원시의회", ["시의회 창원"], "local", "창원", "medium", "neutral", 0),
    OrgProfile("경남농민회", ["경남 농민단체", "전농 경남"], "local", "경남", "medium", "progressive", 0),
    OrgProfile("경남상인회", ["경남 전통시장", "상인연합회 경남"], "local", "경남", "low", "neutral", 0),
    OrgProfile("재향군인회 경남", ["경남 재향군인", "향군 경남"], "local", "경남", "medium", "conservative", 0),
]

# 빠른 검색용 인덱스
_ORG_SEARCH_INDEX: list[tuple[str, OrgProfile]] = []
for _org in ORG_DATABASE:
    _ORG_SEARCH_INDEX.append((_org.canonical_name, _org))
    for _alias in _org.aliases:
        _ORG_SEARCH_INDEX.append((_alias, _org))
# 긴 이름 먼저 매칭 (substring 충돌 방지)
_ORG_SEARCH_INDEX.sort(key=lambda x: len(x[0]), reverse=True)


# ═══════════════════════════════════════════════════════════════
# 탐지 패턴
# ═══════════════════════════════════════════════════════════════

_MOVEMENT_PATTERNS: dict[str, list[str]] = {
    "endorsement": [
        r"지지\s*선언", r"지지\s*표명", r"지지\s*의사", r"공개\s*지지",
        r"출마\s*지지", r"지원\s*선언", r"후보\s*지지",
        r"캠프\s*합류", r"선대위\s*합류", r"공동\s*선언", r"규합",
    ],
    "withdrawal": [
        r"지지\s*철회", r"탈당", r"이탈", r"결별", r"불지지",
        r"선대위\s*탈퇴", r"사퇴", r"반대\s*선언", r"후보\s*반대",
    ],
    "protest": [
        r"규탄\s*성명", r"반대\s*성명", r"항의", r"성토",
        r"집회", r"시위", r"반발", r"공동\s*대응",
    ],
    "alliance": [
        r"연대\s*선언", r"연대", r"정책\s*협약", r"협약식",
        r"공동\s*기자회견", r"업무\s*협약", r"MOU",
    ],
    "meeting": [
        r"간담회", r"면담", r"방문", r"참석",
        r"토론회", r"포럼", r"대담", r"간담",
    ],
    "statement": [
        r"성명\s*발표", r"성명", r"논평", r"입장\s*발표",
        r"기자회견", r"투표\s*독려", r"호소문",
    ],
}

# 지역 추출 패턴
_REGION_MAP = {
    "창원": "창원", "마산": "창원", "진해": "창원",
    "김해": "김해", "진주": "진주", "거제": "거제",
    "양산": "양산", "통영": "통영", "사천": "사천",
    "밀양": "밀양", "함안": "함안", "거창": "거창",
    "합천": "합천", "하동": "하동", "남해": "남해",
    "산청": "산청", "함양": "함양", "의령": "의령",
    "고성": "고성", "창녕": "창녕",
    "경남": "경남", "경상남도": "경남",
}

# 영향력 가중치
_TYPE_BASE_WEIGHT = {
    "labor": 8.0,
    "business": 7.0,
    "religion": 5.0,
    "civic": 4.0,
    "education": 5.0,
    "local": 6.0,
}
_TIER_MULTIPLIER = {"high": 2.0, "medium": 1.3, "low": 0.8}
_REGION_WEIGHT = {
    "창원": 1.5, "김해": 1.3, "양산": 1.2, "진주": 1.2,
    "거제": 1.1, "통영": 1.0, "경남": 1.4,
}


# ═══════════════════════════════════════════════════════════════
# 데이터 구조
# ═══════════════════════════════════════════════════════════════

@dataclass
class OrgSignal:
    """단일 조직 시그널"""
    org_name: str
    org_type: str = ""          # labor | business | religion | civic | education | local
    signal_type: str = ""       # endorsement | withdrawal | protest | alliance | meeting | statement
    stance: str = ""            # support | oppose | neutral | mixed
    region: str = ""
    influence_tier: str = "low"
    influence_score: float = 0.0
    confidence: float = 0.0
    candidate_linked: bool = False
    opponent_linked: bool = False
    issue_linked: str = ""
    source_title: str = ""
    keyword: str = ""
    mention_count: int = 1
    deduped_story_count: int = 0
    media_tier: int = 3
    community_echo: int = 0
    owned_channel_mention: bool = False
    last_seen_at: str = ""

    def to_dict(self) -> dict:
        return {
            "organization_name": self.org_name,
            "organization_type": self.org_type,
            "region": self.region,
            "stance": self.stance,
            "movement_type": self.signal_type,
            "candidate_linked": self.candidate_linked,
            "opponent_linked": self.opponent_linked,
            "issue_linked": self.issue_linked,
            "mention_count": self.mention_count,
            "deduped_story_count": self.deduped_story_count,
            "media_tier": self.media_tier,
            "community_echo": self.community_echo,
            "owned_channel_mention": self.owned_channel_mention,
            "influence_score": round(self.influence_score, 2),
            "confidence": round(self.confidence, 2),
            "last_seen_at": self.last_seen_at,
        }


@dataclass
class OrgSignalSummary:
    """키워드별/전체 조직 시그널 요약"""
    keyword: str = ""
    signals: list[OrgSignal] = field(default_factory=list)
    endorsement_count: int = 0
    withdrawal_count: int = 0
    protest_count: int = 0
    alliance_count: int = 0
    meeting_count: int = 0
    statement_count: int = 0
    movement_count: int = 0         # 전체 (하위 호환)
    net_org_sentiment: float = 0.0  # -1 ~ +1
    high_influence_count: int = 0
    total_influence: float = 0.0
    unique_orgs: int = 0

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "endorsement": self.endorsement_count,
            "withdrawal": self.withdrawal_count,
            "protest": self.protest_count,
            "alliance": self.alliance_count,
            "meeting": self.meeting_count,
            "statement": self.statement_count,
            "movement": self.movement_count,
            "net_sentiment": round(self.net_org_sentiment, 2),
            "high_influence": self.high_influence_count,
            "total_influence": round(self.total_influence, 1),
            "unique_orgs": self.unique_orgs,
            "signals": [s.to_dict() for s in self.signals[:15]],
        }


# ═══════════════════════════════════════════════════════════════
# 핵심 탐지 함수
# ═══════════════════════════════════════════════════════════════

def _find_org(text: str) -> OrgProfile | None:
    """텍스트에서 알려진 조직을 찾습니다 (DB 우선, fallback 패턴)"""
    for name, profile in _ORG_SEARCH_INDEX:
        if name in text:
            return profile
    return None


def _find_org_generic(text: str) -> tuple[str, str]:
    """DB에 없는 조직도 패턴으로 추출 (fallback)"""
    # "OO연합", "OO협의회", "OO노조" 등
    m = re.search(
        r'((?:경남|경상남도|창원|김해|진주|거제|통영|양산|밀양|사천)?\s*'
        r'(?:도의회|시의회|군의회|'
        r'민주노총|한국노총|노동조합|노조|'
        r'상공회의소|경제인연합|경총|중기중앙회|'
        r'농협|수협|산림조합|축협|'
        r'시민단체|시민사회|환경운동연합|참여연대|경실련|'
        r'여성단체|여성회|여성연합|'
        r'변호사회|의사회|약사회|교수협의회|교원단체|'
        r'재향군인회|참전유공자|보훈단체|'
        r'청년회|청년단체|학생회|'
        r'종교단체|목사회|승려회|교구|'
        r'당[원]?협|지구당|'
        r'향우회|동창회|상인회|농민회|'
        r'\w{2,8}(?:연합|연대|협의회|위원회|본부|지부|분회|총회)))',
        text,
    )
    if m:
        name = m.group(1).strip()
        # 유형 추정
        org_type = "civic"
        if any(k in name for k in ["노총", "노조", "노동"]):
            org_type = "labor"
        elif any(k in name for k in ["상공", "경총", "경제", "중기", "기업"]):
            org_type = "business"
        elif any(k in name for k in ["교회", "불교", "천주교", "교구", "사찰", "목사"]):
            org_type = "religion"
        elif any(k in name for k in ["교총", "전교조", "교원", "학부모"]):
            org_type = "education"
        elif any(k in name for k in ["도의회", "시의회", "향우회", "상인회", "농민회", "재향"]):
            org_type = "local"
        return name, org_type
    return "", ""


def _detect_movement(text: str) -> tuple[str, str]:
    """텍스트에서 움직임 유형과 stance를 탐지"""
    for move_type, patterns in _MOVEMENT_PATTERNS.items():
        for p in patterns:
            if re.search(p, text):
                # stance 추론
                if move_type in ("endorsement", "alliance"):
                    stance = "support"
                elif move_type in ("withdrawal", "protest"):
                    stance = "oppose"
                elif move_type == "meeting":
                    stance = "neutral"
                else:
                    stance = "neutral"
                return move_type, stance
    return "", ""


def _extract_region(text: str) -> str:
    """텍스트에서 지역 추출"""
    for keyword, region in _REGION_MAP.items():
        if keyword in text:
            return region
    return ""


def _calc_influence(
    org: OrgProfile | None,
    org_type: str,
    region: str,
    media_tier: int = 3,
    community_echo: int = 0,
) -> float:
    """영향력 점수 계산"""
    # base weight
    base = _TYPE_BASE_WEIGHT.get(org_type, 3.0)

    # tier multiplier
    tier = "low"
    if org:
        tier = org.influence_tier
    tier_mult = _TIER_MULTIPLIER.get(tier, 0.8)

    # region weight
    region_w = _REGION_WEIGHT.get(region, 0.8)

    # media amplification
    media_amp = {1: 2.0, 2: 1.3, 3: 1.0}.get(media_tier, 1.0)

    # community echo bonus
    echo_bonus = min(3.0, community_echo * 0.5)

    return round(base * tier_mult * region_w * media_amp + echo_bonus, 2)


# ═══════════════════════════════════════════════════════════════
# 메인 추출 함수
# ═══════════════════════════════════════════════════════════════

def extract_org_signals(
    titles: list[str],
    keyword: str = "",
    candidate_name: str = "",
    opponents: list[str] = None,
    media_tier: int = 3,
    community_titles: list[str] = None,
    owned_channel_titles: list[str] = None,
) -> OrgSignalSummary:
    """
    뉴스 제목 + 커뮤니티 제목 + 자체채널에서 조직 시그널 추출.

    Args:
        titles: 뉴스/검색 결과 제목 리스트
        keyword: 연결 키워드
        candidate_name: 우리 후보 이름
        opponents: 상대 후보 이름들
        media_tier: 뉴스 미디어 티어
        community_titles: 커뮤니티 제목 (echo 감지용)
        owned_channel_titles: 자체 채널 제목 (mention 감지용)
    """
    opponents = opponents or []
    community_titles = community_titles or []
    owned_channel_titles = owned_channel_titles or []
    summary = OrgSignalSummary(keyword=keyword)

    # 중복 방지 (같은 조직 + 같은 movement_type)
    seen: set[tuple[str, str]] = set()

    for title in titles:
        # 움직임 탐지
        move_type, stance = _detect_movement(title)
        if not move_type:
            continue

        # 조직 탐지 (DB 우선, fallback 패턴)
        org_profile = _find_org(title)
        if org_profile:
            org_name = org_profile.canonical_name
            org_type = org_profile.org_type
        else:
            org_name, org_type = _find_org_generic(title)
            if not org_name:
                continue

        # 중복 체크
        dedup_key = (org_name, move_type)
        if dedup_key in seen:
            # 기존 시그널의 mention_count 증가
            for s in summary.signals:
                if s.org_name == org_name and s.signal_type == move_type:
                    s.mention_count += 1
                    break
            continue
        seen.add(dedup_key)

        # 지역 추출
        region = _extract_region(title)
        if not region and org_profile:
            region = org_profile.region

        # 후보 연결 판단
        candidate_linked = candidate_name and candidate_name in title
        opponent_linked = any(opp in title for opp in opponents)

        # stance 보정
        if candidate_linked and move_type == "endorsement":
            stance = "support"
        elif candidate_linked and move_type == "withdrawal":
            stance = "oppose"
        elif opponent_linked and move_type == "endorsement":
            stance = "oppose"  # 상대 지지 = 우리에게 oppose
        elif opponent_linked and move_type == "withdrawal":
            stance = "support"  # 상대 철회 = 우리에게 support

        # 커뮤니티 에코 (조직명이 커뮤니티에서도 언급되는지)
        community_echo = sum(1 for ct in community_titles if org_name in ct or (org_profile and any(a in ct for a in org_profile.aliases)))

        # 자체 채널 멘션
        owned_mention = any(org_name in ot for ot in owned_channel_titles)

        # 영향력 계산
        influence = _calc_influence(org_profile, org_type, region, media_tier, community_echo)

        # confidence
        confidence = 0.5
        if org_profile:
            confidence += 0.2  # DB에 있는 조직
        if candidate_linked or opponent_linked:
            confidence += 0.15
        if community_echo > 0:
            confidence += 0.1
        if owned_mention:
            confidence += 0.05
        confidence = min(1.0, confidence)

        sig = OrgSignal(
            org_name=org_name,
            org_type=org_type,
            signal_type=move_type,
            stance=stance,
            region=region,
            influence_tier=org_profile.influence_tier if org_profile else "low",
            influence_score=influence,
            confidence=confidence,
            candidate_linked=candidate_linked,
            opponent_linked=opponent_linked,
            issue_linked=keyword,
            source_title=title[:100],
            keyword=keyword,
            mention_count=1,
            deduped_story_count=1,
            media_tier=media_tier,
            community_echo=community_echo,
            owned_channel_mention=owned_mention,
            last_seen_at=datetime.now().isoformat(),
        )
        summary.signals.append(sig)

    # 집계
    summary.endorsement_count = sum(1 for s in summary.signals if s.signal_type == "endorsement")
    summary.withdrawal_count = sum(1 for s in summary.signals if s.signal_type == "withdrawal")
    summary.protest_count = sum(1 for s in summary.signals if s.signal_type == "protest")
    summary.alliance_count = sum(1 for s in summary.signals if s.signal_type == "alliance")
    summary.meeting_count = sum(1 for s in summary.signals if s.signal_type == "meeting")
    summary.statement_count = sum(1 for s in summary.signals if s.signal_type == "statement")
    summary.movement_count = len(summary.signals)
    summary.high_influence_count = sum(1 for s in summary.signals if s.influence_tier in ("high", "medium"))
    summary.total_influence = sum(s.influence_score for s in summary.signals)
    summary.unique_orgs = len(set(s.org_name for s in summary.signals))

    # 순 조직 감성
    support = sum(1 for s in summary.signals if s.stance == "support")
    oppose = sum(1 for s in summary.signals if s.stance == "oppose")
    total = support + oppose
    summary.net_org_sentiment = (support - oppose) / total if total > 0 else 0.0

    return summary


def scan_org_landscape(
    candidate_name: str = "",
    opponents: list[str] = None,
    region: str = "경남",
) -> list[OrgSignalSummary]:
    """
    경남 전체 조직 landscape 스캔.
    keyword_engine의 조직 시드 키워드를 사용하여
    naver_news에서 일괄 수집 후 조직 시그널 추출.

    이 함수는 기존 수집 파이프라인과 별도로,
    조직 전용 스캔이 필요할 때 호출합니다.
    """
    try:
        from collectors.naver_news import search_news
    except ImportError:
        return []

    opponents = opponents or []
    results = []

    # 조직 DB의 모든 canonical name으로 검색
    for org in ORG_DATABASE:
        query = f"{org.canonical_name} {candidate_name}" if candidate_name else org.canonical_name
        try:
            articles = search_news(query, display=20, pages=1)
            titles = [a.get("title", "") for a in articles]
            summary = extract_org_signals(
                titles=titles,
                keyword=org.canonical_name,
                candidate_name=candidate_name,
                opponents=opponents,
            )
            if summary.signals:
                results.append(summary)
        except Exception:
            pass

    return results


# ── Future hooks ──────────────────────────────────────────────

def extract_from_comments(comments: list[dict]) -> OrgSignalSummary:
    """HOOK: 뉴스 댓글에서 조직 시그널 추출 (미구현)"""
    return OrgSignalSummary()

def extract_from_sns(posts: list[dict]) -> OrgSignalSummary:
    """HOOK: SNS 게시물에서 조직 시그널 추출 (미구현)"""
    return OrgSignalSummary()

def extract_from_action_log(actions: list[dict]) -> OrgSignalSummary:
    """HOOK: 후보 행동 로그에서 연관 조직 추출 (미구현)"""
    return OrgSignalSummary()
