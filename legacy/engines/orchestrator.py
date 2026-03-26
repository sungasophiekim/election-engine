"""
Election Strategy Engine — Strategy Orchestrator
v2: 전체 모듈 파이프라인 통합.

Pipeline:
  raw input → canonical issue mapping → news deduplication → anomaly detection
  → issue scoring → score explanation → response readiness → issue response
  → strategy mode → strategy synthesis → orchestrator output
"""
import json
import os
from datetime import datetime

import anthropic

from models.schemas import (
    IssueSignal, RawArticle, ContentDraft, ContentType,
    StrategicBrief, CrisisLevel, OpponentSignal,
)
from config.tenant_config import TenantConfig
from engines.issue_scoring    import score_multiple_signals
from engines.message_validator import validate_with_claude
from engines.voter_and_opponent import (
    calculate_voter_priorities,
    get_schedule_weights,
    analyze_opponents,
)

# v2 modules
from engines.canonical_issue_mapper import CanonicalIssueMapper
from engines.news_deduplicator      import NewsDeduplicator
from engines.anomaly_detector        import AnomalyDetector
from engines.score_explainer         import build_score_explanation
from engines.response_readiness      import ResponseReadinessScorer
from engines.issue_response          import IssueResponseEngine
from engines.strategy_mode_v2        import StrategyModeSelector
from engines.strategy_synthesizer    import StrategySynthesizer
from engines.reaction_attribution    import ReactionAttributor
from engines.leading_index_engine    import compute_leading_index
from engines.decision_logger         import log_strategy_decisions


