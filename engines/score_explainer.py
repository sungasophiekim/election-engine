"""
Engine V2 — Score Explanation Object
대시보드가 "왜 이 이슈가 82점인가?"를 설명할 수 있도록
스코어의 모든 구성요소를 구조화.

기존 issue_scoring.py의 breakdown dict를 확장하여:
1. 각 컴포넌트의 절대값 + 최대값 대비 비율
2. 가장 큰 기여 요인 자동 식별
3. 사람이 읽을 수 있는 설명문 자동 생성
4. anomaly / dedup 결과 통합
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScoreComponent:
    """개별 스코어 구성요소"""
    name: str              # "velocity", "mention", "media", "candidate_bonus", ...
    value: float           # 실제 점수 기여분
    max_possible: float    # 이 컴포넌트의 최대 가능값
    raw_input: float = 0   # 원본 입력값 (건수, 비율 등)
    explanation: str = ""  # "24시간 91건 — 기저선 16건 대비 5.7배"

    @property
    def contribution_pct(self) -> float:
        """최대값 대비 기여 비율"""
        return (self.value / self.max_possible * 100) if self.max_possible > 0 else 0


@dataclass
class ScoreExplanation:
    """이슈 스코어 설명 객체"""
    keyword: str
    canonical_issue: str = ""         # canonical issue mapper의 정규화된 이름
    total_score: float = 0.0
    crisis_level: str = "NORMAL"

    # 구성요소 분해
    components: list[ScoreComponent] = field(default_factory=list)

    # 뉴스 중복 제거
    raw_mentions: int = 0
    deduped_story_count: int = 0

    # 이상치 탐지
    surprise_score: float = 0.0
    z_score: float = 0.0
    is_anomaly: bool = False
    anomaly_reason: str = ""

    # 대응 준비도
    readiness_score: float = 0.0
    readiness_grade: str = ""

    # 자동 생성 설명
    primary_driver: str = ""          # 가장 큰 기여 요인
    explanation_text: str = ""        # 1-2문장 설명

    # 감성 (2단계)
    sentiment_polarity: str = ""      # positive | negative | neutral | mixed
    sentiment_target: str = ""        # ours | theirs | neutral
    sentiment_impact: str = ""        # helps_us | hurts_us | neutral
    sentiment_source: str = ""        # lexicon | claude | hybrid

    def build_explanation(self):
        """컴포넌트 기반으로 설명문 자동 생성"""
        if not self.components:
            return

        # 가장 큰 기여 요인 찾기
        sorted_comp = sorted(self.components, key=lambda c: c.value, reverse=True)
        top = sorted_comp[0]
        self.primary_driver = top.name

        # 설명문 생성
        parts = []

        # 왜 높은가?
        for c in sorted_comp[:3]:
            if c.value > 0:
                parts.append(f"{c.name}: {c.value:.0f}점")

        score_text = f"총 {self.total_score:.0f}점 ({self.crisis_level})"
        driver_text = f"주요인: {top.explanation}" if top.explanation else f"주요인: {top.name} {top.value:.0f}점"

        # 이상치 정보
        anomaly_text = ""
        if self.is_anomaly:
            anomaly_text = f" | 이상 탐지: {self.anomaly_reason}"

        # 중복 제거 정보
        dedup_text = ""
        if self.raw_mentions > 0 and self.deduped_story_count > 0:
            dedup_text = f" | {self.raw_mentions}건 중 {self.deduped_story_count}개 고유 스토리"

        self.explanation_text = f"{score_text}. {driver_text}.{anomaly_text}{dedup_text}"

    def to_dict(self) -> dict:
        """대시보드/API 전달용 dict"""
        return {
            "keyword": self.keyword,
            "canonical_issue": self.canonical_issue,
            "score": round(self.total_score, 1),
            "level": self.crisis_level,
            "components": {c.name: round(c.value, 1) for c in self.components},
            "component_details": [
                {
                    "name": c.name,
                    "value": round(c.value, 1),
                    "max": round(c.max_possible, 1),
                    "pct": round(c.contribution_pct, 0),
                    "input": c.raw_input,
                    "explanation": c.explanation,
                }
                for c in sorted(self.components, key=lambda x: x.value, reverse=True)
            ],
            "raw_mentions": self.raw_mentions,
            "deduped_stories": self.deduped_story_count,
            "surprise_score": round(self.surprise_score, 1),
            "is_anomaly": self.is_anomaly,
            "anomaly_reason": self.anomaly_reason,
            "readiness": round(self.readiness_score, 0),
            "readiness_grade": self.readiness_grade,
            "primary_driver": self.primary_driver,
            "explanation": self.explanation_text,
            "sentiment": {
                "polarity": self.sentiment_polarity,
                "target": self.sentiment_target,
                "impact": self.sentiment_impact,
                "source": self.sentiment_source,
            },
        }


def build_score_explanation(
    keyword: str,
    score_breakdown: dict,
    total_score: float,
    crisis_level: str,
    raw_mentions: int = 0,
    deduped_stories: int = 0,
    anomaly_result=None,
    readiness_result=None,
    canonical_name: str = "",
    sentiment_data: dict = None,
) -> ScoreExplanation:
    """
    기존 issue_scoring breakdown + 새 모듈 결과를 통합하여
    ScoreExplanation 생성.
    """
    exp = ScoreExplanation(
        keyword=keyword,
        canonical_issue=canonical_name or keyword,
        total_score=total_score,
        crisis_level=crisis_level,
        raw_mentions=raw_mentions,
        deduped_story_count=deduped_stories,
    )

    # 기존 breakdown → ScoreComponent 변환
    component_defs = {
        "velocity_score":  ("velocity", 25, "언급 증가 속도"),
        "mention_score":   ("mention", 25, "24시간 언급량"),
        "media_score":     ("media", 10, "미디어 등급"),
        "proximity_bonus": ("election_proximity", 10, "선거 근접도"),
    }

    for key, (name, max_val, desc) in component_defs.items():
        val = score_breakdown.get(key, 0)
        if val > 0:
            exp.components.append(ScoreComponent(
                name=name, value=val, max_possible=max_val,
                explanation=f"{desc} {val:.0f}/{max_val}",
            ))

    # 보너스 분해
    bonus = score_breakdown.get("bonus", 0)
    if bonus > 0:
        # 개별 보너스 추적 (breakdown에 상세가 없으면 합산으로)
        exp.components.append(ScoreComponent(
            name="bonus", value=bonus, max_possible=40,
            explanation=f"후보연결/트렌딩/방송 가산 {bonus:.0f}점",
        ))

    # anomaly 통합
    if anomaly_result:
        exp.surprise_score = anomaly_result.surprise_score
        exp.z_score = anomaly_result.z_score
        exp.is_anomaly = anomaly_result.is_anomaly
        exp.anomaly_reason = anomaly_result.anomaly_reason

    # readiness 통합
    if readiness_result:
        exp.readiness_score = readiness_result.total_readiness
        exp.readiness_grade = readiness_result.readiness_grade

    # sentiment 통합
    if sentiment_data:
        exp.sentiment_polarity = sentiment_data.get("polarity", "")
        exp.sentiment_target = sentiment_data.get("target", "")
        exp.sentiment_impact = sentiment_data.get("impact", "")
        exp.sentiment_source = sentiment_data.get("source", "lexicon")

    exp.build_explanation()
    return exp
