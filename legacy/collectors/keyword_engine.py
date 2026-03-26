"""
Election Strategy Engine — 키워드 발굴 엔진
실시간 이슈 키워드를 자동 발굴합니다.

3계층 키워드 구조:
  1. Seed 키워드 (config 기반, 항상 수집)
  2. Expanded 키워드 (뉴스/소셜에서 자동 추출)
  3. Emerging 키워드 (새로 떠오르는 이슈 감지)

스코어링/대응 모델과 완전 분리 — 키워드만 관리합니다.
"""
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config.tenant_config import TenantConfig


@dataclass
class KeywordEntry:
    """키워드 1건"""
    keyword: str
    source: str          # "seed" | "news_extract" | "social_extract" | "emerging" | "manual"
    category: str        # "후보" | "상대" | "공약" | "지역" | "이슈" | "신규"
    priority: int        # 1(최우선) ~ 5(낮음)
    reason: str          # 왜 이 키워드를 수집하는가
    added_at: str        # ISO timestamp
    active: bool = True  # 수집 대상 여부


class KeywordEngine:
    """실시간 이슈 키워드 발굴 엔진"""

    def __init__(self, config: TenantConfig):
        self.config = config
        self.keywords: list[KeywordEntry] = []
        self._build_seed_keywords()

    # ------------------------------------------------------------------
    # 1계층: Seed 키워드 (config 기반, 항상 수집)
    # ------------------------------------------------------------------
    def _build_seed_keywords(self):
        """config에서 자동 생성되는 기본 키워드"""
        now = datetime.now().isoformat()
        c = self.config

        # 후보 관련
        self._add("seed", "후보", 1, f"{c.candidate_name}", f"우리 후보 직접 모니터링")
        self._add("seed", "후보", 1, f"{c.candidate_name} {c.region}", f"후보+지역 뉴스")
        self._add("seed", "후보", 1, f"{c.candidate_name} 공약", f"후보 공약 관련 보도")

        # 상대 후보 관련
        for opp in c.opponents:
            self._add("seed", "상대", 1, f"{opp}", f"상대 후보 모니터링")
            self._add("seed", "상대", 2, f"{opp} {c.region}", f"상대+지역 뉴스")
            self._add("seed", "상대", 2, f"{opp} 공약", f"상대 공약 추적")

        # 선거 일반
        region_short = c.region.replace("경상남도", "경남").replace("경상북도", "경북").replace("특별시", "").replace("광역시", "")
        self._add("seed", "이슈", 1, f"{region_short}도지사 선거", f"선거 일반 뉴스")
        self._add("seed", "이슈", 1, f"{region_short}도지사 공약", f"선거 공약 뉴스")
        self._add("seed", "이슈", 2, f"{region_short} 선거", f"선거 관련 보도")

        # 공약 관련
        for pledge_name, pledge_data in c.pledges.items():
            # 공약명에서 핵심 단어 추출
            core_words = self._extract_core_words(pledge_name)
            for w in core_words:
                self._add("seed", "공약", 2, f"{region_short} {w}", f"공약 '{pledge_name}' 관련")

        # 지역 이슈
        for region_name, region_data in c.regions.items():
            key_issue = region_data.get("key_issue", "")
            if key_issue:
                self._add("seed", "지역", 3, f"{region_name.replace('시','')} {key_issue}", f"{region_name} 핵심 이슈")

        # 민생/경제 — 선거에 영향을 미치는 생활 이슈
        livelihood = [
            (f"{region_short} 물가", "물가 상승이 유권자 심리에 직접 영향"),
            (f"{region_short} 일자리", "고용 상황 = 현직 성과 평가 지표"),
            (f"{region_short} 부동산", "집값/전세 = 2030 표심 핵심"),
            (f"{region_short} 인구 감소", "지방소멸 위기 → 도지사 역할론"),
            (f"{region_short} 경기 침체", "지역 경제 상황 → 현직 책임론"),
            (f"{region_short} 의료", "필수의료/응급실 → 지역 민생 이슈"),
            (f"{region_short} 교육", "교육 환경 = 가족 유권자 관심"),
            (f"{region_short} 재난 안전", "재난 대응 → 도지사 리더십 평가"),
        ]
        for kw, reason in livelihood:
            self._add("seed", "민생", 3, kw, reason)

        # 국정/정당 — 지방선거에 영향을 미치는 중앙 정치
        national = [
            ("국민의힘 경남", "여당 동향이 박완수에게 직접 영향"),
            ("더불어민주당 경남", "우리 당 경남 조직 동향"),
            ("대통령 경남", "대통령 지지율↔지방선거 연동"),
            ("여야 경남", "중앙 정국이 지방선거에 미치는 영향"),
        ]
        for kw, reason in national:
            self._add("seed", "국정", 3, kw, reason)

        # 조직 시그널 — 정치적으로 유의미한 단체 움직임
        org_keywords = [
            # 노동
            ("민주노총 경남", "민주노총 경남본부 동향 — 조직 투표 영향력"),
            ("한국노총 경남", "한국노총 경남본부 동향"),
            ("금속노조 경남", "금속노조 계열 — 조선/제조업 노조"),
            ("경남 노동조합", "경남 노조 전반 동향"),
            # 경제/산업
            ("창원상공회의소", "창원 경제계 입장"),
            ("경남상공회의소", "경남 경제단체 동향"),
            ("경남 중소기업", "중소기업 협회/단체"),
            # 종교
            ("경남 교회 선거", "개신교 연합 — 보수 조직 투표"),
            ("경남 불교 선거", "불교계 동향"),
            ("경남 천주교 선거", "천주교 교구 입장"),
            # 시민/NGO
            ("경남 시민단체", "시민사회 동향"),
            ("경남 여성단체", "여성단체 입장 — 여성 유권자"),
            ("경남 청년단체", "청년 조직 동향"),
            ("경남 환경단체", "환경단체 입장"),
            # 교육/학부모
            ("경남 교총", "교총 경남 — 교원 단체"),
            ("경남 전교조", "전교조 경남 — 진보 교원"),
            ("경남 학부모", "학부모 단체 동향"),
            # 지역 기반
            ("경남 향우회", "향우회 — 지역 네트워크"),
            ("경남 상인회", "상인회 — 전통시장/상권"),
            ("경남 농민회", "농민회 — 농촌 조직"),
            # 후보 연결
            (f"{c.candidate_name} 지지 선언", "우리 후보 지지 선언 모니터링"),
            (f"{c.candidate_name} 연대", "우리 후보 연대 동향"),
        ]
        for opp in c.opponents:
            org_keywords.append((f"{opp} 지지 선언", f"상대 {opp} 지지 선언 모니터링"))
            org_keywords.append((f"{opp} 연대", f"상대 {opp} 연대 동향"))

        for kw, reason in org_keywords:
            self._add("seed", "조직", 2, kw, reason)

        # ── 빅카인즈 연관어 시드 (Trend Report 기반) ──
        # 출처: 260320 경남대전환 Trend Report — 빅카인즈 SNA 분석
        # 김경수 652건 뉴스에서 도출된 인물/장소/기관/키워드
        bigkinds = [
            # 핵심 인물 (16명 중 주요)
            (f"{c.candidate_name} 이재명", "빅카인즈 SNA — 대통령과 후보 연결"),
            (f"{c.candidate_name} 정청래", "빅카인즈 SNA — 당대표 연결"),
            (f"{c.candidate_name} 박찬대", "빅카인즈 SNA — 단수공천 관련"),
            (f"{c.candidate_name} 노무현", "빅카인즈 SNA — 노무현 레거시 연결"),
            # 핵심 키워드 (18개 중 주요)
            ("경남 광역단체장", "빅카인즈 — 광역단체장 관련 보도"),
            ("경남 단수공천", "빅카인즈 — 공천 이슈"),
            ("경남 AI 대전환", "빅카인즈 — 김경수 AI 정책 키워드"),
            ("경남 타운홀미팅", "빅카인즈 — 타운홀 미팅 이벤트"),
            ("경남 도민 10만원", "빅카인즈 — 생활지원금 공약"),
            ("경남 지방시대", "빅카인즈 — 지방시대위원장 경력"),
            # 뉴스 언급량 추이에서 도출된 이벤트 키워드
            ("부울경 28년 통합", "빅카인즈 — 부울경 행정통합 기사 급등 이벤트"),
            ("한화오션 상생선언", "빅카인즈 — 조선업 상생 이벤트"),
            ("김경수 김태흠", "빅카인즈 — 김태흠 만남 이벤트"),
            # 박완수 측 모니터링
            ("박완수 국민의힘 공천", "빅카인즈 — 상대 공천 동향"),
            ("박완수 환영 인터뷰", "빅카인즈 — 상대 미디어 노출"),
            ("박완수 서경 최고위", "빅카인즈 — 상대 당 활동"),
        ]
        for kw, reason in bigkinds:
            self._add("seed", "빅카인즈", 2, kw, reason)

        # 지역 개발/인프라
        infra = [
            (f"{region_short} 개발", "지역 개발 사업 → 유권자 기대/불만"),
            (f"{region_short} 예산", "도 예산 편성 → 현직 성과 평가"),
            ("부울경 교통", "광역교통 → 부울경 메가시티 핵심"),
            ("경남 기업 투자", "기업 유치/이탈 → 경제 성과 지표"),
        ]
        for kw, reason in infra:
            self._add("seed", "인프라", 3, kw, reason)

    def _add(self, source: str, category: str, priority: int, keyword: str, reason: str):
        """중복 없이 키워드 추가"""
        if any(k.keyword == keyword for k in self.keywords):
            return
        self.keywords.append(KeywordEntry(
            keyword=keyword, source=source, category=category,
            priority=priority, reason=reason,
            added_at=datetime.now().isoformat(),
        ))

    def _extract_core_words(self, text: str) -> list[str]:
        """텍스트에서 핵심 단어 추출 (2글자 이상)"""
        # 조사/접미사 제거 간이 처리
        stopwords = {"경남형", "경남", "르네상스", "패키지"}
        words = re.split(r'[·\s/]+', text)
        return [w for w in words if len(w) >= 2 and w not in stopwords][:3]

    # ------------------------------------------------------------------
    # 2계층: Expanded 키워드 (뉴스/소셜에서 자동 추출)
    # ------------------------------------------------------------------
    def expand_from_articles(self, articles: list[dict]):
        """
        수집된 기사 제목에서 새로운 키워드를 자동 추출.
        빈도가 높은 단어 조합을 키워드로 승격.
        """
        word_counter = Counter()
        bigram_counter = Counter()

        # 불용어
        stopwords = {
            "경남", "경상남도", "도지사", "후보", "선거", "오늘", "내일", "지난",
            "관련", "대한", "위한", "통해", "이번", "올해", "현재", "최근",
            "것으로", "이후", "때문", "하면서", "한편", "이날", "오는", "지역",
            self.config.candidate_name, *self.config.opponents,
        }

        for art in articles:
            title = art.get("title", "")
            # 한글 단어만 추출 (2~6글자)
            words = re.findall(r'[가-힣]{2,6}', title)
            filtered = [w for w in words if w not in stopwords]

            for w in filtered:
                word_counter[w] += 1

            # 바이그램 (연속 2단어)
            for i in range(len(filtered) - 1):
                bigram = f"{filtered[i]} {filtered[i+1]}"
                bigram_counter[bigram] += 1

        # 빈도 3+ 바이그램을 키워드로 추가
        existing = {k.keyword for k in self.keywords}
        for bigram, count in bigram_counter.most_common(20):
            if count >= 3 and bigram not in existing:
                region_short = self.config.region.replace("도", "")
                full_kw = f"{region_short} {bigram}" if region_short not in bigram else bigram
                if full_kw not in existing:
                    self._add(
                        "news_extract", "신규", 3,
                        full_kw,
                        f"뉴스 자동 추출 (빈도 {count}회)",
                    )

        # 빈도 5+ 단일 단어 중 기존에 없는 것
        for word, count in word_counter.most_common(30):
            if count >= 5 and len(word) >= 3:
                region_short = self.config.region.replace("도", "")
                full_kw = f"{region_short} {word}"
                if full_kw not in existing and word not in existing:
                    self._add(
                        "news_extract", "신규", 4,
                        full_kw,
                        f"뉴스 빈출 단어 (빈도 {count}회)",
                    )

    def expand_from_social(self, blog_items: list[dict], cafe_items: list[dict]):
        """블로그/카페 제목에서 새 키워드 추출"""
        all_items = (blog_items or []) + (cafe_items or [])
        if all_items:
            self.expand_from_articles(all_items)

    # ------------------------------------------------------------------
    # 3계층: Emerging 키워드 (새로 떠오르는 이슈 감지)
    # ------------------------------------------------------------------
    def detect_emerging(self, current_articles: list[dict], previous_keywords: set = None):
        """
        이전 수집 대비 새로 등장한 키워드 감지.
        previous_keywords: 이전 수집에서 추출된 키워드 셋
        """
        if not previous_keywords:
            return

        current_words = set()
        for art in current_articles:
            words = re.findall(r'[가-힣]{2,6}', art.get("title", ""))
            current_words.update(words)

        new_words = current_words - previous_keywords
        # 새 단어 중 빈도 높은 것
        new_counter = Counter()
        for art in current_articles:
            words = re.findall(r'[가-힣]{2,6}', art.get("title", ""))
            for w in words:
                if w in new_words and len(w) >= 3:
                    new_counter[w] += 1

        existing = {k.keyword for k in self.keywords}
        for word, count in new_counter.most_common(5):
            if count >= 2:
                region_short = self.config.region.replace("도", "")
                full_kw = f"{region_short} {word}"
                if full_kw not in existing:
                    self._add(
                        "emerging", "신규", 2,
                        full_kw,
                        f"신규 출현 키워드 (빈도 {count}회)",
                    )

    # ------------------------------------------------------------------
    # 수동 키워드 관리
    # ------------------------------------------------------------------
    def add_manual(self, keyword: str, reason: str = "", priority: int = 2):
        """캠프 담당자가 수동으로 키워드 추가"""
        self._add("manual", "이슈", priority, keyword, reason or "수동 추가")

    def deactivate(self, keyword: str):
        """키워드 비활성화 (수집 중단)"""
        for k in self.keywords:
            if k.keyword == keyword:
                k.active = False

    def activate(self, keyword: str):
        """키워드 활성화"""
        for k in self.keywords:
            if k.keyword == keyword:
                k.active = True

    # ------------------------------------------------------------------
    # 키워드 목록 반환
    # ------------------------------------------------------------------
    def get_active_keywords(self) -> list[str]:
        """활성 키워드만 우선순위순으로 반환"""
        active = [k for k in self.keywords if k.active]
        active.sort(key=lambda k: k.priority)
        return [k.keyword for k in active]

    def get_by_category(self, category: str) -> list[KeywordEntry]:
        """카테고리별 키워드"""
        return [k for k in self.keywords if k.category == category and k.active]

    def get_by_priority(self, max_priority: int = 3) -> list[str]:
        """우선순위 N 이하만 (1=최우선)"""
        return [k.keyword for k in self.keywords
                if k.active and k.priority <= max_priority]

    # ------------------------------------------------------------------
    # 자동 발굴 실행 (뉴스 수집 → 키워드 추출 → 반환)
    # ------------------------------------------------------------------
    def discover(self) -> list[str]:
        """
        전체 키워드 발굴 파이프라인 실행.
        1. Seed 키워드로 뉴스 수집
        2. 기사 제목에서 새 키워드 추출
        3. 소셜에서 추가 키워드 추출
        4. 활성 키워드 전체 반환
        """
        from collectors.naver_news import search_news
        from collectors.social_collector import search_blogs, search_cafes

        # Seed 키워드 중 우선순위 1-2로 뉴스 수집
        seed_kws = self.get_by_priority(2)
        all_articles = []
        all_blogs = []
        all_cafes = []

        for kw in seed_kws[:10]:  # 최대 10개 (API 호출 제한)
            try:
                articles = search_news(kw, display=50)
                all_articles.extend(articles)
            except Exception:
                pass

            try:
                blog = search_blogs(kw, display=30)
                all_blogs.extend(blog.top_items[:10])
            except Exception:
                pass

            try:
                cafe = search_cafes(kw, display=30)
                all_cafes.extend(cafe.top_items[:10])
            except Exception:
                pass

        # 2. 기사에서 키워드 확장
        if all_articles:
            self.expand_from_articles(all_articles)

        # 3. 소셜에서 키워드 확장
        if all_blogs or all_cafes:
            self.expand_from_social(all_blogs, all_cafes)

        return self.get_active_keywords()

    # ------------------------------------------------------------------
    # 보고서
    # ------------------------------------------------------------------
    def format_report(self) -> str:
        """키워드 현황 보고서"""
        lines = ["=" * 60, "  키워드 현황 보고서", "=" * 60, ""]

        categories = {}
        for k in self.keywords:
            categories.setdefault(k.category, []).append(k)

        cat_order = ["후보", "상대", "공약", "지역", "이슈", "신규"]
        for cat in cat_order:
            kws = categories.get(cat, [])
            if not kws:
                continue
            active = [k for k in kws if k.active]
            inactive = [k for k in kws if not k.active]
            lines.append(f"  [{cat}] {len(active)}개 활성 / {len(inactive)}개 비활성")
            for k in sorted(kws, key=lambda x: x.priority):
                status = "●" if k.active else "○"
                src_tag = {"seed": "기본", "news_extract": "뉴스추출", "social_extract": "소셜추출",
                           "emerging": "신규출현", "manual": "수동"}.get(k.source, k.source)
                lines.append(f"    {status} P{k.priority} [{src_tag:4s}] {k.keyword}")
                lines.append(f"      └ {k.reason}")
            lines.append("")

        lines.append(f"  총 {len(self.keywords)}개 키워드"
                     f" ({sum(1 for k in self.keywords if k.active)}개 활성)")
        return "\n".join(lines)
