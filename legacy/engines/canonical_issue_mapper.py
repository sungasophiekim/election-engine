"""
Engine V2 — Canonical Issue Mapper
키워드 폭발을 정규화하여 동일 이슈를 하나의 canonical issue로 클러스터링.

문제:
  김경수, 김경수 경남, 김경수 강남, 김경수 강남 발언, 김경수 강남 논란
  → 모두 별개 키워드로 처리되어 스코어가 분산되고 대시보드가 오염됨

해결:
  1. 엔티티 정규화 (후보명, 지역명, 정책명 → 태그)
  2. 자카드 유사도 + 공통 엔티티 기반 클러스터링
  3. 클러스터별 대표 이름(canonical name) 자동 선정
  4. alias → canonical 매핑 테이블 유지
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IssueEntity:
    """키워드에 붙는 구조화된 메타데이터"""
    term: str
    entity_type: str          # candidate | opponent | region | policy | scandal | election
    owner_side: str           # ours | theirs | neutral
    priority: int = 3         # 1(최고) ~ 5(최저)
    region: str = ""
    aliases: list[str] = field(default_factory=list)


@dataclass
class CanonicalIssue:
    """정규화된 이슈 단위"""
    issue_id: str                     # 예: "kimgyeongsu_gangnam"
    canonical_name: str               # 대표 이름: "김경수 강남 발언"
    aliases: list[str]                # ["김경수 강남", "김경수 강남 논란", ...]
    issue_type: str                   # candidate_scandal | policy | opponent_attack | regional | general
    target_side: str                  # ours | theirs | neutral
    candidate_linked: bool = False
    region: str = ""
    entities: list[str] = field(default_factory=list)  # ["김경수", "강남"]
    created_at: str = ""
    last_seen_at: str = ""

    # 클러스터 내 키워드별 스코어 합산용
    member_scores: dict = field(default_factory=dict)  # {keyword: score}

    @property
    def aggregated_score(self) -> float:
        """클러스터 내 최고 스코어 (합산 아님 — 중복 카운팅 방지)"""
        return max(self.member_scores.values()) if self.member_scores else 0.0

    @property
    def total_mentions(self) -> int:
        """alias 전체 건수는 별도 집계 필요 — 여기서는 member 수 반환"""
        return len(self.member_scores)


class CanonicalIssueMapper:
    """
    키워드 → canonical issue 매핑 엔진.

    사용법:
        mapper = CanonicalIssueMapper(config)
        mapper.build_entity_table()
        clusters = mapper.cluster_keywords(keyword_list)
        canonical = mapper.get_canonical("김경수 강남 논란")
    """

    # 이슈 타입 판별용 접미 패턴
    SCANDAL_SUFFIXES = ["논란", "의혹", "파문", "스캔들", "폭로", "고발", "수사", "비리"]
    POLICY_SUFFIXES = ["정책", "공약", "계획", "대책", "전략", "지원", "예산", "법안"]
    ATTACK_SUFFIXES = ["비판", "공격", "반박", "맹공", "질타", "추궁"]

    def __init__(self, config):
        self.config = config
        self.entities: dict[str, IssueEntity] = {}
        self.canonical_map: dict[str, str] = {}          # keyword → issue_id
        self.issues: dict[str, CanonicalIssue] = {}      # issue_id → CanonicalIssue
        self._build_entity_table()

    def _build_entity_table(self):
        """config 기반으로 엔티티 정규화 테이블 구축"""
        cfg = self.config

        # 후보
        self.entities[cfg.candidate_name] = IssueEntity(
            term=cfg.candidate_name, entity_type="candidate",
            owner_side="ours", priority=1,
            aliases=self._name_variants(cfg.candidate_name),
        )

        # 상대 후보
        for opp in cfg.opponents:
            name = opp if isinstance(opp, str) else opp.get("name", opp)
            self.entities[name] = IssueEntity(
                term=name, entity_type="opponent",
                owner_side="theirs", priority=1,
                aliases=self._name_variants(name),
            )

        # 지역
        for region_name in (cfg.regions or {}):
            self.entities[region_name] = IssueEntity(
                term=region_name, entity_type="region",
                owner_side="neutral", priority=2, region=region_name,
            )

        # 정책/공약
        for pledge_name in (cfg.pledges or {}):
            self.entities[pledge_name] = IssueEntity(
                term=pledge_name, entity_type="policy",
                owner_side="ours", priority=2,
            )

    def _name_variants(self, name: str) -> list[str]:
        """이름의 변형 생성 (성만, 성+이름 등)"""
        variants = [name]
        if len(name) >= 3:
            variants.append(name[0] + name[2])  # 성 + 끝글자: 김수
            variants.append(name[:2])            # 성 + 첫이름: 김경
        return variants

    def _extract_entities(self, keyword: str) -> list[str]:
        """키워드에서 알려진 엔티티를 추출"""
        found = []
        for entity_name, entity in self.entities.items():
            all_forms = [entity_name] + entity.aliases
            for form in all_forms:
                if form in keyword:
                    found.append(entity_name)
                    break
        return found

    def _determine_issue_type(self, keyword: str, entities: list[str]) -> str:
        """키워드 + 엔티티로 이슈 타입 결정"""
        has_candidate = any(
            self.entities[e].entity_type == "candidate" for e in entities if e in self.entities
        )
        has_opponent = any(
            self.entities[e].entity_type == "opponent" for e in entities if e in self.entities
        )

        for suffix in self.SCANDAL_SUFFIXES:
            if suffix in keyword:
                if has_candidate:
                    return "candidate_scandal"
                if has_opponent:
                    return "opponent_scandal"
                return "general_scandal"

        for suffix in self.ATTACK_SUFFIXES:
            if suffix in keyword:
                return "opponent_attack" if has_opponent else "political_attack"

        for suffix in self.POLICY_SUFFIXES:
            if suffix in keyword:
                return "policy"

        has_region = any(
            self.entities[e].entity_type == "region" for e in entities if e in self.entities
        )
        if has_region:
            return "regional"

        return "general"

    def _determine_target_side(self, entities: list[str]) -> str:
        """이슈가 우리/상대/중립 중 누구에 관한 것인지"""
        sides = set()
        for e in entities:
            if e in self.entities:
                sides.add(self.entities[e].owner_side)
        if "ours" in sides and "theirs" not in sides:
            return "ours"
        if "theirs" in sides and "ours" not in sides:
            return "theirs"
        if "ours" in sides and "theirs" in sides:
            return "both"
        return "neutral"

    def _jaccard_similarity(self, a: str, b: str) -> float:
        """두 키워드의 자카드 유사도 (음절 기반)"""
        set_a = set(a.replace(" ", ""))
        set_b = set(b.replace(" ", ""))
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)

    def _entity_overlap(self, ent_a: list[str], ent_b: list[str]) -> float:
        """두 엔티티 리스트의 겹침 비율"""
        if not ent_a or not ent_b:
            return 0.0
        set_a, set_b = set(ent_a), set(ent_b)
        return len(set_a & set_b) / len(set_a | set_b)

    def _should_merge(self, kw_a: str, kw_b: str, ent_a: list[str], ent_b: list[str]) -> bool:
        """두 키워드를 같은 이슈로 클러스터링할지 결정"""
        # 한쪽이 다른쪽을 포함하면 (서브스트링) → 병합
        if kw_a in kw_b or kw_b in kw_a:
            return True

        # 엔티티 완전 일치 + 자카드 0.4 이상 → 병합
        ent_overlap = self._entity_overlap(ent_a, ent_b)
        jac = self._jaccard_similarity(kw_a, kw_b)

        if ent_overlap >= 1.0 and jac >= 0.3:
            return True
        if ent_overlap >= 0.5 and jac >= 0.5:
            return True

        return False

    def _choose_canonical_name(self, keywords: list[str]) -> str:
        """클러스터 내에서 대표 이름 선택 — 가장 짧고 구체적인 것"""
        # 2어절 이상이면서 가장 짧은 것 우선
        multi_word = [kw for kw in keywords if " " in kw]
        if multi_word:
            return min(multi_word, key=len)
        return min(keywords, key=len)

    def _make_issue_id(self, canonical_name: str) -> str:
        """canonical name → 안전한 issue_id"""
        return canonical_name.replace(" ", "_").replace("/", "_")[:50]

    def cluster_keywords(self, keywords: list[str]) -> list[CanonicalIssue]:
        """
        키워드 리스트를 canonical issue 클러스터로 변환.

        Returns: CanonicalIssue 리스트 (deduplicated)
        """
        # 1. 각 키워드의 엔티티 추출
        kw_entities = {}
        for kw in keywords:
            kw_entities[kw] = self._extract_entities(kw)

        # 2. 그리디 클러스터링
        clusters: list[list[str]] = []
        assigned = set()

        # 우선순위 정렬: 짧은 키워드(=핵심어)가 먼저 클러스터 시드
        sorted_kws = sorted(keywords, key=len)

        for kw in sorted_kws:
            if kw in assigned:
                continue

            # 기존 클러스터에 병합 가능한지 확인
            merged = False
            for cluster in clusters:
                seed = cluster[0]
                if self._should_merge(kw, seed, kw_entities[kw], kw_entities[seed]):
                    cluster.append(kw)
                    assigned.add(kw)
                    merged = True
                    break

            if not merged:
                clusters.append([kw])
                assigned.add(kw)

        # 3. CanonicalIssue 생성
        self.issues.clear()
        self.canonical_map.clear()

        results = []
        for cluster in clusters:
            canonical_name = self._choose_canonical_name(cluster)
            issue_id = self._make_issue_id(canonical_name)

            all_entities = set()
            for kw in cluster:
                all_entities.update(kw_entities[kw])
            entities = list(all_entities)

            issue_type = self._determine_issue_type(canonical_name, entities)
            target_side = self._determine_target_side(entities)
            candidate_linked = any(
                self.entities[e].entity_type == "candidate"
                for e in entities if e in self.entities
            )

            issue = CanonicalIssue(
                issue_id=issue_id,
                canonical_name=canonical_name,
                aliases=cluster,
                issue_type=issue_type,
                target_side=target_side,
                candidate_linked=candidate_linked,
                entities=entities,
            )

            self.issues[issue_id] = issue
            for kw in cluster:
                self.canonical_map[kw] = issue_id

            results.append(issue)

        return results

    def get_canonical(self, keyword: str) -> Optional[CanonicalIssue]:
        """키워드 → 소속 canonical issue 반환"""
        issue_id = self.canonical_map.get(keyword)
        if issue_id:
            return self.issues.get(issue_id)
        return None

    def get_canonical_name(self, keyword: str) -> str:
        """키워드 → canonical name. 매핑 없으면 원본 반환."""
        issue = self.get_canonical(keyword)
        return issue.canonical_name if issue else keyword

    def merge_scores_by_canonical(self, keyword_scores: dict[str, float]) -> dict[str, float]:
        """
        {keyword: score} → {canonical_name: max_score}
        동일 이슈의 키워드 변형들을 하나로 합산.
        """
        canonical_scores: dict[str, float] = {}
        for kw, score in keyword_scores.items():
            cname = self.get_canonical_name(kw)
            if cname in canonical_scores:
                canonical_scores[cname] = max(canonical_scores[cname], score)
            else:
                canonical_scores[cname] = score
        return canonical_scores