class ElectionStrategyOrchestrator:
    """
    Election Strategy Engine 메인 오케스트레이터.
    캠프별로 독립된 인스턴스를 사용합니다 (멀티테넌트 격리).

    v2: 모든 엔진 모듈을 순차적으로 연결하는 통합 파이프라인.
    """

    def __init__(self, config: TenantConfig, anthropic_api_key: str):
        self.config = config
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)

        # v2 module instances
        self.canonical_mapper   = CanonicalIssueMapper(config)
        self.news_deduplicator  = NewsDeduplicator()
        self.anomaly_detector   = AnomalyDetector()
        self.readiness_scorer   = ResponseReadinessScorer(config)
        self.issue_response_eng = IssueResponseEngine(config)
        self.strategy_mode      = StrategyModeSelector()
        self.strategy_synth     = StrategySynthesizer(config)
        self.reaction_attributor = ReactionAttributor(
            candidate_name=config.candidate_name,
            regions=config.regions if hasattr(config, 'regions') else {},
        )

    # ── v2 핵심: 통합 파이프라인 ───────────────────────────────────
    def generate_morning_brief(
        self,
        issue_signals:  list[IssueSignal],
        opponent_data:  list[dict],
        raw_articles:   list[dict] = None,     # v2: 뉴스 원문 (dedup용)
        anomaly_data:   list[dict] = None,     # v2: 키워드별 과거 데이터
        polling_data:   dict = None,           # v2: 여론조사 데이터
        unified_signals: list = None,          # v3: UnifiedSignal 리스트 (attribution용)
        channel_metrics: list = None,          # v3: ChannelMetrics 리스트 (attribution용)
    ) -> StrategicBrief:
        """
        v2 전략 브리핑 생성 — 전체 파이프라인 실행.

        Pipeline:
          1. canonical issue mapping
          2. news deduplication
          3. anomaly detection
          4. issue scoring (with anomaly + dedup enrichment)
          5. score explanation
          6. response readiness
          7. issue response (with readiness influence)
          8. strategy mode v2
          9. strategy synthesis (with mode override)
          10. Claude 통합 브리핑
        """
        raw_articles = raw_articles or []
        anomaly_data = anomaly_data or []
        polling_data = polling_data or {}

        # ── Step 1: Canonical Issue Mapping ─────────────────────────
        keywords = [s.keyword for s in issue_signals]
        canonical_issues = self.canonical_mapper.cluster_keywords(keywords)

        # keyword → canonical_name 맵
        canonical_map = {}
        for kw in keywords:
            canonical_map[kw] = self.canonical_mapper.get_canonical_name(kw)

        # ── Step 2: News Deduplication ──────────────────────────────
        dedup_results = {}  # {keyword: {"raw_count": N, "story_count": M, "dedup_ratio": R}}
        if raw_articles:
            # 키워드별 기사 그룹핑
            keyword_articles = {}
            for article in raw_articles:
                for kw in keywords:
                    title = article.get("title", "")
                    content = article.get("content", "")
                    if kw in title or kw in content:
                        keyword_articles.setdefault(kw, []).append(article)

            for kw, articles in keyword_articles.items():
                metrics = self.news_deduplicator.get_dedup_metrics(articles)
                dedup_results[kw] = metrics

        # ── Step 3: Anomaly Detection ──────────────────────────────
        anomaly_results = []
        if anomaly_data:
            anomaly_results = self.anomaly_detector.analyze_batch(anomaly_data)
        else:
            # 기본: signal 데이터로 간이 anomaly 분석
            for sig in issue_signals:
                ar = self.anomaly_detector.analyze(
                    keyword=sig.keyword,
                    current_24h=sig.mention_count,
                    current_6h=0,
                )
                anomaly_results.append(ar)

        # anomaly map for lookup
        anomaly_map = {ar.keyword: ar for ar in anomaly_results if hasattr(ar, 'keyword')}

        # ── Step 4: Issue Scoring (enriched) ────────────────────────
        scored_issues = score_multiple_signals(
            issue_signals, self.config,
            anomaly_results=anomaly_results,
            dedup_results=dedup_results,
        )
        top_issues = scored_issues[:5]

        # 전체 위기 레벨 결정
        overall_level = CrisisLevel.NORMAL
        if top_issues:
            overall_level = top_issues[0].level

        # ── Step 5: Score Explanation ───────────────────────────────
        score_explanations = []
        for issue in top_issues:
            kw = issue.keyword
            explanation = build_score_explanation(
                keyword=kw,
                score_breakdown=issue.breakdown,
                total_score=issue.score,
                crisis_level=issue.level.name,
                raw_mentions=issue.breakdown.get("raw_article_count", 0),
                deduped_stories=issue.breakdown.get("deduped_story_count", 0),
                anomaly_result=anomaly_map.get(kw),
                canonical_name=canonical_map.get(kw, kw),
            )
            score_explanations.append(explanation)

        # ── Step 6: Response Readiness ──────────────────────────────
        readiness_scores = []
        readiness_map = {}
        for issue in top_issues:
            kw = issue.keyword
            canonical_name = canonical_map.get(kw, kw)
            # canonical issue에서 메타데이터 가져오기
            ci = self.canonical_mapper.get_canonical(kw)
            issue_type = ci.issue_type if ci else ""
            target_side = ci.target_side if ci else ""

            rdns = self.readiness_scorer.score(
                keyword=kw,
                issue_score=issue.score,
                issue_type=issue_type,
                target_side=target_side,
            )
            readiness_scores.append(rdns)
            readiness_map[kw] = rdns

        # score explanation에 readiness 반영
        for expl, rdns in zip(score_explanations, readiness_scores):
            if hasattr(expl, 'readiness_score'):
                expl.readiness_score = rdns.total_readiness
            if hasattr(expl, 'readiness_grade'):
                expl.readiness_grade = rdns.readiness_grade

        # ── Step 7: Issue Response (with readiness) ─────────────────
        issue_responses = self.issue_response_eng.analyze_all(
            top_issues, issue_signals, readiness_map=readiness_map,
        )

        # ── Step 8: Strategy Mode v2 ───────────────────────────────
        # 후보 연관 위기 이슈 체크
        candidate_name = self.config.candidate_name
        candidate_crisis = any(
            i.level == CrisisLevel.CRISIS and candidate_name in i.keyword
            for i in top_issues
        )

        # opponent_signals for mode decision
        opponent_signals_list = analyze_opponents(
            self.config, opponent_data, top_issues
        )

        # momentum from polling
        momentum = polling_data.get("momentum", "stable")
        our_trend = polling_data.get("our_trend", 0.0)
        polling_gap = polling_data.get("gap", 0.0)
        days_left = self.strategy_synth._days_until_election()

        mode_decision = self.strategy_mode.decide(
            issue_scores=top_issues,
            polling_gap=polling_gap,
            momentum=momentum,
            our_trend=our_trend,
            opponent_signals=opponent_signals_list,
            days_left=days_left,
            candidate_linked_crisis=candidate_crisis,
        )

        # ── Step 9: Strategy Synthesis (with mode override) ─────────
        schedule_weights = get_schedule_weights(self.config, top_issues)

        # DailyStrategy 생성 (strategy_synthesizer에서 mode_override 사용)
        # NOTE: synthesize의 결과는 Claude 브리핑에 추가 컨텍스트로 활용
        daily_strategy = self.strategy_synth.synthesize(
            issue_scores=top_issues,
            opponent_signals=opponent_signals_list,
            polling_data=polling_data,
            mode_override=mode_decision,
        )

        # ── Step 9.5: Reaction Attribution (v3) ─────────────────────
        unified_signals = unified_signals or []
        channel_metrics = channel_metrics or []
        attribution_data = []

        if unified_signals or channel_metrics:
            # 행동 추출: 3가지 소스
            all_actions = []
            if channel_metrics:
                all_actions.extend(
                    self.reaction_attributor.extract_actions_from_channels(channel_metrics)
                )
            all_actions.extend(
                self.reaction_attributor.extract_actions_from_strategy(daily_strategy)
            )
            # schedule_events가 DailyStrategy에 포함되어 있지 않으므로
            # daily_strategy.region_schedule에서 이미 추출됨 (extract_actions_from_strategy)

            # 귀인 매칭 (여론조사 데이터 전달)
            if all_actions and unified_signals:
                attributions = self.reaction_attributor.attribute_reactions(
                    all_actions, unified_signals,
                    polling_data=polling_data,
                )
                attr_summary = self.reaction_attributor.build_summary(
                    all_actions, attributions, unified_signals
                )
                attribution_data = attr_summary.top_attributions
                daily_strategy.attribution_summary = {
                    "total_actions": attr_summary.total_actions,
                    "attributed_count": attr_summary.attributed_count,
                    "unlinked_reactions": attr_summary.unlinked_reactions,
                    "poll_watch_regions": attr_summary.poll_watch_regions,
                    "movement_detected": attr_summary.movement_detected,
                    "strongest_linkage": attr_summary.strongest_linkage,
                }

        # ── Step 9.7: Leading Index (v4) ─────────────────────────────
        leading_index = compute_leading_index(
            issue_scores=top_issues,
            anomaly_results=anomaly_results,
            unified_signals=unified_signals,
            polling_data=polling_data,
            attribution_summary=daily_strategy.attribution_summary,
            candidate_name=self.config.candidate_name,
            opponents=self.config.opponents if hasattr(self.config, 'opponents') else [],
            issue_signals=issue_signals,
            tenant_id=self.config.tenant_id,
        )

        # ── Step 10: Claude 통합 브리핑 ─────────────────────────────
        brief_text, actions, drafts = self._call_claude_for_brief(
            top_issues, schedule_weights, opponent_signals_list,
            score_explanations=score_explanations,
            mode_decision=mode_decision,
            issue_responses=issue_responses,
            leading_index=leading_index,
        )

        # ── Step 9.9: Decision Logging (v5) ──────────────────────────
        decision_records = log_strategy_decisions(
            daily_strategy=daily_strategy,
            issue_responses=issue_responses,
            leading_index=leading_index,
            tenant_id=self.config.tenant_id,
        )
        # 저장은 호출자(대시보드)가 db.save_decisions(decision_records)로 수행
        # orchestrator는 brief에 기록만 첨부

        return StrategicBrief(
            tenant_id        = self.config.tenant_id,
            generated_at     = datetime.now(),
            top_issues       = top_issues,
            crisis_level     = overall_level,
            response_actions = actions,
            content_drafts   = drafts,
            schedule_weights = schedule_weights,
            opponent_alerts  = [s.recommended_action for s in opponent_signals_list],
            # v2 enrichment
            score_explanations = score_explanations,
            readiness_scores   = readiness_scores,
            mode_decision      = mode_decision,
            canonical_map      = canonical_map,
            issue_responses    = issue_responses,
            # v3 attribution
            attribution_data   = attribution_data,
            # v4 leading index
            leading_index      = leading_index,
            # v5 learning loop
            decision_records   = decision_records,
        )

    def _call_claude_for_brief(
        self,
        top_issues,
        schedule_weights,
        opponent_signals,
        score_explanations=None,
        mode_decision=None,
        issue_responses=None,
        leading_index=None,
    ) -> tuple[str, list[str], list[str]]:
        """Claude API로 통합 전략 브리핑 생성 (v2 enrichment 포함)"""

        issues_str = "\n".join(
            f"- [{i.level.name}] {i.keyword}: {i.score:.0f}점 (반감기 {i.estimated_halflife_hours}h)"
            for i in top_issues
        )

        top_regions = sorted(schedule_weights.items(), key=lambda x: x[1], reverse=True)[:3]
        regions_str = ", ".join(f"{r}({s:.2f})" for r, s in top_regions)

        opp_str = "\n".join(
            f"- {s.opponent_name}: 공격확률 {s.attack_prob_72h*100:.0f}% / {s.message_shift}"
            for s in opponent_signals
        )

        pledges_str = "\n".join(
            f"- {name}: {info['수치']}"
            for name, info in self.config.pledges.items()
        )

        # v2: score explanation context
        explain_str = ""
        if score_explanations:
            explain_lines = []
            for expl in score_explanations[:5]:
                line = f"- {expl.keyword}: {expl.explanation_text}"
                if hasattr(expl, 'is_anomaly') and expl.is_anomaly:
                    line += f" [이상 감지: {expl.anomaly_reason}]"
                explain_lines.append(line)
            explain_str = "\n".join(explain_lines)

        # v2: mode decision context
        mode_str = ""
        if mode_decision:
            mode_str = f"캠페인 모드: {mode_decision.mode_korean} ({mode_decision.mode}) — {mode_decision.reasoning}"

        # v2: issue response context
        response_str = ""
        if issue_responses:
            resp_lines = []
            for r in issue_responses[:5]:
                resp_lines.append(
                    f"- {r.keyword}: [{r.stance}] {r.response_message} (담당: {r.owner}, 긴급도: {r.urgency})"
                )
            response_str = "\n".join(resp_lines)

        system_prompt = f"""당신은 '{self.config.candidate_name}' 후보 ({self.config.region} {self.config.election_type})의 수석 전략 참모 AI입니다.

[후보 슬로건] {self.config.slogan}
[핵심 메시지] {self.config.core_message}
[주요 공약]
{pledges_str}
[금기사항] {', '.join(self.config.forbidden_words[:5])}

당신의 역할:
- 오늘의 이슈, 지역 우선순위, 경쟁자 동향을 종합해 캠프 운영 지시를 내립니다.
- 모든 제안은 핵심 메시지와 일관성을 유지해야 합니다.
- 검증되지 않은 수치는 절대 제시하지 않습니다.
- 반드시 JSON 형식으로만 응답합니다."""

        # v4: leading index context
        leading_str = ""
        if leading_index:
            leading_str = (
                f"선행지수: {leading_index.index:.0f}/100 ({leading_index.direction}) "
                f"— {leading_index.explanation_text}"
            )

        user_message = f"""오늘 날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}

[이슈 스코어링 결과]
{issues_str if issues_str else "특이 이슈 없음"}

[스코어 분석 (v2)]
{explain_str if explain_str else "분석 없음"}

[캠페인 모드 (v2)]
{mode_str if mode_str else "미결정"}

[이슈 대응 전략 (v2)]
{response_str if response_str else "대응 미수립"}

[선행지수 (v4)]
{leading_str if leading_str else "미산출"}

[오늘 유세 우선 지역 TOP3]
{regions_str}

[경쟁자 동향]
{opp_str if opp_str else "특이 동향 없음"}

위 정보를 바탕으로 오늘의 전략 브리핑을 작성해 주세요.
다음 JSON 형식으로만 응답하세요:

{{
  "situation_summary": "오늘 전체 상황 2~3문장 요약",
  "priority_actions": [
    "즉시 해야 할 행동 1",
    "즉시 해야 할 행동 2",
    "즉시 해야 할 행동 3"
  ],
  "press_release_draft": "오늘 유세 관련 보도자료 초안 (3~4문단)",
  "sns_draft": "X(트위터)용 오늘의 메시지 초안 (140자 내외)",
  "risk_assessment": "오늘의 주요 리스크 한 문장"
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            raw = response.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()

            data = json.loads(raw)

            actions = data.get("priority_actions", [])
            drafts  = []
            if data.get("press_release_draft"):
                drafts.append(f"[보도자료 초안]\n{data['press_release_draft']}")
            if data.get("sns_draft"):
                drafts.append(f"[SNS 초안]\n{data['sns_draft']}")
            if data.get("risk_assessment"):
                drafts.append(f"[리스크 평가]\n{data['risk_assessment']}")

            return raw, actions, drafts

        except Exception as e:
            fallback = f"Claude 브리핑 생성 실패: {str(e)}"
            return fallback, ["수동 대응 필요"], []

    # ── 콘텐츠 검증 래퍼 ─────────────────────────────────────────
    def validate_content(self, draft: ContentDraft):
        """엔진 2 래퍼 — 콘텐츠 배포 전 검증"""
        return validate_with_claude(draft, self.config, self.client)

    # ── 실시간 위기 대응 ─────────────────────────────────────────
    def handle_crisis(self, issue_signal: IssueSignal) -> dict:
        """
        위기 이슈 하나에 대한 즉각 대응 패키지 생성.
        알림 + 대응 시나리오 3가지 + 초안 문구를 한 번에 반환합니다.
        """
        from engines.issue_scoring import calculate_issue_score
        scored = calculate_issue_score(issue_signal, self.config)

        system_prompt = f"""당신은 '{self.config.candidate_name}' 후보 선거캠프의 위기대응 AI입니다.
