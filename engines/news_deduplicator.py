"""
Engine V2 — News Deduplication Layer
제목 유사도 기반으로 중복/통신사 전재 기사를 클러스터링.

문제:
  "김경수 경남도지사 출마 선언" 이 연합뉴스 원문 1건 → 30개 매체 전재
  → mention_count 30으로 부풀어 스코어 오염

해결:
  1. 제목 정규화 (공백, 특수문자, 기자명 제거)
  2. 제목 n-gram 유사도로 스토리 클러스터링
  3. raw_mentions vs deduped_story_count 이중 출력
  4. 대시보드에서 "82건 (19개 스토리)" 형태로 표시 가능
"""
import re
from dataclasses import dataclass, field


@dataclass
class NewsStory:
    """중복 제거된 뉴스 스토리 단위"""
    story_id: int
    representative_title: str     # 클러스터 대표 제목
    representative_source: str    # 최고 티어 출처
    articles: list[dict] = field(default_factory=list)  # 원본 기사 리스트
    best_media_tier: int = 3
    first_seen: str = ""
    last_seen: str = ""

    @property
    def article_count(self) -> int:
        return len(self.articles)

    @property
    def sources(self) -> list[str]:
        return list(set(a.get("source", "") for a in self.articles))


class NewsDeduplicator:
    """
    제목 유사도 기반 뉴스 중복 제거기.

    사용법:
        dedup = NewsDeduplicator()
        stories = dedup.deduplicate(articles)
        print(f"{len(articles)}건 → {len(stories)}개 스토리")
    """

    # 제거할 패턴: 기자명, 사진, 영상, 종합 등
    NOISE_PATTERNS = [
        r"\[.*?\]",           # [종합], [속보], [사진], [영상]
        r"\(.*?기자\)",        # (홍길동 기자)
        r"기자$",
        r"…$", r"\.\.\.$",
        r"[^\w\s가-힣]",      # 특수문자
    ]

    # 미디어 티어 매핑
    TIER1_SOURCES = {
        "KBS", "SBS", "MBC", "JTBC", "YTN", "TV조선", "채널A", "MBN",
        "조선일보", "동아일보", "중앙일보", "한겨레", "경향신문",
        "연합뉴스", "뉴시스", "뉴스1",
    }
    TIER2_SOURCES = {
        "오마이뉴스", "뉴스타파", "머니투데이", "이데일리", "매일경제",
        "한국경제", "서울경제", "아시아경제", "파이낸셜뉴스",
    }

    def __init__(self, similarity_threshold: float = 0.6):
        self.threshold = similarity_threshold

    def _normalize_title(self, title: str) -> str:
        """제목 정규화: 노이즈 제거 + 공백 통일"""
        t = title.strip()
        for pattern in self.NOISE_PATTERNS:
            t = re.sub(pattern, "", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _get_media_tier(self, source: str) -> int:
        """출처 → 미디어 티어"""
        for s in self.TIER1_SOURCES:
            if s in source:
                return 1
        for s in self.TIER2_SOURCES:
            if s in source:
                return 2
        return 3

    def _char_ngrams(self, text: str, n: int = 3) -> set[str]:
        """문자 n-gram 집합 생성"""
        text = text.replace(" ", "")
        if len(text) < n:
            return {text}
        return {text[i:i+n] for i in range(len(text) - n + 1)}

    def _title_similarity(self, a: str, b: str) -> float:
        """두 정규화 제목의 n-gram 자카드 유사도"""
        ngrams_a = self._char_ngrams(a)
        ngrams_b = self._char_ngrams(b)
        if not ngrams_a or not ngrams_b:
            return 0.0
        intersection = ngrams_a & ngrams_b
        union = ngrams_a | ngrams_b
        return len(intersection) / len(union)

    def deduplicate(self, articles: list[dict]) -> list[NewsStory]:
        """
        기사 리스트 → 중복 제거된 스토리 리스트.

        각 기사는 최소 {"title": str} 필요.
        선택: {"source": str, "published": str, "url": str}

        Returns:
            NewsStory 리스트 (스토리별로 원본 기사 그룹핑)
        """
        if not articles:
            return []

        # 1. 정규화
        normalized = []
        for art in articles:
            norm_title = self._normalize_title(art.get("title", ""))
            if len(norm_title) < 5:  # 너무 짧으면 스킵
                continue
            normalized.append({
                "original": art,
                "norm_title": norm_title,
                "tier": self._get_media_tier(art.get("source", "")),
            })

        # 2. 그리디 클러스터링 (O(n²) — 300건 이하에서 충분히 빠름)
        clusters: list[list[dict]] = []
        assigned = set()

        for i, item in enumerate(normalized):
            if i in assigned:
                continue

            cluster = [item]
            assigned.add(i)

            for j in range(i + 1, len(normalized)):
                if j in assigned:
                    continue
                sim = self._title_similarity(item["norm_title"], normalized[j]["norm_title"])
                if sim >= self.threshold:
                    cluster.append(normalized[j])
                    assigned.add(j)

            clusters.append(cluster)

        # 3. NewsStory 생성
        stories = []
        for sid, cluster in enumerate(clusters):
            # 대표 기사: 가장 높은 미디어 티어 → 그 중 가장 긴 제목
            cluster.sort(key=lambda x: (x["tier"], -len(x["norm_title"])))
            rep = cluster[0]

            story = NewsStory(
                story_id=sid,
                representative_title=rep["original"].get("title", rep["norm_title"]),
                representative_source=rep["original"].get("source", ""),
                articles=[c["original"] for c in cluster],
                best_media_tier=rep["tier"],
                first_seen=min(
                    (c["original"].get("published", "") for c in cluster),
                    default="",
                ),
                last_seen=max(
                    (c["original"].get("published", "") for c in cluster),
                    default="",
                ),
            )
            stories.append(story)

        return stories

    def get_dedup_metrics(self, articles: list[dict]) -> dict:
        """
        중복 제거 메트릭 반환.

        Returns:
            {
                "raw_mentions": 82,
                "deduped_story_count": 19,
                "dedup_ratio": 0.23,
                "stories": [NewsStory, ...]
            }
        """
        stories = self.deduplicate(articles)
        raw = len(articles)
        deduped = len(stories)
        return {
            "raw_mentions": raw,
            "deduped_story_count": deduped,
            "dedup_ratio": deduped / raw if raw > 0 else 0,
            "stories": stories,
        }
