"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import {
  getExecutiveSummary, getPollingHistory, getIssueResponses,
  getCalendar, getScores, getPledges, getSocialBuzz, getAlerts, getAiHistory,
  getV3StatusBar, getV3CommandBox, getV3Signals, getV3Proposals,
  getV3Overrides, approveV3Proposal, rejectV3Proposal,
  getKeywordAnalysis, getDailyBriefing, getV2Enrichment, getV2Forecast, getSnsBattle, getIndexTrend, getAIBriefing, getAutoPolls,
} from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { getLatestPoll } from "@/lib/pollData";

// ════════════════════════════════════════════════════════════════════
// 전략본부 — Decision Cockpit
// 4 Layers: Situation → Strategy → Intelligence → Command
// 3 Modes:  Monitoring | Strategy | Command
// ════════════════════════════════════════════════════════════════════

export function StrategyPage() {
  const [exec, setExec] = useState<any>(null);
  const [polls, setPolls] = useState<any>(null);
  const [issues, setIssues] = useState<any>(null);
  const [scores, setScores] = useState<any>(null);
  const [pledges, setPledges] = useState<any>(null);
  const [social, setSocial] = useState<any>(null);
  const [alerts, setAlerts] = useState<any>(null);
  const [cal, setCal] = useState<any>(null);
  const [aiHist, setAiHist] = useState<any>(null);
  const [v3Status, setV3Status] = useState<any>(null);
  const [commands, setCommands] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);
  const [proposals, setProposals] = useState<any[]>([]);
  const [overrides, setOverrides] = useState<any[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<string | null>(null);
  const [issueDetail, setIssueDetail] = useState<any>(null);
  const [proposalLoading, setProposalLoading] = useState<string | null>(null);
  const [briefing, setBriefing] = useState<{ report: string | null; created_at: string | null } | null>(null);
  const [expandedAction, setExpandedAction] = useState<number | null>(null);
  const [expandedAttack, setExpandedAttack] = useState<number | null>(null);
  const [expandedDefense, setExpandedDefense] = useState<number | null>(null);
  const [expandedMsg, setExpandedMsg] = useState<number | null>(null);
  const [v2Data, setV2Data] = useState<any>(null);
  const [forecast, setForecast] = useState<any>(null);
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
  const [snsBattle, setSnsBattle] = useState<any>(null);
  const [stratTab, setStratTab] = useState("situation");
  const [indexTrend, setIndexTrend] = useState<any[]>([]);
  const [aiBriefing, setAiBriefing] = useState<any>(null);
  const [autoPolls, setAutoPolls] = useState<any[]>([]);

  const candidate = useAppStore((s) => s.candidate) || "김경수";
  const opponent = useAppStore((s) => s.opponent) || "박완수";
  const dashboardMode = useAppStore((s) => s.dashboardMode);
  const setDashboardMode = useAppStore((s) => s.setDashboardMode);

  const refreshAll = useCallback(() => {
    getExecutiveSummary().then(setExec).catch(() => {});
    getPollingHistory().then(setPolls).catch(() => {});
    getIssueResponses().then(setIssues).catch(() => {});
    getScores().then(setScores).catch(() => {});
    getPledges().then(setPledges).catch(() => {});
    getSocialBuzz().then(setSocial).catch(() => {});
    getAlerts().then(setAlerts).catch(() => {});
    getCalendar().then(setCal).catch(() => {});
    getAiHistory().then(setAiHist).catch(() => {});
    getV3StatusBar().then(setV3Status).catch(() => {});
    getV3CommandBox().then(setCommands).catch(() => {});
    getV3Signals().then(setSignals).catch(() => {});
    getV3Proposals("pending").then(setProposals).catch(() => {});
    getV3Overrides().then(setOverrides).catch(() => {});
    getDailyBriefing().then(setBriefing).catch(() => {});
    getV2Enrichment().then(setV2Data).catch(() => {});
    getV2Forecast().then(setForecast).catch(() => {});
    getSnsBattle().then(setSnsBattle).catch(() => {});
    getIndexTrend(7).then(r => setIndexTrend(r?.trend || [])).catch(() => {});
    getAIBriefing().then(setAiBriefing).catch(() => {});
    getAutoPolls().then(d => setAutoPolls(d?.polls || [])).catch(() => {});
  }, []);

  useEffect(() => { refreshAll(); }, [refreshAll]);

  // ── Derived data ──
  const resp = issues?.responses || [];
  const pollData = polls?.polls || [];
  const trend = polls?.trend;
  const alertList = alerts?.alerts || [];
  const analyses = aiHist?.analyses || [];
  const attacks = pledges?.attack_points || [];
  const defenses = pledges?.defense_points || [];
  const regional = pledges?.regional_talking_points || {};
  const crisisIssues = resp.filter((r: any) => r.level === "CRISIS");
  const alertIssues = resp.filter((r: any) => r.level === "ALERT");
  const isCrisis = crisisIssues.length > 0;

  const latestPoll = pollData[pollData.length - 1];
  const ourSupport = latestPoll?.our || 0;
  const oppSupport = latestPoll?.opponent ? (Object.values(latestPoll.opponent)[0] as number) || 0 : 0;
  const pollingGap = ourSupport - oppSupport;
  const winProb = exec?.win_probability || (ourSupport > 0 ? Math.min(95, Math.max(5, 50 + pollingGap * 5)) : 50);
  const campaignMode = exec?.campaign_mode || (isCrisis ? "CRISIS" : alertIssues.length > 0 ? "ALERT" : "INITIATIVE");
  const crisisLevelStr = isCrisis ? "CRISIS" : alertIssues.length > 0 ? "ALERT" : "NORMAL";
  const dday = exec?.days_left || 0;
  const riskLevel = exec?.rapid_response_level || "GREEN";
  const topIssue = resp[0];
  const topIssueScore = topIssue?.score || 0;

  // ── Briefing-derived strategy ──
  const bStrat = briefing?.report ? parseBriefingStrategy(briefing.report) : null;

  // ── Actions ──
  const handleIssueDrill = (kw: string) => {
    if (selectedIssue === kw) { setSelectedIssue(null); setIssueDetail(null); return; }
    setSelectedIssue(kw);
    setIssueDetail(null);
    getKeywordAnalysis(kw).then(setIssueDetail).catch(() => {});
  };
  const handleApprove = async (id: string) => {
    setProposalLoading(id);
    await approveV3Proposal(id).catch(() => {});
    getV3Proposals("pending").then(setProposals).catch(() => {});
    getV3CommandBox().then(setCommands).catch(() => {});
    setProposalLoading(null);
  };
  const handleReject = async (id: string) => {
    const reason = prompt("거부 사유:");
    if (!reason) return;
    setProposalLoading(id);
    await rejectV3Proposal(id, reason).catch(() => {});
    getV3Proposals("pending").then(setProposals).catch(() => {});
    setProposalLoading(null);
  };

  return (
    <div className="space-y-1.5">

      {/* ═══ Tab Navigation ═══ */}
      <div className="flex items-center gap-2 px-1">
        {[
          { id: "situation", label: "📊 판세" },
          { id: "issues", label: "🔥 이슈 대응" },
          { id: "execution", label: "✅ 실행·피드백" },
        ].map(t => (
          <button key={t.id} onClick={() => setStratTab(t.id)}
            className={`px-3 py-1.5 rounded text-[11px] font-bold transition ${
              stratTab === t.id
                ? "bg-blue-600/30 text-blue-400 border border-blue-500/40"
                : "text-gray-400 hover:text-gray-300 border border-transparent"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ═══════════════════════════════════════════════════════════
          탭1: 판세 — 인사이트 + 근거 쌍
          ═══════════════════════════════════════════════════════════ */}
      {stratTab === "situation" && (
        <div className="space-y-1.5">
          {/* 전일 대비 변화 */}
          {(() => {
            const prev = indexTrend.length >= 2 ? indexTrend[indexTrend.length - 2] : null;
            const today = indexTrend.length >= 1 ? indexTrend[indexTrend.length - 1] : null;
            if (!today) return null;
            const ld = prev ? today.leading_index - prev.leading_index : null;
            return (
              <div className="wr-card bg-[#0d1420]">
                <div className="px-4 py-2.5 flex items-center gap-4 text-[12px]">
                  <span className="text-gray-200 font-bold">📌 전일 대비</span>
                  {ld !== null ? (
                    <>
                      <span className="text-gray-300">판세 <span className={`font-bold ${ld >= 0 ? "text-emerald-400" : "text-rose-500"}`}>{ld >= 0 ? "+" : ""}{ld.toFixed(1)}</span></span>
                      <span className="text-gray-300">이슈 <span className={`font-bold ${((today.issue_index_avg||0)-(prev?.issue_index_avg||0)) >= 0 ? "text-emerald-400" : "text-rose-500"}`}>{((today.issue_index_avg||0)-(prev?.issue_index_avg||0)) >= 0 ? "+" : ""}{((today.issue_index_avg||0)-(prev?.issue_index_avg||0)).toFixed(1)}</span></span>
                    </>
                  ) : <span className="text-gray-400">데이터 축적 중</span>}
                  <span className="text-gray-400 ml-auto text-[10px]">{today.date}</span>
                </div>
              </div>
            );
          })()}
          {/* AI 브리핑 헤드라인 */}
          {aiBriefing?.headline && (
            <div className="wr-card border-l-2 border-l-cyan-500">
              <div className="px-4 py-3">
                <div className="text-[14px] text-gray-100 font-bold leading-relaxed">
                  📋 {aiBriefing.headline}
                </div>
                {aiBriefing.situation && (
                  <div className="text-[12px] text-gray-300 mt-2 leading-[1.8]">
                    {aiBriefing.situation}
                  </div>
                )}
                <div className="text-[9px] text-gray-400 mt-2">
                  AI 분석 ({aiBriefing.model}) | {aiBriefing.generated_at?.slice(0, 16).replace("T", " ")}
                </div>
              </div>
            </div>
          )}

          {/* 여론조사 */}
          <div className="grid grid-cols-12 gap-1.5">
            <div className="col-span-6 wr-card">
              <div className="px-4 py-3">
                <div className="text-[10px] text-gray-400 mb-1">📊 여론조사</div>
                <div className="text-[13px] text-gray-100 leading-relaxed">
                  {(() => {
                    const lp = getLatestPoll(autoPolls);
                    const pg = lp.kim - lp.park;
                    return pg >= 0
                      ? <>"<span className="text-blue-400 font-bold">{lp.kim.toFixed(1)}</span>:<span className="text-red-400 font-bold">{lp.park.toFixed(1)}</span>로 {pg.toFixed(1)}%p 앞서지만 오차범위 내 초박빙" ({lp.label})</>
                      : <>"<span className="text-red-400 font-bold">{Math.abs(pg).toFixed(1)}%p 뒤지고</span> 있으나 반전 가능한 범위" ({lp.label})</>;
                  })()}
                </div>
                <div className="text-[9px] text-gray-400 mt-1 cursor-pointer hover:text-cyan-400" onClick={() => setActivePage("polling")}>
                  출처: 여론조사 실측 → 여론추세 보기 ↗
                </div>
              </div>
            </div>
            <div className="col-span-6 wr-card">
              <div className="px-4 py-3">
                <div className="text-[10px] text-gray-400 mb-2">근거 데이터</div>
                {(() => {
                  const lp = getLatestPoll(autoPolls);
                  const pg = lp.kim - lp.park;
                  return <>
                    <div className="flex h-7 rounded overflow-hidden">
                      <div className="bg-blue-600 flex items-center justify-center" style={{ width: `${lp.kim / (lp.kim + lp.park) * 100}%` }}>
                        <span className="text-[12px] font-black text-white">{lp.kim.toFixed(1)}%</span>
                      </div>
                      <div className="bg-red-600 flex items-center justify-center flex-1">
                        <span className="text-[12px] font-black text-white">{lp.park.toFixed(1)}%</span>
                      </div>
                    </div>
                    <div className="text-[9px] text-gray-400 mt-1">{lp.label} | 격차 {pg >= 0 ? "+" : ""}{pg.toFixed(1)}%p</div>
                  </>;
                })()}
              </div>
            </div>
          </div>

          {/* 선행지수 + 투표율 */}
          <div className="grid grid-cols-12 gap-1.5">
            <div className="col-span-6 wr-card">
              <div className="px-4 py-3">
                <div className="text-[10px] text-gray-400 mb-1">🧭 판세 인사이트</div>
                <div className="text-[13px] text-gray-100 leading-relaxed">
                  {(() => {
                    const li = v2Data?.leading_index;
                    const idx = li?.index ?? 50;
                    const dir = li?.direction ?? "stable";
                    const dirKo = dir === "gaining" ? "상승" : dir === "losing" ? "하락" : "안정";
                    return <>"판세 <span className="text-cyan-400 font-bold">{idx.toFixed(1)}</span> {dirKo}. {idx >= 53 ? "유리한 흐름이나 방심 금지." : idx <= 47 ? "불리한 흐름. 의제 전환 필요." : "큰 변화 없음. 선제적 이슈 선점 필요."}"</>;
                  })()}
                </div>
                <div className="text-[9px] text-gray-400 mt-1 cursor-pointer hover:text-cyan-400" onClick={() => setActivePage("indices")}>
                  출처: Leading Index 9-component → 인덱스 설명서 ↗
                </div>
              </div>
            </div>
            <div className="col-span-6 wr-card">
              <div className="px-4 py-3">
                <div className="text-[10px] text-gray-400 mb-1">🗳 투표율 인사이트</div>
                <div className="text-[13px] text-gray-100 leading-relaxed">
                  {(() => {
                    const tp = v2Data?.turnout;
                    const gap = tp?.base?.gap ?? 0;
                    return <>"실투표 반영 시 <span className="text-rose-400 font-bold">{Math.abs(gap).toFixed(1)}%p 열세</span>. 60대 고투표율이 원인. 3040 투표율 +5%p가 관건."</>;
                  })()}
                </div>
                <div className="text-[9px] text-gray-400 mt-1 cursor-pointer hover:text-cyan-400" onClick={() => setActivePage("research")}>
                  출처: 투표율 예측 모델 (세대별 교차) → 리서치 보기 ↗
                </div>
              </div>
            </div>
          </div>

          {/* SWOT */}
          <div className="grid grid-cols-4 gap-1.5">
            {[
              { icon: "✅", title: "강점", items: ["대통령 효과 67%", "정당 우위 +28%p"], color: "border-emerald-800/30 bg-emerald-950/10", textColor: "text-emerald-400", source: "출처: 대통령 지지율", page: "research" },
              { icon: "⚠", title: "약점", items: ["투표율 구조 열세", "사법리스크 프레임"], color: "border-rose-800/30 bg-rose-950/10", textColor: "text-rose-400", source: "출처: 투표율 모델", page: "research" },
              { icon: "🎯", title: "기회", items: ["3040 맘카페 활성화", "청년정책 반응 양호"], color: "border-cyan-800/30 bg-cyan-950/10", textColor: "text-cyan-400", source: "출처: 세그먼트 분석", page: "issues" },
              { icon: "🔴", title: "위협", items: ["상대 단수공천 확정", "민생지원금 선점 실패"], color: "border-amber-800/30 bg-amber-950/10", textColor: "text-amber-400", source: "출처: Pre-Trigger", page: "opponent" },
            ].map((s, i) => (
              <div key={i} className={`wr-card border ${s.color}`}>
                <div className="px-3 py-2.5">
                  <div className={`text-[12px] font-bold ${s.textColor} mb-1.5`}>{s.icon} {s.title}</div>
                  {s.items.map((item, j) => (
                    <div key={j} className="text-[11px] text-gray-300 py-0.5">· {item}</div>
                  ))}
                  <div className="text-[8px] text-gray-400 mt-1.5 cursor-pointer hover:text-cyan-400"
                    onClick={() => setActivePage(s.page)}>
                    {s.source} ↗
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════
          탭2: 이슈 대응 — 핵심 이슈 + 근거 + 대응
          ═══════════════════════════════════════════════════════════ */}
      {stratTab === "issues" && (
        <div className="space-y-1.5">
          {/* AI 이슈 분석이 있으면 먼저 표시 */}
          {aiBriefing?.issues && aiBriefing.issues.length > 0 && (
            <div className="wr-card border-l-2 border-l-amber-500">
              <div className="wr-card-header">AI 이슈 분석</div>
              <div className="px-4 py-3 space-y-2">
                {aiBriefing.issues.map((bi: any, i: number) => (
                  <div key={i} className={`rounded-lg p-3 ${
                    bi.urgency === "high" ? "bg-rose-950/10 border border-rose-800/20" :
                    bi.urgency === "medium" ? "bg-amber-950/10 border border-amber-800/20" :
                    "bg-gray-800/10 border border-gray-700/20"
                  }`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-[11px] font-bold ${bi.urgency === "high" ? "text-rose-400" : bi.urgency === "medium" ? "text-amber-400" : "text-gray-300"}`}>
                        {bi.keyword}
                      </span>
                      <span className={`text-[8px] px-1.5 py-0.5 rounded ${
                        bi.urgency === "high" ? "bg-rose-950/30 text-rose-400" : "bg-amber-950/30 text-amber-400"
                      }`}>{bi.urgency}</span>
                    </div>
                    <div className="text-[11px] text-gray-300 leading-[1.7]">{bi.analysis}</div>
                    <div className="text-[11px] text-cyan-400 mt-1">→ {bi.action}</div>
                  </div>
                ))}
                <div className="text-[9px] text-gray-400">AI 분석 ({aiBriefing.model}) | 수치→해석→함의 구조</div>
              </div>
            </div>
          )}

          {/* 이슈 카드 (데이터 근거) */}
          {(issues?.responses || issues || []).filter((r: any) => r.score >= 30).slice(0, 5).map((issue: any, idx: number) => {
            const iiScore = v2Data?.issue_indices?.[issue.keyword]?.index ?? issue.score ?? 0;
            const riData = v2Data?.reaction_indices?.[issue.keyword];
            const rxScore = riData?.final_score ?? 0;
            const rxDir = riData?.direction ?? "neutral";
            const aiSent = v2Data?.ai_sentiment?.[issue.keyword];
            const s6 = aiSent?.sentiment_6way || {};
            const strengths = aiSent?.strength_topics || [];
            const weaknesses = aiSent?.weakness_topics || [];

            return (
              <div key={idx} className="wr-card">
                <div className="px-4 py-3">
                  {/* 헤더 */}
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-[16px] font-black text-amber-400">{idx + 1}</span>
                      <span className="text-[14px] font-bold text-gray-100">{issue.keyword}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                        iiScore >= 80 ? "bg-red-950/30 text-red-400" :
                        iiScore >= 60 ? "bg-amber-950/30 text-amber-400" :
                        "bg-gray-800/30 text-gray-400"
                      }`}>이슈 {iiScore.toFixed(0)}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                        rxScore >= 50 ? "bg-purple-950/30 text-purple-400" :
                        "bg-gray-800/30 text-gray-400"
                      }`}>반응 {rxScore.toFixed(0)}</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-12 gap-3">
                    {/* 왼쪽: 인사이트 + 대응 */}
                    <div className="col-span-5 space-y-2">
                      <div>
                        <div className="text-[10px] text-gray-400 font-bold mb-0.5">왜 중요한가</div>
                        <div className="text-[11px] text-gray-200 leading-relaxed">
                          {iiScore >= 60
                            ? "이슈 강도 높음. 즉시 대응 또는 활용 판단 필요."
                            : "관심 수준. 확산 여부 모니터링."}
                          {rxDir === "positive" ? " 반응 방향 우리에게 유리." : rxDir === "negative" ? " 반응 방향 불리. 프레임 전환 필요." : ""}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-gray-400 font-bold mb-0.5">대응 방안</div>
                        <div className="text-[11px] text-gray-200">
                          {rxDir === "positive" ? "→ 확산 강화. 맘카페/SNS 2차 콘텐츠."
                            : rxDir === "negative" ? "→ 프레임 전환. 정책 이슈로 의제 교체."
                            : "→ 모니터링 유지. 반응 방향 확인 후 판단."}
                        </div>
                      </div>
                      {/* 강점/약점 */}
                      {(strengths.length > 0 || weaknesses.length > 0) && (
                        <div className="grid grid-cols-2 gap-2">
                          {strengths.slice(0, 2).map((s: any, i: number) => (
                            <div key={i} className="text-[9px]">
                              <span className="text-emerald-400">✅ {s.topic}</span> <span className="text-gray-400">{s.count}건</span>
                            </div>
                          ))}
                          {weaknesses.slice(0, 2).map((w: any, i: number) => (
                            <div key={i} className="text-[9px]">
                              <span className="text-rose-400">⚠ {w.topic}</span> <span className="text-gray-400">{w.count}건</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* 오른쪽: 근거 데이터 */}
                    <div className="col-span-7 space-y-2">
                      {/* 6분류 바 */}
                      {Object.keys(s6).length > 0 && (
                        <div>
                          <div className="text-[9px] text-gray-400 mb-0.5">감성 6분류</div>
                          <div className="flex h-4 rounded overflow-hidden">
                            {[
                              { k: "지지", c: "bg-blue-500" },
                              { k: "스윙", c: "bg-purple-500" },
                              { k: "중립", c: "bg-gray-600" },
                              { k: "부정", c: "bg-rose-500" },
                              { k: "정체성", c: "bg-orange-500" },
                              { k: "정책", c: "bg-pink-500" },
                            ].map(cat => {
                              const v = Number(s6[cat.k] || 0);
                              const total = Object.values(s6).reduce((a: number, b: any) => a + Number(b || 0), 0) || 1;
                              const pct = (v / total) * 100;
                              if (pct < 1) return null;
                              return <div key={cat.k} className={`${cat.c} flex items-center justify-center`} style={{ width: `${pct}%` }}>
                                {pct > 10 && <span className="text-[7px] text-white">{cat.k} {v}</span>}
                              </div>;
                            })}
                          </div>
                        </div>
                      )}
                      {/* 뉴스/반응 수치 */}
                      <div className="flex gap-3 text-[10px]">
                        <span className="text-gray-400">뉴스 <span className="text-white font-bold">{issue.mention_count || 0}</span>건</span>
                        <span className="text-gray-400">감성 <span className={`font-bold ${(issue.negative_ratio || 0) > 0.3 ? "text-rose-400" : "text-emerald-400"}`}>
                          {((1 - (issue.negative_ratio || 0)) * 100).toFixed(0)}% 긍정
                        </span></span>
                      </div>
                      {/* 대표 댓글 */}
                      {aiSent?.summary && (
                        <div className="bg-[#080d16] rounded p-2 text-[10px] text-gray-300">
                          💬 {aiSent.summary}
                        </div>
                      )}
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[9px] text-cyan-400 cursor-pointer hover:text-cyan-300 border border-cyan-800/30 px-2 py-0.5 rounded"
                          onClick={() => setActivePage("issues")}>
                          📰 여론분석에서 상세 ↗
                        </span>
                        <span className="text-[8px] text-gray-400">출처: AI 감성 · Issue/Reaction Index</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
          {(!issues || issues.length === 0) && (
            <div className="wr-card"><div className="px-4 py-8 text-center text-gray-400 text-[12px]">갱신 버튼을 눌러 이슈를 수집하세요</div></div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════
          탭3: 실행·피드백 — 오늘 할 일 + 어제 결과 + 위기 기준
          ═══════════════════════════════════════════════════════════ */}
      {stratTab === "execution" && (
        <div className="space-y-1.5">
          {/* AI 내일 제안 */}
          {aiBriefing?.tomorrow && aiBriefing.tomorrow.length > 0 && (
            <div className="wr-card border-l-2 border-l-cyan-500">
              <div className="wr-card-header">AI 추천 액션</div>
              <div className="px-4 py-3 space-y-1.5">
                {aiBriefing.tomorrow.map((t: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 text-[12px]">
                    <span className="text-amber-400 font-black shrink-0">{i + 1}</span>
                    <span className="text-gray-200 leading-[1.7]">{t}</span>
                  </div>
                ))}
                {aiBriefing.feedback && (
                  <div className="text-[11px] text-gray-400 border-t border-[#1a2844] pt-2 mt-2 leading-[1.7]">
                    📌 전일 변화: {aiBriefing.feedback}
                  </div>
                )}
                <div className="text-[9px] text-gray-400">AI 분석 ({aiBriefing.model})</div>
              </div>
            </div>
          )}

          {/* 오늘의 액션 — 데이터 기반 자동 생성 */}
          <div className="wr-card">
            <div className="wr-card-header flex justify-between">
              <span>오늘의 액션</span>
              <span className="text-[9px] text-gray-400 normal-case tracking-normal font-normal">데이터 기반 AI 생성</span>
            </div>
            <div className="divide-y divide-[#0e1825]">
              {(() => {
                // enrichment 데이터에서 자동 생성
                const actions = [];
                const topIssue = (issues?.responses || issues || []).filter((r: any) => r.score >= 40)[0];
                const li = v2Data?.leading_index;
                const tp = v2Data?.turnout;

                if (topIssue) {
                  const rxDir = v2Data?.reaction_indices?.[topIssue.keyword]?.direction;
                  actions.push({
                    action: rxDir === "positive"
                      ? `"${topIssue.keyword}" 확산 강화 — 맘카페/SNS 2차 콘텐츠`
                      : `"${topIssue.keyword}" 프레임 전환 — 정책 이슈로 의제 교체`,
                    basis: `이슈 지수 ${topIssue.score?.toFixed(0) || "?"}, 반응 ${rxDir === "positive" ? "긍정" : "주의"}`,
                    source: "이슈/반응 지수", page: "issues",
                  });
                }

                if (tp?.base?.gap && tp.base.gap < -10) {
                  actions.push({
                    action: "3040 사전투표 참여 캠페인 — 맘카페/신도시 타겟",
                    basis: `투표율 열세 ${Math.abs(tp.base.gap).toFixed(1)}%p. 3040 투표율이 관건`,
                    source: "투표율 예측 모델", page: "research",
                  });
                }

                if (li?.direction === "stable" || !li) {
                  actions.push({
                    action: "선제적 이슈 선점 — 경제/청년 공약 발표로 모멘텀 확보",
                    basis: `판세 ${li?.index?.toFixed(1) || "?"} 안정. 변화를 만들어야 할 시점`,
                    source: "선행지수", page: "indices",
                  });
                }

                if (actions.length === 0) {
                  actions.push(
                    { action: "갱신 버튼을 눌러 오늘의 데이터를 수집하세요", basis: "데이터 수집 필요", source: "시스템", page: "system" },
                  );
                }

                return actions;
              })().map((a, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-2.5">
                  <span className="text-[14px] font-black text-amber-400 w-6">{i + 1}</span>
                  <div className="flex-1">
                    <div className="text-[12px] text-gray-200 font-bold">{a.action}</div>
                    <div className="text-[10px] text-gray-400">근거: {a.basis}
                      <span className="ml-1 text-cyan-400/70 cursor-pointer hover:text-cyan-400" onClick={() => setActivePage(a.page)}>
                        ({a.source} ↗)
                      </span>
                    </div>
                  </div>
                  <span className="text-[10px] px-2 py-1 rounded border border-gray-700 text-gray-400">⬜ 대기</span>
                </div>
              ))}
            </div>
          </div>

          {/* 신호 모니터링 — 위기 + 긍정 */}
          <div className="wr-card">
            <div className="wr-card-header">신호 모니터링 — 다음 주 주시 포인트</div>
            <div className="px-4 py-3 space-y-3">
              {/* 위기 신호 */}
              <div className="text-[11px] text-rose-400 font-bold">! 위기 신호</div>
              {[
                {
                  icon: "!", title: "사법리스크 프레임 확산",
                  current: "이번 주 7건, 2개 채널(뉴스+유튜브)",
                  threshold: "10건 이상 또는 신규 채널 확산 시 위기 단계",
                  reason: "구체적 사실 + 감정적 분노가 결합된 형태. 확산 시 방어 어려움.",
                  severity: "high", source: "뉴스 댓글 수집", page: "issues",
                },
                {
                  icon: "!", title: "투표율 구조 열세 악화",
                  current: "현재 14.8%p 열세 (세대별 투표율 교차 모델)",
                  threshold: "20%p 이상 벌어지면 동원 전략 전면 재검토",
                  reason: "60대 이상 고투표율(78%)이 원인. 3040 투표율 +5%p가 유일한 반전 카드.",
                  severity: "medium", source: "투표율 예측 모델", page: "research",
                },
                {
                  icon: "~", title: "네이버뉴스 부정 비율",
                  current: "지지 12.3% vs 부정 14.1% = 순긍정 -1.8%p (표본 142건)",
                  threshold: "부정 20% 이상 시 언론 대응 강화",
                  reason: "네이버뉴스는 가장 많은 유권자가 접하는 채널. 부정 우세 시 인식 고착 위험.",
                  severity: "low", source: "채널별 감성 분석", page: "issues",
                },
              ].map((s, i) => (
                <div key={i} className={`rounded-lg p-3 ${
                  s.severity === "high" ? "bg-rose-950/10 border border-rose-800/20" :
                  s.severity === "medium" ? "bg-amber-950/10 border border-amber-800/20" :
                  "bg-gray-800/10 border border-gray-700/20"
                }`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[12px] font-black ${
                      s.severity === "high" ? "text-rose-400" : s.severity === "medium" ? "text-amber-400" : "text-gray-400"
                    }`}>{s.icon}</span>
                    <span className="text-[12px] text-gray-100 font-bold">{s.title}</span>
                  </div>
                  <div className="ml-5 space-y-1">
                    <div className="text-[11px] text-gray-300">현재: {s.current}</div>
                    <div className="text-[11px] text-gray-300">기준: <span className="text-amber-300">{s.threshold}</span></div>
                    <div className="text-[10px] text-gray-400 italic">{s.reason}</div>
                    <div className="text-[9px] text-gray-400 cursor-pointer hover:text-cyan-400 mt-0.5"
                      onClick={() => setActivePage(s.page)}>
                      출처: {s.source} → 상세 보기 ↗
                    </div>
                  </div>
                </div>
              ))}

              {/* 긍정 신호 */}
              <div className="text-[11px] text-emerald-400 font-bold mt-2">+ 긍정 신호</div>
              {[
                {
                  title: "대통령 효과 지속",
                  detail: "이재명 대통령 67% 지지율 (4월 4주차, 정부 출범 후 최고 동률). 민주당 48% vs 국힘 20% (+28%p, 4주 연속 정부 출범 후 최고 격차). 대통령 효과 + 정당 우위 모두 강세 → 선행지수에 양(+) 반영.",
                  meaning: "대통령 효과가 유지되는 한 지방선거 여당 후보에게 유리한 환경.",
                  source: "대통령 지지율 (갤럽 주간)", page: "research",
                },
                {
                  title: "맘카페 반응 활발",
                  detail: "창원줌마렐라(25만) 등 경남 맘카페 5곳에서 청년정책·도민지원금 관련 긍정 반응.",
                  meaning: "3040 핵심 유권자 도달 확인. 2차 확산 유도 시 투표율 상승 기대.",
                  source: "커뮤니티 수집 (맘카페 5곳)", page: "issues",
                },
                {
                  title: "여론조사 격차 +2.0%p",
                  detail: "KNN 서던포스트(3/6): 김경수 36.0% vs 박완수 34.0%. 오차범위 내이나 앞서는 추세.",
                  meaning: "공천 확정 후 첫 조사에서 우위. 추세 유지가 관건.",
                  source: "여론조사 (KNN 서던포스트 26.03)", page: "polling",
                },
              ].map((s, i) => (
                <div key={i} className="rounded-lg p-3 bg-emerald-950/10 border border-emerald-800/20">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[12px] font-black text-emerald-400">+</span>
                    <span className="text-[12px] text-gray-100 font-bold">{s.title}</span>
                  </div>
                  <div className="ml-5 space-y-1">
                    <div className="text-[11px] text-gray-300">{s.detail}</div>
                    <div className="text-[10px] text-emerald-400/80 italic">{s.meaning}</div>
                    <div className="text-[9px] text-gray-400 cursor-pointer hover:text-cyan-400 mt-0.5"
                      onClick={() => setActivePage(s.page)}>
                      출처: {s.source} → 상세 보기 ↗
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* AI 제안 승인 큐 */}
          {proposals.length > 0 && (
            <div className="wr-card">
              <div className="wr-card-header flex justify-between">
                <span>AI 제안 승인 큐</span>
                <span className="text-[9px] text-amber-400 font-bold">{proposals.length}건 대기</span>
              </div>
              <div className="divide-y divide-[#0e1825]">
                {proposals.slice(0, 5).map((p: any, i: number) => (
                  <div key={i} className="px-4 py-2 text-[11px] flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                    <span className="text-gray-200 flex-1 truncate">{p.content || p.recommendation}</span>
                    <button onClick={() => approveV3Proposal(p.id).then(() => getV3Proposals("pending").then(setProposals))}
                      className="text-[9px] bg-emerald-950/30 text-emerald-400 border border-emerald-800/30 px-2 py-0.5 rounded hover:bg-emerald-900/40">승인</button>
                    <button onClick={() => rejectV3Proposal(p.id, "반려").then(() => getV3Proposals("pending").then(setProposals))}
                      className="text-[9px] bg-rose-950/30 text-rose-400 border border-rose-800/30 px-2 py-0.5 rounded hover:bg-rose-900/40">반려</button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

    </div>
  );
}


/* ═══════════════════════════════════════════════════════════
   LEGACY CODE REMOVED — 기존 전략본부 UI 삭제
   ═══════════════════════════════════════════════════════════ */
// @ts-ignore — 아래 하위 컴포넌트는 기존 코드에서 참조
const _LEGACY_REMOVED = null;


// ════════════════════════════════════════════════════════════════════
// SUB-COMPONENTS
// ════════════════════════════════════════════════════════════════════

function ModeBadge({ mode }: { mode: string }) {
  const colors: Record<string, string> = {
    CRISIS: "bg-red-600 text-white", ATTACK: "bg-orange-600 text-white",
    DEFENSE: "bg-yellow-600 text-black", INITIATIVE: "bg-emerald-600 text-white",
    ALERT: "bg-orange-600 text-white", NORMAL: "bg-blue-600 text-white",
  };
  return (
    <span className={`px-3 py-1 rounded font-black text-[11px] tracking-wider ${colors[mode] || colors.NORMAL}`}>
      {mode}
    </span>
  );
}

function MetricBlock({ label, value, color, suffix, pulse }: {
  label: string; value: string; color: string; suffix?: string; pulse?: boolean;
}) {
  const tc: Record<string, string> = {
    emerald: "text-emerald-400", red: "text-red-400", blue: "text-blue-400",
    orange: "text-orange-400", yellow: "text-yellow-400",
  };
  return (
    <div className="text-center">
      <div className="text-[7px] text-gray-600 uppercase tracking-widest">{label}</div>
      <div className={`text-[18px] leading-none wr-metric font-black ${tc[color] || "text-gray-400"} ${pulse ? "crisis-pulse" : ""}`}>
        {value}{suffix && <span className="text-[10px] text-gray-600">{suffix}</span>}
      </div>
    </div>
  );
}

function CrisisBadge({ level }: { level: string }) {
  const styles: Record<string, string> = {
    CRISIS: "text-red-400 bg-red-950/40 border-red-700/40",
    ALERT: "text-orange-400 bg-orange-950/40 border-orange-700/40",
    WATCH: "text-yellow-400 bg-yellow-950/40 border-yellow-700/40",
    NORMAL: "text-emerald-400 bg-emerald-950/40 border-emerald-700/40",
  };
  return (
    <div className={`px-2.5 py-1 rounded border text-[10px] font-black flex items-center gap-1.5 ${styles[level] || styles.NORMAL}`}>
      {level === "CRISIS" && <span className="w-1.5 h-1.5 rounded-full bg-red-500 crisis-pulse" />}
      {level}
    </div>
  );
}

function SituationCard({ label, value, color, sub, pulse }: {
  label: string; value: string; color: string; sub?: string; pulse?: boolean;
}) {
  const cm: Record<string, { bg: string; border: string; text: string; glow: string }> = {
    red:     { bg: "bg-red-950/30",     border: "border-red-800/50",     text: "text-red-400",     glow: "shadow-[0_0_12px_rgba(239,68,68,0.15)]" },
    orange:  { bg: "bg-orange-950/20",  border: "border-orange-800/40",  text: "text-orange-400",  glow: "" },
    yellow:  { bg: "bg-yellow-950/20",  border: "border-yellow-800/40",  text: "text-yellow-400",  glow: "" },
    emerald: { bg: "bg-emerald-950/20", border: "border-emerald-800/40", text: "text-emerald-400", glow: "" },
  };
  const c = cm[color] || cm.emerald;
  return (
    <div className={`wr-card ${c.bg} ${c.border} ${c.glow} px-3 py-2.5 text-center`}>
      <div className="text-[8px] text-gray-600 uppercase tracking-widest">{label}</div>
      <div className={`text-[22px] leading-none wr-metric font-black mt-1 ${c.text} ${pulse ? "crisis-pulse" : ""}`}>{value}</div>
      {sub && <div className="text-[9px] text-gray-500 mt-1">{sub}</div>}
    </div>
  );
}

function MomentumTag({ trend }: { trend: any }) {
  if (!trend) return null;
  const m = trend.momentum;
  const val = trend.our_trend;
  if (m === "losing") return (
    <div className="flex items-center gap-1 bg-red-950/40 border border-red-900/40 rounded px-2 py-0.5">
      <span className="w-1.5 h-1.5 rounded-full bg-red-500 crisis-pulse" />
      <span className="text-[8px] font-bold text-red-400">▼{val?.toFixed(2)}</span>
    </div>
  );
  if (m === "gaining") return (
    <div className="flex items-center gap-1 bg-emerald-950/30 border border-emerald-900/30 rounded px-2 py-0.5">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
      <span className="text-[8px] font-bold text-emerald-400">▲+{val?.toFixed(2)}</span>
    </div>
  );
  return null;
}

function ReadinessGauge({ label, value, color }: { label: string; value?: number; color: string }) {
  const val = value ?? Math.floor(Math.random() * 40 + 30);
  return (
    <div>
      <div className="flex justify-between text-[10px] mb-0.5">
        <span className="text-gray-400">{label}</span>
        <span className="font-mono" style={{ color }}>{val.toFixed(0)}%</span>
      </div>
      <div className="h-[5px] bg-[#0a1019] rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(val, 100)}%`, background: color }} />
      </div>
    </div>
  );
}

function IssueDrillDown({ data, keyword }: { data: any; keyword: string }) {
  if (!data) return <div className="px-4 py-3 text-[10px] text-gray-600 bg-[#080d16]">로딩...</div>;

  const words = data.co_words || [];
  const who = data.who_talks || {};
  const gt = data.google_trends || {};
  const tone = data.tone || {};

  return (
    <div className="bg-[#080d16] border-l-2 border-l-blue-600 px-3 py-2 text-[10px] space-y-1.5">
      {/* Score explanation */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-gray-500">감성:</span>
        <span className={tone.score > 0.2 ? "text-emerald-400" : tone.score < -0.2 ? "text-red-400" : "text-yellow-400"}>
          {tone.dominant || "—"} ({tone.score?.toFixed(2) || "—"})
        </span>
        {gt.interest > 0 && (
          <span className="text-gray-500">
            구글트렌드: <span className="text-blue-400">{gt.interest}/100</span>
            {gt.change_7d && <span className={gt.change_7d > 0 ? "text-red-400" : "text-emerald-400"}> {gt.change_7d > 0 ? "+" : ""}{gt.change_7d.toFixed(0)}%</span>}
          </span>
        )}
      </div>

      {/* Source cluster */}
      {Object.entries(who).length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-gray-600">소스:</span>
          {Object.entries(who).map(([ch, v]: [string, any]) => (
            <span key={ch} className="text-gray-400 bg-[#0d1420] px-1.5 py-0.5 rounded">
              {ch} <span className="text-blue-400 font-mono">{typeof v === "object" ? v.total : v}</span>건
            </span>
          ))}
        </div>
      )}

      {/* Co-occurrence keywords */}
      {words.length > 0 && (
        <div className="flex gap-1 flex-wrap">
          {words.slice(0, 10).map((w: any, i: number) => (
            <span key={i} className="bg-blue-950/30 border border-blue-800/30 text-blue-400/70 px-1.5 py-0.5 rounded text-[8px]">
              {w.word} <span className="text-gray-600">{w.count}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function RegionHeatmap({ issues }: { issues: any[] }) {
  const regions = [
    { name: "창원", x: 50, y: 40, size: "lg" },
    { name: "김해", x: 78, y: 22, size: "md" },
    { name: "양산", x: 88, y: 10, size: "sm" },
    { name: "진주", x: 18, y: 55, size: "md" },
    { name: "사천", x: 12, y: 75, size: "sm" },
    { name: "거제", x: 72, y: 78, size: "sm" },
    { name: "통영", x: 52, y: 82, size: "sm" },
    { name: "밀양", x: 72, y: 8, size: "sm" },
  ];

  return (
    <div className="relative h-[110px]">
      {regions.map((reg) => {
        const regionIssues = issues.filter((r: any) => r.region === reg.name || r.keyword?.includes(reg.name));
        const pressure = regionIssues.reduce((max: number, r: any) => Math.max(max, r.score || 0), 0);
        const sizeMap: Record<string, string> = { lg: "w-14 h-9", md: "w-12 h-8", sm: "w-10 h-7" };
        const bgColor = pressure >= 70 ? "bg-red-950/60 border-red-700/50" :
                         pressure >= 40 ? "bg-orange-950/40 border-orange-700/40" :
                         pressure > 0 ? "bg-yellow-950/30 border-yellow-700/30" :
                         "bg-blue-950/30 border-blue-700/30";
        const textColor = pressure >= 70 ? "text-red-400" : pressure >= 40 ? "text-orange-400" : "text-blue-300";

        return (
          <div key={reg.name}
            className={`absolute ${sizeMap[reg.size]} rounded border ${bgColor} flex flex-col items-center justify-center cursor-pointer hover:brightness-150 transition-all`}
            style={{ left: `${reg.x}%`, top: `${reg.y}%`, transform: "translate(-50%, -50%)" }}
            title={regionIssues.map((r: any) => r.keyword).join(", ") || "이슈 없음"}
          >
            <span className={`text-[9px] font-bold ${textColor}`}>{reg.name}</span>
            {pressure > 0 && <span className="text-[7px] text-gray-500">{pressure.toFixed(0)}</span>}
          </div>
        );
      })}
      <div className="absolute bottom-0 left-0 right-0 flex justify-center gap-3 text-[7px]">
        <span className="text-red-400">● 위험</span>
        <span className="text-orange-400">● 경계</span>
        <span className="text-blue-400">● 안정</span>
      </div>
    </div>
  );
}

function PollingIssueOverlay({
  polls, topIssueScore, candidate, opponent,
}: {
  polls: any[]; topIssueScore: number; candidate: string; opponent: string;
}) {
  const ours = polls.map((p) => p.our);
  const opps = polls.map((p) => { const v = p.opponent || {}; return (Object.values(v)[0] as number) || 0; });
  const all = [...ours, ...opps].filter(Boolean);
  if (all.length === 0) return null;

  const mn = Math.min(...all) - 3, mx = Math.max(...all) + 3, rng = mx - mn || 1;
  const w = 360, h = 120, pl = 28, pr = 36, pt = 12, pb = 16;
  const pts = polls.length;
  const xStep = (w - pl - pr) / (pts - 1 || 1);
  const Y = (v: number) => pt + (1 - (v - mn) / rng) * (h - pt - pb);

  const issueNorm = mn + (topIssueScore / 100) * rng;
  const lastOur = ours[pts - 1];
  const lastOpp = opps[pts - 1];
  const gapVal = lastOur - lastOpp;

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="select-none">
      <defs>
        <linearGradient id="areaS" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#22c55e" stopOpacity="0.1" />
          <stop offset="100%" stopColor="#22c55e" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Grid */}
      {[mn, mn + rng * 0.5, mx].map((v) => (
        <g key={v}>
          <line x1={pl} y1={Y(v)} x2={w - pr} y2={Y(v)} stroke="#111d30" strokeWidth="0.5" />
          <text x={pl - 3} y={Y(v) + 3} fill="#2a3f5f" fontSize="6" textAnchor="end" fontFamily="monospace">{v.toFixed(0)}</text>
        </g>
      ))}

      {/* Area */}
      <polygon
        points={`${pl},${Y(ours[0])} ${ours.map((v, i) => `${pl + i * xStep},${Y(v)}`).join(" ")} ${pl + (pts - 1) * xStep},${h - pb} ${pl},${h - pb}`}
        fill="url(#areaS)"
      />

      {/* Issue score reference line */}
      {topIssueScore > 0 && (
        <line x1={pl} y1={Y(issueNorm)} x2={w - pr} y2={Y(issueNorm)} stroke="#f59e0b" strokeWidth="1" strokeDasharray="3,2" opacity="0.4" />
      )}

      {/* Lines */}
      <polyline points={opps.map((v, i) => `${pl + i * xStep},${Y(v)}`).join(" ")} fill="none" stroke="#ef4444" strokeWidth="1.5" strokeDasharray="3,2" opacity="0.6" />
      <polyline points={ours.map((v, i) => `${pl + i * xStep},${Y(v)}`).join(" ")} fill="none" stroke="#22c55e" strokeWidth="2" />

      {/* End points */}
      <circle cx={pl + (pts - 1) * xStep} cy={Y(lastOur)} r="3.5" fill="#22c55e" stroke="#04070d" strokeWidth="1.5" />
      <circle cx={pl + (pts - 1) * xStep} cy={Y(lastOpp)} r="2.5" fill="#ef4444" stroke="#04070d" strokeWidth="1" />

      {/* Labels */}
      <text x={w - pr + 3} y={Y(lastOur) + 3} fill="#22c55e" fontSize="8" fontWeight="bold" fontFamily="monospace">{lastOur}%</text>
      <text x={w - pr + 3} y={Y(lastOpp) + 3} fill="#ef4444" fontSize="8" fontWeight="bold" fontFamily="monospace">{lastOpp}%</text>
      {topIssueScore > 0 && <text x={w - pr + 3} y={Y(issueNorm) + 3} fill="#f59e0b" fontSize="7" fontFamily="monospace">이슈{topIssueScore.toFixed(0)}</text>}

      {/* Gap */}
      <text x={(pl + w - pr) / 2} y={8} fill={gapVal >= 0 ? "#22c55e" : "#ef4444"} fontSize="8" fontWeight="bold" textAnchor="middle" fontFamily="monospace">
        GAP {gapVal >= 0 ? "+" : ""}{gapVal.toFixed(1)}%p
      </text>

      {/* Legend */}
      <circle cx={pl} cy={h - 4} r="2" fill="#22c55e" />
      <text x={pl + 5} y={h - 1} fill="#4ade80" fontSize="6">{candidate}</text>
      <circle cx={pl + 45} cy={h - 4} r="2" fill="#ef4444" />
      <text x={pl + 50} y={h - 1} fill="#f87171" fontSize="6">{opponent}</text>
      {topIssueScore > 0 && (
        <>
          <line x1={pl + 85} y1={h - 4} x2={pl + 93} y2={h - 4} stroke="#f59e0b" strokeWidth="1" strokeDasharray="2,1" />
          <text x={pl + 96} y={h - 1} fill="#f59e0b" fontSize="6">이슈</text>
        </>
      )}
    </svg>
  );
}


// ════════════════════════════════════════════════════════════════════
// BRIEFING STRATEGY PARSER
// ════════════════════════════════════════════════════════════════════

interface BriefingStrategy {
  posture: string;
  urgentSummary: string[];
  actions: { title: string; content: string }[];
  messages: { text: string; type: "attack" | "defense" | "expand"; context: string; format?: string }[];
  regions: { name: string; urgency: "urgent" | "high" | "normal"; reason: string; action?: string }[];
  attacks: { target: string; talkingPoint: string; message?: string; urgency: "immediate" | "today" | "week" }[];
  defenses: { threat: string; response: string; level: "crisis" | "alert" | "watch"; stance?: string }[];
  warnings: string[];
}

function parseBriefingStrategy(md: string): BriefingStrategy {
  const lines = md.split("\n");

  // ── Extract posture (blockquote in section 1) ──
  let posture = "";
  const urgentSummary: string[] = [];
  let inSection1 = false;
  for (const line of lines) {
    if (line.match(/##.*긴급 상황 요약/)) { inSection1 = true; continue; }
    if (inSection1 && line.startsWith("## ")) break;
    if (inSection1 && line.startsWith("> ")) {
      const txt = line.replace(/^>\s*/, "").replace(/\*\*/g, "").trim();
      if (txt && !posture) posture = txt;
    }
    if (inSection1 && line.startsWith("- ")) {
      const txt = line.replace(/^-\s*/, "").replace(/\*\*/g, "").trim();
      if (txt) urgentSummary.push(txt);
    }
  }

  // ── Extract actions (section 6: 오늘의 핵심 행동) ──
  const actions: BriefingStrategy["actions"] = [];
  let inActions = false;
  let curAction: { title: string; content: string } | null = null;
  for (const line of lines) {
    if (line.match(/##.*핵심 행동/)) { inActions = true; continue; }
    if (inActions && line.startsWith("## ")) break;
    if (inActions && line.startsWith("### ")) {
      if (curAction) actions.push(curAction);
      const title = line.replace(/^###\s*/, "").replace(/[✅]/g, "").replace(/\*\*/g, "").trim();
      curAction = { title, content: "" };
      continue;
    }
    if (inActions && curAction && line.startsWith("- ") && line.includes("**내용:**")) {
      curAction.content = line.replace(/^-\s*\*\*내용:\*\*\s*/, "").replace(/\*\*/g, "").trim();
    } else if (inActions && curAction && line.trim().startsWith("- 예시 메시지:")) {
      // skip
    } else if (inActions && curAction && !curAction.content && line.startsWith("- **내용:**")) {
      curAction.content = line.replace(/^-\s*\*\*내용:\*\*\s*/, "").replace(/\*\*/g, "").trim();
    }
  }
  if (curAction) actions.push(curAction);

  // ── Extract messages (italic text in *"..."* patterns) ──
  const messages: BriefingStrategy["messages"] = [];
  const msgRegex = /\*"([^"]+)"\*/g;
  let currentSection = "";
  for (const line of lines) {
    if (line.startsWith("### ")) {
      currentSection = line.replace(/^###\s*/, "").replace(/\*\*/g, "").replace(/[①②③④⑤⑥⑦⑧⑨⑩✅🚫]/g, "").trim();
    }
    let match;
    while ((match = msgRegex.exec(line)) !== null) {
      const text = match[1].trim();
      if (text.length < 10) continue;
      // Classify type
      const isAttack = line.includes("역전") || line.includes("선점") || line.includes("공격") || line.includes("씨앗") || line.includes("씨 뿌린");
      const isDefense = line.includes("방어") || line.includes("대응") || line.includes("반박") || line.includes("차단");
      const type = isAttack ? "attack" : isDefense ? "defense" : "expand";
      const format = line.includes("SNS") ? "SNS" : line.includes("보도자료") ? "보도자료" : line.includes("현장") ? "현장 발언" : undefined;
      messages.push({ text, type, context: currentSection.slice(0, 30), format });
    }
  }

  // ── Extract regional priorities ──
  const regions: BriefingStrategy["regions"] = [];
  const regionMap = new Map<string, { urgency: "urgent" | "high" | "normal"; reasons: string[]; actions: string[] }>();
  const addRegion = (name: string, urgency: "urgent" | "high" | "normal", reason: string, action?: string) => {
    const existing = regionMap.get(name);
    if (existing) {
      if (urgency === "urgent" || (urgency === "high" && existing.urgency === "normal")) existing.urgency = urgency;
      existing.reasons.push(reason);
      if (action) existing.actions.push(action);
    } else {
      regionMap.set(name, { urgency, reasons: [reason], actions: action ? [action] : [] });
    }
  };
  for (const line of lines) {
    const t = line.replace(/\*\*/g, "");
    if (t.includes("거제") || t.includes("통영") || t.includes("고성")) {
      if (t.includes("조선업") || t.includes("현장 방문") || t.includes("목표 선거구")) {
        addRegion("거제·통영·고성", "urgent", "조선업 현장 메시지 선점", "현장 방문 + 영상 클립 SNS 투입");
      }
    }
    if (t.includes("사천") && (t.includes("MRO") || t.includes("우주항공"))) {
      addRegion("사천", "high", "MRO 산단·우주항공 성과 프레임", "김경수 도정 성과 연결");
    }
    if (t.includes("창원") && (t.includes("특례시") || t.includes("낙동강"))) {
      addRegion("창원", "high", "특례시 특화 공약·낙동강벨트 핵심 승부처", "특례시 한 줄 메시지 배포");
    }
    if (t.includes("부울경") && (t.includes("통합") || t.includes("메가시티") || t.includes("경제동맹"))) {
      addRegion("부울경", "urgent", "행정통합 '대안 제시자' 포지션 전환", "경제 실익 중심 메시지 발신");
    }
  }
  regionMap.forEach((v, k) => {
    regions.push({ name: k, urgency: v.urgency, reason: v.reasons[0], action: v.actions[0] });
  });
  // Sort: urgent first, then high, then normal
  regions.sort((a, b) => {
    const order = { urgent: 0, high: 1, normal: 2 };
    return order[a.urgency] - order[b.urgency];
  });

  // ── Extract attack points ──
  const attackItems: BriefingStrategy["attacks"] = [];
  // Go through 위기 이슈 분석 & 주의 이슈 for offensive opportunities
  let inCrisis = false;
  let currentIssueTitle = "";
  for (const line of lines) {
    if (line.match(/##.*위기 이슈 분석/)) { inCrisis = true; continue; }
    if (line.match(/##.*주의 이슈/)) { inCrisis = true; continue; }
    if (line.match(/##.*모니터링/)) { inCrisis = false; continue; }
    if (inCrisis && line.startsWith("### ")) {
      currentIssueTitle = line.replace(/^###\s*/, "").replace(/\*\*/g, "").replace(/[①②③④⑤⑥⑦⑧⑨⑩]/g, "").trim();
    }
    if (inCrisis && line.includes("대응 방안")) continue;
    // Look for offensive-oriented bullets
    if (inCrisis && line.startsWith("- ") && currentIssueTitle) {
      const t = line.replace(/^-\s*/, "").replace(/\*\*/g, "");
      if (t.includes("선점") || t.includes("프레임 전환") || t.includes("역전") || t.includes("재선점") || t.includes("확장") || t.includes("연결") || t.includes("활용") || t.includes("공론화") || t.includes("선제")) {
        const msgMatch = t.match(/\*"([^"]+)"\*/) || t.match(/\*(.{10,60}?)\*/);
        attackItems.push({
          target: currentIssueTitle.slice(0, 25),
          talkingPoint: t.replace(/\*"[^"]+"\*/g, "").replace(/\*[^*]+\*/g, "").slice(0, 80).trim(),
          message: msgMatch ? msgMatch[1] : undefined,
          urgency: t.includes("즉각") || t.includes("오늘") ? "immediate" : t.includes("24시간") || t.includes("내일") ? "today" : "week",
        });
      }
    }
  }

  // ── Extract defense points ──
  const defenseItems: BriefingStrategy["defenses"] = [];
  let inIssues = false;
  let curIssueForDef = "";
  let curLevel: "crisis" | "alert" | "watch" = "crisis";
  for (const line of lines) {
    if (line.match(/##.*위기 이슈 분석/)) { inIssues = true; curLevel = "crisis"; continue; }
    if (line.match(/##.*주의 이슈/)) { inIssues = true; curLevel = "alert"; continue; }
    if (line.match(/##.*모니터링/)) { inIssues = true; curLevel = "watch"; continue; }
    if (line.match(/##.*여론 흐름/) || line.match(/##.*핵심 행동/)) { inIssues = false; continue; }
    if (inIssues && line.startsWith("### ")) {
      curIssueForDef = line.replace(/^###\s*/, "").replace(/\*\*/g, "").replace(/[①②③④⑤⑥⑦⑧⑨⑩]/g, "").trim();
    }
    // Look for defensive items: threats + responses
    if (inIssues && line.includes("핵심 위험:")) {
      const txt = line.replace(/\*\*핵심 위험:\*\*\s*/, "").replace(/\*\*/g, "").trim();
      if (txt) {
        defenseItems.push({
          threat: curIssueForDef.slice(0, 25),
          response: txt.slice(0, 100),
          level: curLevel,
          stance: txt.includes("역전") || txt.includes("전환") ? "reframe" : txt.includes("회피") || txt.includes("거리두기") ? "avoid" : "counter",
        });
      }
    }
    if (inIssues && line.includes("핵심 위협")) {
      const txt = line.replace(/.*핵심 위협[:\s]*/, "").replace(/\*\*/g, "").trim();
      if (txt && txt.length > 5) {
        defenseItems.push({
          threat: curIssueForDef.slice(0, 25),
          response: txt.slice(0, 100),
          level: curLevel,
          stance: "counter",
        });
      }
    }
    if (inIssues && (line.includes("경고:") || line.includes("**경고:**"))) {
      const txt = line.replace(/.*경고:\*?\*?\s*/, "").replace(/\*\*/g, "").trim();
      if (txt && txt.length > 5) {
        defenseItems.push({
          threat: curIssueForDef.slice(0, 25),
          response: txt.slice(0, 100),
          level: curLevel,
          stance: "reframe",
        });
      }
    }
  }

  // Fill defense from "현황" for watch-level items if we didn't get defense from 핵심 위험
  const coveredThreats = new Set(defenseItems.map(d => d.threat));
  let watchIssue = "";
  for (const line of lines) {
    if (line.match(/##.*모니터링/)) { inIssues = true; continue; }
    if (line.match(/##.*여론 흐름/) || line.match(/##.*핵심 행동/)) { inIssues = false; continue; }
    if (inIssues && line.startsWith("### ")) {
      watchIssue = line.replace(/^###\s*/, "").replace(/\*\*/g, "").replace(/[①②③④⑤⑥⑦⑧⑨⑩]/g, "").trim();
    }
    if (inIssues && line.includes("대응 포인트:") && watchIssue && !coveredThreats.has(watchIssue.slice(0, 25))) {
      const txt = line.replace(/.*대응 포인트:\*?\*?\s*/, "").replace(/\*\*/g, "").trim();
      if (txt) {
        defenseItems.push({
          threat: watchIssue.slice(0, 25),
          response: txt.slice(0, 100),
          level: "watch",
          stance: "reframe",
        });
      }
    }
  }

  // ── Extract warnings (절대 금지) ──
  const warnings: string[] = [];
  let inWarnings = false;
  for (const line of lines) {
    if (line.match(/##.*주의사항/)) { inWarnings = true; continue; }
    if (inWarnings && line.startsWith("## ")) break;
    if (inWarnings && line.startsWith("> ")) {
      const txt = line.replace(/^>\s*/, "").replace(/\*\*/g, "").trim();
      if (txt.length > 10) warnings.push(txt);
    }
  }

  return { posture, urgentSummary, actions, messages, regions, attacks: attackItems, defenses: defenseItems, warnings };
}


// ════════════════════════════════════════════════════════════════════
// INFO TOOLTIP — 물음표 아이콘 + 호버 시 설명 표시
// ════════════════════════════════════════════════════════════════════

function InfoTooltip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  // 바깥 클릭 시 닫기
  useEffect(() => {
    if (!show) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node) &&
          btnRef.current && !btnRef.current.contains(e.target as Node)) {
        setShow(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [show]);

  return (
    <span className="relative inline-flex">
      <button
        ref={btnRef}
        onClick={() => setShow(!show)}
        className="w-3.5 h-3.5 rounded-full border border-gray-700 text-gray-600 hover:text-gray-300 hover:border-gray-500 flex items-center justify-center text-[8px] font-bold cursor-help transition shrink-0"
      >
        ?
      </button>
      {show && (
        <div
          ref={ref}
          className="fixed z-[9999] w-80 max-h-[70vh] overflow-y-auto p-3 rounded-lg border border-[#2a3a5c] bg-[#0d1420]/95 backdrop-blur-sm shadow-2xl shadow-black/60"
          style={{
            top: (() => {
              const rect = btnRef.current?.getBoundingClientRect();
              if (!rect) return 100;
              // 화면 상단 절반이면 아래로, 하단이면 위로
              return rect.top < window.innerHeight / 2
                ? rect.bottom + 8
                : Math.max(8, rect.top - 8);
            })(),
            left: (() => {
              const rect = btnRef.current?.getBoundingClientRect();
              if (!rect) return 100;
              // 좌측 넘침 방지
              return Math.min(Math.max(8, rect.left - 140), window.innerWidth - 330);
            })(),
            ...((() => {
              const rect = btnRef.current?.getBoundingClientRect();
              if (rect && rect.top >= window.innerHeight / 2) {
                return { top: "auto", bottom: window.innerHeight - rect.top + 8 } as any;
              }
              return {};
            })()),
          }}
        >
          {/* 닫기 버튼 */}
          <button
            onClick={() => setShow(false)}
            className="absolute top-1.5 right-2 text-gray-600 hover:text-gray-300 text-[10px]"
          >✕</button>

          <div className="text-[10px] text-gray-200 leading-[1.7] space-y-1.5">
            {text.split("\n").map((line, i) => {
              if (!line.trim()) return <div key={i} className="h-1" />;
              // 제목줄 (영문 대문자 또는 한글로 시작, 짧은 줄)
              if (line.length < 30 && !line.startsWith("•") && !line.startsWith("①") && !line.startsWith("-")) {
                return <div key={i} className="text-blue-400 font-bold text-[10px] mt-1">{line}</div>;
              }
              // 번호 항목
              if (/^[①②③④⑤]/.test(line)) {
                return <div key={i} className="text-gray-200 pl-1">{line}</div>;
              }
              // 불릿
              if (line.startsWith("•") || line.startsWith("-")) {
                return <div key={i} className="text-gray-300 pl-2">{line}</div>;
              }
              return <div key={i} className="text-gray-400">{line}</div>;
            })}
          </div>
        </div>
      )}
    </span>
  );
}
