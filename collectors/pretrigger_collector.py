"""
Pre-Trigger Collector — 상대 선제행동 사전 감지
"터지기 전에" 감지하는 수집기.

3가지 감지 채널:
  1. 경남도청 보도자료/공지 모니터링
  2. 상대 SNS 패턴 변화 감지
  3. 기자단/언론 사전 시그널 감지

기존 collector 재사용: naver_news.py, owned_channels.py
"""
import os
import re
import time
import httpx
from dataclasses import dataclass, field
from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════
# 데이터 구조
# ═══════════════════════════════════════════════════════════════

@dataclass
class PreTriggerSignal:
    """사전 감지 시그널 1건"""
    signal_type: str          # "gov_website" | "opponent_sns" | "journalist" | "policy_preempt"
    severity: str             # "critical" | "warning" | "info"
    title: str                # "도청에서 '민생지원금' 보도자료 준비 중"
    detail: str               # 상세 설명
    source: str               # "경남도청 보도자료", "박완수 페이스북"
    source_url: str = ""
    keyword_matched: list = field(default_factory=list)  # 매칭된 키워드
    our_policy_overlap: str = ""    # 겹치는 우리 공약
    recommended_action: str = ""    # "즉시 선제 발표 검토"
    time_urgency: str = ""         # "즉시" | "24시간 내" | "모니터링"
    detected_at: str = ""
    confidence: float = 0.0        # 0~1

    def to_dict(self) -> dict:
        return {
            "type": self.signal_type,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "source": self.source,
            "source_url": self.source_url,
            "keywords": self.keyword_matched,
            "our_overlap": self.our_policy_overlap,
            "action": self.recommended_action,
            "urgency": self.time_urgency,
            "confidence": round(self.confidence, 2),
            "detected_at": self.detected_at,
        }


@dataclass
class PreTriggerReport:
    """Pre-Trigger 종합 보고"""
    signals: list[PreTriggerSignal] = field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0
    scanned_sources: int = 0
    scan_time: str = ""

    def to_dict(self) -> dict:
        return {
            "signals": [s.to_dict() for s in self.signals],
            "critical": self.critical_count,
            "warning": self.warning_count,
            "scanned": self.scanned_sources,
            "scan_time": self.scan_time,
        }


# ═══════════════════════════════════════════════════════════════
# 정책 선점 키워드 — 우리 공약과 겹칠 수 있는 상대 정책
# ═══════════════════════════════════════════════════════════════

POLICY_ALERT_KEYWORDS = {
    # 키워드 → (우리 공약, 긴급도)
    # ── 지원금/예산 (현직 선심 최대 위험) ──
    "민생지원금": ("도민 10만원 생활지원금", "critical"),
    "생활지원금": ("도민 10만원 생활지원금", "critical"),
    "도민지원": ("도민 10만원 생활지원금", "warning"),
    "긴급지원금": ("도민 10만원 생활지원금", "critical"),
    "10만원": ("도민 10만원 생활지원금", "critical"),
    "10만 원": ("도민 10만원 생활지원금", "critical"),
    "추경": ("예산 선점", "critical"),
    "추가경정": ("예산 선점", "critical"),
    "지역사랑상품권": ("소비 진작 선점", "warning"),
    # ── 메가시티/행정통합 ──
    "메가시티": ("부울경 메가시티", "critical"),
    "행정통합": ("부울경 행정통합", "warning"),
    "부울경": ("부울경 메가시티", "warning"),
    # ── 의대/교육 ──
    "의대 신설": ("창원대 의대", "critical"),
    "의과대학": ("창원대 의대", "critical"),
    # ── 청년/주거 ──
    "청년 월세": ("청년 월세 30만원", "warning"),
    "청년": ("청년 정책", "warning"),
    "주거": ("주거 안정", "warning"),
    "주택": ("주거 안정", "warning"),
    # ── 경제/산업 ──
    "조선업 지원": ("조선·방산 르네상스", "warning"),
    "소상공인": ("소상공인 지원", "warning"),
    "일자리": ("경남형 일자리", "warning"),
    "고용": ("경남형 일자리", "warning"),
    # ── AI/신산업 ──
    "인공지능": ("AI 대전환", "critical"),
    "로봇": ("AI·로봇 산업", "warning"),
    # ── 우주항공 ──
    "우주항공": ("우주항공 클러스터", "warning"),
    "항공우주청": ("우주항공 클러스터", "warning"),
    # ── 교통 ──
    "교통 카드": ("부울경 교통패스", "warning"),
    "광역교통": ("부울경 광역교통망", "warning"),
    # ── 복지/돌봄 ──
    "돌봄센터": ("경남형 돌봄 모델", "warning"),
    "민생": ("민생 안정", "warning"),
    # ── 기타 ──
    "스마트팜": ("경남형 스마트팜", "info"),
    "관광": ("경남 관광", "info"),
    "단수공천": ("상대 정치 동향", "warning"),
    "공천": ("상대 정치 동향", "info"),
}

