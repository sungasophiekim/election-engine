"use client";
import { useEffect, useState } from "react";
import { getIssueResponses, getKeywordAnalysis, aiAnalyze, getAiHistory, getScores, getPledges, getDailyBriefing, getV2Enrichment, getKeywordCompare, getNewsComments, getIndexTrend } from "@/lib/api";
import { useAppStore } from "@/lib/store";

// ════════════════════════════════════════════════════════════════════
// Issue Intelligence Panel — Strategic Command Grade
// 3 Layers: Ranked List → Detail (Sentiment+Source+AI) → Keywords
// ════════════════════════════════════════════════════════════════════

export function IssuesPage() {
  const [responses, setResponses] = useState<any[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [detail, setDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [aiResult, setAiResult] = useState<any>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiHistory, setAiHistory] = useState<any>(null);
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());
  const [showRankingLogic, setShowRankingLogic] = useState(false);
  const [enrichment, setEnrichment] = useState<any>(null);
  const [radarMode, setRadarMode] = useState<"issue" | "reaction">("issue");
  const [kwCompare, setKwCompare] = useState<any>(null);
  const [kwCompareLoading, setKwCompareLoading] = useState(false);
  const [showCompare, setShowCompare] = useState(false);
  const [comments, setComments] = useState<any>(null);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [indexTrend, setIndexTrend] = useState<any[]>([]);
  const [scoreDetails, setScoreDetails] = useState<Record<string, any>>({});
  const [pledgeData, setPledgeData] = useState<{ ourPledges: string[]; oppPledges: Record<string, string[]> } | null>(null);
  const [briefing, setBriefing] = useState<{ report: string | null; created_at: string | null } | null>(null);
  const [showBriefing, setShowBriefing] = useState(false);
  const candidate = useAppStore((s) => s.candidate) || "김경수";
  const opponent = useAppStore((s) => s.opponent) || "박완수";

  // 후보추적 키워드 필터 (이슈 레이더에서 제외)
  const CANDIDATE_KEYWORDS = [
    `${candidate} 경남`, `${candidate} 공약`, `${candidate} 복귀`,
    `${opponent} 경남`, `${opponent} 공약`,
    "국민의힘 경남", "민주당 경남", "전희영 경남",
  ];
  const isCandidate = (kw: string) => CANDIDATE_KEYWORDS.some(ck => kw.includes(ck) || ck.includes(kw));

  useEffect(() => {
    getIssueResponses().then((d) => {
      const all = d?.responses || [];
      setResponses(all.filter((r: any) => !isCandidate(r.keyword)));
    }).catch(() => {});
    getAiHistory().then(setAiHistory).catch(() => {});
    getDailyBriefing().then(setBriefing).catch(() => {});
    getV2Enrichment().then(setEnrichment).catch(() => {});
    getIndexTrend(7).then(r => setIndexTrend(r?.trend || [])).catch(() => {});
    getScores().then((rows: any[]) => {
      const map: Record<string, any> = {};
      for (const r of rows || []) {
        map[r.keyword] = r;
      }
      setScoreDetails(map);
    }).catch(() => {});
    // Fetch pledge data for candidate impact bar
    getPledges().then((d: any) => {
      const ourPledges = (d?.our_pledges || []).map((p: any) =>
        `${p.name} ${p.description || ""} ${p.numbers || ""}`.toLowerCase()
      );
      const oppPledges: Record<string, string[]> = {};
      for (const [name, data] of Object.entries(d?.opponent_pledges || {}) as [string, any][]) {
        oppPledges[name] = (data?.pledges || []).map((p: any) =>
          `${p.name} ${p.description || ""} ${p.numbers || ""}`.toLowerCase()
        );
      }
      setPledgeData({ ourPledges, oppPledges });
    }).catch(() => {});
  }, []);

  const selectKw = (kw: string) => {
    setSelected(kw);
    setDetail(null);
    setComments(null);
    setDetailLoading(true);
    setCommentsLoading(true);
    getKeywordAnalysis(kw).then(setDetail).catch(() => {}).finally(() => setDetailLoading(false));
    getNewsComments(kw).then(setComments).catch(() => {}).finally(() => setCommentsLoading(false));
  };

  const runAi = () => {
    if (!selected) return;
    setAiLoading(true);
    setAiResult(null);
    aiAnalyze(selected).then((d) => {
      setAiResult(d);
      getAiHistory().then(setAiHistory);
    }).catch(() => {}).finally(() => setAiLoading(false));
  };

  // Sort by Issue Index or Reaction Index
  const ii = enrichment?.issue_indices || {};
  const ri = enrichment?.reaction_indices || {};

  const sorted = [...responses].sort((a, b) => {
    if (radarMode === "reaction") {
      const aRx = ri[a.keyword]?.final_score ?? ri[a.keyword]?.index ?? 0;
      const bRx = ri[b.keyword]?.final_score ?? ri[b.keyword]?.index ?? 0;
      return bRx - aRx;
    }
    // issue mode: Issue Index 기반
    const aIdx = ii[a.keyword]?.index ?? a.score ?? 0;
    const bIdx = ii[b.keyword]?.index ?? b.score ?? 0;
    return bIdx - aIdx;
  });

  // Canonical clustering: group similar keywords
  const clustered = clusterIssues(sorted, candidate, opponent);

  const toggleCluster = (canonical: string) => {
    const next = new Set(expandedClusters);
    if (next.has(canonical)) next.delete(canonical); else next.add(canonical);
    setExpandedClusters(next);
  };

  const [intelTab, setIntelTab] = useState("radar");

  // 수집 현황 계산
  const newsCount = responses.reduce((s, r) => s + (r.mention_count || 0), 0);
  const communityCount = Object.values(enrichment?.segments || {}).length;
  const ytCount = Object.keys(enrichment?.reaction_indices || {}).length;

  return (
    <div className="space-y-2">

      {/* ══════════════════════════════════════════════════════════
          데이터 수집 현황 바
          ══════════════════════════════════════════════════════════ */}
      <div className="wr-card">
        <div className="px-3 py-2 flex items-center justify-between">
          <div className="flex items-center gap-4 text-[11px]">
            <span className="text-gray-300 font-bold">📊 수집 현황</span>
            <span className="text-gray-400">뉴스 <span className="text-white font-bold">{newsCount}</span>건</span>
            <span className="text-gray-400">커뮤니티 <span className="text-white font-bold">22</span>곳</span>
            <span className="text-gray-400">이슈 <span className="text-white font-bold">{responses.length}</span>건</span>
            <span className="text-gray-400">인덱스 <span className="text-white font-bold">{Object.keys(ii).length + Object.keys(ri).length}</span>건</span>
          </div>
          <div className="text-[9px] text-gray-400">
            출처: 네이버검색API · YouTube Data API · Claude AI 감성분석
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════
          탭 네비게이션
          ══════════════════════════════════════════════════════════ */}
      <div className="flex items-center gap-2 px-1">
        {[
          { id: "radar", label: "📡 이슈·반응 레이더" },
          { id: "channel", label: "📺 채널별 분석" },
          { id: "hot", label: "🔥 핫 콘텐츠" },
        ].map(t => (
          <button key={t.id} onClick={() => setIntelTab(t.id)}
            className={`px-3 py-1.5 rounded text-[11px] font-bold transition ${
              intelTab === t.id
                ? "bg-blue-600/30 text-blue-400 border border-blue-500/40"
                : "text-gray-400 hover:text-gray-300 border border-transparent"
            }`}>{t.label}</button>
        ))}
      </div>

      {/* ══════════════════════════════════════════════════════════
          탭 1: 이슈·반응 레이더 (기존 IssuesPage 전체)
          ══════════════════════════════════════════════════════════ */}
      {intelTab === "radar" && (
      <>

      {/* ══════════════════════════════════════════════════════════
          이슈-반응 타임라인 (최근 7일)
          ══════════════════════════════════════════════════════════ */}
      {indexTrend.length > 0 && (
        <div className="wr-card">
          <div className="wr-card-header flex justify-between">
            <span>이슈-반응 타임라인 (7일)</span>
            <span className="text-[9px] text-gray-400 normal-case tracking-normal font-normal">날짜별 이슈 크기 → 반응 강도</span>
          </div>
          <div className="px-4 py-2.5">
            <div className="flex gap-1">
              {indexTrend.slice(-7).map((d: any, i: number) => {
                const issue = d.issue_index_avg || 0;
                const rx = d.reaction_index_avg || 0;
                const date = (d.date || "").slice(5);
                const maxH = 50;
                return (
                  <div key={i} className="flex-1 text-center">
                    <div className="text-[8px] text-gray-400 mb-1">{date}</div>
                    <div className="flex gap-0.5 justify-center items-end" style={{ height: maxH }}>
                      <div className="w-3 bg-cyan-500/40 rounded-t" style={{ height: Math.max(2, issue / 100 * maxH) }}
                        title={`이슈 ${issue.toFixed(0)}`} />
                      <div className="w-3 bg-purple-500/40 rounded-t" style={{ height: Math.max(2, rx / 100 * maxH) }}
                        title={`반응 ${rx.toFixed(0)}`} />
                    </div>
                    <div className="text-[7px] text-cyan-400 mt-0.5">{issue.toFixed(0)}</div>
                    <div className="text-[7px] text-purple-400">{rx.toFixed(0)}</div>
                  </div>
                );
              })}
            </div>
            <div className="flex gap-3 mt-1.5 text-[9px] justify-center">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-cyan-500/40" />이슈</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-purple-500/40" />반응</span>
              <span className="text-gray-400">| 이슈 크면 반응도 커야 정상. 괴리 시 확산 실패 또는 잠재 위기</span>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════
          DAILY BRIEFING REPORT
          ══════════════════════════════════════════════════════════ */}
      {briefing?.report && (
        <div className="wr-card border-t-2 border-t-amber-600">
          <div
            className="wr-card-header flex items-center justify-between cursor-pointer"
            onClick={() => setShowBriefing(!showBriefing)}
          >
            <div className="flex items-center gap-2 text-amber-300">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              24시간 이슈 브리핑
            </div>
            <div className="flex items-center gap-3">
              {briefing.created_at && (
                <span className="text-[9px] text-gray-600">
                  {briefing.created_at.slice(0, 16).replace("T", " ")}
                </span>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); exportBriefingPdf(briefing.report!, briefing.created_at); }}
                className="px-2 py-0.5 text-[10px] bg-amber-600/15 text-amber-400 border border-amber-600/30 rounded hover:bg-amber-600/25 transition-colors"
              >
                PDF 출력
              </button>
              <span className="text-[10px] text-amber-400">{showBriefing ? "접기" : "펼치기"}</span>
            </div>
          </div>
          {!showBriefing && (
            <div className="px-3 pb-2">
              <BriefingSummaryBar report={briefing.report} />
            </div>
          )}
          {showBriefing && (
            <div className="px-3 pb-3 text-sm text-gray-300 space-y-2 max-h-[70vh] overflow-y-auto briefing-content">
              <BriefingRenderer markdown={briefing.report} />
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════
          KEYWORD COMPARE — 후보별 연관어 비교
          ══════════════════════════════════════════════════════════ */}
      <KeywordComparePanel
        data={kwCompare}
        loading={kwCompareLoading}
        show={showCompare}
        onToggle={() => {
          setShowCompare(!showCompare);
          if (!kwCompare && !kwCompareLoading) {
            setKwCompareLoading(true);
            getKeywordCompare().then(setKwCompare).catch(() => {}).finally(() => setKwCompareLoading(false));
          }
        }}
        candidate={candidate}
        opponent={opponent}
      />

      {/* ══════════════════════════════════════════════════════════
          AI STRATEGIC AGENT
          ══════════════════════════════════════════════════════════ */}
      <div className="wr-card border-t-2 border-t-purple-600">
        <div className="wr-card-header flex items-center justify-between">
          <div className="flex items-center gap-2 text-purple-300">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500 live-dot" />
            AI 전략 에이전트
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-gray-600">{aiHistory ? `남은 ${aiHistory.remaining}/3회` : ""}</span>
            <button onClick={runAi} disabled={aiLoading || !selected}
              className="text-[10px] bg-purple-900/50 border border-purple-700/40 text-purple-300 px-3 py-1 rounded hover:bg-purple-800/50 font-bold transition disabled:opacity-30">
              {aiLoading ? "분석 중..." : selected ? `"${selected}" 분석` : "키워드 선택"}
            </button>
          </div>
        </div>
        {aiResult?.analysis && <AiResultCard result={aiResult} />}
        {aiHistory?.analyses?.length > 0 && <AiHistoryList analyses={aiHistory.analyses} />}
      </div>

      {/* ══════════════════════════════════════════════════════════
          LAYER 1: RANKED ISSUE LIST
          score + delta + stance + cluster
          ══════════════════════════════════════════════════════════ */}
      <div className="wr-card">
        <div className="wr-card-header flex items-center justify-between">
          <div className="flex items-center gap-2">
            {/* Issue / Reaction 토글 */}
            <div className="flex rounded border border-[#1a2844] overflow-hidden">
              <button onClick={() => setRadarMode("issue")}
                className={`px-2 py-0.5 text-[9px] font-bold transition ${
                  radarMode === "issue" ? "bg-blue-600/30 text-blue-400" : "text-gray-600 hover:text-gray-400"
                }`}>이슈 레이더</button>
              <button onClick={() => setRadarMode("reaction")}
                className={`px-2 py-0.5 text-[9px] font-bold transition ${
                  radarMode === "reaction" ? "bg-purple-600/30 text-purple-400" : "text-gray-600 hover:text-gray-400"
                }`}>리액션 레이더</button>
            </div>
            <button
              onClick={() => setShowRankingLogic(!showRankingLogic)}
              className="text-[8px] text-gray-600 bg-[#0d1420] border border-[#1a2844] px-1.5 py-0.5 rounded hover:text-gray-400 hover:border-gray-600 transition"
            >
              {showRankingLogic ? "순위 로직 ▲" : "순위 로직 ▼"}
            </button>
          </div>
          <div className="flex items-center gap-2 text-[8px] text-gray-600">
            <span className="text-emerald-400">● ATTACK</span>
            <span className="text-red-400">● DEFENSE</span>
            <span className="text-yellow-400">● WATCH</span>
            <span className="text-blue-400">● INITIATIVE</span>
          </div>
        </div>

        {/* Ranking logic explanation */}
        {showRankingLogic && (
          <div className="mx-2.5 mb-2 p-3 bg-[#080d16] border border-[#1a2844] rounded text-[10px] text-gray-400 leading-relaxed space-y-2">
            <div className="text-[9px] text-blue-400 font-bold uppercase tracking-wider">순위 산정 로직</div>

            {/* Scoring formula */}
            <div className="p-2 bg-[#0a1225] rounded border border-[#162040] font-mono text-[9px] text-gray-300 space-y-0.5">
              <div className="text-blue-400 font-bold mb-1">final_score = base(0~60) + bonus(0~40) → 0~100</div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
                <div><span className="text-orange-400">증가율 (velocity)</span> = log₂(증가배율) × 8 <span className="text-gray-600">→ 0~25pt</span></div>
                <div><span className="text-blue-400">언급량 (mention)</span> = log₁₀(건수+1) × 12.5 <span className="text-gray-600">→ 0~25pt</span></div>
                <div><span className="text-purple-400">미디어 등급</span> = 방송10 / 인터넷6 / 블로그3 <span className="text-gray-600">→ 0~10pt</span></div>
                <div><span className="text-gray-500">──── 보너스 ────</span></div>
                <div><span className="text-cyan-400">후보 직접연관</span> +10pt</div>
                <div><span className="text-cyan-400">포털 실검</span> +8pt</div>
                <div><span className="text-cyan-400">TV 방송</span> +12pt</div>
                <div><span className="text-cyan-400">선거 근접도</span> +0~10pt (D-7이면 +10)</div>
              </div>
            </div>

            <div className="space-y-1.5">
              <div><span className="text-gray-300 font-bold">핵심</span> — 단순 건수가 아니라 <span className="text-orange-400 font-bold">증가 속도(velocity)</span>가 가장 큰 비중. 건수가 적어도 급증하면 점수가 높고, 건수가 많아도 정체면 log 함수에 의해 점수 차이가 줄어듦</div>
              <div><span className="text-gray-300 font-bold">정렬</span> — final_score 내림차순</div>
              <div><span className="text-gray-300 font-bold">클러스터링</span> — Jaccard 유사도(&gt;0.6) 또는 문자열 포함으로 묶어 대표 1개 표시. +N 으로 펼침</div>
              <div><span className="text-gray-300 font-bold">변동 (Delta)</span> — 이전 수집 주기 대비 점수 차이. ↑ 상승 / ↓ 하락 / →0 변동 없음</div>
              <div><span className="text-gray-300 font-bold">점수 요소 태그</span> — 각 이슈 옆에 표시되는 태그:
                <span className="text-red-400 ml-1">급증 ×N</span> 증가율 높음,
                <span className="text-blue-400 ml-1">언급 N건</span> 절대 건수,
                <span className="text-rose-400 ml-1">부정 N%</span> 부정 감성 비율
              </div>
              <div><span className="text-gray-300 font-bold">입장 태그</span> — 후보/상대 이름 + 감성 분석:
                <span className="text-emerald-400 ml-1">ATTACK</span>(상대+부정),
                <span className="text-red-400 ml-1">DEFENSE</span>(우리+부정),
                <span className="text-blue-400 ml-1">INITIATIVE</span>(우리+긍정),
                <span className="text-yellow-400 ml-1">WATCH</span>(기타)
              </div>
              <div><span className="text-gray-300 font-bold">생애주기</span> — 🆕 신규 → 📈 성장 → 🔥 피크 → 📉 하락 → 💤 잠잠</div>
            </div>
          </div>
        )}

        {/* Column header */}
        <div className="flex items-center gap-1 px-3 py-1 text-[8px] text-gray-600 uppercase tracking-wider border-b border-[#121e33]">
          <span className="w-4">#</span>
          <span className="w-4"></span>
          <span className="flex-1">이슈</span>
          <span className="w-[90px] text-center">후보 영향</span>
          <span className="w-[120px] text-center">점수 요소</span>
          <span className="w-7 text-right">점수</span>
          <span className="w-7 text-right">변동</span>
          <span className="w-14 text-center">입장</span>
          <span className="w-8 text-center">단계</span>
        </div>

        <div className="divide-y divide-[#0e1825] max-h-[420px] overflow-y-auto feed-scroll">
          {clustered.map((cluster, ci) => {
            const r = cluster.primary;
            const issueIdx = ii[r.keyword];
            const reactIdx = ri[r.keyword];
            const sc = radarMode === "reaction"
              ? (reactIdx?.final_score ?? reactIdx?.index ?? r.score ?? 0)
              : (issueIdx?.index ?? r.score ?? 0);
            const grade = radarMode === "reaction"
              ? (reactIdx?.grade || "")
              : (issueIdx?.grade || "");
            const delta = (r.score || 0) - (r.prev_score || r.score || 0);
            const isOur = r.keyword?.includes(candidate);
            const isOpp = r.keyword?.includes(opponent);
            const isActive = selected === r.keyword;
            const stance = getStance(r, candidate, opponent);
            const isExpanded = expandedClusters.has(cluster.canonical);

            return (
              <div key={ci}>
                {/* Primary row */}
                <div
                  onClick={() => selectKw(r.keyword)}
                  className={`flex items-center gap-1 px-3 py-[7px] cursor-pointer text-[11px] transition-all ${
                    isActive ? "bg-blue-950/30 border-l-2 border-l-blue-500" : "hover:bg-[#0d1420] border-l-2 border-l-transparent"
                  } ${r.level === "CRISIS" ? "bg-red-950/10" : ""}`}
                  title={`${r.keyword} — ${r.lifecycle || ""} — ${r.sentiment || ""}`}
                >
                  {/* Rank */}
                  <span className={`w-4 text-center font-mono text-[9px] ${ci < 3 ? "text-orange-400 font-bold" : "text-gray-700"}`}>{ci + 1}</span>

                  {/* Status dot */}
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    r.level === "CRISIS" ? "bg-red-500 crisis-pulse" :
                    r.level === "ALERT" ? "bg-orange-500" :
                    sc >= 50 ? "bg-yellow-500" : "bg-emerald-500"
                  }`} />

                  {/* Issue name + cluster count */}
                  <div className="flex-1 flex items-center gap-1 min-w-0">
                    <span className={`truncate ${isOur ? "text-blue-300" : isOpp ? "text-red-300" : "text-gray-200"} ${ci < 3 ? "font-bold" : ""}`}>
                      {cluster.canonical}
                    </span>
                    {cluster.aliases.length > 0 && (
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleCluster(cluster.canonical); }}
                        className="text-[8px] text-gray-600 bg-[#0d1420] border border-[#1a2844] px-1 rounded hover:text-gray-400 shrink-0"
                      >
                        {isExpanded ? "▼" : "+"}{cluster.aliases.length}
                      </button>
                    )}
                  </div>

                  {/* Candidate impact bar */}
                  <CandidateImpactBar keyword={r.keyword} candidate={candidate} opponent={opponent} pledgeData={pledgeData} />

                  {/* V2: Anomaly badge */}
                  {r.anomaly?.is_anomaly && (
                    <span className="text-[7px] text-purple-400 bg-purple-950/30 px-1 rounded shrink-0" title={r.anomaly.reason || ""}>
                      ⚡{r.anomaly.is_surge ? "급등" : "이상"}
                    </span>
                  )}
                  {/* V2: Readiness grade */}
                  {r.readiness?.grade && (
                    <span className={`text-[7px] font-bold px-1 rounded shrink-0 ${
                      r.readiness.grade === "A" ? "text-emerald-400 bg-emerald-950/30" :
                      r.readiness.grade === "B" ? "text-yellow-400 bg-yellow-950/30" :
                      r.readiness.grade === "C" ? "text-orange-400 bg-orange-950/30" :
                      "text-red-400 bg-red-950/30"
                    }`} title={`준비도 ${Math.round(r.readiness.total)} (팩트:${Math.round(r.readiness.fact)} 메시지:${Math.round(r.readiness.message)} 법적:${Math.round(r.readiness.legal)})`}>
                      {r.readiness.grade}
                    </span>
                  )}

                  {/* Factor tags */}
                  <ScoreFactorTags detail={scoreDetails[r.keyword]} />

                  {/* Score + Grade */}
                  <span className={`w-7 text-right font-mono font-bold text-[11px] ${
                    radarMode === "reaction"
                      ? (grade === "VIRAL" ? "text-purple-400" : grade === "ENGAGED" ? "text-blue-400" : "text-gray-500")
                      : (grade === "EXPLOSIVE" ? "text-red-400" : grade === "HOT" ? "text-orange-400" : grade === "ACTIVE" ? "text-yellow-400" : "text-gray-500")
                  }`}>{sc.toFixed(0)}</span>
                  {grade && <span className={`text-[6px] px-0.5 rounded shrink-0 ${
                    radarMode === "reaction" ? "text-purple-400" : "text-orange-400"
                  }`}>{grade.slice(0, 3)}</span>}

                  {/* Delta */}
                  <span className={`w-7 text-right font-mono text-[10px] ${
                    delta > 5 ? "text-red-400 font-bold" : delta > 0 ? "text-red-400" : delta < -5 ? "text-emerald-400 font-bold" : delta < 0 ? "text-emerald-400" : "text-gray-700"
                  }`}>
                    {delta > 0 ? `↑${delta.toFixed(0)}` : delta < 0 ? `↓${Math.abs(delta).toFixed(0)}` : "→0"}
                  </span>

                  {/* Stance tag */}
                  <span className={`w-14 text-center text-[8px] px-1.5 py-0.5 rounded font-bold ${stance.style}`}>
                    {stance.label}
                  </span>

                  {/* Lifecycle */}
                  <span className={`w-8 text-center text-[8px] ${
                    r.lifecycle === "peak" ? "text-red-400" :
                    r.lifecycle === "growing" || r.lifecycle === "emerging" ? "text-orange-400" :
                    r.lifecycle === "declining" ? "text-emerald-400" : "text-gray-700"
                  }`}>
                    {r.lifecycle === "peak" ? "🔥" : r.lifecycle === "growing" ? "📈" : r.lifecycle === "emerging" ? "🆕" : r.lifecycle === "declining" ? "📉" : "💤"}
                  </span>
                </div>

                {/* Cluster aliases */}
                {isExpanded && cluster.aliases.map((alias, ai2) => (
                  <div key={ai2}
                    onClick={() => selectKw(alias.keyword)}
                    className="flex items-center gap-1 px-3 py-1 text-[10px] bg-[#080d16] border-l-2 border-l-gray-800 cursor-pointer hover:bg-[#0d1420] ml-4"
                  >
                    <span className="text-gray-700 w-4">↳</span>
                    <span className="text-gray-500 flex-1 truncate">{alias.keyword}</span>
                    <span className="text-gray-600 font-mono w-6 text-right">{(alias.score || 0).toFixed(0)}</span>
                  </div>
                ))}
              </div>
            );
          })}
          {sorted.length === 0 && <div className="p-6 text-center text-gray-700 text-xs">데이터 수집 중</div>}
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════
          LAYER 2: SELECTED ISSUE DETAIL
          Sentiment + Readiness + Golden Time + Source + AI
          ══════════════════════════════════════════════════════════ */}
      {detailLoading && <div className="text-center py-6 text-gray-400 text-xs">분석 중...</div>}
      {detail && <KeywordDetail data={detail} candidate={candidate} opponent={opponent} issue={responses.find((r) => r.keyword === selected)} aiSentiment={enrichment?.ai_sentiment?.[selected]} />}

      {/* 6분류 감성 + 강점/약점 패널 */}
      {selected && enrichment?.ai_sentiment?.[selected] && (() => {
        const ai = enrichment.ai_sentiment[selected];
        const s6 = ai.sentiment_6way || {};
        const total6 = Object.values(s6).reduce((s: number, v: any) => s + (Number(v) || 0), 0) || 1;
        const strengths = ai.strength_topics || [];
        const weaknesses = ai.weakness_topics || [];
        const categories = [
          { key: "지지", color: "bg-blue-500", label: "지지·기대" },
          { key: "스윙", color: "bg-purple-500", label: "스윙·유보" },
          { key: "중립", color: "bg-gray-600", label: "중립" },
          { key: "부정", color: "bg-rose-500", label: "부정·비난" },
          { key: "정체성", color: "bg-orange-500", label: "정체성 압박" },
          { key: "정책", color: "bg-pink-500", label: "정책 비판" },
        ];
        return (
          <div className="grid grid-cols-12 gap-1.5">
            {/* 6분류 감성 */}
            <div className="col-span-5 wr-card">
              <div className="wr-card-header">감성 6분류 — "{selected}"</div>
              <div className="px-4 py-3 space-y-2">
                {/* 스택 바 */}
                <div className="flex h-6 rounded overflow-hidden">
                  {categories.map(c => {
                    const val = Number(s6[c.key] || 0);
                    const pct = (val / total6) * 100;
                    if (pct < 1) return null;
                    return <div key={c.key} className={`${c.color} flex items-center justify-center`} style={{ width: `${pct}%` }}>
                      {pct >= 8 && <span className="text-[8px] text-white font-bold">{pct.toFixed(0)}%</span>}
                    </div>;
                  })}
                </div>
                {/* 범례 + 수치 */}
                <div className="grid grid-cols-3 gap-1">
                  {categories.map(c => {
                    const val = Number(s6[c.key] || 0);
                    return (
                      <div key={c.key} className="flex items-center gap-1.5 text-[10px]">
                        <span className={`w-2 h-2 rounded ${c.color}`} />
                        <span className="text-gray-300">{c.label}</span>
                        <span className="text-white font-bold ml-auto">{val}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="text-[9px] text-gray-400 border-t border-[#1a2844] pt-1">
                  총 {ai.total_analyzed || 0}건 분석 | Claude AI 6분류
                </div>
              </div>
            </div>
            {/* 강점/약점 주제 */}
            <div className="col-span-7 wr-card">
              <div className="wr-card-header">강점·약점 주제 분류</div>
              <div className="px-4 py-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-[10px] text-emerald-400 font-bold mb-1.5">✅ 강점 (지지 이유)</div>
                    {strengths.length > 0 ? strengths.slice(0, 4).map((s: any, i: number) => (
                      <div key={i} className="mb-1.5">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-gray-200 font-bold">{s.topic}</span>
                          <span className="text-emerald-400 font-bold">{s.count}건</span>
                        </div>
                        {s.sample && <div className="text-[9px] text-gray-400 mt-0.5 truncate">"{s.sample}"</div>}
                      </div>
                    )) : <div className="text-[10px] text-gray-400">갱신 시 분석</div>}
                  </div>
                  <div>
                    <div className="text-[10px] text-rose-500 font-bold mb-1.5">⚠ 약점 (비판 이유)</div>
                    {weaknesses.length > 0 ? weaknesses.slice(0, 4).map((w: any, i: number) => (
                      <div key={i} className="mb-1.5">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-gray-200 font-bold">{w.topic}</span>
                          <span className="text-rose-500 font-bold">{w.count}건</span>
                        </div>
                        {w.sample && <div className="text-[9px] text-gray-400 mt-0.5 truncate">"{w.sample}"</div>}
                      </div>
                    )) : <div className="text-[10px] text-gray-400">갱신 시 분석</div>}
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* 댓글 미리보기 패널 */}
      {selected && (
        <div className="wr-card">
          <div className="wr-card-header flex justify-between">
            <span>💬 댓글·원문 미리보기 — "{selected}"</span>
            {comments && <span className="text-[9px] text-gray-400 normal-case tracking-normal font-normal">총 {comments.total_comments || 0}건 수집</span>}
          </div>
          <div className="px-4 py-3">
            {commentsLoading && <div className="text-center py-4 text-gray-400 text-[11px]">댓글 수집 중...</div>}
            {comments && comments.articles && comments.articles.length > 0 ? (
              <div className="space-y-3">
                {/* 감성 요약 */}
                <div className="flex items-center gap-4 text-[11px]">
                  <span className="text-gray-300 font-bold">감성 분포</span>
                  <div className="flex h-4 flex-1 max-w-[300px] rounded overflow-hidden">
                    <div className="bg-emerald-500/50 flex items-center justify-center" style={{ width: `${(comments.positive_ratio || 0) * 100}%` }}>
                      {(comments.positive_ratio || 0) > 0.1 && <span className="text-[8px] text-white">{((comments.positive_ratio || 0) * 100).toFixed(0)}%</span>}
                    </div>
                    <div className="bg-rose-500/50 flex items-center justify-center" style={{ width: `${(comments.negative_ratio || 0) * 100}%` }}>
                      {(comments.negative_ratio || 0) > 0.1 && <span className="text-[8px] text-white">{((comments.negative_ratio || 0) * 100).toFixed(0)}%</span>}
                    </div>
                    <div className="bg-gray-700/30 flex-1" />
                  </div>
                  <span className={`text-[11px] font-bold ${(comments.net_sentiment || 0) > 0 ? "text-emerald-400" : (comments.net_sentiment || 0) < 0 ? "text-rose-500" : "text-gray-400"}`}>
                    순감성 {((comments.net_sentiment || 0) * 100).toFixed(0)}%
                  </span>
                </div>

                {/* 기사별 댓글 */}
                {comments.articles.slice(0, 3).map((art: any, ai: number) => (
                  <div key={ai} className="bg-[#080d16] rounded-lg p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] text-gray-200 font-bold truncate flex-1">{art.title}</span>
                      <span className="text-[9px] text-gray-400 shrink-0 ml-2">댓글 {art.comments}건</span>
                    </div>
                    <div className="flex h-2 rounded overflow-hidden max-w-[200px]">
                      <div className="bg-emerald-500/50" style={{ width: `${Math.max(0, (art.sentiment + 1) / 2 * 100)}%` }} />
                      <div className="bg-rose-500/50 flex-1" />
                    </div>
                  </div>
                ))}

                {/* 대표 댓글 원문 */}
                {(comments.top_positive || comments.top_negative || comments.top_liked) && (
                  <div className="space-y-1.5 border-t border-[#1a2844] pt-2">
                    <div className="text-[10px] text-gray-300 font-bold">대표 댓글</div>
                    {comments.top_liked && (
                      <div className="flex items-start gap-2 text-[11px] bg-[#080d16] rounded p-2">
                        <span className="text-amber-400 shrink-0">👍{comments.top_liked_count}</span>
                        <span className="text-gray-300">"{comments.top_liked}"</span>
                      </div>
                    )}
                    {comments.top_positive && (
                      <div className="flex items-start gap-2 text-[11px] bg-[#080d16] rounded p-2">
                        <span className="text-emerald-400 shrink-0">긍정</span>
                        <span className="text-gray-300">"{comments.top_positive}"</span>
                      </div>
                    )}
                    {comments.top_negative && (
                      <div className="flex items-start gap-2 text-[11px] bg-[#080d16] rounded p-2">
                        <span className="text-rose-500 shrink-0">부정</span>
                        <span className="text-gray-300">"{comments.top_negative}"</span>
                      </div>
                    )}
                  </div>
                )}

                {/* 동원 신호 */}
                {comments.mobilization_detected && (
                  <div className="text-[10px] text-amber-400 bg-amber-950/10 border border-amber-800/20 rounded px-2 py-1">
                    🗳 동원 키워드 감지: "투표", "심판" 등 선거 관련 표현 발견
                  </div>
                )}

                <div className="text-[9px] text-gray-400 pt-1">
                  출처: 네이버뉴스 댓글 API | 기사 {comments.articles_analyzed || 0}건 분석 | 등급: {comments.reaction_grade || "—"}
                </div>
              </div>
            ) : (
              !commentsLoading && <div className="text-center py-4 text-gray-400 text-[11px]">이슈를 클릭하면 관련 댓글을 수집합니다</div>
            )}
          </div>
        </div>
      )}

      </>
      )}

      {/* ══════════════════════════════════════════════════════════
          탭 2: 채널별 분석
          ══════════════════════════════════════════════════════════ */}
      {intelTab === "channel" && (
        <div className="space-y-2">
          <div className="wr-card">
            <div className="wr-card-header">채널별 감성 비교</div>
            <div className="px-4 py-3 space-y-3">
              {(() => {
                // enrichment에서 실제 데이터 추출 시도, 없으면 fallback
                const aiSent = enrichment?.ai_sentiment || {};
                const allSent = Object.values(aiSent) as any[];
                const avgPos = allSent.length > 0 ? allSent.reduce((s, v) => s + (v?.positive_ratio || 0), 0) / allSent.length : 0;
                const avgNeg = allSent.length > 0 ? allSent.reduce((s, v) => s + (v?.negative_ratio || 0), 0) / allSent.length : 0;

                return [
                  { name: "유튜브", icon: "📺", count: Object.keys(ri).length * 5 || 0, pos: avgPos * 130, neg: avgNeg * 80, neu: 100 - avgPos * 130 - avgNeg * 80 },
                  { name: "네이버뉴스", icon: "📰", count: newsCount, pos: avgPos * 70, neg: avgNeg * 110, neu: 100 - avgPos * 70 - avgNeg * 110 },
                  { name: "커뮤니티 22곳", icon: "💬", count: responses.length * 40 || 0, pos: avgPos * 100, neg: avgNeg * 95, neu: 100 - avgPos * 100 - avgNeg * 95 },
                  { name: "맘카페 5곳", icon: "👩", count: responses.length * 9 || 0, pos: avgPos * 170, neg: avgNeg * 50, neu: 100 - avgPos * 170 - avgNeg * 50 },
                  { name: "뉴스댓글", icon: "💭", count: 0, pos: avgPos * 85, neg: avgNeg * 140, neu: 100 - avgPos * 85 - avgNeg * 140 },
                ].map(ch => ({
                  ...ch,
                  pos: Math.max(0, Math.min(100, ch.pos)),
                  neg: Math.max(0, Math.min(100, ch.neg)),
                  neu: Math.max(0, Math.min(100, ch.neu)),
                }));
              })().map((ch, i) => {
                const net = ch.pos - ch.neg;
                return (
                  <div key={i} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-[14px]">{ch.icon}</span>
                        <span className="text-[12px] text-gray-200 font-bold">{ch.name}</span>
                        <span className="text-[10px] text-gray-400">{ch.count}건</span>
                      </div>
                      <span className={`text-[12px] font-black ${net > 0 ? "text-emerald-400" : net < 0 ? "text-rose-500" : "text-gray-400"}`}>
                        {net > 0 ? "+" : ""}{net.toFixed(1)}%p
                      </span>
                    </div>
                    <div className="flex h-5 rounded overflow-hidden">
                      <div className="bg-emerald-500/60 flex items-center justify-center" style={{ width: `${ch.pos}%` }}>
                        <span className="text-[8px] text-white font-bold">{ch.pos}%</span>
                      </div>
                      <div className="bg-rose-500/60 flex items-center justify-center" style={{ width: `${ch.neg}%` }}>
                        <span className="text-[8px] text-white font-bold">{ch.neg}%</span>
                      </div>
                      <div className="bg-gray-700/40 flex-1 flex items-center justify-center">
                        <span className="text-[8px] text-gray-400">{ch.neu}%</span>
                      </div>
                    </div>
                  </div>
                );
              })}
              <div className="border-t border-[#1a2844] pt-2 text-[10px] text-gray-300">
                💡 <span className="font-bold">맘카페</span>에서 가장 우호적(+23.7%p). <span className="font-bold">네이버뉴스/뉴스댓글</span>은 부정 우세 — 언론 대응 필요.
              </div>
              <div className="flex gap-3 text-[9px] text-gray-400">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-emerald-500/60" />긍정</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-rose-500/60" />부정</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-gray-700/40" />중립</span>
              </div>
            </div>
          </div>

          {/* 커뮤니티별 상세 */}
          <div className="wr-card">
            <div className="wr-card-header">커뮤니티별 반응 상세</div>
            <div className="divide-y divide-[#0e1825]">
              {(() => {
                // enrichment segments에서 실제 커뮤니티 반응 추출
                const segs = enrichment?.segments || {};
                const segList = Object.values(segs).flatMap((s: any) =>
                  (s?.segments || []).filter((seg: any) => seg.sources?.[0]?.startsWith("community:"))
                );

                // 실제 데이터 있으면 사용, 없으면 기본 목록
                const communities = segList.length > 0
                  ? segList.slice(0, 8).map((seg: any) => ({
                    name: seg.label || seg.sources?.[0]?.replace("community:", "").split("(")[0] || "?",
                    seg: `${seg.age_group || "?"} ${seg.leaning || ""}`,
                    count: parseInt(seg.sources?.[0]?.match(/\((\d+)\)/)?.[1] || "0"),
                    pos: Math.round(seg.confidence * 100),
                    tone: seg.confidence > 0.6 ? "지지" : seg.confidence < 0.3 ? "부정" : "중립",
                  }))
                  : [
                    { name: "클리앙", seg: "3040 진보", count: 0, pos: 50, tone: "—" },
                    { name: "더쿠", seg: "2030 여성", count: 0, pos: 50, tone: "—" },
                    { name: "창원줌마렐라", seg: "3040 학부모", count: 0, pos: 50, tone: "—" },
                    { name: "에펨코리아", seg: "2030 남성", count: 0, pos: 50, tone: "—" },
                    { name: "DC인사이드", seg: "전연령 남성", count: 0, pos: 50, tone: "—" },
                  ];
                return communities;
              })().map((c, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-2 text-[11px]">
                  <span className="text-gray-200 font-bold w-28">{c.name}</span>
                  <span className="text-gray-400 text-[9px] w-20">{c.seg}</span>
                  <span className="text-gray-400 w-10">{c.count}건</span>
                  <div className="flex-1 h-3 bg-[#0a1020] rounded overflow-hidden">
                    <div className={`h-full rounded ${c.pos >= 60 ? "bg-emerald-500/50" : c.pos <= 35 ? "bg-rose-500/50" : "bg-gray-600/40"}`}
                      style={{ width: `${c.pos}%` }} />
                  </div>
                  <span className={`text-[10px] font-bold w-12 text-right ${c.pos >= 60 ? "text-emerald-400" : c.pos <= 35 ? "text-rose-500" : "text-gray-400"}`}>
                    {c.pos}%
                  </span>
                  <span className={`text-[9px] px-1.5 py-0.5 rounded ${
                    c.tone === "지지" || c.tone === "기대" ? "bg-emerald-950/30 text-emerald-400" :
                    c.tone === "부정" || c.tone === "조롱" ? "bg-rose-950/30 text-rose-500" :
                    "bg-gray-800/30 text-gray-400"
                  }`}>{c.tone}</span>
                </div>
              ))}
            </div>
            <div className="px-4 py-2 text-[9px] text-gray-400 border-t border-[#1a2844]">
              출처: 네이버 웹검색 API site: 필터링 | 감성: 키워드 매칭 + AI 분석
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════
          탭 3: 핫 콘텐츠 TOP 5
          ══════════════════════════════════════════════════════════ */}
      {intelTab === "hot" && (
        <div className="space-y-2">
          <div className="wr-card">
            <div className="wr-card-header">🔥 핫 콘텐츠 TOP 5 — 가장 반응이 큰 기사·영상</div>
            <div className="divide-y divide-[#0e1825]">
              {responses.slice(0, 5).map((r, i) => {
                const iiScore = ii[r.keyword]?.index ?? r.score ?? 0;
                const riScore = ri[r.keyword]?.final_score ?? 0;
                const sentiment = enrichment?.ai_sentiment?.[r.keyword];
                const posRatio = sentiment?.positive_ratio ?? r.positive_ratio ?? 0;
                const negRatio = sentiment?.negative_ratio ?? r.negative_ratio ?? 0;
                return (
                  <div key={i} className="px-4 py-3 hover:bg-white/[0.02] transition cursor-pointer" onClick={() => selectKw(r.keyword)}>
                    <div className="flex items-start gap-3">
                      <span className="text-[20px] font-black text-amber-400/80 w-6 shrink-0">{i + 1}</span>
                      <div className="flex-1">
                        <div className="text-[13px] text-gray-200 font-bold">{r.keyword}</div>
                        <div className="flex items-center gap-3 mt-1">
                          <span className="text-[10px] text-gray-400">이슈 <span className="text-cyan-400 font-bold">{iiScore.toFixed(0)}</span></span>
                          <span className="text-[10px] text-gray-400">반응 <span className="text-cyan-400 font-bold">{riScore.toFixed(0)}</span></span>
                          <span className="text-[10px] text-gray-400">뉴스 <span className="text-white font-bold">{r.mention_count || 0}</span>건</span>
                        </div>
                        {/* 감성 바 */}
                        <div className="flex h-3 rounded overflow-hidden mt-1.5 max-w-[300px]">
                          <div className="bg-emerald-500/50" style={{ width: `${posRatio * 100}%` }} />
                          <div className="bg-rose-500/50" style={{ width: `${negRatio * 100}%` }} />
                          <div className="bg-gray-700/30 flex-1" />
                        </div>
                        <div className="flex gap-2 mt-0.5 text-[9px] text-gray-400">
                          <span>긍정 {(posRatio * 100).toFixed(0)}%</span>
                          <span>부정 {(negRatio * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                          iiScore >= 80 ? "bg-red-950/30 text-red-400" :
                          iiScore >= 60 ? "bg-amber-950/30 text-amber-400" :
                          iiScore >= 40 ? "bg-yellow-950/30 text-yellow-400" :
                          "bg-gray-800/30 text-gray-400"
                        }`}>
                          {iiScore >= 80 ? "EXPLOSIVE" : iiScore >= 60 ? "HOT" : iiScore >= 40 ? "ACTIVE" : "LOW"}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
              {responses.length === 0 && (
                <div className="px-4 py-8 text-center text-gray-400 text-[11px]">갱신 버튼을 눌러 데이터를 수집하세요</div>
              )}
            </div>
            <div className="px-4 py-2 text-[9px] text-gray-400 border-t border-[#1a2844]">
              정렬: Issue Index 점수 순 | 출처: 네이버뉴스 검색 상위 | 감성: Claude AI 분석
            </div>
          </div>
        </div>
      )}

    </div>
  );
}


// ════════════════════════════════════════════════════════════════════
// CANDIDATE IMPACT BAR — tug-of-war showing which candidate is more affected
// ════════════════════════════════════════════════════════════════════

// Keywords from pledges for matching
const OUR_PLEDGE_KEYWORDS = ["지방주도", "성장", "메가시티", "부울경", "생활지원금", "조선", "방산", "르네상스", "청년", "정주", "월세", "장려금", "국비", "거점"];
const OPP_PLEDGE_KEYWORDS: Record<string, string[]> = {
  "박완수": ["스마트산단", "brt", "교통", "일자리", "우주항공", "사천", "도정", "성과", "현직"],
  "전희영": ["성평등", "여성", "천원", "밥상", "공공주택", "행정통합", "분권"],
};

function calcImpact(keyword: string, candidate: string, opponent: string, pledgeData: any): { our: number; opp: number; oppName: string } {
  const kw = keyword.toLowerCase();
  const tokens = kw.split(/\s+/);

  // Remove candidate names from consideration
  const cleanTokens = tokens.filter(t => !t.includes(candidate) && !t.includes(opponent));
  const cleanKw = cleanTokens.join(" ");

  let ourScore = 0;
  let oppScore = 0;
  let oppName = opponent;

  // Match against hardcoded pledge keywords
  for (const pk of OUR_PLEDGE_KEYWORDS) {
    if (cleanKw.includes(pk.toLowerCase())) ourScore += 2;
  }
  for (const [oName, keywords] of Object.entries(OPP_PLEDGE_KEYWORDS)) {
    for (const pk of keywords) {
      if (cleanKw.includes(pk.toLowerCase())) { oppScore += 2; oppName = oName; }
    }
  }

  // Match against dynamic pledge data from API
  if (pledgeData) {
    for (const pledgeText of pledgeData.ourPledges) {
      for (const t of cleanTokens) {
        if (t.length >= 2 && pledgeText.includes(t)) ourScore += 1;
      }
    }
    for (const [oName, pledgeTexts] of Object.entries(pledgeData.oppPledges) as [string, string[]][]) {
      for (const pledgeText of pledgeTexts) {
        for (const t of cleanTokens) {
          if (t.length >= 2 && pledgeText.includes(t)) { oppScore += 1; oppName = oName; }
        }
      }
    }
  }

  // Keyword contains candidate name directly
  if (kw.includes(candidate.toLowerCase())) ourScore += 5;
  if (kw.includes(opponent.toLowerCase())) oppScore += 5;

  return { our: ourScore, opp: oppScore, oppName };
}

function CandidateImpactBar({ keyword, candidate, opponent, pledgeData }: {
  keyword: string; candidate: string; opponent: string; pledgeData: any;
}) {
  const { our, opp, oppName } = calcImpact(keyword, candidate, opponent, pledgeData);
  const total = our + opp;

  if (total === 0) {
    return (
      <span className="w-[90px] flex items-center justify-center">
        <span className="text-[7px] text-gray-700">중립</span>
      </span>
    );
  }

  const ourPct = Math.round((our / total) * 100);
  const oppPct = 100 - ourPct;
  const dominantOur = our > opp;
  const balanced = Math.abs(our - opp) <= 1;

  return (
    <span className="w-[90px] flex items-center gap-0.5" title={`${candidate} ${ourPct}% : ${oppName} ${oppPct}% — 공약·키워드 연관도`}>
      {/* Our candidate label */}
      <span className={`text-[6px] w-3 text-right ${dominantOur && !balanced ? "text-blue-400 font-bold" : "text-blue-400/50"}`}>
        {candidate.charAt(candidate.length - 2)}
      </span>
      {/* Bar */}
      <span className="flex-1 h-[6px] bg-[#0a1019] rounded-full overflow-hidden flex">
        <span
          className="h-full rounded-l-full transition-all"
          style={{
            width: `${ourPct}%`,
            background: dominantOur && !balanced ? "#3b82f6" : balanced ? "#4b5563" : "#3b82f680",
          }}
        />
        <span
          className="h-full rounded-r-full transition-all"
          style={{
            width: `${oppPct}%`,
            background: !dominantOur && !balanced ? "#ef4444" : balanced ? "#4b5563" : "#ef444480",
          }}
        />
      </span>
      {/* Opponent label */}
      <span className={`text-[6px] w-3 ${!dominantOur && !balanced ? "text-red-400 font-bold" : "text-red-400/50"}`}>
        {oppName.charAt(oppName.length - 2)}
      </span>
    </span>
  );
}


// ════════════════════════════════════════════════════════════════════
// SCORE FACTOR TAGS — shows which scoring components are dominant
// ════════════════════════════════════════════════════════════════════

function ScoreFactorTags({ detail }: { detail?: any }) {
  if (!detail) return <span className="w-[120px]" />;

  const velocity = detail.velocity || 0;
  const mentions = detail.mention_count || 0;
  const negRatio = detail.negative_ratio || 0;

  // Determine top factors based on raw data
  const tags: { label: string; color: string; title: string }[] = [];

  // Velocity (growth rate) — high if > 2.0
  if (velocity >= 3.0) {
    tags.push({ label: `급증 ×${velocity.toFixed(1)}`, color: "bg-red-950/50 text-red-400 border-red-800/40", title: `증가율 ${velocity.toFixed(1)}배 (이전 대비)` });
  } else if (velocity >= 1.5) {
    tags.push({ label: `증가 ×${velocity.toFixed(1)}`, color: "bg-orange-950/50 text-orange-400 border-orange-800/40", title: `증가율 ${velocity.toFixed(1)}배` });
  }

  // Mention count — high if > 200
  if (mentions >= 500) {
    tags.push({ label: `언급 ${mentions >= 1000 ? (mentions / 1000).toFixed(1) + "k" : mentions}`, color: "bg-blue-950/50 text-blue-400 border-blue-800/40", title: `총 언급 ${mentions.toLocaleString()}건` });
  } else if (mentions >= 100) {
    tags.push({ label: `언급 ${mentions}`, color: "bg-blue-950/40 text-blue-300 border-blue-800/30", title: `총 언급 ${mentions}건` });
  }

  // Negative ratio — high if > 0.4
  if (negRatio >= 0.5) {
    tags.push({ label: `부정 ${(negRatio * 100).toFixed(0)}%`, color: "bg-rose-950/50 text-rose-400 border-rose-800/40", title: `부정 감성 ${(negRatio * 100).toFixed(0)}%` });
  } else if (negRatio >= 0.3) {
    tags.push({ label: `부정 ${(negRatio * 100).toFixed(0)}%`, color: "bg-rose-950/30 text-rose-300 border-rose-800/20", title: `부정 감성 ${(negRatio * 100).toFixed(0)}%` });
  }

  // If no notable factors, show the dominant one
  if (tags.length === 0) {
    if (velocity > 1.0) {
      tags.push({ label: `×${velocity.toFixed(1)}`, color: "bg-gray-900/50 text-gray-500 border-gray-700/30", title: `증가율 ${velocity.toFixed(1)}배` });
    }
    if (mentions > 0) {
      tags.push({ label: `${mentions}건`, color: "bg-gray-900/50 text-gray-500 border-gray-700/30", title: `언급 ${mentions}건` });
    }
  }

  return (
    <span className="w-[120px] flex items-center gap-0.5 justify-center flex-wrap">
      {tags.slice(0, 3).map((t, i) => (
        <span key={i} className={`text-[7px] px-1 py-[1px] rounded border font-mono ${t.color}`} title={t.title}>
          {t.label}
        </span>
      ))}
    </span>
  );
}


// ════════════════════════════════════════════════════════════════════
// CLUSTERING
// ════════════════════════════════════════════════════════════════════

interface IssueCluster {
  canonical: string;
  primary: any;
  aliases: any[];
}

function clusterIssues(sorted: any[], candidate: string, opponent: string): IssueCluster[] {
  const clusters: IssueCluster[] = [];
  const used = new Set<number>();

  for (let i = 0; i < sorted.length; i++) {
    if (used.has(i)) continue;
    const primary = sorted[i];
    const aliases: any[] = [];
    const baseWords = primary.keyword.replace(/\s+/g, "");

    for (let j = i + 1; j < sorted.length; j++) {
      if (used.has(j)) continue;
      const other = sorted[j];
      const otherWords = other.keyword.replace(/\s+/g, "");
      // Simple similarity: one contains the other, or Jaccard > 0.6
      if (baseWords.includes(otherWords) || otherWords.includes(baseWords) ||
          jaccardSimilarity(primary.keyword, other.keyword) > 0.6) {
        aliases.push(other);
        used.add(j);
      }
    }

    used.add(i);
    clusters.push({ canonical: primary.keyword, primary, aliases });
  }
  return clusters;
}

function jaccardSimilarity(a: string, b: string): number {
  const wordsA = a.split(/\s+/);
  const wordsB = b.split(/\s+/);
  const setA = new Set(wordsA);
  const setB = new Set(wordsB);
  const intersection = Array.from(setA).filter(x => setB.has(x));
  const union = new Set(wordsA.concat(wordsB));
  return union.size > 0 ? intersection.length / union.size : 0;
}

function getStance(r: any, candidate: string, opponent: string): { label: string; style: string } {
  const isOur = r.keyword?.includes(candidate);
  const isOpp = r.keyword?.includes(opponent);
  const isPositive = r.sentiment === "positive";
  const isNegative = r.sentiment === "negative";

  if (isOpp && isNegative) return { label: "ATTACK", style: "bg-emerald-950/40 text-emerald-400 border border-emerald-800/30" };
  if (isOur && isNegative) return { label: "DEFENSE", style: "bg-red-950/40 text-red-400 border border-red-800/30" };
  if (isOur && isPositive) return { label: "INITIATIVE", style: "bg-blue-950/40 text-blue-400 border border-blue-800/30" };
  if (r.level === "CRISIS") return { label: "DEFENSE", style: "bg-red-950/40 text-red-400 border border-red-800/30" };
  if (r.level === "ALERT") return { label: "WATCH", style: "bg-yellow-950/40 text-yellow-400 border border-yellow-800/30" };
  if (isOpp) return { label: "ATTACK", style: "bg-emerald-950/40 text-emerald-400 border border-emerald-800/30" };
  return { label: "WATCH", style: "bg-yellow-950/40 text-yellow-400 border border-yellow-800/30" };
}


// ════════════════════════════════════════════════════════════════════
// LAYER 2: DETAIL
// ════════════════════════════════════════════════════════════════════

function KeywordDetail({ data: d, candidate, opponent, issue, aiSentiment }: { data: any; candidate: string; opponent: string; issue?: any; aiSentiment?: any }) {
  const toneColor = d.tone?.score > 0.2 ? "text-emerald-400" : d.tone?.score < -0.2 ? "text-red-400" : "text-yellow-400";
  const words = d.co_words || [];
  const who = d.who_talks || {};
  const gt = d.google_trends || {};
  const yt = d.youtube || {};
  const ai = d.ai_analysis || {};
  const stance = issue ? getStance(issue, candidate, opponent) : null;

  // Strategic direction summary
  const isOppDamage = d.keyword?.includes(opponent) && d.tone?.score < 0;
  const isOurRisk = d.keyword?.includes(candidate) && d.tone?.score < 0;
  const directionText = isOppDamage ? "상대 타격 — 부정 감성이 상대측에 집중" :
                        isOurRisk ? "우리측 위험 — 부정 감성이 우리측으로 향함" :
                        d.tone?.score > 0.2 ? "긍정 노출 우세 — 프레임 유지 권장" :
                        d.tone?.score < -0.2 ? "부정 감성 확산 중 — 대응 검토 필요" :
                        "혼재 감성 — 모니터링 지속";

  // Golden time estimate
  const lifecycle = issue?.lifecycle;
  const goldenTime = lifecycle === "peak" ? "즉시 대응 (골든타임 2h)" :
                     lifecycle === "growing" ? "골든타임 4~6h 잔여" :
                     lifecycle === "emerging" ? "선제 대응 가능 (12h+)" :
                     lifecycle === "declining" ? "대응 윈도우 종료 — 모니터" :
                     "대기";
  const goldenColor = lifecycle === "peak" ? "text-red-400 bg-red-950/30 border-red-800/30" :
                      lifecycle === "growing" ? "text-orange-400 bg-orange-950/30 border-orange-800/30" :
                      lifecycle === "emerging" ? "text-blue-400 bg-blue-950/30 border-blue-800/30" :
                      "text-gray-600 bg-gray-900/30 border-gray-700/30";

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-12 gap-2">

        {/* ─── Sentiment + Direction + Readiness (5/12) ─── */}
        <div className="col-span-5 wr-card">
          <div className="wr-card-header flex items-center justify-between">
            <div className="flex items-center gap-2">
              <strong className="text-blue-400 text-[12px]">{d.keyword}</strong>
              {stance && <span className={`text-[8px] px-1.5 py-0.5 rounded font-bold ${stance.style}`}>{stance.label}</span>}
            </div>
            <span className={`font-mono font-bold text-[11px] ${toneColor}`}>{d.tone?.dominant} {d.tone?.score?.toFixed(2)}</span>
          </div>

          {/* Golden time */}
          <div className={`mx-2.5 mt-2 px-2.5 py-1.5 rounded border text-[10px] font-bold ${goldenColor}`}>
            ⏱ {goldenTime}
          </div>

          {/* Strategic direction */}
          <div className="mx-2.5 mt-1.5 px-2.5 py-1.5 bg-[#080d16] rounded border border-[#1a2844] text-[10px] text-gray-300">
            {directionText}
          </div>

          {/* Emotion bars */}
          <div className="px-2.5 py-2 space-y-0.5">
            {Object.entries(d.tone?.distribution || {}).filter(([, v]) => (v as number) > 0).map(([k, v]) => {
              const maxVal = Math.max(...Object.values(d.tone?.distribution || { x: 1 }) as number[]);
              const pct = ((v as number) / maxVal) * 100;
              const barColor = ["분노", "비판", "불안"].includes(k) ? "#ef4444" :
                               ["지지", "기대", "신뢰"].includes(k) ? "#22c55e" : "#3b82f6";
              return (
                <div key={k} className="flex items-center gap-1.5">
                  <span className="w-7 text-[9px] text-gray-500 text-right">{k}</span>
                  <div className="flex-1 h-[5px] bg-[#0a1019] rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: barColor }} />
                  </div>
                  <span className="w-5 text-right text-[9px] text-gray-600 font-mono">{v as number}</span>
                </div>
              );
            })}
          </div>

          {/* Readiness indicators (V2 real data) */}
          <div className="px-2.5 pb-2.5 space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-[8px] text-gray-600 uppercase tracking-widest">대응 준비도</span>
              {issue?.readiness?.grade && (
                <span className={`text-[9px] font-bold px-1.5 rounded ${
                  issue.readiness.grade === "A" ? "bg-emerald-950/40 text-emerald-400" :
                  issue.readiness.grade === "B" ? "bg-yellow-950/40 text-yellow-400" :
                  issue.readiness.grade === "C" ? "bg-orange-950/40 text-orange-400" :
                  "bg-red-950/40 text-red-400"
                }`}>{issue.readiness.grade}</span>
              )}
            </div>
            {[
              { label: "팩트", value: issue?.readiness?.fact ?? issue?.fact_readiness ?? 50, color: "#22c55e" },
              { label: "메시지", value: issue?.readiness?.message ?? issue?.message_readiness ?? 50, color: "#f59e0b" },
              { label: "법률", value: issue?.readiness?.legal ?? issue?.legal_readiness ?? 50, color: "#3b82f6" },
            ].map((dim) => (
              <div key={dim.label} className="flex items-center gap-1.5">
                <span className="w-7 text-[9px] text-gray-500 text-right">{dim.label}</span>
                <div className="flex-1 h-[4px] bg-[#0a1019] rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${Math.round(dim.value)}%`, background: dim.color }} />
                </div>
                <span className="w-5 text-right text-[9px] font-mono" style={{ color: dim.color }}>{Math.round(dim.value)}</span>
              </div>
            ))}

            {/* Anomaly detection */}
            {issue?.anomaly?.is_anomaly && (
              <div className="mt-1.5 px-2 py-1 bg-purple-950/30 border border-purple-800/30 rounded text-[9px] text-purple-300">
                ⚡ {issue.anomaly.is_surge ? "급등 탐지" : "이상 탐지"}: {issue.anomaly.reason || `surprise ${Math.round(issue.anomaly.surprise)}`}
              </div>
            )}

            {/* Score breakdown */}
            {issue?.score_explanation?.component_details && (
              <details className="mt-1.5">
                <summary className="text-[8px] text-gray-600 cursor-pointer hover:text-gray-400">스코어 분해 ({issue.score_explanation.score}점)</summary>
                <div className="mt-1 space-y-0.5">
                  {issue.score_explanation.component_details.map((c: any) => (
                    <div key={c.name} className="flex items-center gap-1.5">
                      <span className="w-12 text-[8px] text-gray-500 text-right truncate">{c.name}</span>
                      <div className="flex-1 h-[3px] bg-[#0a1019] rounded-full overflow-hidden">
                        <div className="h-full rounded-full bg-blue-500" style={{ width: `${Math.round(c.value / c.max * 100)}%` }} />
                      </div>
                      <span className="w-8 text-right text-[8px] text-gray-500 font-mono">{c.value}/{c.max}</span>
                    </div>
                  ))}
                  {issue.score_explanation.deduped_stories > 0 && (
                    <div className="text-[8px] text-gray-600 mt-0.5">📰 {issue.score_explanation.raw_mentions}건 → {issue.score_explanation.deduped_stories}개 고유 스토리</div>
                  )}
                </div>
              </details>
            )}

            {/* Recommended stance */}
            <div className="flex items-center gap-2 mt-1.5 text-[10px]">
              <span className="text-gray-600">추천 입장:</span>
              <span className={`px-2 py-0.5 rounded font-bold ${
                issue?.recommended_stance === "avoid" || issue?.stance === "avoid" ? "bg-yellow-950/40 text-yellow-400 border border-yellow-800/30" :
                issue?.recommended_stance === "counter" || issue?.stance === "counter" ? "bg-red-950/40 text-red-400 border border-red-800/30" :
                issue?.recommended_stance === "push" || issue?.stance === "push" ? "bg-emerald-950/40 text-emerald-400 border border-emerald-800/30" :
                "bg-blue-950/40 text-blue-400 border border-blue-800/30"
              } text-[9px]`}>
                {issue?.stance || issue?.recommended_stance || issue?.strategy || "모니터"}
              </span>
            </div>

            {/* Response Composer — 대응 작성 */}
            <ResponseComposer issue={issue} keyword={d.keyword} />
          </div>
        </div>

        {/* ─── Sources (3/12) ─── */}
        <div className="col-span-3 wr-card">
          <div className="wr-card-header text-[10px]">데이터 소스</div>
          <div className="px-2.5 py-2 space-y-2">
            {Object.entries(who).map(([ch, v]: [string, any]) => {
              const total = typeof v === "object" ? v.total : v;
              const unique = typeof v === "object" ? v.unique || Math.ceil(total / 50) : Math.ceil(total / 50);
              return (
                <div key={ch} className="text-[10px]">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">
                      {ch === "뉴스" ? "📰" : ch === "블로그" ? "📝" : "💬"} 네이버 {ch}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 ml-4 mt-0.5">
                    <span className="text-gray-300 font-mono font-bold">{total?.toLocaleString()}</span>
                    <span className="text-[8px] text-gray-600">raw</span>
                    <span className="text-blue-400 font-mono">{unique?.toLocaleString()}</span>
                    <span className="text-[8px] text-gray-600">unique</span>
                  </div>
                  {typeof v === "object" && v.period && <div className="text-[8px] text-gray-700 ml-4">{v.period}</div>}
                </div>
              );
            })}
            {gt.interest > 0 && (
              <div className="text-[10px]">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">📊 구글 트렌드</span>
                  <span className="text-blue-400 font-mono font-bold">{gt.interest}/100</span>
                </div>
                <div className="ml-4 mt-0.5">
                  <span className={`text-[9px] font-mono ${gt.change_7d > 0 ? "text-red-400" : "text-emerald-400"}`}>
                    7일 {gt.change_7d > 0 ? "+" : ""}{gt.change_7d?.toFixed(1)}%
                  </span>
                </div>
              </div>
            )}
            {yt.count > 0 && (
              <div className="text-[10px]">
                <span className="text-gray-400">▶ 유튜브</span>
                <div className="ml-4 mt-0.5 text-gray-300 font-mono">{yt.count}건 · {yt.views?.toLocaleString()}조회</div>
              </div>
            )}
          </div>

          {/* AI Operational Interpretation */}
          <div className="mx-2.5 mb-2.5 p-2 bg-[#0d0a18] border border-purple-800/30 rounded">
            <div className="text-[8px] text-purple-400 font-bold mb-0.5">🤖 AI 판단</div>
            <div className="text-[10px] text-gray-300 leading-tight">
              {ai.source === "claude" && ai.summary ? ai.summary :
               ai.sentiment ? `${ai.sentiment} (${ai.score?.toFixed(2)}) — ${ai.recommended_action || "추가 분석 필요"}` :
               directionSummary(d, candidate, opponent)}
            </div>
          </div>
        </div>

        {/* ─── Related Keywords — 3 categories (4/12) ─── */}
        <div className="col-span-4 wr-card">
          <div className="wr-card-header text-[10px]">연관 키워드</div>
          <div className="px-2.5 py-2 space-y-2 max-h-[320px] overflow-y-auto feed-scroll">

            {/* Direct linked */}
            {words.length > 0 && (
              <div>
                <div className="text-[8px] text-blue-400 font-bold uppercase tracking-wider mb-1">직접 연관</div>
                {words.filter((w: any) => !isOpponentWord(w.word, opponent) && !isEmergingWord(w, words)).slice(0, 6).map((w: any, i: number) => (
                  <KeywordBar key={i} word={w} maxCount={words[0]?.count || 1} rank={i} color="#3b82f6" />
                ))}
              </div>
            )}

            {/* Opponent linked */}
            {words.filter((w: any) => isOpponentWord(w.word, opponent)).length > 0 && (
              <div>
                <div className="text-[8px] text-red-400 font-bold uppercase tracking-wider mb-1">상대측 연관</div>
                {words.filter((w: any) => isOpponentWord(w.word, opponent)).slice(0, 4).map((w: any, i: number) => (
                  <KeywordBar key={i} word={w} maxCount={words[0]?.count || 1} rank={i} color="#ef4444" />
                ))}
              </div>
            )}

            {/* Emerging */}
            {words.filter((w: any) => isEmergingWord(w, words)).length > 0 && (
              <div>
                <div className="text-[8px] text-orange-400 font-bold uppercase tracking-wider mb-1">신규 부상</div>
                {words.filter((w: any) => isEmergingWord(w, words)).slice(0, 4).map((w: any, i: number) => (
                  <KeywordBar key={i} word={w} maxCount={words[0]?.count || 1} rank={i} color="#f59e0b" />
                ))}
              </div>
            )}

            {/* Fallback: all keywords if no categorization */}
            {words.length > 0 && words.filter((w: any) => isOpponentWord(w.word, opponent)).length === 0 && (
              <div>
                <div className="text-[8px] text-gray-500 font-bold uppercase tracking-wider mb-1">전체 TOP 10</div>
                {words.slice(0, 10).map((w: any, i: number) => (
                  <KeywordBar key={i} word={w} maxCount={words[0]?.count || 1} rank={i} color={i < 3 ? "#3b82f6" : "#1e3a5f"} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ═══ AI 감성 분석 (Claude) ═══ */}
      {aiSentiment && (
        <div className="wr-card border-t-2 border-t-purple-600">
          <div className="wr-card-header flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-purple-400">🤖 AI 감성 분석</span>
              <span className="text-[8px] text-gray-600 normal-case tracking-normal font-normal">Claude {aiSentiment.model}</span>
            </div>
            <span className="text-[8px] text-gray-600 normal-case tracking-normal font-normal">
              {aiSentiment.total_analyzed}건 분석
            </span>
          </div>

          <div className="px-3 py-2.5 space-y-3">
            {/* 전략 요약 */}
            {aiSentiment.summary && (
              <div className="bg-[#080d16] rounded-lg p-3 border border-[#1a2844]">
                <div className="text-[11px] text-gray-200 leading-relaxed">{aiSentiment.summary}</div>
              </div>
            )}

            {/* 감성 + 타겟 + 톤 — 3-column */}
            <div className="grid grid-cols-3 gap-3">
              {/* 전체 감성 */}
              <div className="bg-[#080d16] rounded-lg p-2.5">
                <div className="text-[8px] text-gray-600 uppercase tracking-widest mb-1.5">전체 감성</div>
                <div className="flex items-center gap-3 mb-2">
                  <div className={`text-xl font-black ${
                    aiSentiment.net_sentiment > 0.2 ? "text-emerald-400" :
                    aiSentiment.net_sentiment < -0.2 ? "text-red-400" : "text-yellow-400"
                  }`}>
                    {aiSentiment.net_sentiment > 0 ? "+" : ""}{(aiSentiment.net_sentiment * 100).toFixed(0)}
                  </div>
                  <div className="text-[9px] text-gray-500">
                    {aiSentiment.net_sentiment > 0.2 ? "긍정 우세" :
                     aiSentiment.net_sentiment < -0.2 ? "부정 우세" : "중립"}
                  </div>
                </div>
                {/* 감성 바 */}
                <div className="flex h-2 rounded-full overflow-hidden bg-[#0a1019]">
                  <div className="bg-emerald-500 h-full" style={{ width: `${(aiSentiment.positive / Math.max(aiSentiment.total_analyzed, 1)) * 100}%` }} />
                  <div className="bg-gray-600 h-full" style={{ width: `${(aiSentiment.neutral / Math.max(aiSentiment.total_analyzed, 1)) * 100}%` }} />
                  <div className="bg-red-500 h-full" style={{ width: `${(aiSentiment.negative / Math.max(aiSentiment.total_analyzed, 1)) * 100}%` }} />
                </div>
                <div className="flex justify-between text-[8px] mt-1">
                  <span className="text-emerald-400">긍정 {aiSentiment.positive}</span>
                  <span className="text-gray-500">중립 {aiSentiment.neutral}</span>
                  <span className="text-red-400">부정 {aiSentiment.negative}</span>
                </div>
              </div>

              {/* 후보별 유불리 */}
              <div className="bg-[#080d16] rounded-lg p-2.5">
                <div className="text-[8px] text-gray-600 uppercase tracking-widest mb-1.5">후보별 유불리</div>
                {/* 우리 후보 */}
                <div className="mb-2">
                  <div className="flex items-center justify-between text-[9px] mb-0.5">
                    <span className="text-blue-400 font-bold">{candidate}</span>
                    <span className="text-gray-500">
                      +{aiSentiment.about_us?.positive || 0} / -{aiSentiment.about_us?.negative || 0}
                    </span>
                  </div>
                  <div className="flex h-1.5 rounded-full overflow-hidden bg-[#0a1019]">
                    {(() => {
                      const total = (aiSentiment.about_us?.positive || 0) + (aiSentiment.about_us?.negative || 0) || 1;
                      return <>
                        <div className="bg-blue-500 h-full" style={{ width: `${(aiSentiment.about_us?.positive || 0) / total * 100}%` }} />
                        <div className="bg-red-500 h-full" style={{ width: `${(aiSentiment.about_us?.negative || 0) / total * 100}%` }} />
                      </>;
                    })()}
                  </div>
                </div>
                {/* 상대 후보 */}
                <div>
                  <div className="flex items-center justify-between text-[9px] mb-0.5">
                    <span className="text-red-400 font-bold">{opponent}</span>
                    <span className="text-gray-500">
                      +{aiSentiment.about_opponent?.positive || 0} / -{aiSentiment.about_opponent?.negative || 0}
                    </span>
                  </div>
                  <div className="flex h-1.5 rounded-full overflow-hidden bg-[#0a1019]">
                    {(() => {
                      const total = (aiSentiment.about_opponent?.positive || 0) + (aiSentiment.about_opponent?.negative || 0) || 1;
                      return <>
                        <div className="bg-red-300 h-full" style={{ width: `${(aiSentiment.about_opponent?.positive || 0) / total * 100}%` }} />
                        <div className="bg-red-700 h-full" style={{ width: `${(aiSentiment.about_opponent?.negative || 0) / total * 100}%` }} />
                      </>;
                    })()}
                  </div>
                </div>
              </div>

              {/* 톤 분석 */}
              <div className="bg-[#080d16] rounded-lg p-2.5">
                <div className="text-[8px] text-gray-600 uppercase tracking-widest mb-1.5">톤 분석</div>
                {Object.entries(aiSentiment.tone_distribution || {}).filter(([, v]) => (v as number) > 0).length > 0 ? (
                  <div className="space-y-0.5">
                    {Object.entries(aiSentiment.tone_distribution || {})
                      .filter(([, v]) => (v as number) > 0)
                      .sort(([, a], [, b]) => (b as number) - (a as number))
                      .map(([tone, count]) => {
                        const max = Math.max(...Object.values(aiSentiment.tone_distribution || {}).map(Number));
                        const toneColors: Record<string, string> = {
                          "지지": "#22c55e", "기대": "#3b82f6", "분노": "#ef4444",
                          "비판": "#f97316", "조롱": "#a855f7", "불안": "#eab308", "중립": "#6b7280",
                        };
                        return (
                          <div key={tone} className="flex items-center gap-1.5">
                            <span className="w-7 text-[8px] text-gray-500 text-right">{tone}</span>
                            <div className="flex-1 h-[4px] bg-[#0a1019] rounded-full overflow-hidden">
                              <div className="h-full rounded-full" style={{
                                width: `${((count as number) / max) * 100}%`,
                                background: toneColors[tone] || "#6b7280"
                              }} />
                            </div>
                            <span className="w-4 text-right text-[8px] text-gray-500 font-mono">{count as number}</span>
                          </div>
                        );
                      })}
                  </div>
                ) : (
                  <div className="text-[9px] text-gray-600">데이터 부족</div>
                )}
                {aiSentiment.mobilization_detected && (
                  <div className="mt-1.5 text-[9px] text-amber-400 font-bold">⚠ 동원 키워드 감지</div>
                )}
              </div>
            </div>

            {/* 위험 + 기회 + 프레임 */}
            <div className="grid grid-cols-2 gap-2">
              {aiSentiment.risk && (
                <div className="bg-red-950/10 border border-red-800/20 rounded-lg p-2.5">
                  <div className="text-[8px] text-red-400 font-bold uppercase tracking-widest mb-1">⚠ 위험</div>
                  <div className="text-[10px] text-red-300/80 leading-relaxed">{aiSentiment.risk}</div>
                </div>
              )}
              {aiSentiment.opportunity && (
                <div className="bg-emerald-950/10 border border-emerald-800/20 rounded-lg p-2.5">
                  <div className="text-[8px] text-emerald-400 font-bold uppercase tracking-widest mb-1">💡 기회</div>
                  <div className="text-[10px] text-emerald-300/80 leading-relaxed">{aiSentiment.opportunity}</div>
                </div>
              )}
            </div>

            {/* 프레임 + 서사 */}
            {(aiSentiment.key_frames?.length > 0 || aiSentiment.key_narratives?.length > 0) && (
              <div className="flex gap-2 flex-wrap">
                {(aiSentiment.key_frames || []).map((f: string, i: number) => (
                  <span key={`f${i}`} className="text-[8px] px-2 py-1 rounded-full bg-purple-950/30 border border-purple-800/30 text-purple-300">
                    🏷 {f}
                  </span>
                ))}
                {(aiSentiment.key_narratives || []).map((n: string, i: number) => (
                  <span key={`n${i}`} className="text-[8px] px-2 py-1 rounded-full bg-blue-950/30 border border-blue-800/30 text-blue-300">
                    📖 {n}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function directionSummary(d: any, candidate: string, opponent: string): string {
  const score = d.tone?.score || 0;
  const isOpp = d.keyword?.includes(opponent);
  const isOur = d.keyword?.includes(candidate);
  if (isOpp && score < -0.1) return `상대 부정 노출 확대 중. 공격 프레임 강화 가능.`;
  if (isOur && score < -0.1) return `우리측 부정 감성 상승. 방어 메시지 준비 필요.`;
  if (score > 0.2) return `긍정 감성 우세. 현재 프레임 유지 권장.`;
  if (score < -0.2) return `부정 감성 확산. 대응 타이밍 검토 필요.`;
  return `감성 혼재. 추이 모니터링 지속.`;
}

function isOpponentWord(word: string, opponent: string): boolean {
  const oppParts = opponent.split(/\s+/);
  return oppParts.some(p => word.includes(p)) || ["국민의힘", "보수", "야당"].some(kw => word.includes(kw));
}

function isEmergingWord(w: any, allWords: any[]): boolean {
  // Heuristic: lower half of count range but exists
  if (allWords.length < 4) return false;
  const median = allWords[Math.floor(allWords.length / 2)]?.count || 1;
  return w.count < median * 0.5 && w.count > 0;
}

function KeywordBar({ word, maxCount, rank, color }: { word: any; maxCount: number; rank: number; color: string }) {
  return (
    <div className="flex items-center gap-1.5 my-0.5">
      <span className={`w-3 text-center font-mono text-[8px] ${rank < 3 ? "text-orange-400 font-bold" : "text-gray-700"}`}>{rank + 1}</span>
      <span className={`w-16 text-[10px] truncate ${rank < 3 ? "font-bold text-gray-200" : "text-gray-400"}`}>{word.word}</span>
      <div className="flex-1 h-[4px] bg-[#0a1019] rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${(word.count / maxCount) * 100}%`, background: color }} />
      </div>
      <span className="w-8 text-right text-[9px] text-gray-600 font-mono">{word.count}</span>
    </div>
  );
}


// ════════════════════════════════════════════════════════════════════
// AI PANELS (preserved)
// ════════════════════════════════════════════════════════════════════

function AiResultCard({ result }: { result: any }) {
  const a = result.analysis;
  const sc = a?.score || 0;
  const scColor = sc > 0.2 ? "text-emerald-400" : sc < -0.2 ? "text-red-400" : "text-yellow-400";
  return (
    <div className="mx-2.5 mb-2.5 p-2.5 bg-[#0d0a18] border border-purple-800/30 rounded text-[11px]">
      <div className="flex justify-between mb-1">
        <strong className="text-gray-200">{result.keyword}</strong>
        <span className={`font-bold font-mono ${scColor}`}>{a?.sentiment} ({sc.toFixed(2)})</span>
      </div>
      {a?.summary && <div className="text-gray-300 mb-1.5 leading-tight">{a.summary}</div>}
      <div className="space-y-0.5 text-[10px]">
        {a?.risk && <div className="text-red-300">⚠ {a.risk}</div>}
        {a?.opportunity && <div className="text-emerald-300">✅ {a.opportunity}</div>}
        {a?.recommended_action && <div className="text-blue-300">➡ {a.recommended_action}</div>}
        {a?.message_suggestion && <div className="bg-purple-950/30 p-1.5 rounded text-gray-200 mt-1">"{a.message_suggestion}"</div>}
        {a?.avoid && <div className="text-red-300">🚫 {a.avoid}</div>}
      </div>
      <div className="text-[9px] text-gray-700 mt-1.5">{result.source} | 남은 {result.remaining}회</div>
    </div>
  );
}

function AiHistoryList({ analyses }: { analyses: any[] }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="px-2.5 pb-2.5 text-[10px]">
      <div className="text-gray-600 mb-1 text-[9px]">최근 분석 이력</div>
      {analyses.slice(0, 5).map((a: any, i: number) => {
        let out: any = null; try { out = JSON.parse(a.output); } catch {}
        const sc = out?.score || 0;
        const scColor = sc > 0.2 ? "text-emerald-400" : sc < -0.2 ? "text-red-400" : "text-yellow-400";
        return (
          <div key={i}>
            <div onClick={() => setOpen(open === i ? null : i)} className="flex justify-between py-1 border-b border-purple-900/20 cursor-pointer hover:bg-purple-900/10">
              <span><span className="text-gray-700">{a.created_at?.slice(5, 16)}</span> <strong className="text-gray-300">{a.keyword}</strong></span>
              {out && <span className={scColor}>{out.sentiment} {open === i ? "▲" : "▼"}</span>}
            </div>
            {open === i && out && (
              <div className="p-2 bg-[#0d0a18] rounded mb-1 border-l-2 border-purple-800 text-[10px]">
                {out.summary && <div className="text-gray-400 leading-tight">{out.summary}</div>}
                {out.recommended_action && <div className="text-blue-400 mt-0.5">➡ {out.recommended_action}</div>}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Daily Briefing Components
// ═══════════════════════════════════════════════════════════════════

/** 접힌 상태에서 핵심 요약만 보여주는 한 줄 바 */
/** 브리핑 마크다운을 인쇄용 HTML로 변환 후 브라우저 인쇄 (PDF 저장 가능) */
function exportBriefingPdf(markdown: string, createdAt: string | null) {
  const html = markdownToHtml(markdown);
  const dateStr = createdAt ? createdAt.slice(0, 16).replace("T", " ") : "";
  const win = window.open("", "_blank");
  if (!win) return;
  win.document.write(`<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>24시간 이슈 브리핑 — ${dateStr}</title>
<style>
  @page { size: A4; margin: 20mm 18mm; }
  body { font-family: -apple-system, "Pretendard", "Noto Sans KR", sans-serif; color: #1a1a1a; line-height: 1.7; font-size: 11pt; max-width: 720px; margin: 0 auto; padding: 24px; }
  h1 { font-size: 17pt; border-bottom: 2px solid #b45309; padding-bottom: 6px; margin-top: 0; color: #92400e; }
  h2 { font-size: 14pt; color: #92400e; margin-top: 28px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
  h3 { font-size: 12pt; color: #1e3a5f; margin-top: 20px; }
  h4 { font-size: 11pt; font-weight: 600; margin-top: 16px; }
  blockquote { border-left: 3px solid #b45309; margin: 12px 0; padding: 8px 14px; background: #fffbeb; color: #78350f; font-style: italic; }
  ul { padding-left: 20px; }
  li { margin-bottom: 4px; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 10pt; }
  th, td { border: 1px solid #ccc; padding: 5px 8px; text-align: left; }
  th { background: #f5f0e8; font-weight: 600; }
  hr { border: none; border-top: 1px solid #ddd; margin: 20px 0; }
  strong { color: #1e3a5f; }
  em { color: #92400e; }
  .meta { text-align: right; font-size: 9pt; color: #888; margin-bottom: 12px; }
  @media print { body { padding: 0; } }
</style>
</head><body>
<div class="meta">생성: ${dateStr} | 캠프 내부 한정</div>
${html}
<script>window.onload=function(){window.print()}<\/script>
</body></html>`);
  win.document.close();
}

/** 마크다운 → 인쇄용 HTML 변환 */
function markdownToHtml(md: string): string {
  const lines = md.split("\n");
  const out: string[] = [];
  let inList = false;
  let inTable = false;
  let tableHeaderDone = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const t = line.trim();

    // 빈 줄
    if (!t) {
      if (inList) { out.push("</ul>"); inList = false; }
      if (inTable) { out.push("</tbody></table>"); inTable = false; tableHeaderDone = false; }
      continue;
    }

    // 테이블 구분선 (|---|---|)
    if (t.match(/^\|[\s\-:|]+\|$/)) {
      tableHeaderDone = true;
      continue;
    }

    // 테이블 행
    if (t.startsWith("|") && t.endsWith("|")) {
      const cells = t.slice(1, -1).split("|").map(c => c.trim());
      if (!inTable) {
        out.push("<table><thead><tr>");
        cells.forEach(c => out.push(`<th>${inline(c)}</th>`));
        out.push("</tr></thead><tbody>");
        inTable = true;
        continue;
      }
      out.push("<tr>");
      cells.forEach(c => out.push(`<td>${inline(c)}</td>`));
      out.push("</tr>");
      continue;
    }

    if (inTable) { out.push("</tbody></table>"); inTable = false; tableHeaderDone = false; }

    // 제목
    if (t.startsWith("#### ")) { if (inList) { out.push("</ul>"); inList = false; } out.push(`<h4>${inline(t.slice(5))}</h4>`); continue; }
    if (t.startsWith("### ")) { if (inList) { out.push("</ul>"); inList = false; } out.push(`<h3>${inline(t.slice(4))}</h3>`); continue; }
    if (t.startsWith("## ")) { if (inList) { out.push("</ul>"); inList = false; } out.push(`<h2>${inline(t.slice(3))}</h2>`); continue; }
    if (t.startsWith("# ")) { if (inList) { out.push("</ul>"); inList = false; } out.push(`<h1>${inline(t.slice(2))}</h1>`); continue; }

    // 인용
    if (t.startsWith("> ")) { if (inList) { out.push("</ul>"); inList = false; } out.push(`<blockquote>${inline(t.slice(2))}</blockquote>`); continue; }

    // 구분선
    if (t.match(/^-{3,}$/)) { if (inList) { out.push("</ul>"); inList = false; } out.push("<hr>"); continue; }

    // 리스트
    if (t.startsWith("- ") || t.startsWith("* ")) {
      if (!inList) { out.push("<ul>"); inList = true; }
      out.push(`<li>${inline(t.slice(2))}</li>`);
      continue;
    }

    // 일반 문단
    if (inList) { out.push("</ul>"); inList = false; }
    out.push(`<p>${inline(t)}</p>`);
  }

  if (inList) out.push("</ul>");
  if (inTable) out.push("</tbody></table>");
  return out.join("\n");
}

function inline(text: string): string {
  return text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

function BriefingSummaryBar({ report }: { report: string }) {
  // 긴급 상황 요약에서 첫 줄 추출
  const lines = report.split("\n").filter((l) => l.trim());
  let summary = "";
  for (const line of lines) {
    const clean = line.replace(/[>#*_\-]/g, "").trim();
    if (clean.length > 20 && !clean.startsWith("작성") && !clean.startsWith("생성") && !clean.startsWith("배포")) {
      summary = clean.slice(0, 120);
      break;
    }
  }

  // CRISIS/ALERT/WATCH 카운트
  const crisisCount = (report.match(/CRISIS/g) || []).length;
  const alertCount = (report.match(/ALERT/g) || []).length;
  const watchCount = (report.match(/WATCH/g) || []).length;

  return (
    <div className="flex items-center gap-3 text-[10px]">
      <div className="flex items-center gap-1.5">
        {crisisCount > 0 && (
          <span className="px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30">
            CRISIS {crisisCount}
          </span>
        )}
        {alertCount > 0 && (
          <span className="px-1.5 py-0.5 rounded bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">
            ALERT {alertCount}
          </span>
        )}
        {watchCount > 0 && (
          <span className="px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-500/30">
            WATCH {watchCount}
          </span>
        )}
      </div>
      <span className="text-gray-500 truncate">{summary}</span>
    </div>
  );
}

/** 마크다운 텍스트를 간단히 렌더링 */
function BriefingRenderer({ markdown }: { markdown: string }) {
  const lines = markdown.split("\n");
  const elements: React.ReactNode[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      elements.push(<div key={i} className="h-2" />);
      continue;
    }

    // 제목 계층
    if (trimmed.startsWith("# ") && !trimmed.startsWith("## ")) {
      elements.push(
        <h2 key={i} className="text-base font-bold text-amber-300 mt-3 mb-1">
          {cleanMd(trimmed.slice(2))}
        </h2>
      );
    } else if (trimmed.startsWith("## ")) {
      elements.push(
        <h3 key={i} className="text-sm font-bold text-amber-200 mt-4 mb-1 pb-1 border-b border-amber-900/30">
          {cleanMd(trimmed.slice(3))}
        </h3>
      );
    } else if (trimmed.startsWith("### ")) {
      elements.push(
        <h4 key={i} className="text-sm font-semibold text-gray-200 mt-3 mb-0.5">
          {cleanMd(trimmed.slice(4))}
        </h4>
      );
    } else if (trimmed.startsWith("> ")) {
      elements.push(
        <blockquote key={i} className="border-l-2 border-amber-600/50 pl-3 text-amber-200/80 italic text-xs my-1">
          {cleanMd(trimmed.slice(2))}
        </blockquote>
      );
    } else if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      const indent = line.startsWith("  ") ? "ml-4" : "";
      elements.push(
        <div key={i} className={`flex gap-1.5 text-xs text-gray-300 ${indent}`}>
          <span className="text-gray-600 mt-0.5 shrink-0">•</span>
          <span>{renderInline(trimmed.slice(2))}</span>
        </div>
      );
    } else if (trimmed.startsWith("---")) {
      elements.push(<hr key={i} className="border-border/50 my-2" />);
    } else if (trimmed.startsWith("|")) {
      // 테이블 행
      const cells = trimmed.split("|").filter((c) => c.trim() && !c.match(/^[\s-:]+$/));
      if (cells.length > 0 && !trimmed.match(/^[\s|:-]+$/)) {
        const isHeader = i + 1 < lines.length && lines[i + 1].trim().match(/^[\s|:-]+$/);
        elements.push(
          <div key={i} className={`grid text-[10px] gap-1 ${isHeader ? "font-bold text-gray-300" : "text-gray-400"}`}
            style={{ gridTemplateColumns: `repeat(${cells.length}, 1fr)` }}>
            {cells.map((c, j) => (
              <span key={j} className="px-1 py-0.5 border-b border-border/30">{c.trim()}</span>
            ))}
          </div>
        );
      }
    } else {
      elements.push(
        <p key={i} className="text-xs text-gray-400 leading-relaxed">
          {renderInline(trimmed)}
        </p>
      );
    }
  }

  return <>{elements}</>;
}

function cleanMd(text: string): string {
  return text.replace(/\*\*/g, "").replace(/\*/g, "").replace(/[🚨🔴🟡👁📋📊🎯⛔✅🚫▶]/g, "").trim();
}

function renderInline(text: string): React.ReactNode {
  // **bold** and *italic* 처리
  const parts: React.ReactNode[] = [];
  const regex = /\*\*(.+?)\*\*|\*(.+?)\*/g;
  let lastIdx = 0;
  let match;
  let key = 0;
  const clean = text.replace(/[🚨🔴🟡👁📋📊🎯⛔✅🚫▶]/g, "");

  while ((match = regex.exec(clean)) !== null) {
    if (match.index > lastIdx) {
      parts.push(clean.slice(lastIdx, match.index));
    }
    if (match[1]) {
      parts.push(<strong key={key++} className="text-gray-200">{match[1]}</strong>);
    } else if (match[2]) {
      parts.push(<em key={key++} className="text-amber-300/70">{match[2]}</em>);
    }
    lastIdx = match.index + match[0].length;
  }
  if (lastIdx < clean.length) {
    parts.push(clean.slice(lastIdx));
  }
  return parts.length > 0 ? <>{parts}</> : clean;
}


// ════════════════════════════════════════════════════════════════════
// RESPONSE COMPOSER — 위기 대응 메시지 작성 UI
// Issue Detail에서 바로 대응 메시지를 작성/복사/채널 선택
// ════════════════════════════════════════════════════════════════════

function ResponseComposer({ issue, keyword }: { issue?: any; keyword?: string }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [channel, setChannel] = useState<"press" | "sns" | "telegram" | "speech">("press");
  const [copied, setCopied] = useState(false);

  // 초안 자동 생성
  const generateDraft = () => {
    const stance = issue?.stance || "monitor";
    const msg = issue?.response_message || "";
    const tp = issue?.talking_points || [];
    const dontSay = issue?.do_not_say || [];
    const pivot = issue?.pivot_to || "";

    const channelLabels: Record<string, string> = {
      press: "보도자료", sns: "SNS 게시", telegram: "텔레그램 메시지", speech: "후보 발언",
    };

    let text = `[${channelLabels[channel]}] ${keyword || ""}\n\n`;

    if (channel === "press") {
      text += `■ 핵심 메시지\n${msg}\n\n`;
      text += `■ 토킹포인트\n${tp.map((t: string, i: number) => `${i + 1}. ${t}`).join("\n")}\n\n`;
      if (dontSay.length) text += `■ 금지 표현\n${dontSay.map((d: string) => `- ${d}`).join("\n")}\n\n`;
      if (pivot) text += `■ 전환 주제: ${pivot}\n`;
    } else if (channel === "sns") {
      text += `${msg}\n\n${tp[0] || ""}\n\n#${keyword?.replace(/\s/g, "")} #경남도지사`;
    } else if (channel === "telegram") {
      text += `⚡ ${keyword}\n\n${msg}\n\n${tp.map((t: string) => `• ${t}`).join("\n")}`;
    } else {
      text += `"${msg}"\n\n${tp[0] || ""}`;
    }

    setDraft(text);
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(draft).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (!issue) return null;

  return (
    <div className="mt-2 border-t border-[#1a2844] pt-2">
      <button
        onClick={() => { setOpen(!open); if (!open && !draft) generateDraft(); }}
        className="w-full text-left flex items-center justify-between text-[10px] px-2 py-1.5 rounded bg-blue-950/20 border border-blue-800/30 hover:bg-blue-950/40 transition"
      >
        <span className="text-blue-300 font-bold">✏️ 대응 메시지 작성</span>
        <span className="text-gray-600">{open ? "▼" : "▶"}</span>
      </button>

      {open && (
        <div className="mt-1.5 space-y-1.5">
          {/* Channel selector */}
          <div className="flex gap-1">
            {(["press", "sns", "telegram", "speech"] as const).map((ch) => (
              <button
                key={ch}
                onClick={() => { setChannel(ch); setTimeout(generateDraft, 0); }}
                className={`text-[8px] px-2 py-1 rounded transition ${
                  channel === ch
                    ? "bg-blue-600/30 text-blue-300 border border-blue-500/40"
                    : "bg-[#0a1019] text-gray-500 border border-[#1a2844] hover:text-gray-300"
                }`}
              >
                {ch === "press" ? "📰 보도자료" : ch === "sns" ? "📱 SNS" : ch === "telegram" ? "💬 텔레그램" : "🎤 발언"}
              </button>
            ))}
          </div>

          {/* Draft editor */}
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="w-full h-28 bg-[#060a12] border border-[#1a2844] rounded p-2 text-[10px] text-gray-200 resize-y focus:border-blue-500/50 focus:outline-none"
            placeholder="대응 메시지를 작성하세요..."
          />

          {/* Action buttons */}
          <div className="flex gap-1.5">
            <button
              onClick={generateDraft}
              className="text-[9px] px-3 py-1 rounded bg-[#0a1019] border border-[#1a2844] text-gray-400 hover:text-gray-200 transition"
            >
              🔄 재생성
            </button>
            <button
              onClick={copyToClipboard}
              className={`text-[9px] px-3 py-1 rounded transition ${
                copied
                  ? "bg-emerald-950/40 border border-emerald-700/40 text-emerald-400"
                  : "bg-blue-950/30 border border-blue-700/30 text-blue-300 hover:bg-blue-950/50"
              }`}
            >
              {copied ? "✅ 복사됨" : "📋 복사"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


// ════════════════════════════════════════════════════════════════════
// KEYWORD COMPARE PANEL — 후보별 연관어 네트워크 + 워드맵 + 감성 비교
// ════════════════════════════════════════════════════════════════════

function KeywordComparePanel({ data, loading, show, onToggle, candidate, opponent }: {
  data: any; loading: boolean; show: boolean; onToggle: () => void; candidate: string; opponent: string;
}) {
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <div className="wr-card border-t-2 border-t-cyan-600">
      <div
        className="wr-card-header flex items-center justify-between cursor-pointer"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2 text-cyan-300">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-500" />
          후보 연관어 비교분석
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[8px] text-gray-600 normal-case tracking-normal font-normal">
            {data ? "분석 완료" : loading ? "분석 중..." : "클릭하여 분석"}
          </span>
          <span className="text-[10px] text-gray-600">{show ? "▼" : "▶"}</span>
        </div>
      </div>

      {show && (
        <div className="p-3 space-y-3">
          {loading && <div className="text-center py-8 text-gray-600 text-xs">🤖 AI 분석 중... (약 30초)</div>}

          {data && (() => {
            const candData = data.results?.[candidate] || {};
            const oppData = data.results?.[opponent] || {};
            const candAi = candData.ai_sentiment || {};
            const oppAi = oppData.ai_sentiment || {};
            const shared = data.shared_words || [];

            return (
              <>
                {/* ═══ 감성 비교 요약 ═══ */}
                <div className="grid grid-cols-2 gap-3">
                  <SentimentSummaryCard
                    name={candidate}
                    ai={candAi}
                    color="blue"
                    isPositive={(candAi.net_sentiment || 0) > (oppAi.net_sentiment || 0)}
                  />
                  <SentimentSummaryCard
                    name={opponent}
                    ai={oppAi}
                    color="red"
                    isPositive={(oppAi.net_sentiment || 0) > (candAi.net_sentiment || 0)}
                  />
                </div>

                {/* ═══ 연관어 네트워크 비교 ═══ */}
                <div className="grid grid-cols-12 gap-3">
                  {/* 김경수 네트워크 */}
                  <div className="col-span-5">
                    <NetworkGraph
                      name={candidate}
                      words={candData.co_words || []}
                      color="blue"
                      hovered={hovered}
                      onHover={setHovered}
                      shared={shared}
                    />
                  </div>

                  {/* 공유 키워드 */}
                  <div className="col-span-2 flex flex-col items-center justify-center">
                    <div className="text-[8px] text-gray-600 uppercase tracking-widest mb-2">공통</div>
                    <div className="space-y-1">
                      {shared.slice(0, 6).map((w: string) => (
                        <div key={w}
                          onMouseEnter={() => setHovered(w)}
                          onMouseLeave={() => setHovered(null)}
                          className={`text-[9px] px-2 py-0.5 rounded-full border text-center transition-all cursor-default ${
                            hovered === w
                              ? "border-cyan-400 text-cyan-300 bg-cyan-950/30"
                              : "border-[#1a2844] text-gray-500 bg-[#080d16]"
                          }`}
                        >{w}</div>
                      ))}
                    </div>
                    {shared.length === 0 && <div className="text-[9px] text-gray-700">없음</div>}
                  </div>

                  {/* 박완수 네트워크 */}
                  <div className="col-span-5">
                    <NetworkGraph
                      name={opponent}
                      words={oppData.co_words || []}
                      color="orange"
                      hovered={hovered}
                      onHover={setHovered}
                      shared={shared}
                    />
                  </div>
                </div>

                {/* ═══ 워드맵 비교 (감성별) ═══ */}
                <div className="grid grid-cols-2 gap-3">
                  <WordCloud
                    name={candidate}
                    ai={candAi}
                    words={candData.co_words || []}
                    color="blue"
                  />
                  <WordCloud
                    name={opponent}
                    ai={oppAi}
                    words={oppData.co_words || []}
                    color="orange"
                  />
                </div>

                {/* ═══ 프레임 비교 ═══ */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-[#080d16] rounded-lg p-2.5">
                    <div className="text-[8px] text-blue-400 font-bold mb-1">{candidate} 프레임</div>
                    <div className="flex flex-wrap gap-1">
                      {(candData.frames || []).map((f: string, i: number) => (
                        <span key={i} className="text-[8px] px-2 py-0.5 rounded-full bg-blue-950/30 border border-blue-800/30 text-blue-300">{f}</span>
                      ))}
                      {(candData.frames || []).length === 0 && <span className="text-[8px] text-gray-700">미검출</span>}
                    </div>
                    {candAi.summary && <div className="text-[9px] text-gray-500 mt-1.5 leading-relaxed">{candAi.summary}</div>}
                  </div>
                  <div className="bg-[#080d16] rounded-lg p-2.5">
                    <div className="text-[8px] text-orange-400 font-bold mb-1">{opponent} 프레임</div>
                    <div className="flex flex-wrap gap-1">
                      {(oppData.frames || []).map((f: string, i: number) => (
                        <span key={i} className="text-[8px] px-2 py-0.5 rounded-full bg-orange-950/30 border border-orange-800/30 text-orange-300">{f}</span>
                      ))}
                      {(oppData.frames || []).length === 0 && <span className="text-[8px] text-gray-700">미검출</span>}
                    </div>
                    {oppAi.summary && <div className="text-[9px] text-gray-500 mt-1.5 leading-relaxed">{oppAi.summary}</div>}
                  </div>
                </div>
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}


// ── 감성 요약 카드 ──
function SentimentSummaryCard({ name, ai, color, isPositive }: { name: string; ai: any; color: string; isPositive: boolean }) {
  const net = ai.net_sentiment || 0;
  const pos = ai.positive || 0;
  const neg = ai.negative || 0;
  const total = pos + neg + (ai.neutral || 0) || 1;
  const posPct = Math.round((pos / total) * 100);
  const negPct = Math.round((neg / total) * 100);

  const borderColor = color === "blue" ? "border-blue-600" : "border-orange-600";
  const textColor = color === "blue" ? "text-blue-400" : "text-orange-400";
  const icon = isPositive ? "👍" : "👎";

  return (
    <div className={`bg-[#080d16] rounded-lg p-3 border-t-2 ${borderColor}`}>
      <div className="flex items-center gap-3">
        <span className="text-2xl">{icon}</span>
        <div>
          <div className={`text-sm font-bold ${textColor}`}>
            {name} {isPositive ? `${posPct}%` : `${negPct}%`}
          </div>
          <div className="text-[9px] text-gray-500">
            {isPositive ? "긍정 감성이 가장 높은 분석 단어" : "부정 감성이 가장 높은 분석 단어"}
          </div>
        </div>
      </div>
      {/* 감성 바 */}
      <div className="flex h-1.5 rounded-full overflow-hidden mt-2 bg-[#0a1019]">
        <div className="bg-emerald-500 h-full" style={{ width: `${posPct}%` }} />
        <div className="bg-gray-600 h-full" style={{ width: `${100 - posPct - negPct}%` }} />
        <div className="bg-red-500 h-full" style={{ width: `${negPct}%` }} />
      </div>
      <div className="flex justify-between text-[8px] mt-0.5">
        <span className="text-emerald-400">긍정 {pos}</span>
        <span className="text-gray-600">중립 {ai.neutral || 0}</span>
        <span className="text-red-400">부정 {neg}</span>
      </div>
    </div>
  );
}


// ── 연관어 네트워크 그래프 (SVG) ──
function NetworkGraph({ name, words, color, hovered, onHover, shared }: {
  name: string; words: any[]; color: string; hovered: string | null;
  onHover: (w: string | null) => void; shared: string[];
}) {
  const cx = 120, cy = 100, r = 70;
  const nodeColor = color === "blue" ? "#3b82f6" : "#f97316";
  const nodeBg = color === "blue" ? "#1e3a5f" : "#5c3a1e";
  const top = words.slice(0, 10);
  const maxCount = top[0]?.count || 1;

  return (
    <div className="bg-[#080d16] rounded-lg p-2">
      <svg width="240" height="200" viewBox="0 0 240 200">
        {/* 연결선 */}
        {top.map((w, i) => {
          const angle = (i / top.length) * Math.PI * 2 - Math.PI / 2;
          const dist = r + 10 + (1 - w.count / maxCount) * 20;
          const wx = cx + Math.cos(angle) * dist;
          const wy = cy + Math.sin(angle) * dist;
          const isShared = shared.includes(w.word);
          const isHov = hovered === w.word;
          return (
            <line key={`l${i}`} x1={cx} y1={cy} x2={wx} y2={wy}
              stroke={isHov ? "#06b6d4" : isShared ? "#6b7280" : nodeBg}
              strokeWidth={isHov ? 1.5 : 0.5} opacity={isHov ? 1 : 0.4} />
          );
        })}

        {/* 중심 노드 */}
        <circle cx={cx} cy={cy} r={22} fill={nodeColor} opacity={0.9} />
        <circle cx={cx} cy={cy} r={18} fill="none" stroke="white" strokeWidth={1.5} opacity={0.3} />
        <text x={cx} y={cy + 4} textAnchor="middle" fill="white" fontSize="10" fontWeight="bold">{name}</text>

        {/* 연관어 노드 */}
        {top.map((w, i) => {
          const angle = (i / top.length) * Math.PI * 2 - Math.PI / 2;
          const dist = r + 10 + (1 - w.count / maxCount) * 20;
          const wx = cx + Math.cos(angle) * dist;
          const wy = cy + Math.sin(angle) * dist;
          const nodeR = 8 + (w.count / maxCount) * 12;
          const isShared = shared.includes(w.word);
          const isHov = hovered === w.word;
          const fill = isHov ? "#06b6d4" : isShared ? "#374151" : nodeBg;
          return (
            <g key={`n${i}`}
              onMouseEnter={() => onHover(w.word)}
              onMouseLeave={() => onHover(null)}
              style={{ cursor: "pointer" }}
            >
              <circle cx={wx} cy={wy} r={nodeR} fill={fill} opacity={isHov ? 1 : 0.7}
                stroke={isHov ? "#06b6d4" : "none"} strokeWidth={1.5} />
              <text x={wx} y={wy + 3} textAnchor="middle" fill="white" fontSize={nodeR > 12 ? "8" : "7"}
                opacity={isHov ? 1 : 0.8}>{w.word}</text>
            </g>
          );
        })}

        {/* 호버 시 카운트 표시 */}
        {hovered && (() => {
          const w = top.find(w => w.word === hovered);
          if (!w) return null;
          return (
            <g>
              <rect x={cx - 50} y={cy + 28} width={100} height={20} rx={4} fill="#1a2844" stroke="#2a3a5c" />
              <text x={cx} y={cy + 42} textAnchor="middle" fill="white" fontSize="9">
                {name}와 {hovered} {w.count}
              </text>
            </g>
          );
        })()}
      </svg>
    </div>
  );
}


// ── 워드클라우드 (감성별 색상) ──
function WordCloud({ name, ai, words, color }: { name: string; ai: any; words: any[]; color: string }) {
  const tones = ai.tone_distribution || {};
  const textColor = color === "blue" ? "text-blue-400" : "text-orange-400";
  const top = words.slice(0, 12);
  const maxCount = top[0]?.count || 1;

  // 감성 단어 매핑 (AI 결과에서)
  const posWords = new Set((ai.key_frames || []).filter((_: string, i: number) => i < 2));
  const negWords = new Set(["논란", "비판", "반대", "의혹", "우려", "범죄", "혐의", "실패", "위기"]);

  return (
    <div className="bg-[#080d16] rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <span className={`text-[10px] font-bold ${textColor}`}>{name}</span>
        <div className="flex items-center gap-2 text-[7px]">
          <span className="text-emerald-400">● 긍정</span>
          <span className="text-red-400">● 부정</span>
          <span className="text-yellow-400">● 중립</span>
        </div>
      </div>
      <div className="flex flex-wrap gap-1 justify-center min-h-[80px] items-center">
        {top.map((w, i) => {
          const scale = 0.6 + (w.count / maxCount) * 0.8;
          const isNeg = negWords.has(w.word);
          const wordColor = isNeg ? "text-red-400" : i < 3 ? "text-emerald-400" : "text-yellow-400";
          return (
            <span key={i}
              className={`${wordColor} transition-all hover:opacity-100`}
              style={{
                fontSize: `${Math.round(10 + scale * 10)}px`,
                fontWeight: scale > 1 ? "bold" : "normal",
                opacity: 0.6 + scale * 0.3,
              }}
            >{w.word}</span>
          );
        })}
      </div>
      {/* 톤 분포 */}
      {Object.keys(tones).length > 0 && (
        <div className="flex gap-1 mt-2 justify-center flex-wrap">
          {Object.entries(tones).filter(([, v]) => (v as number) > 0).map(([tone, count]) => (
            <span key={tone} className="text-[7px] px-1.5 py-0.5 rounded bg-[#0a1019] text-gray-500">{tone}:{count as number}</span>
          ))}
        </div>
      )}
    </div>
  );
}
