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


# ── 테스트 ───────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

    from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
    engine = KeywordEngine(SAMPLE_GYEONGNAM_CONFIG)

    print("=== Seed 키워드 ===")
    print(f"총 {len(engine.keywords)}개")
    for k in engine.keywords:
        print(f"  P{k.priority} [{k.category}] {k.keyword}")

    print(f"\n=== 키워드 자동 발굴 실행 ===")
    discovered = engine.discover()
    print(f"발굴 후 총 {len(engine.keywords)}개")

    print(f"\n{engine.format_report()}")