# 감지 대상 — "박완수" 뿐 아니라 "경남도", "경남지사"도 포함
OPPONENT_ALIASES = ["박완수", "경남도", "경남지사", "경남도지사", "경상남도"]

# 중대발표 시그널 패턴
ANNOUNCEMENT_PATTERNS = [
    r"중대\s*발표", r"긴급\s*발표", r"특별\s*발표",
    r"기자\s*브리핑", r"보도\s*자료", r"정책\s*발표",
    r"도정\s*브리핑", r"도지사\s*발표", r"도청\s*발표",
    r"엠바고", r"사전\s*공지", r"예고",
    r"내일\s*발표", r"곧\s*발표", r"조만간",
]

# 경남 지역 언론사
GYEONGNAM_MEDIA = [
    "경남신문", "경남일보", "KNN", "경남도민일보",
    "창원시정신문", "경남연합일보", "뉴스경남",
]


# ═══════════════════════════════════════════════════════════════
# 1. 경남도청 모니터링
# ═══════════════════════════════════════════════════════════════

def scan_gov_website() -> list[PreTriggerSignal]:
    """경남도청 홈페이지 보도자료/공지 스캔"""
    signals = []

    # 경남도청 보도자료 페이지 스캔
    urls = [
        ("https://www.gyeongnam.go.kr/board/list.gyeong?boardId=BBS_0000006", "경남도청 보도자료"),
        ("https://www.gyeongnam.go.kr/board/list.gyeong?boardId=BBS_0000005", "경남도청 공지사항"),
    ]

    for url, source_name in urls:
        try:
            resp = httpx.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            }, timeout=15, follow_redirects=True)

            if resp.status_code != 200:
                continue

            text = resp.text
            # 제목 추출 (게시판 패턴)
            titles = re.findall(r'<(?:a|td|span)[^>]*>([^<]{5,80})</(?:a|td|span)>', text)

            for title in titles:
                title = title.strip()
                # 정책 키워드 매칭
                for kw, (our_policy, severity) in POLICY_ALERT_KEYWORDS.items():
                    if kw in title:
                        signals.append(PreTriggerSignal(
                            signal_type="gov_website",
                            severity=severity,
                            title=f"도청 보도자료에서 '{kw}' 감지",
                            detail=f"제목: {title[:60]}",
                            source=source_name,
                            source_url=url,
                            keyword_matched=[kw],
                            our_policy_overlap=our_policy,
                            recommended_action=f"'{our_policy}' 공약 선제 발표 검토" if severity == "critical" else "모니터링 강화",
                            time_urgency="즉시" if severity == "critical" else "24시간 내",
                            detected_at=datetime.now().isoformat(),
                            confidence=0.8,
                        ))

                # 중대발표 패턴 매칭
                for pattern in ANNOUNCEMENT_PATTERNS:
                    if re.search(pattern, title):
                        signals.append(PreTriggerSignal(
                            signal_type="gov_website",
                            severity="warning",
                            title=f"도청에서 중대발표 시그널 감지",
                            detail=f"제목: {title[:60]}",
                            source=source_name,
                            source_url=url,
                            keyword_matched=[pattern.replace(r"\s*", " ")],
                            recommended_action="발표 내용 사전 파악 필요",
                            time_urgency="즉시",
                            detected_at=datetime.now().isoformat(),
                            confidence=0.7,
                        ))
                        break

        except Exception as e:
            print(f"  [PreTrigger] 도청 스캔 실패: {e}")

    return signals


# ═══════════════════════════════════════════════════════════════
# 2. 상대 SNS 패턴 변화 감지
# ═══════════════════════════════════════════════════════════════