핵심 메시지: {self.config.core_message}
금기사항: {', '.join(self.config.forbidden_words[:5])}
반드시 JSON으로만 응답합니다."""

        user_message = f"""위기 이슈 감지:
- 키워드: {issue_signal.keyword}
- 위험도: {scored.score:.0f}/100 ({scored.level.name})
- 부정 비율: {issue_signal.negative_ratio*100:.0f}%
- 방송 보도: {'예' if issue_signal.tv_reported else '아니오'}

다음 JSON으로 즉각 대응 패키지를 작성해 주세요:
{{
  "alert_message": "선대위원장에게 보낼 카카오톡 알림 문자 (3줄)",
  "scenarios": [
    {{"name": "선제 발표", "pros": "장점", "cons": "단점", "draft": "발표문 초안"}},
    {{"name": "침묵 유지", "pros": "장점", "cons": "단점", "draft": ""}},
    {{"name": "이슈 전환", "pros": "장점", "cons": "단점", "draft": "전환 메시지 초안"}}
  ],
  "recommended": "선제 발표 | 침묵 유지 | 이슈 전환 중 택일",
  "golden_time_hours": 2
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1200,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = response.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            return {"score": scored, "response_package": json.loads(raw)}
        except Exception as e:
            return {"score": scored, "error": str(e)}