def scan_opponent_sns(
    opponent_name: str = "박완수",
    opponent_sns: dict = None,
) -> list[PreTriggerSignal]:
    """상대 후보 SNS에서 사전 시그널 감지"""
    signals = []
    opponent_sns = opponent_sns or {}

    # 네이버 검색으로 상대 최근 동향 체크
    try:
        from collectors.naver_news import search_news

        # 감지 대상 확대 — 박완수 + 경남도 + 경남지사
        aliases = OPPONENT_ALIASES if opponent_name in OPPONENT_ALIASES else [opponent_name] + OPPONENT_ALIASES

        pre_queries = [
            f"{opponent_name} 발표",
            f"{opponent_name} 정책",
            f"{opponent_name} 공약",
            f"경남도 정책 발표",
            f"경남도청 보도자료",
            f"경남도 추경",
            f"경남도 지원금",
        ]

        for query in pre_queries:
            articles = search_news(query, display=10, pages=1)
            for art in articles:
                title = art.get("title", "")
                desc = art.get("description", "")
                text = title + " " + desc

                # 감지 대상이 포함된 기사만 (박완수 OR 경남도 OR 경남지사)
                if not any(alias in text for alias in aliases):
                    continue

                # 정책 키워드 매칭 (중대발표 패턴 없이도 키워드만으로 감지)
                matched_policies = []
                for kw, (our_policy, sev) in POLICY_ALERT_KEYWORDS.items():
                    if kw in text:
                        matched_policies.append((kw, our_policy, sev))

                # 키워드 매칭 있으면 바로 시그널 생성
                if matched_policies:
                    top_sev = "critical" if any(s == "critical" for _, _, s in matched_policies) else "warning"
                    signals.append(PreTriggerSignal(
                        signal_type="policy_preempt",
                        severity=top_sev,
                        title=f"정책 선점 감지: {', '.join(kw for kw, _, _ in matched_policies[:3])}",
                        detail=f"기사: {title[:60]}",
                        source=f"네이버 검색 '{query}'",
                        keyword_matched=[kw for kw, _, _ in matched_policies],
                        our_policy_overlap=matched_policies[0][1],
                        recommended_action=f"'{matched_policies[0][1]}' 공약 선제 발표 검토" if top_sev == "critical" else "모니터링 강화",
                        time_urgency="즉시" if top_sev == "critical" else "24시간 내",
                        detected_at=datetime.now().isoformat(),
                        confidence=0.75,
                    ))
                    continue

                # 중대발표 패턴 (키워드 매칭 없어도)
                for pattern in ANNOUNCEMENT_PATTERNS:
                    if re.search(pattern, text):
                        matched_policies = []
                        for kw, (our_policy, sev) in POLICY_ALERT_KEYWORDS.items():
                            if kw in text:
                                matched_policies.append((kw, our_policy, sev))

                        severity = "critical" if matched_policies else "warning"
                        overlap = matched_policies[0][1] if matched_policies else ""

                        signals.append(PreTriggerSignal(
                            signal_type="opponent_sns",
                            severity=severity,
                            title=f"상대 측 발표 시그널: {title[:40]}",
                            detail=f"전체 제목: {title[:80]}",
                            source=f"네이버 검색 '{query}'",
                            keyword_matched=[kw for kw, _, _ in matched_policies] if matched_policies else [query],
                            our_policy_overlap=overlap,
                            recommended_action="선제 대응 검토" if severity == "critical" else "모니터링",
                            time_urgency="즉시" if severity == "critical" else "24시간 내",
                            detected_at=datetime.now().isoformat(),
                            confidence=0.6,
                        ))
                        break
            time.sleep(0.3)

    except Exception as e:
        print(f"  [PreTrigger] 상대 SNS 스캔 실패: {e}")

    # 중복 제거 (같은 제목)
    seen = set()
    unique = []
    for s in signals:
        key = s.title[:30]
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return unique


# ═══════════════════════════════════════════════════════════════
# 3. 기자단 사전 시그널
# ═══════════════════════════════════════════════════════════════

def scan_journalist_signals() -> list[PreTriggerSignal]:
    """경남 기자단/지역 언론에서 사전 시그널 감지"""
    signals = []

    try:
        from collectors.naver_news import search_news

        # 엠바고/발표 예정 시그널 검색
        queries = [
            "경남도 발표 예정",
            "경남도청 브리핑",
            "경남 긴급 발표",
            "경남도지사 정책 발표",
        ]

        for query in queries:
            articles = search_news(query, display=5, pages=1)
            for art in articles:
                title = art.get("title", "")
                source = art.get("source", "")

                # 경남 지역 언론 기사 우선
                is_local = any(media in (source or title) for media in GYEONGNAM_MEDIA)

                for pattern in ANNOUNCEMENT_PATTERNS:
                    if re.search(pattern, title):
                        # 정책 키워드 교차
                        matched = []
                        for kw, (our_policy, sev) in POLICY_ALERT_KEYWORDS.items():
                            if kw in title:
                                matched.append((kw, our_policy, sev))

                        signals.append(PreTriggerSignal(
                            signal_type="journalist",
                            severity="critical" if matched else ("warning" if is_local else "info"),
                            title=f"언론 사전 시그널: {title[:40]}",
                            detail=f"{title[:80]}",
                            source=source or "네이버 뉴스",
                            keyword_matched=[kw for kw, _, _ in matched] if matched else [query],
                            our_policy_overlap=matched[0][1] if matched else "",
                            recommended_action="발표 내용 사전 파악 + 선제 대응 준비" if matched else "모니터링",
                            time_urgency="즉시" if matched else "24시간 내",
                            detected_at=datetime.now().isoformat(),
                            confidence=0.7 if is_local else 0.5,
                        ))
                        break
            time.sleep(0.3)

    except Exception as e:
        print(f"  [PreTrigger] 기자 시그널 스캔 실패: {e}")

    # 중복 제거
    seen = set()
    unique = []
    for s in signals:
        key = s.title[:30]
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


# ═══════════════════════════════════════════════════════════════
# 4. 정책 선점 경고
# ═══════════════════════════════════════════════════════════════

def check_policy_preemption(
    recent_titles: list[str],
    our_pledges: dict = None,
) -> list[PreTriggerSignal]:
    """최근 수집된 뉴스/검색 제목에서 우리 공약과 겹치는 상대 정책 감지"""
    signals = []
    our_pledges = our_pledges or {}

    for title in recent_titles:
        for kw, (our_policy, severity) in POLICY_ALERT_KEYWORDS.items():
            if kw in title and ("발표" in title or "추진" in title or "검토" in title or "예정" in title):
                signals.append(PreTriggerSignal(
                    signal_type="policy_preempt",
                    severity=severity,
                    title=f"⚠ 선점 위험: '{kw}' — 상대가 유사 정책 준비 중",
                    detail=f"감지 제목: {title[:80]}",
                    source="뉴스/검색 키워드",
                    keyword_matched=[kw],
                    our_policy_overlap=our_policy,
                    recommended_action=f"'{our_policy}' 즉시 선제 발표 검토",
                    time_urgency="즉시",
                    detected_at=datetime.now().isoformat(),
                    confidence=0.75,
                ))

    # 중복 제거
    seen = set()
    unique = []
    for s in signals:
        key = s.our_policy_overlap + s.keyword_matched[0] if s.keyword_matched else ""
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


# ═══════════════════════════════════════════════════════════════
# MAIN: 종합 스캔
# ═══════════════════════════════════════════════════════════════

def scan_pretriggers(
    opponent_name: str = "박완수",
    opponent_sns: dict = None,
    our_pledges: dict = None,
    recent_titles: list[str] = None,
) -> PreTriggerReport:
    """
    Pre-Trigger 전체 스캔.
    3개 채널 + 정책 선점 검사를 종합.
    """
    report = PreTriggerReport(scan_time=datetime.now().isoformat())
    all_signals = []

    # 1. 도청 모니터링
    try:
        gov_signals = scan_gov_website()
        all_signals.extend(gov_signals)
        report.scanned_sources += 1
    except Exception:
        pass

    # 2. 상대 SNS
    try:
        opp_signals = scan_opponent_sns(opponent_name, opponent_sns)
        all_signals.extend(opp_signals)
        report.scanned_sources += 1
    except Exception:
        pass

    # 3. 기자 시그널
    try:
        jour_signals = scan_journalist_signals()
        all_signals.extend(jour_signals)
        report.scanned_sources += 1
    except Exception:
        pass

    # 4. 정책 선점
    if recent_titles:
        try:
            preempt_signals = check_policy_preemption(recent_titles, our_pledges)
            all_signals.extend(preempt_signals)
            report.scanned_sources += 1
        except Exception:
            pass

    # 정렬: critical → warning → info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_signals.sort(key=lambda s: severity_order.get(s.severity, 9))

    report.signals = all_signals
    report.critical_count = sum(1 for s in all_signals if s.severity == "critical")
    report.warning_count = sum(1 for s in all_signals if s.severity == "warning")

    return report
