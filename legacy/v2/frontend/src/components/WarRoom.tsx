"use client";
import { useEffect, useState, useCallback } from "react";
import {
  getExecutiveSummary, getPollingHistory, getIssueResponses,
  getCalendar, getScores, getSocialBuzz, getAlerts, getAiHistory,
  getV3StatusBar, getV3CommandBox, getV3Signals, getV3Proposals,
  getV3Overrides, approveV3Proposal, rejectV3Proposal,
  getKeywordAnalysis, getSnsBattle, getV2Enrichment, getIndexTrend, getAutoPolls,
  getCandidateBuzz, getNewsClusters,
} from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { POLL_DATA, mergeAutoPolls, getLatestPoll } from "@/lib/pollData";

// ════════════════════════════════════════════════════════════════════
// WAR ROOM — Strategic Command Cockpit
// Layout preserved: TopBar → Chart+Action → Issue+Region+Intel
// Added: interpretation + override + execution layers
// ════════════════════════════════════════════════════════════════════

export function WarRoom() {
  const [exec, setExec] = useState<any>(null);
  const [polls, setPolls] = useState<any>(null);
  const [issues, setIssues] = useState<any>(null);
  const [scores, setScores] = useState<any>(null);
  const [social, setSocial] = useState<any>(null);
  const [alerts, setAlerts] = useState<any>(null);
  const [cal, setCal] = useState<any>(null);
  const [aiHist, setAiHist] = useState<any>(null);
  const [commands, setCommands] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);
  const [proposals, setProposals] = useState<any[]>([]);
  const [overrides, setOverrides] = useState<any[]>([]);
  const [proposalLoading, setProposalLoading] = useState<string | null>(null);
  const [snsBattle, setSnsBattle] = useState<any>(null);
  const [enrichment, setEnrichment] = useState<any>(null);
  const [indexTrend, setIndexTrend] = useState<any[]>([]);
  const [autoPolls, setAutoPolls] = useState<any[]>([]);
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<string | null>(null);
  const [issueDetail, setIssueDetail] = useState<any>(null);
  const [candidateBuzz, setCandidateBuzz] = useState<Record<string, any>>({});
  const [newsClusters, setNewsClusters] = useState<any[]>([]);

  const candidate = useAppStore((s) => s.candidate) || "김경수";
  const opponent = useAppStore((s) => s.opponent) || "박완수";
  const setActivePage = useAppStore((s) => s.setActivePage);

  const refreshAll = useCallback(() => {
    getExecutiveSummary().then(setExec).catch(() => {});
    getPollingHistory().then(setPolls).catch(() => {});
    getIssueResponses().then(setIssues).catch(() => {});
    getScores().then(setScores).catch(() => {});
    getSocialBuzz().then(setSocial).catch(() => {});
    getAlerts().then(setAlerts).catch(() => {});
    getCalendar().then(setCal).catch(() => {});
    getAiHistory().then(setAiHist).catch(() => {});
    getV3CommandBox().then(setCommands).catch(() => {});
    getV3Signals().then(setSignals).catch(() => {});
    getV3Proposals("pending").then(setProposals).catch(() => {});
    getV3Overrides().then(setOverrides).catch(() => {});
    getSnsBattle().then(setSnsBattle).catch(() => {});
    getV2Enrichment().then(setEnrichment).catch(() => {});
    getIndexTrend(7).then(r => setIndexTrend(r?.trend || [])).catch(() => {});
    getAutoPolls().then(d => setAutoPolls(d?.polls || [])).catch(() => {});
    getCandidateBuzz().then(d => setCandidateBuzz(d?.buzz || {})).catch(() => {});
    getNewsClusters().then(d => setNewsClusters(d?.clusters || [])).catch(() => {});
  }, []);

  useEffect(() => { refreshAll(); }, [refreshAll]);

  // ── Derived ──
  // 후보추적 키워드 필터 (이슈 레이더에서 제외)
  const CAND_KWS = [`${candidate} 경남`, `${candidate} 공약`, `${candidate} 복귀`,
    `${opponent} 경남`, `${opponent} 공약`, "국민의힘 경남", "민주당 경남", "전희영 경남"];
  const isCandKw = (kw: string) => CAND_KWS.some(ck => kw.includes(ck) || ck.includes(kw));
  const resp = (issues?.responses || []).filter((r: any) => !isCandKw(r.keyword));
  const pollData = polls?.polls || [];
  const trend = polls?.trend;
  const alertList = alerts?.alerts || [];
  const analyses = aiHist?.analyses || [];
  const crisisIssues = resp.filter((r: any) => r.level === "CRISIS");
  const alertIssues = resp.filter((r: any) => r.level === "ALERT");
  const isCrisis = crisisIssues.length > 0;

  const latestPoll = pollData[pollData.length - 1];
  const prevPoll = pollData.length > 1 ? pollData[pollData.length - 2] : null;
  const ourSupport = latestPoll?.our || 0;
  const oppSupport = latestPoll?.opponent ? (Object.values(latestPoll.opponent)[0] as number) || 0 : 0;
  const prevOur = prevPoll?.our || ourSupport;
  const prevOpp = prevPoll?.opponent ? (Object.values(prevPoll.opponent)[0] as number) || 0 : oppSupport;
  const pollingGap = ourSupport - oppSupport;
  const prevGap = prevOur - prevOpp;
  const gapDelta = pollingGap - prevGap;
  const gapMomentum = trend?.our_trend || 0;
  const winProb = exec?.win_probability || (ourSupport > 0 ? Math.min(95, Math.max(5, 50 + pollingGap * 5)) : 50);
  const dday = exec?.days_left || 0;
  const riskLevel = exec?.rapid_response_level || "GREEN";

  // ── Actions ──
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
  const handleIssueDrill = (kw: string) => {
    if (selectedIssue === kw) { setSelectedIssue(null); setIssueDetail(null); return; }
    setSelectedIssue(kw);
    setIssueDetail(null);
    getKeywordAnalysis(kw).then(setIssueDetail).catch(() => {});
  };

  // 전일 대비 계산
  const prevSnap = indexTrend.length >= 2 ? indexTrend[indexTrend.length - 2] : null;
  const todaySnap = indexTrend.length >= 1 ? indexTrend[indexTrend.length - 1] : null;
  // 판세지수 전일대비 (enrichment turnout correction 사용)
  const pandseNow = enrichment?.turnout?.correction?.pandse_index ?? null;
  const liDelta = todaySnap && prevSnap ? (pandseNow ? pandseNow - 50 : todaySnap.leading_index - prevSnap.leading_index) : null;
  const iiDelta = todaySnap && prevSnap ? (todaySnap.issue_index_avg || 0) - (prevSnap.issue_index_avg || 0) : null;
  const rxDelta = todaySnap && prevSnap ? (todaySnap.reaction_index_avg || 0) - (prevSnap.reaction_index_avg || 0) : null;

  return (
    <div className="space-y-1.5 pb-12 relative">

      {/* ═══════════════════════════════════════════════════════════════
          전일 대비 변화 배너
          ═══════════════════════════════════════════════════════════════ */}
      {todaySnap && (
        <div className="wr-card bg-[#0d1420] border-[#1a2844]">
          <div className="px-4 py-2 flex items-center gap-4 text-[11px]">
            <span className="text-gray-300 font-bold shrink-0">📌 전일 대비</span>
            {liDelta !== null ? (
              <>
                <span className="text-gray-400">판세지수 <span className={`font-bold ${liDelta >= 0 ? "text-emerald-400" : "text-rose-500"}`}>{liDelta >= 0 ? "+" : ""}{liDelta.toFixed(1)}</span></span>
                <span className="text-gray-400">이슈 <span className={`font-bold ${(iiDelta || 0) >= 0 ? "text-emerald-400" : "text-rose-500"}`}>{(iiDelta || 0) >= 0 ? "+" : ""}{(iiDelta || 0).toFixed(1)}</span></span>
                <span className="text-gray-400">반응 <span className={`font-bold ${(rxDelta || 0) >= 0 ? "text-emerald-400" : "text-rose-500"}`}>{(rxDelta || 0) >= 0 ? "+" : ""}{(rxDelta || 0).toFixed(1)}</span></span>
              </>
            ) : (
              <span className="text-gray-400">데이터 축적 중 (2일 이상 필요)</span>
            )}
            {crisisIssues.length > 0 && (
              <span className="text-red-400 font-bold ml-auto">🔴 위기 이슈 {crisisIssues.length}건</span>
            )}
            {crisisIssues.length === 0 && (
              <span className="text-gray-400 ml-auto">최종: {todaySnap.date}</span>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          역대 득표율 + 9대 여론조사 — 최상단
          ═══════════════════════════════════════════════════════════════ */}
      <div className="wr-card animate-fadeIn" style={{overflow:"visible"}}>
        <div className="wr-card-header flex justify-between items-center">
          <div className="flex items-center gap-2">
            <span>역대 득표율 + 9대 여론조사</span>
          </div>
          <div className="flex items-center gap-3 text-[8px]">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" /><span className="text-gray-400">김경수</span></span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /><span className="text-gray-400">박완수</span></span>
            <span className="text-gray-400">●실제득표 ○여론조사 | 출처: 중앙선관위, nesdc</span>
          </div>
        </div>
        <div className="p-2">
          <WarRoomPollChart autoPolls={autoPolls} />
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════
          여론조사 vs 실투표 예측 — 핵심 지표
          ═══════════════════════════════════════════════════════════════ */}
      {(() => {
        const recentPolls = POLL_DATA.filter(p => p.type === "poll").slice(-5);
        const latestPoll = POLL_DATA[POLL_DATA.length - 1];
        const pk = latestPoll.kim;
        const pp = latestPoll.park;
        const pollGapVal = pk - pp;
        const turnoutModel = enrichment?.turnout;
        const tBase = turnoutModel?.base;
        const tKim = tBase?.kim_pct || 50;
        const tPark = tBase?.park_pct || 50;
        const tGap = tBase?.gap || 0;
        const tTurnout = tBase?.total_turnout || 0;
        return (
          <div className="wr-card border-2 border-blue-800/40 bg-[#060d18] live-pulse relative wr-scanline border-glow">
            <div className="px-4 py-3 space-y-3">
              <div className="text-[12px] text-blue-300 font-black uppercase tracking-wider">여론조사 vs 실투표 예측</div>

              <div className="grid grid-cols-3 gap-4">
                {/* 여론조사 */}
                <div className="space-y-1.5">
                  <div className="text-[10px] text-gray-400 font-bold animate-slide-left">여론조사 (지지 의향)</div>
                  <div className="flex h-10 rounded-lg overflow-hidden">
                    <div className="bg-blue-600 flex items-center justify-center animate-bar bar-breath" style={{ width: `${pk / (pk + pp) * 100}%` }}>
                      <span className="text-[16px] font-black text-white animate-number" style={{animationDelay:"0.5s"}}>{pk.toFixed(1)}%</span>
                    </div>
                    <div className="bg-red-600 flex items-center justify-center animate-bar-delay bar-breath" style={{ width: `${pp / (pk + pp) * 100}%`, animationDelay: "2s" }}>
                      <span className="text-[16px] font-black text-white animate-number" style={{animationDelay:"0.7s"}}>{pp.toFixed(1)}%</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className={`text-[14px] font-black animate-number gap-shimmer ${pollGapVal >= 0 ? "text-blue-400 win-glow" : "text-red-400 lose-glow"}`} style={{animationDelay:"0.8s"}}>
                      {pollGapVal >= 0 ? "+" : ""}{pollGapVal.toFixed(1)}%p
                    </span>
                    <span className="text-[8px] text-gray-500">{latestPoll.label} ({latestPoll.date})</span>
                  </div>
                </div>

                {/* 실투표 예측 기본값 */}
                <div className="space-y-1.5">
                  <div className="text-[10px] text-gray-400 font-bold animate-slide-left" style={{animationDelay:"0.1s"}}>실투표 예측 <span className="text-gray-600 font-normal">(기본값)</span></div>
                  <div className="flex h-10 rounded-lg overflow-hidden">
                    <div className="bg-blue-900 flex items-center justify-center animate-bar" style={{ width: `${tKim}%`, animationDelay:"0.2s" }}>
                      <span className="text-[16px] font-black text-blue-300 animate-number" style={{animationDelay:"0.7s"}}>{tKim.toFixed(1)}%</span>
                    </div>
                    <div className="bg-red-900 flex items-center justify-center animate-bar-delay" style={{ width: `${tPark}%`, animationDelay:"0.3s" }}>
                      <span className="text-[16px] font-black text-red-300 animate-number" style={{animationDelay:"0.9s"}}>{tPark.toFixed(1)}%</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className={`text-[14px] font-black animate-number ${tGap >= 0 ? "text-emerald-400 win-glow" : "text-rose-500 lose-glow"}`} style={{animationDelay:"1.0s"}}>
                      {tGap >= 0 ? "+" : ""}{tGap.toFixed(1)}%p
                    </span>
                    <span className="text-[8px] text-gray-500">7대 투표율 · NESDC 3개 조사</span>
                  </div>
                </div>

                {/* 실투표 예측 다이내믹 */}
                {(() => {
                  const corr = turnoutModel?.correction;
                  if (!corr) return <div />;
                  const pandseIndex = corr.pandse_index || 50;
                  const dynKim = corr.dynamic_kim || 50;
                  const dynPark = corr.dynamic_park || 50;
                  const dynGap = corr.dynamic_gap || 0;
                  const mix = corr.mix || "";
                  return (
                    <div className="space-y-1.5">
                      <div className="text-[10px] text-cyan-400 font-bold animate-slide-left" style={{animationDelay:"0.2s"}}>실투표 다이내믹 <span className="text-cyan-700 font-normal">({mix})</span></div>
                      <div className="flex h-10 rounded-lg overflow-hidden border border-cyan-800/40">
                        <div className="flex items-center justify-center animate-bar" style={{ width: `${dynKim}%`, background: "linear-gradient(135deg, #1e3a5f, #0e7490)", animationDelay:"0.3s" }}>
                          <span className="text-[16px] font-black text-cyan-200">{dynKim.toFixed(1)}%</span>
                        </div>
                        <div className="flex items-center justify-center animate-bar-delay" style={{ width: `${dynPark}%`, background: "linear-gradient(135deg, #5b2130, #831843)", animationDelay:"0.4s" }}>
                          <span className="text-[16px] font-black text-pink-300 animate-number" style={{animationDelay:"1.1s"}}>{dynPark.toFixed(1)}%</span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className={`text-[14px] font-black animate-number ${dynGap >= 0 ? "text-cyan-400 tight-race" : "text-pink-400 tight-race"}`} style={{animationDelay:"1.2s"}}>
                          {dynGap >= 0 ? "+" : ""}{dynGap.toFixed(1)}%p
                        </span>
                        <span className="text-[8px] text-cyan-600">판세 {pandseIndex}pt · D-{corr.d_day || "?"}</span>
                      </div>
                    </div>
                  );
                })()}
              </div>
            </div>
          </div>
        );
      })()}

      {/* 후보 버즈 비교 — 이슈 레이더 위에 배치 (아래 BOTTOM ROW 앞으로 이동됨) */}
      {false && Object.keys(candidateBuzz).length > 0 && (() => {
        // 후보별 주요 키워드만 (경남, 공약)
        const mainKws = ["경남", "공약"];
        const ourKws = Object.entries(candidateBuzz).filter(([kw]) => kw.includes(candidate) && mainKws.some(m => kw.includes(m)));
        const oppKws = Object.entries(candidateBuzz).filter(([kw]) => kw.includes(opponent) && mainKws.some(m => kw.includes(m)));
        const allOur = Object.entries(candidateBuzz).filter(([kw]) => kw.includes(candidate));
        const allOpp = Object.entries(candidateBuzz).filter(([kw]) => kw.includes(opponent));
        const sumVal = (arr: [string, any][], key: string) => arr.reduce((s, [, b]) => s + (b[key] || 0), 0);

        const ourMention = sumVal(allOur, "mention_count");
        const oppMention = sumVal(allOpp, "mention_count");
        const ourVel = allOur.length > 0 ? allOur.reduce((s, [, b]) => s + (b.velocity || 0), 0) / allOur.length : 0;
        const oppVel = allOpp.length > 0 ? allOpp.reduce((s, [, b]) => s + (b.velocity || 0), 0) / allOpp.length : 0;

        // 6분류 집계
        const agg6 = (arr: [string, any][]) => {
          const r: Record<string, number> = {};
          arr.forEach(([, b]) => {
            const s6 = b.ai_sentiment?.sentiment_6way || {};
            Object.entries(s6).forEach(([k, v]) => { r[k] = (r[k] || 0) + (v as number); });
          });
          return r;
        };
        const our6 = agg6(allOur);
        const opp6 = agg6(allOpp);
        const our6Total = Object.values(our6).reduce((a, b) => a + b, 0) || 1;
        const opp6Total = Object.values(opp6).reduce((a, b) => a + b, 0) || 1;

        const S6_COLORS: Record<string, string> = { "지지": "bg-blue-500", "스윙": "bg-amber-400", "부정": "bg-rose-500", "정체성": "bg-red-700", "정책": "bg-orange-500", "중립": "bg-gray-600" };

        // 승리 지표
        const mentionWin = ourMention > oppMention;
        const velWin = ourVel > oppVel;
        const supportWin = (our6["지지"] || 0) > (opp6["지지"] || 0);
        const negLess = (our6["부정"] || 0) < (opp6["부정"] || 0);

        return (
          <div className="wr-card">
            <div className="px-3 py-2">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-blue-300 font-bold">후보 버즈 비교</span>
                <span className="text-[9px] text-gray-600">이슈 스코어링 별도</span>
              </div>

              <div className="grid grid-cols-12 gap-3">
                {/* 좌: 핵심 지표 비교 테이블 */}
                <div className="col-span-5">
                  <table className="w-full text-[10px]">
                    <thead>
                      <tr className="text-gray-500">
                        <th className="text-left font-normal pb-1"></th>
                        <th className="text-right font-normal pb-1 text-blue-400">{candidate}</th>
                        <th className="text-right font-normal pb-1 text-red-400">{opponent}</th>
                        <th className="text-center font-normal pb-1 w-6"></th>
                      </tr>
                    </thead>
                    <tbody className="text-gray-300">
                      <tr>
                        <td className="text-gray-500 py-0.5">언급량</td>
                        <td className={`text-right font-bold ${mentionWin ? "text-white" : ""}`}>{ourMention}</td>
                        <td className={`text-right font-bold ${!mentionWin ? "text-white" : ""}`}>{oppMention}</td>
                        <td className="text-center">{mentionWin ? <span className="text-blue-400">W</span> : <span className="text-red-400">W</span>}</td>
                      </tr>
                      <tr>
                        <td className="text-gray-500 py-0.5">확산속도</td>
                        <td className={`text-right ${velWin ? "text-white font-bold" : ""}`}>{ourVel.toFixed(1)}</td>
                        <td className={`text-right ${!velWin ? "text-white font-bold" : ""}`}>{oppVel.toFixed(1)}</td>
                        <td className="text-center">{velWin ? <span className="text-blue-400">W</span> : <span className="text-red-400">W</span>}</td>
                      </tr>
                      <tr>
                        <td className="text-gray-500 py-0.5">지지</td>
                        <td className={`text-right ${supportWin ? "text-blue-400 font-bold" : ""}`}>{our6["지지"] || 0}</td>
                        <td className={`text-right ${!supportWin ? "text-red-400 font-bold" : ""}`}>{opp6["지지"] || 0}</td>
                        <td className="text-center">{supportWin ? <span className="text-blue-400">W</span> : <span className="text-red-400">W</span>}</td>
                      </tr>
                      <tr>
                        <td className="text-gray-500 py-0.5">부정</td>
                        <td className={`text-right ${negLess ? "" : "text-rose-400 font-bold"}`}>{our6["부정"] || 0}</td>
                        <td className={`text-right ${!negLess ? "" : "text-rose-400 font-bold"}`}>{opp6["부정"] || 0}</td>
                        <td className="text-center">{negLess ? <span className="text-blue-400">W</span> : <span className="text-red-400">W</span>}</td>
                      </tr>
                      <tr>
                        <td className="text-gray-500 py-0.5">스윙</td>
                        <td className="text-right">{our6["스윙"] || 0}</td>
                        <td className="text-right">{opp6["스윙"] || 0}</td>
                        <td></td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* 중: 감성 6분류 스택 바 비교 */}
                <div className="col-span-4 flex flex-col justify-center space-y-1.5">
                  <div>
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-[9px] text-blue-400">{candidate}</span>
                      <span className="text-[8px] text-gray-500">{our6Total > 1 ? `${our6Total}건` : ""}</span>
                    </div>
                    <div className="flex h-3 rounded overflow-hidden">
                      {Object.entries(S6_COLORS).map(([k, c]) => (our6[k] || 0) > 0 && (
                        <div key={k} className={c} style={{ width: `${((our6[k] || 0) / our6Total) * 100}%` }} title={`${k} ${our6[k]}`} />
                      ))}
                      {our6Total <= 1 && <div className="bg-gray-700 w-full" />}
                    </div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-[9px] text-red-400">{opponent}</span>
                      <span className="text-[8px] text-gray-500">{opp6Total > 1 ? `${opp6Total}건` : ""}</span>
                    </div>
                    <div className="flex h-3 rounded overflow-hidden">
                      {Object.entries(S6_COLORS).map(([k, c]) => (opp6[k] || 0) > 0 && (
                        <div key={k} className={c} style={{ width: `${((opp6[k] || 0) / opp6Total) * 100}%` }} title={`${k} ${opp6[k]}`} />
                      ))}
                      {opp6Total <= 1 && <div className="bg-gray-700 w-full" />}
                    </div>
                  </div>
                  <div className="flex gap-1.5 text-[8px] text-gray-500 flex-wrap">
                    {Object.entries(S6_COLORS).map(([k, c]) => (
                      <span key={k}><span className={`inline-block w-1.5 h-1.5 rounded-full ${c} mr-0.5`} />{k}</span>
                    ))}
                  </div>
                </div>

                {/* 우: 키워드별 상세 (핵심만) */}
                <div className="col-span-3 space-y-0.5">
                  <div className="text-[8px] text-gray-500 mb-1">키워드별</div>
                  {[...ourKws, ...oppKws].map(([kw, b]: [string, any]) => {
                    const isOur = kw.includes(candidate);
                    const sent = b.ai_sentiment?.net_sentiment;
                    const shortName = kw.replace(candidate, "").replace(opponent, "").trim() || "경남";
                    return (
                      <div key={kw} className="flex items-center gap-1 text-[9px]">
                        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${isOur ? "bg-blue-500" : "bg-red-500"}`} />
                        <span className="text-gray-400 truncate flex-1">{shortName}</span>
                        <span className="text-white font-bold">{b.mention_count}</span>
                        {sent != null && sent !== 0 && (
                          <span className={`${sent > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                            {sent > 0 ? "+" : ""}{(sent * 100).toFixed(0)}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* ═══════════════════════════════════════════════════════════════
          INDEX DASHBOARD ROW — 핵심 인덱스 (최상단)
          ═══════════════════════════════════════════════════════════════ */}
      {/* ═══════════════════════════════════════════════════════════════
          통합 인덱스 카드 — 지수 헤더 + 후보별 차트
          ═══════════════════════════════════════════════════════════════ */}
      {(() => {
        const ii = enrichment?.issue_indices;
        const ri = enrichment?.reaction_indices;

        // 이슈지수: 전체 키워드 평균 활성도 (절대값)
        const issueAvg = ii ? Math.round(Object.values(ii).reduce((s: number, v: any) => s + (v?.index || 0), 0) / Math.max(Object.keys(ii).length, 1)) : 0;
        const issueCount = ii ? Object.keys(ii).length : 0;
        const issueGrade = issueAvg >= 70 ? "EXPLOSIVE" : issueAvg >= 55 ? "HOT" : issueAvg >= 40 ? "ACTIVE" : "LOW";
        const issueGradeColor = issueGrade === "EXPLOSIVE" ? "bg-red-500/15 text-red-400 border-red-500/30" : issueGrade === "HOT" ? "bg-orange-500/15 text-orange-400 border-orange-500/30" : issueGrade === "ACTIVE" ? "bg-yellow-500/15 text-yellow-400 border-yellow-500/30" : "bg-gray-800/30 text-gray-400 border-gray-700/30";
        const issueColor = issueAvg >= 70 ? "text-red-400" : issueAvg >= 55 ? "text-orange-400" : issueAvg >= 40 ? "text-yellow-400" : "text-gray-400";

        // 반응지수: 전체 키워드 평균 감성 (방향)
        const rxCount = ri ? Object.keys(ri).length : 0;
        const rxSentAvg = ri ? Object.values(ri).reduce((s: number, v: any) => s + (v?.net_sentiment || 0), 0) / Math.max(rxCount, 1) : 0;
        const rxSentPct = Math.round(rxSentAvg * 100); // -100 ~ +100
        const rxDir = rxSentAvg > 0.2 ? "긍정" : rxSentAvg < -0.2 ? "부정" : "중립";
        const rxGradeColor = rxDir === "긍정" ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" : rxDir === "부정" ? "bg-rose-500/15 text-rose-500 border-rose-500/30" : "bg-gray-800/30 text-gray-400 border-gray-700/30";
        const rxColor = rxSentAvg > 0.2 ? "text-emerald-400" : rxSentAvg < -0.2 ? "text-rose-500" : "text-gray-400";

        // 판세지수
        const corr = enrichment?.turnout?.correction;
        const pandseIdx = corr?.pandse_index ?? 50;
        const dynGap = corr?.dynamic_gap ?? 0;
        const pandseGrade = pandseIdx > 55 ? "우세" : pandseIdx < 45 ? "열세" : "접전";
        const pandseGradeColor = pandseGrade === "우세" ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" : pandseGrade === "열세" ? "bg-rose-500/15 text-rose-500 border-rose-500/30" : "bg-gray-800/30 text-gray-400 border-gray-700/30";
        const pandseColor = pandseIdx >= 55 ? "text-emerald-400" : pandseIdx <= 45 ? "text-rose-500" : "text-cyan-400";

        // 종합
        const overallLabel = dynGap > 2 ? "우세" : dynGap < -2 ? "열세" : "접전";
        const overallColor = dynGap > 2 ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" : dynGap < -2 ? "bg-rose-500/15 text-rose-500 border-rose-500/30" : "bg-amber-500/15 text-amber-400 border-amber-500/30";

        return (
          <div className="wr-card">
            {/* 헤더 */}
            <div className="px-3 py-2 flex items-center justify-between border-b border-[#0e1825]">
              <div className="flex items-center gap-4">
                <span className="text-[10px] text-gray-300 font-bold">지표 현황 (7일)</span>
                <span className={`text-[9px] font-black px-2 py-0.5 rounded border ${overallColor}`}>{overallLabel} ({dynGap >= 0 ? "+" : ""}{dynGap.toFixed(1)}%p)</span>
              </div>
              <span className="text-[8px] text-gray-500">{indexTrend.length}일 · D-{corr?.d_day ?? "?"}</span>
            </div>

            {/* 3개 지수 — 후보별 비교 */}
            <div className="grid grid-cols-3 border-b border-[#0e1825]">
              {/* 이슈지수 — candidate_buzz에서 후보별 언급량 비교 */}
              {(() => {
                const buzz = enrichment?.candidate_buzz || candidateBuzz || {};
                const kimBuzz = Object.entries(buzz).filter(([k]) => k.includes(candidate));
                const parkBuzz = Object.entries(buzz).filter(([k]) => k.includes(opponent));
                const kimMentions = kimBuzz.reduce((s, [,b]: [string, any]) => s + (b?.mention_count || 0), 0);
                const parkMentions = parkBuzz.reduce((s, [,b]: [string, any]) => s + (b?.mention_count || 0), 0);
                const total = kimMentions + parkMentions || 1;
                const kimPct = Math.round(kimMentions / total * 100);
                const parkPct = 100 - kimPct;
                const gap = kimMentions - parkMentions;
                const grade = gap > 20 ? "우세" : gap < -20 ? "열세" : "접전";
                const gradeC = grade === "우세" ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" : grade === "열세" ? "bg-rose-500/15 text-rose-500 border-rose-500/30" : "bg-gray-800/30 text-gray-400 border-gray-700/30";
                return (
                  <div className="px-3 py-2 border-r border-[#0e1825]">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[9px] text-gray-500">이슈지수</span>
                      <span className={`text-[7px] font-black px-1.5 py-0.5 rounded border ${gradeC}`}>{grade}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="text-center">
                        <div className="text-[8px] text-blue-400">{candidate}</div>
                        <div className="text-[18px] font-black wr-metric text-blue-400 metric-pulse">{kimMentions}</div>
                        <div className="text-[7px] text-gray-600">{kimBuzz.length}개 키워드</div>
                      </div>
                      <div className="text-center px-1">
                        <div className={`text-[12px] font-black wr-metric ${gap > 0 ? "text-blue-400" : gap < 0 ? "text-red-400" : "text-gray-400"}`}>
                          {kimPct}:{parkPct}
                        </div>
                      </div>
                      <div className="text-center">
                        <div className="text-[8px] text-red-400">{opponent}</div>
                        <div className="text-[18px] font-black wr-metric text-red-400 metric-pulse">{parkMentions}</div>
                        <div className="text-[7px] text-gray-600">{parkBuzz.length}개 키워드</div>
                      </div>
                    </div>
                    <div className="text-[7px] text-gray-600 text-center mt-1">미디어 언급량 비교</div>
                  </div>
                );
              })()}

              {/* 반응지수 — candidate_buzz에서 후보별 감성 비교 */}
              {(() => {
                const buzz = enrichment?.candidate_buzz || candidateBuzz || {};
                const kimBuzz = Object.entries(buzz).filter(([k]) => k.includes(candidate));
                const parkBuzz = Object.entries(buzz).filter(([k]) => k.includes(opponent));
                const kimSent = kimBuzz.length > 0 ? kimBuzz.reduce((s, [,b]: [string, any]) => s + (b?.ai_sentiment?.net_sentiment || 0), 0) / kimBuzz.length : 0;
                const parkSent = parkBuzz.length > 0 ? parkBuzz.reduce((s, [,b]: [string, any]) => s + (b?.ai_sentiment?.net_sentiment || 0), 0) / parkBuzz.length : 0;
                const kimPct = Math.round(kimSent * 100);
                const parkPct = Math.round(parkSent * 100);
                const gap = kimPct - parkPct;
                const grade = gap > 15 ? "우세" : gap < -15 ? "열세" : "접전";
                const gradeC = grade === "우세" ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" : grade === "열세" ? "bg-rose-500/15 text-rose-500 border-rose-500/30" : "bg-gray-800/30 text-gray-400 border-gray-700/30";
                return (
                  <div className="px-3 py-2 border-r border-[#0e1825]">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[9px] text-gray-500">반응지수</span>
                      <span className={`text-[7px] font-black px-1.5 py-0.5 rounded border ${gradeC}`}>{grade}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="text-center">
                        <div className="text-[8px] text-blue-400">{candidate}</div>
                        <div className={`text-[18px] font-black wr-metric metric-pulse ${kimPct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {kimPct > 0 ? "+" : ""}{kimPct}
                        </div>
                        <div className="text-[7px] text-gray-600">감성 {kimBuzz.length}개</div>
                      </div>
                      <div className="text-center px-1">
                        <div className="text-[8px] text-gray-500">vs</div>
                      </div>
                      <div className="text-center">
                        <div className="text-[8px] text-red-400">{opponent}</div>
                        <div className={`text-[18px] font-black wr-metric metric-pulse ${parkPct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {parkPct > 0 ? "+" : ""}{parkPct}
                        </div>
                        <div className="text-[7px] text-gray-600">감성 {parkBuzz.length}개</div>
                      </div>
                    </div>
                    <div className="text-[7px] text-gray-600 text-center mt-1">AI 감성분석 (6분류)</div>
                  </div>
                );
              })()}

              {/* 판세지수 */}
              <div className="px-3 py-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[9px] text-gray-500">판세지수</span>
                  <span className={`text-[7px] font-black px-1.5 py-0.5 rounded border ${pandseGradeColor}`}>{pandseGrade}</span>
                </div>
                <div className="flex items-center justify-center">
                  <div className={`text-[28px] font-black wr-metric leading-none metric-pulse ${pandseColor}`}>
                    {pandseIdx.toFixed(1)}<span className="text-[9px] text-gray-500 ml-0.5">pt</span>
                  </div>
                </div>
                <div className="text-[7px] text-gray-600 text-center mt-1">선행지수 · {(corr?.factors || []).length} Factors</div>
              </div>
            </div>

            {/* 차트 */}
            {indexTrend.length >= 1 ? (
              <div className="p-3">
                <IndexBattleChart data={indexTrend} candidate={candidate} opponent={opponent} />
              </div>
            ) : (
              <div className="px-4 py-6 text-center text-[11px] text-gray-400">
                데이터 축적 중 ({indexTrend.length}/1일)
              </div>
            )}
          </div>
        );
      })()}

      {/* ═══════════════════════════════════════════════════════════════
          MAIN ROW: Large Polling Chart (8/12)
          ═══════════════════════════════════════════════════════════════ */}
      {/* 역대 차트 — 최상단으로 이동됨 */}

      {/* 여론조사 추세 차트 — 삭제됨 (역대 차트에 통합) */}

      {/* INDEX BATTLE — 이동됨 (역대 차트 앞으로) */}

      {/* ═══════════════════════════════════════════════════════════════
          오늘의 사건 TOP (뉴스 클러스터링)
          ═══════════════════════════════════════════════════════════════ */}
      {newsClusters.length > 0 && (
        <div className="wr-card">
          <div className="wr-card-header flex justify-between">
            <span>오늘의 사건 TOP</span>
            <span className="text-[9px] text-gray-400 font-normal">뉴스 클러스터링 · 24시간</span>
          </div>
          <div className="grid grid-cols-12 gap-1 p-1.5">
            {newsClusters.slice(0, 6).map((c: any, i: number) => {
              const sideColor = c.side?.includes("우리") ? "border-l-blue-500"
                : c.side?.includes("상대 측") ? "border-l-red-500"
                : c.side?.includes("상대 내부") ? "border-l-orange-500"
                : "border-l-gray-600";
              const urgencyBg = c.urgency === "즉시" ? "bg-red-500/20 text-red-300"
                : c.urgency === "오늘 내" ? "bg-orange-500/15 text-orange-300"
                : c.urgency === "이번 주" ? "bg-blue-500/10 text-blue-300"
                : "bg-gray-500/10 text-gray-400";
              const ourColor = (c.our_impact || 0) > 0 ? "text-emerald-400" : (c.our_impact || 0) < 0 ? "text-rose-400" : "text-gray-400";
              const oppColor = (c.opp_impact || 0) > 0 ? "text-emerald-400" : (c.opp_impact || 0) < 0 ? "text-rose-400" : "text-gray-400";
              return (
                <div key={i} className={`col-span-4 bg-[#0a0f18] rounded-lg p-2.5 border-l-2 ${sideColor}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${urgencyBg}`}>{c.urgency}</span>
                    <span className="text-[9px] text-gray-500">{c.count}건</span>
                  </div>
                  <div className="text-[11px] text-gray-100 font-bold leading-tight mb-1.5 line-clamp-2">{c.name}</div>
                  <div className="text-[9px] text-gray-500 mb-1">{c.side}</div>
                  <div className="flex gap-3 text-[10px]">
                    <span className={ourColor}>우리 {(c.our_impact || 0) > 0 ? "+" : ""}{c.our_impact || 0}</span>
                    <span className={oppColor}>상대 {(c.opp_impact || 0) > 0 ? "+" : ""}{c.opp_impact || 0}</span>
                  </div>
                  {c.articles?.[0] && (
                    <div className="text-[9px] text-gray-500 mt-1.5 truncate" title={c.articles[0].title}>→ {c.articles[0].title}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          후보 버즈 비교 (이슈 레이더 바로 위)
          ═══════════════════════════════════════════════════════════════ */}
      {Object.keys(candidateBuzz).length > 0 && (() => {
        const mainKws = ["경남", "공약"];
        const ourKws = Object.entries(candidateBuzz).filter(([kw]) => kw.includes(candidate) && mainKws.some(m => kw.includes(m)));
        const oppKws = Object.entries(candidateBuzz).filter(([kw]) => kw.includes(opponent) && mainKws.some(m => kw.includes(m)));
        const allOur = Object.entries(candidateBuzz).filter(([kw]) => kw.includes(candidate));
        const allOpp = Object.entries(candidateBuzz).filter(([kw]) => kw.includes(opponent));
        const sumVal = (arr: [string, any][], key: string) => arr.reduce((s, [, b]) => s + (b[key] || 0), 0);
        const ourMention = sumVal(allOur, "mention_count");
        const oppMention = sumVal(allOpp, "mention_count");
        const ourVel = allOur.length > 0 ? allOur.reduce((s, [, b]) => s + (b.velocity || 0), 0) / allOur.length : 0;
        const oppVel = allOpp.length > 0 ? allOpp.reduce((s, [, b]) => s + (b.velocity || 0), 0) / allOpp.length : 0;
        const agg6 = (arr: [string, any][]) => {
          const r: Record<string, number> = {};
          arr.forEach(([, b]) => { const s6 = b.ai_sentiment?.sentiment_6way || {}; Object.entries(s6).forEach(([k, v]) => { r[k] = (r[k] || 0) + (v as number); }); });
          return r;
        };
        const our6 = agg6(allOur); const opp6 = agg6(allOpp);
        const our6Total = Object.values(our6).reduce((a, b) => a + b, 0) || 1;
        const opp6Total = Object.values(opp6).reduce((a, b) => a + b, 0) || 1;
        const S6_COLORS: Record<string, string> = { "지지": "bg-blue-500", "스윙": "bg-amber-400", "부정": "bg-rose-500", "정체성": "bg-red-700", "정책": "bg-orange-500", "중립": "bg-gray-600" };
        const mentionWin = ourMention > oppMention;
        const velWin = ourVel > oppVel;
        const supportWin = (our6["지지"] || 0) > (opp6["지지"] || 0);
        const negLess = (our6["부정"] || 0) < (opp6["부정"] || 0);
        return (
          <div className="wr-card">
            <div className="px-3 py-2">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-blue-300 font-bold">후보 버즈 비교</span>
                <span className="text-[9px] text-gray-600">이슈 스코어링 별도</span>
              </div>
              <div className="grid grid-cols-12 gap-3">
                <div className="col-span-5">
                  <table className="w-full text-[10px]">
                    <thead><tr className="text-gray-500">
                      <th className="text-left font-normal pb-1"></th>
                      <th className="text-right font-normal pb-1 text-blue-400">{candidate}</th>
                      <th className="text-right font-normal pb-1 text-red-400">{opponent}</th>
                      <th className="text-center font-normal pb-1 w-6"></th>
                    </tr></thead>
                    <tbody className="text-gray-300">
                      <tr><td className="text-gray-500 py-0.5">언급량</td><td className={`text-right font-bold ${mentionWin ? "text-white" : ""}`}>{ourMention}</td><td className={`text-right font-bold ${!mentionWin ? "text-white" : ""}`}>{oppMention}</td><td className="text-center">{mentionWin ? <span className="text-blue-400">W</span> : <span className="text-red-400">W</span>}</td></tr>
                      <tr><td className="text-gray-500 py-0.5">확산속도</td><td className={`text-right ${velWin ? "text-white font-bold" : ""}`}>{ourVel.toFixed(1)}</td><td className={`text-right ${!velWin ? "text-white font-bold" : ""}`}>{oppVel.toFixed(1)}</td><td className="text-center">{velWin ? <span className="text-blue-400">W</span> : <span className="text-red-400">W</span>}</td></tr>
                      <tr><td className="text-gray-500 py-0.5">지지</td><td className={`text-right ${supportWin ? "text-blue-400 font-bold" : ""}`}>{our6["지지"] || 0}</td><td className={`text-right ${!supportWin ? "text-red-400 font-bold" : ""}`}>{opp6["지지"] || 0}</td><td className="text-center">{supportWin ? <span className="text-blue-400">W</span> : <span className="text-red-400">W</span>}</td></tr>
                      <tr><td className="text-gray-500 py-0.5">부정</td><td className={`text-right ${negLess ? "" : "text-rose-400 font-bold"}`}>{our6["부정"] || 0}</td><td className={`text-right ${!negLess ? "" : "text-rose-400 font-bold"}`}>{opp6["부정"] || 0}</td><td className="text-center">{negLess ? <span className="text-blue-400">W</span> : <span className="text-red-400">W</span>}</td></tr>
                    </tbody>
                  </table>
                </div>
                <div className="col-span-4 flex flex-col justify-center space-y-1.5">
                  <div>
                    <div className="flex items-center justify-between mb-0.5"><span className="text-[9px] text-blue-400">{candidate}</span><span className="text-[8px] text-gray-500">{our6Total > 1 ? `${our6Total}건` : ""}</span></div>
                    <div className="flex h-3 rounded overflow-hidden">{Object.entries(S6_COLORS).map(([k, c]) => (our6[k] || 0) > 0 && (<div key={k} className={c} style={{ width: `${((our6[k] || 0) / our6Total) * 100}%` }} title={`${k} ${our6[k]}`} />))}{our6Total <= 1 && <div className="bg-gray-700 w-full" />}</div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-0.5"><span className="text-[9px] text-red-400">{opponent}</span><span className="text-[8px] text-gray-500">{opp6Total > 1 ? `${opp6Total}건` : ""}</span></div>
                    <div className="flex h-3 rounded overflow-hidden">{Object.entries(S6_COLORS).map(([k, c]) => (opp6[k] || 0) > 0 && (<div key={k} className={c} style={{ width: `${((opp6[k] || 0) / opp6Total) * 100}%` }} title={`${k} ${opp6[k]}`} />))}{opp6Total <= 1 && <div className="bg-gray-700 w-full" />}</div>
                  </div>
                  <div className="flex gap-1.5 text-[8px] text-gray-500 flex-wrap">{Object.entries(S6_COLORS).map(([k, c]) => (<span key={k}><span className={`inline-block w-1.5 h-1.5 rounded-full ${c} mr-0.5`} />{k}</span>))}</div>
                </div>
                <div className="col-span-3 space-y-0.5">
                  <div className="text-[8px] text-gray-500 mb-1">키워드별</div>
                  {[...ourKws, ...oppKws].map(([kw, b]: [string, any]) => {
                    const isOur = kw.includes(candidate); const sent = b.ai_sentiment?.net_sentiment;
                    const shortName = kw.replace(candidate, "").replace(opponent, "").trim() || "경남";
                    return (<div key={kw} className="flex items-center gap-1 text-[9px]"><span className={`w-1.5 h-1.5 rounded-full shrink-0 ${isOur ? "bg-blue-500" : "bg-red-500"}`} /><span className="text-gray-400 truncate flex-1">{shortName}</span><span className="text-white font-bold">{b.mention_count}</span>{sent != null && sent !== 0 && (<span className={`${sent > 0 ? "text-emerald-400" : "text-rose-400"}`}>{sent > 0 ? "+" : ""}{(sent * 100).toFixed(0)}</span>)}</div>);
                  })}
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* ═══════════════════════════════════════════════════════════════
          BOTTOM ROW: Issue Radar (4/12) + Region Map (4/12) + Intel (4/12)
          ═══════════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-12 gap-1.5">

        {/* ─── Issue Radar (6/12) ─── */}
        <div className="col-span-6 wr-card">
          <div className="wr-card-header flex justify-between">
            <span>이슈 레이더</span>
            {crisisIssues.length > 0 && (
              <span className="text-red-400 text-[9px] font-bold crisis-pulse">{crisisIssues.length} CRISIS</span>
            )}
          </div>
          <div className="divide-y divide-[#0e1825] max-h-[280px] overflow-y-auto feed-scroll">
            {(() => {
              const ii = enrichment?.issue_indices || {};
              // Issue Index로 정렬, 없으면 기존 score 사용
              const sorted = [...resp].sort((a: any, b: any) => {
                const aIdx = ii[a.keyword]?.index ?? a.score ?? 0;
                const bIdx = ii[b.keyword]?.index ?? b.score ?? 0;
                return bIdx - aIdx;
              });
              const ri = enrichment?.reaction_indices || {};
              return sorted.slice(0, 12).map((r: any, i: number) => {
                const idx = ii[r.keyword];
                const score = idx?.index ?? r.score ?? 0;
                const grade = idx?.grade || "";
                const isOur = r.keyword?.includes(candidate);
                const isOpp = r.keyword?.includes(opponent);
                const isActive = selectedIssue === r.keyword;
                const gradeColor = grade === "EXPLOSIVE" ? "text-red-400" : grade === "HOT" ? "text-orange-400" : grade === "ACTIVE" ? "text-yellow-400" : "text-gray-400";
                const rxData = ri[r.keyword];
                const rxScore = rxData?.final_score || rxData?.index || 0;
                const rxDir = rxData?.direction;
                return (
                  <div key={i}>
                    <div onClick={() => handleIssueDrill(r.keyword)}
                      className={`flex items-center gap-1 px-2 py-[6px] cursor-pointer text-[11px] transition-all ${
                        isActive ? "bg-blue-950/30 border-l-2 border-l-blue-500" : "hover:bg-[#0d1420] border-l-2 border-l-transparent"
                      }`}>
                      <span className={`w-3 text-center font-mono text-[9px] ${i < 3 ? "text-orange-400 font-bold" : "text-gray-400"}`}>{i + 1}</span>
                      <span className={`flex-1 truncate ${isOur ? "text-blue-300" : isOpp ? "text-red-300" : "text-gray-300"} ${i < 3 ? "font-bold" : ""}`}>
                        {r.keyword}
                      </span>
                      <span className={`text-[9px] font-mono font-bold shrink-0 ${gradeColor}`}>{score.toFixed(0)}</span>
                      {grade && <span className={`text-[7px] px-1 rounded shrink-0 ${gradeColor} bg-opacity-20`}>{grade}</span>}
                      {rxScore > 0 && (
                        <span className={`text-[8px] font-mono shrink-0 ml-0.5 ${
                          rxDir === "positive" ? "text-purple-400" : rxDir === "negative" ? "text-rose-400" : "text-gray-400"
                        }`}>Rx{rxScore.toFixed(0)}</span>
                      )}
                    </div>
                    {isActive && <IssueDrillDown data={issueDetail} reactionData={enrichment?.reaction_indices?.[r.keyword]} />}
                  </div>
                );
              });
            })()}
            {resp.length === 0 && <div className="p-4 text-center text-gray-400 text-xs">데이터 수집 중</div>}
          </div>
        </div>

        {/* ─── Reaction Radar (6/12) ─── */}
        <div className="col-span-6 wr-card">
          <div className="wr-card-header flex justify-between">
            <span>리액션 레이더</span>
            <span className="text-[8px] text-gray-400 normal-case tracking-normal font-normal">반응 강도 순</span>
          </div>
          <div className="divide-y divide-[#0e1825] max-h-[280px] overflow-y-auto feed-scroll">
            {(() => {
              const ri = enrichment?.reaction_indices || {};
              const keywords = Object.keys(ri);
              if (keywords.length === 0) {
                return <div className="p-4 text-center text-gray-400 text-xs">전략 갱신 후 표시</div>;
              }
              const sorted = keywords
                .map((kw) => ({ keyword: kw, ...ri[kw] }))
                .sort((a: any, b: any) => (b.final_score || b.index || 0) - (a.final_score || a.index || 0));
              return sorted.slice(0, 12).map((r: any, i: number) => {
                const score = r.final_score || r.index || 0;
                const grade = r.grade || "";
                const dir = r.direction || "";
                const isOur = r.keyword?.includes(candidate);
                const isOpp = r.keyword?.includes(opponent);
                const gradeColor = grade === "VIRAL" ? "text-purple-400" : grade === "ENGAGED" ? "text-blue-400" : grade === "RIPPLE" ? "text-gray-400" : "text-gray-400";
                const dirIcon = dir === "positive" ? "▲" : dir === "negative" ? "▼" : "●";
                const dirColor = dir === "positive" ? "text-emerald-400" : dir === "negative" ? "text-rose-500" : "text-gray-400";
                const conf = r.confidence || 0;
                return (
                <div key={i}>
                  <div
                    onClick={() => handleIssueDrill(r.keyword)}
                    className="flex items-center gap-1 px-2 py-[6px] cursor-pointer text-[11px] hover:bg-[#0d1420] border-l-2 border-l-transparent transition-all">
                    <span className={`w-3 text-center font-mono text-[9px] ${i < 3 ? "text-purple-400 font-bold" : "text-gray-400"}`}>{i + 1}</span>
                    <span className={`flex-1 truncate ${isOur ? "text-blue-300" : isOpp ? "text-red-300" : "text-gray-300"} ${i < 3 ? "font-bold" : ""}`}>
                      {r.keyword}
                    </span>
                    <span className={`text-[9px] font-mono font-bold shrink-0 ${gradeColor}`}>{score.toFixed(0)}</span>
                    <span className={`text-[8px] shrink-0 ${dirColor}`}>{dirIcon}</span>
                    {grade && <span className={`text-[7px] px-1 rounded shrink-0 ${gradeColor}`}>{grade}</span>}
                    {r.velocity_flag && <span className="text-[7px] text-amber-400 shrink-0">⚡</span>}
                    {conf >= 0.6 && <span className="text-[7px] text-gray-400 shrink-0">{(conf * 100).toFixed(0)}%</span>}
                  </div>
                  {selectedIssue === r.keyword && (
                    <IssueDrillDown data={issueDetail} reactionData={r} />
                  )}
                </div>
                );
              });
            })()}
          </div>
        </div>

      </div>

      {/* ═══════════════════════════════════════════════════════════════
          FIXED BOTTOM STRIP: Today's 3 Commands
          ═══════════════════════════════════════════════════════════════ */}
      <div className="fixed bottom-0 left-[58px] right-0 h-10 bg-[#060a11]/95 border-t border-[#1a2844] backdrop-blur-sm flex items-center px-4 gap-4 z-50">
        <span className="text-[9px] text-emerald-400 font-black uppercase tracking-wider shrink-0">TODAY</span>
        <div className="w-px h-5 bg-[#1a2844]" />
        {commands.slice(0, 3).map((cmd: any, i: number) => (
          <div key={i} className="flex items-center gap-1.5 text-[10px]">
            <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold shrink-0 ${
              i === 0 ? "bg-emerald-600 text-white" : "bg-[#0d1420] border border-[#1a2844] text-gray-400"
            }`}>{i + 1}</span>
            <span className="text-gray-300 truncate max-w-[200px]">{cmd.final_recommendation || cmd.ai_recommendation}</span>
            {cmd.assigned_owner && <span className="text-[8px] text-gray-400 shrink-0">{cmd.assigned_owner}</span>}
          </div>
        ))}
        {commands.length === 0 && <span className="text-[10px] text-gray-400">승인된 지시 없음</span>}
        <div className="ml-auto flex items-center gap-2">
          {proposals.length > 0 && (
            <button
              onClick={() => setActivePage("queue")}
              className="text-[9px] bg-orange-950/40 border border-orange-700/40 text-orange-400 px-2 py-0.5 rounded hover:bg-orange-900/40 transition font-bold"
            >
              📋 {proposals.length} 대기
            </button>
          )}
          {overrides.length > 0 && (
            <span className="text-[9px] bg-red-950/40 border border-red-700/40 text-red-400 px-2 py-0.5 rounded font-bold">
              ⚡ {overrides.length} Override
            </span>
          )}
        </div>
      </div>
    </div>
  );
}


// ════════════════════════════════════════════════════════════════════
// SUB-COMPONENTS
// ════════════════════════════════════════════════════════════════════

function MomentumTag({ trend }: { trend: any }) {
  if (!trend) return null;
  const m = trend.momentum;
  const val = trend.our_trend;
  if (m === "losing") return (
    <div className="flex items-center gap-1 bg-red-950/40 border border-red-900/40 rounded px-2 py-0.5">
      <span className="w-1.5 h-1.5 rounded-full bg-red-500 crisis-pulse" />
      <span className="text-[9px] font-bold text-rose-500">하락세 {val?.toFixed(2)}%p/일</span>
    </div>
  );
  if (m === "gaining") return (
    <div className="flex items-center gap-1 bg-emerald-950/30 border border-emerald-900/30 rounded px-2 py-0.5">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
      <span className="text-[9px] font-bold text-emerald-400">상승세 +{val?.toFixed(2)}%p/일</span>
    </div>
  );
  return (
    <div className="flex items-center gap-1 bg-yellow-950/20 border border-yellow-900/30 rounded px-2 py-0.5">
      <span className="w-1.5 h-1.5 rounded-full bg-yellow-500" />
      <span className="text-[9px] font-bold text-yellow-400">유지</span>
    </div>
  );
}

// ── Enhanced Polling Chart with overlays ──
function FusionChart({ polls, candidate, opponent, issues, signals, overrides, trend, leadingIndex }: {
  polls: any[]; candidate: string; opponent: string; issues: any[]; signals: any[]; overrides: any[]; trend: any; leadingIndex?: number;
}) {
  const ours = polls.map((p) => p.our);
  const opps = polls.map((p) => { const v = p.opponent || {}; return (Object.values(v)[0] as number) || 0; });
  const all = [...ours, ...opps].filter(Boolean);
  if (all.length === 0) return null;
  const mn = Math.min(...all) - 3, mx = Math.max(...all) + 3, rng = mx - mn || 1;
  const w = 720, h = 180, pl = 42, pr = 55, pt = 18, pb = 26;
  const pts = polls.length;
  const xStep = (w - pl - pr) / (pts - 1 || 1);
  const Y = (v: number) => pt + (1 - (v - mn) / rng) * (h - pt - pb);

  const gridLines = [];
  for (let v = Math.ceil(mn / 2) * 2; v <= mx; v += 2) gridLines.push(v);

  const lastOur = ours[pts - 1];
  const lastOpp = opps[pts - 1];
  const gapVal = lastOur - lastOpp;

  // Issue impact markers: match poll dates to crisis issues
  const issueMarkers = issues.filter((r: any) => r.level === "CRISIS" || r.level === "ALERT").slice(0, 4);

  // Forecast band (dotted projection 3 points)
  const ourTrend = trend?.our_trend || 0;
  const forecastPts = 3;

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="select-none">
      <defs>
        <linearGradient id="areaOur" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#2563eb" stopOpacity="0.15" />
          <stop offset="100%" stopColor="#2563eb" stopOpacity="0" />
        </linearGradient>
        <filter id="glowG"><feGaussianBlur stdDeviation="2" result="g" /><feMerge><feMergeNode in="g" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
      </defs>

      {/* Grid */}
      {gridLines.map(v => (
        <g key={v}>
          <line x1={pl} y1={Y(v)} x2={w - pr} y2={Y(v)} stroke="#111d30" strokeWidth="1" />
          <text x={pl - 5} y={Y(v) + 3} fill="#4b6a9b" fontSize="8" textAnchor="end" fontFamily="monospace">{v}</text>
        </g>
      ))}

      {/* Gap zone */}
      {pts > 1 && (
        <polygon
          points={`${ours.map((v, i) => `${pl + i * xStep},${Y(v)}`).join(" ")} ${[...opps].reverse().map((v, i) => `${pl + (pts - 1 - i) * xStep},${Y(v)}`).join(" ")}`}
          fill={gapVal >= 0 ? "rgba(34,197,94,0.04)" : "rgba(239,68,68,0.04)"}
        />
      )}

      {/* Area */}
      <polygon points={`${pl},${Y(ours[0])} ${ours.map((v, i) => `${pl + i * xStep},${Y(v)}`).join(" ")} ${pl + (pts - 1) * xStep},${h - pb} ${pl},${h - pb}`} fill="url(#areaOur)" />

      {/* Overlay A: Issue impact markers */}
      {issueMarkers.map((issue: any, idx: number) => {
        const matchIdx = Math.min(pts - 1, Math.max(0, pts - 1 - idx * 2));
        const cx = pl + matchIdx * xStep;
        return (
          <g key={`iss-${idx}`}>
            <line x1={cx} y1={pt} x2={cx} y2={h - pb} stroke={issue.level === "CRISIS" ? "#ef4444" : "#f59e0b"} strokeWidth="0.5" strokeDasharray="2,3" opacity="0.4" />
            <rect x={cx - 2} y={h - pb + 2} width={4} height={4} rx="1" fill={issue.level === "CRISIS" ? "#ef4444" : "#f59e0b"} opacity="0.7" />
            <text x={cx} y={h - pb + 14} fill={issue.level === "CRISIS" ? "#ef4444" : "#f59e0b"} fontSize="6" textAnchor="middle" opacity="0.7">
              {issue.keyword?.slice(0, 8)}
            </text>
          </g>
        );
      })}

      {/* Overlay B: Internal signal/override markers */}
      {overrides.slice(0, 2).map((ov: any, idx: number) => {
        const cx = pl + Math.max(0, pts - 2 - idx) * xStep;
        return (
          <g key={`ov-${idx}`}>
            <circle cx={cx} cy={pt + 8} r="3" fill="none" stroke="#8b5cf6" strokeWidth="1" opacity="0.6" />
            <text x={cx + 5} y={pt + 10} fill="#8b5cf6" fontSize="6" opacity="0.6">OVR</text>
          </g>
        );
      })}

      {/* Lines */}
      <polyline points={opps.map((v, i) => `${pl + i * xStep},${Y(v)}`).join(" ")} fill="none" stroke="#ef4444" strokeWidth="1.5" strokeDasharray="4,3" opacity="0.7" />
      <polyline points={ours.map((v, i) => `${pl + i * xStep},${Y(v)}`).join(" ")} fill="none" stroke="#2563eb" strokeWidth="2.5" filter="url(#glowG)" />

      {/* Overlay C: Forecast band (dotted) */}
      {ourTrend !== 0 && (
        <polyline
          points={Array.from({ length: forecastPts }, (_, i) => {
            const x = pl + (pts - 1 + i + 1) * xStep;
            const y = Y(lastOur + ourTrend * (i + 1));
            return `${x},${y}`;
          }).join(" ")}
          fill="none" stroke="#2563eb" strokeWidth="1.5" strokeDasharray="4,4" opacity="0.35"
        />
      )}

      {/* Points */}
      {ours.map((v, i) => <circle key={`o${i}`} cx={pl + i * xStep} cy={Y(v)} r={i === pts - 1 ? 5 : 2.5} fill="#2563eb" stroke="#04070d" strokeWidth={i === pts - 1 ? 2 : 1} />)}
      {opps.map((v, i) => <circle key={`e${i}`} cx={pl + i * xStep} cy={Y(v)} r={i === pts - 1 ? 4 : 2} fill="#ef4444" stroke="#04070d" strokeWidth={i === pts - 1 ? 2 : 1} />)}

      {/* Right labels */}
      <rect x={w - pr + 5} y={Y(lastOur) - 12} width="46" height="18" rx="3" fill="#0a1a0f" stroke="#2563eb" strokeWidth="0.5" />
      <text x={w - pr + 28} y={Y(lastOur) + 1} fill="#2563eb" fontSize="11" fontWeight="bold" textAnchor="middle" fontFamily="monospace">{lastOur}%</text>
      <rect x={w - pr + 5} y={Y(lastOpp) - 12} width="46" height="18" rx="3" fill="#1a0a0a" stroke="#ef4444" strokeWidth="0.5" />
      <text x={w - pr + 28} y={Y(lastOpp) + 1} fill="#ef4444" fontSize="11" fontWeight="bold" textAnchor="middle" fontFamily="monospace">{lastOpp}%</text>

      {/* Gap annotation */}
      {pts > 1 && (
        <g>
          <line x1={w - pr + 2} y1={Y(lastOur)} x2={w - pr + 2} y2={Y(lastOpp)} stroke={gapVal >= 0 ? "#2563eb" : "#ef4444"} strokeWidth="1" strokeDasharray="2,2" />
          <rect x={w - pr - 8} y={(Y(lastOur) + Y(lastOpp)) / 2 - 8} width="18" height="16" rx="2" fill={gapVal >= 0 ? "#0a1a0f" : "#1a0a0a"} />
          <text x={w - pr + 1} y={(Y(lastOur) + Y(lastOpp)) / 2 + 4} fill={gapVal >= 0 ? "#2563eb" : "#ef4444"} fontSize="8" fontWeight="bold" textAnchor="middle" fontFamily="monospace">
            {gapVal >= 0 ? "+" : ""}{gapVal.toFixed(1)}
          </text>
        </g>
      )}

      {/* X axis dates */}
      {polls.map((p, i) => (
        <text key={`d${i}`} x={pl + i * xStep} y={h - pb + 22} fill="#4b6a9b" fontSize="7" textAnchor="middle" fontFamily="monospace">{p.date?.slice(5)}</text>
      ))}

      {/* Leading Index overlay — 오른쪽 Y축 (0~100) */}
      {leadingIndex != null && leadingIndex > 0 && (() => {
        const liY = pt + (1 - leadingIndex / 100) * (h - pt - pb);
        const liColor = leadingIndex >= 57 ? "#06b6d4" : leadingIndex <= 43 ? "#ef4444" : "#6b7280";
        return (
          <g>
            <line x1={pl} y1={liY} x2={w - pr} y2={liY} stroke={liColor} strokeWidth="1" strokeDasharray="6,3" opacity="0.5" />
            <circle cx={w - pr} cy={liY} r="4" fill={liColor} stroke="#04070d" strokeWidth="1.5" />
            <text x={w - pr + 28} y={liY + 3} fill={liColor} fontSize="9" fontWeight="bold" textAnchor="middle" fontFamily="monospace">
              판세 {leadingIndex.toFixed(0)}
            </text>
          </g>
        );
      })()}

      {/* Legend */}
      <circle cx={pl} cy={10} r="3" fill="#2563eb" />
      <text x={pl + 6} y={13} fill="#4ade80" fontSize="8" fontWeight="bold">{candidate}</text>
      <circle cx={pl + 60} cy={10} r="3" fill="#ef4444" />
      <text x={pl + 66} y={13} fill="#f87171" fontSize="8" fontWeight="bold">{opponent}</text>
      <line x1={pl + 115} y1={10} x2={pl + 125} y2={10} stroke="#2563eb" strokeWidth="1.5" strokeDasharray="3,3" opacity="0.4" />
      <text x={pl + 128} y={13} fill="#2563eb" fontSize="7" opacity="0.5">예측</text>
      <rect x={pl + 155} y={8} width="4" height="4" rx="1" fill="#f59e0b" opacity="0.7" />
      <text x={pl + 162} y={13} fill="#f59e0b" fontSize="7" opacity="0.7">이슈</text>
      <line x1={pl + 185} y1={10} x2={pl + 195} y2={10} stroke="#06b6d4" strokeWidth="1" strokeDasharray="6,3" opacity="0.5" />
      <text x={pl + 198} y={13} fill="#06b6d4" fontSize="7" opacity="0.7">LI</text>
    </svg>
  );
}

function WarRoomPollChart({ autoPolls = [] }: { autoPolls?: any[] }) {
  const data = mergeAutoPolls(autoPolls);
  const n = data.length;
  const w = 900, h = 185, pl = 32, pr = 10, pt = 14, pb = 35;
  const xs = (w - pl - pr) / (n - 1);
  const mn = 25, mx = 70, rng = mx - mn;
  const Y = (v: number) => pt + (1 - (v - mn) / rng) * (h - pt - pb);
  const dividerX = pl + 2.5 * xs;

  // 라인 총 길이 계산 (애니메이션용)
  const calcLen = (pts: { x: number; y: number }[]) => {
    let len = 0;
    for (let i = 1; i < pts.length; i++) {
      len += Math.sqrt((pts[i].x - pts[i-1].x) ** 2 + (pts[i].y - pts[i-1].y) ** 2);
    }
    return Math.ceil(len);
  };
  const kimPts = data.map((d, i) => ({ x: pl + i * xs, y: Y(d.kim) }));
  const parkPts = data.map((d, i) => ({ x: pl + i * xs, y: Y(d.park) }));
  const kimLen = calcLen(kimPts);
  const parkLen = calcLen(parkPts);

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`}>
      <style>{`
        @keyframes drawLine { from { stroke-dashoffset: var(--len); } to { stroke-dashoffset: 0; } }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes popIn { 0% { r: 0; opacity: 0; } 60% { r: 5; } 100% { opacity: 1; } }
        .anim-line-kim { stroke-dasharray: ${kimLen}; stroke-dashoffset: ${kimLen}; animation: drawLine 1.5s ease-out forwards; }
        .anim-line-park { stroke-dasharray: ${parkLen}; stroke-dashoffset: ${parkLen}; animation: drawLine 1.5s ease-out 0.3s forwards; }
        .anim-dot { opacity: 0; animation: fadeIn 0.3s ease-out forwards; }
        .anim-label { opacity: 0; animation: fadeIn 0.4s ease-out forwards; }
      `}</style>
      {[30, 40, 50, 60].map(v => (
        <g key={v}>
          <line x1={pl} y1={Y(v)} x2={w - pr} y2={Y(v)} stroke="#111d30" strokeWidth="0.5" />
          <text x={pl - 4} y={Y(v) + 3} fill="#4b6a9b" fontSize="7" textAnchor="end" fontFamily="monospace">{v}</text>
        </g>
      ))}
      <line x1={dividerX} y1={pt} x2={dividerX} y2={h - pb} stroke="#374151" strokeWidth="1" strokeDasharray="4,4" />
      <polygon
        points={data.map((d, i) => `${pl + i * xs},${Y(d.kim)}`).join(" ") + " " +
          [...data].reverse().map((d, i) => `${pl + (n - 1 - i) * xs},${Y(d.park)}`).join(" ")}
        fill="rgba(100,100,100,0.03)" className="anim-label" style={{ animationDelay: "0.8s" }}
      />
      <polyline points={parkPts.map(p => `${p.x},${p.y}`).join(" ")}
        fill="none" stroke="#ef4444" strokeWidth="2" strokeLinejoin="round" className="anim-line-park" />
      <polyline points={kimPts.map(p => `${p.x},${p.y}`).join(" ")}
        fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinejoin="round" className="anim-line-kim line-glow" />
      {data.map((d, i) => {
        const isE = d.type === "election";
        const delay = `${0.8 + i * 0.08}s`;
        return (
          <g key={i}>
            <circle cx={pl + i * xs} cy={Y(d.kim)} r={isE ? 4.5 : 3}
              fill={isE ? "#2563eb" : "none"} stroke="#2563eb" strokeWidth={isE ? 2 : 1.5}
              className={`anim-dot ${i === n - 1 ? "index-dot" : ""}`} style={{ animationDelay: delay }} />
            <text x={pl + i * xs} y={Y(d.kim) - 6} fill="#2563eb"
              fontSize={isE ? "9" : "8"} fontWeight="bold" textAnchor="middle"
              className="anim-label" style={{ animationDelay: delay }}>{d.kim}</text>
            <circle cx={pl + i * xs} cy={Y(d.park)} r={isE ? 4.5 : 3}
              fill={isE ? "#ef4444" : "none"} stroke="#ef4444" strokeWidth={isE ? 2 : 1.5}
              className="anim-dot" style={{ animationDelay: delay }} />
            <text x={pl + i * xs} y={Y(d.park) + 13} fill="#ef4444"
              fontSize={isE ? "9" : "8"} fontWeight="bold" textAnchor="middle"
              className="anim-label" style={{ animationDelay: delay }}>{d.park}</text>
            <text x={pl + i * xs} y={h - pb + 10} fill="#6b7280" fontSize="7" textAnchor="middle"
              className="anim-label" style={{ animationDelay: delay }}>{d.label}</text>
            <text x={pl + i * xs} y={h - 3} fill="#6b7280" fontSize="6" textAnchor="middle" fontFamily="monospace"
              className="anim-label" style={{ animationDelay: delay }}>{d.date}</text>
          </g>
        );
      })}
    </svg>
  );
}

function ForecastTrendChart({ data, candidate, opponent }: { data: any[]; candidate: string; opponent: string }) {
  // poll_actual_park가 0인 날 제외 (불완전 데이터)
  const recent = data.slice(-7).filter(d => (d.poll_actual_kim || 0) > 0 && (d.poll_actual_park || 0) > 0);
  if (recent.length < 2) return <div className="h-32 flex items-center justify-center text-gray-400 text-xs">유효 데이터 2일 이상 필요 ({recent.length}/2)</div>;

  const n = recent.length;
  const w = 520, h = 160, pl = 38, pr = 50, pt = 14, pb = 26;
  const xs = (w - pl - pr) / (n - 1);

  const pollKim = recent.map(d => d.poll_actual_kim || 0);
  const pollPark = recent.map(d => d.poll_actual_park || 0);

  // Y축 — 여론조사 데이터 범위에 맞게 좁힘
  const pollVals = [...pollKim, ...pollPark].filter(v => v > 0);
  if (pollVals.length === 0) return <div className="h-32 flex items-center justify-center text-gray-400 text-xs">데이터 없음</div>;

  const mn = Math.floor(Math.min(...pollVals) - 1);
  const mx = Math.ceil(Math.max(...pollVals) + 1);
  const rng = mx - mn || 1;
  const Y = (v: number) => pt + (1 - (v - mn) / rng) * (h - pt - pb);

  const lastPK = pollKim[n - 1];
  const lastPP = pollPark[n - 1];
  const pollGap = lastPK - lastPP;

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`}>
      {/* 그리드 — 1%p 단위 */}
      {Array.from({ length: mx - mn + 1 }, (_, i) => mn + i).map(v => (
        <g key={v}>
          <line x1={pl} y1={Y(v)} x2={w - pr} y2={Y(v)} stroke="#111d30" strokeWidth="0.5" />
          <text x={pl - 4} y={Y(v) + 3} fill="#4b6a9b" fontSize="8" textAnchor="end" fontFamily="monospace">{v}%</text>
        </g>
      ))}

      {/* 격차 영역 */}
      <polygon
        points={pollKim.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ") + " " +
          [...pollPark].reverse().map((v, i) => `${pl + (n - 1 - i) * xs},${Y(v)}`).join(" ")}
        fill={pollGap >= 0 ? "rgba(37,99,235,0.10)" : "rgba(239,68,68,0.10)"}
      />

      {/* 박완수 라인 */}
      <polyline points={pollPark.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ")}
        fill="none" stroke="#ef4444" strokeWidth="2.5" opacity="0.8" strokeLinejoin="round" />
      {/* 김경수 라인 */}
      <polyline points={pollKim.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ")}
        fill="none" stroke="#2563eb" strokeWidth="3" strokeLinejoin="round" />

      {/* 매일 값 — 김경수 */}
      {pollKim.map((v, i) => (
        <g key={`pk${i}`}>
          <circle cx={pl + i * xs} cy={Y(v)} r={i === n - 1 ? 5 : 3} fill="#2563eb" stroke="#04070d" strokeWidth={i === n - 1 ? 2 : 1} />
          <text x={pl + i * xs} y={Y(v) - 8} fill="#2563eb" fontSize={i === n - 1 ? "11" : "9"} fontWeight="bold" textAnchor="middle">
            {v.toFixed(1)}
          </text>
        </g>
      ))}
      {/* 매일 값 — 박완수 */}
      {pollPark.map((v, i) => (
        <g key={`pp${i}`}>
          <circle cx={pl + i * xs} cy={Y(v)} r={i === n - 1 ? 3.5 : 2} fill="#ef4444" stroke="#04070d" strokeWidth={i === n - 1 ? 1.5 : 0.5} opacity="0.8" />
          <text x={pl + i * xs} y={Y(v) + 12} fill="#ef4444" fontSize={i === n - 1 ? "9" : "7"} textAnchor="middle" opacity="0.8">
            {v.toFixed(1)}
          </text>
        </g>
      ))}

      {/* 오른쪽 라벨 */}
      <rect x={w - pr + 3} y={Y(lastPK) - 12} width={46} height={18} rx="3" fill="#0a0f1a" stroke="#2563eb" strokeWidth="1" />
      <text x={w - pr + 26} y={Y(lastPK) + 2} fill="#2563eb" fontSize="11" fontWeight="bold" textAnchor="middle">{lastPK.toFixed(1)}%</text>

      <rect x={w - pr + 3} y={Y(lastPP) - 12} width={46} height={18} rx="3" fill="#1a0a0a" stroke="#ef4444" strokeWidth="1" />
      <text x={w - pr + 26} y={Y(lastPP) + 2} fill="#ef4444" fontSize="11" fontWeight="bold" textAnchor="middle">{lastPP.toFixed(1)}%</text>

      {/* 격차 표시 */}
      <text x={w - pr + 26} y={(Y(lastPK) + Y(lastPP)) / 2 + 3} fill={pollGap >= 0 ? "#34d399" : "#fb7185"} fontSize="9" fontWeight="bold" textAnchor="middle">
        {pollGap >= 0 ? "+" : ""}{pollGap.toFixed(1)}
      </text>

      {/* X축 */}
      {recent.map((d, i) => (
        <text key={i} x={pl + i * xs} y={h - 3} fill="#4b6a9b" fontSize="7" textAnchor="middle" fontFamily="monospace">
          {(d.date || "").slice(5)}
        </text>
      ))}
    </svg>
  );
}

function IndexBattleChart({ data, candidate, opponent }: { data: any[]; candidate: string; opponent: string }) {
  const recent = data.slice(-7).filter(d => (d.leading_index || 0) > 0);
  if (recent.length < 2) return <div className="h-32 flex items-center justify-center text-gray-400 text-xs">데이터 2일 이상 필요 ({recent.length}/2)</div>;

  const charts = [
    { title: "이슈", ourKey: "issue_index_avg", oppKey: "opp_issue_avg" },
    { title: "반응", ourKey: "reaction_index_avg", oppKey: "opp_reaction_avg" },
    { title: "판세", ourKey: "leading_index", oppKey: "_opp_leading" },
  ];

  return (
    <div className="grid grid-cols-3 gap-2">
      {charts.map(chart => {
        const n = recent.length;
        const w = 260, h = 130, pl = 6, pr = 6, pt = 8, pb = 20;
        const xs = (w - pl - pr) / (n - 1);

        const ourVals = recent.map(d => d[chart.ourKey] || 0);
        const oppVals = chart.oppKey
          ? chart.oppKey === "_opp_leading"
            ? recent.map(d => 100 - (d[chart.ourKey] || 50))  // 선행지수: 상대 = 100 - 우리
            : recent.map(d => d[chart.oppKey] || 0)
          : [];
        const allV = [...ourVals, ...oppVals].filter(Boolean);
        if (allV.length === 0) return null;
        const mn = Math.max(0, Math.min(...allV) - 10);
        const mx = Math.min(100, Math.max(...allV) + 10);
        const rng = mx - mn || 1;
        const Y = (v: number) => pt + (1 - (v - mn) / rng) * (h - pt - pb);

        const lastOur = ourVals[n - 1];
        const prevOur = ourVals[n - 2] || lastOur;
        const delta = lastOur - prevOur;
        const lastOpp = oppVals.length > 0 ? oppVals[n - 1] : null;
        const gap = lastOpp !== null ? lastOur - lastOpp : null;
        const winning = gap !== null ? gap > 0 : lastOur >= 50;

        return (
          <div key={chart.title} className={`rounded-lg p-2 border bg-[#080d16] border-[#121e33]`}>
            {/* 헤더 */}
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] text-gray-300 font-bold">{chart.title}</span>
              <div className="flex items-center gap-1">
                <span className="text-[14px] font-black text-blue-500">{lastOur.toFixed(0)}</span>
                <span className="text-[9px] text-gray-400">vs</span>
                <span className="text-[14px] font-black text-red-500">{lastOpp !== null ? lastOpp.toFixed(0) : "—"}</span>
                {gap !== null && (
                  <span className={`text-[10px] font-mono font-bold ml-1 px-1 rounded ${gap > 0 ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-500"}`}>
                    {gap > 0 ? "+" : ""}{gap.toFixed(0)}
                  </span>
                )}
              </div>
            </div>

            {/* 차트 */}
            <svg width="100%" viewBox={`0 0 ${w} ${h}`}>
              {/* 선행지수 50 기준선 */}
              {chart.ourKey === "leading_index" && mn < 50 && mx > 50 && (
                <>
                  <line x1={pl} y1={Y(50)} x2={w - pr} y2={Y(50)} stroke="#374151" strokeWidth="0.5" strokeDasharray="3,3" />
                  <text x={w - pr} y={Y(50) - 2} fill="#374151" fontSize="6" textAnchor="end">50</text>
                </>
              )}

              {/* 격차 영역 (우리-상대 사이) */}
              {oppVals.length > 0 && (
                <polygon
                  points={ourVals.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ") + " " +
                    [...oppVals].reverse().map((v, i) => `${pl + (n - 1 - i) * xs},${Y(v)}`).join(" ")}
                  fill={winning ? "rgba(37,99,235,0.08)" : "rgba(239,68,68,0.06)"}
                />
              )}

              {/* 상대 라인 — 국힘 빨강 점선 */}
              {oppVals.length > 0 && (
                <polyline points={oppVals.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ")}
                  fill="none" stroke="#ef4444" strokeWidth="2" strokeDasharray="4,3" opacity="0.7" />
              )}

              {/* 우리 라인 — 민주 파랑 실선 */}
              <polyline points={ourVals.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ")}
                fill="none" stroke="#2563eb" strokeWidth="3" strokeLinejoin="round" />

              {/* 매일 값 — 우리 (민주 파랑) */}
              {ourVals.map((v, i) => (
                <g key={`o${i}`}>
                  <circle cx={pl + i * xs} cy={Y(v)} r={i === n - 1 ? 5 : 3}
                    fill="#2563eb" stroke="#04070d" strokeWidth={i === n - 1 ? 2 : 1} />
                  <text x={pl + i * xs} y={Y(v) - 7} fill="#2563eb"
                    fontSize={i === n - 1 ? "10" : "8"} fontWeight="bold" textAnchor="middle">
                    {v.toFixed(0)}
                  </text>
                </g>
              ))}

              {/* 매일 값 — 상대 (국힘 빨강) */}
              {oppVals.map((v, i) => (
                <g key={`e${i}`}>
                  <circle cx={pl + i * xs} cy={Y(v)} r={i === n - 1 ? 4 : 2}
                    fill="#ef4444" stroke="#04070d" strokeWidth={i === n - 1 ? 1.5 : 0.5} opacity="0.8" />
                  <text x={pl + i * xs} y={Y(v) + 12} fill="#ef4444"
                    fontSize={i === n - 1 ? "9" : "7"} textAnchor="middle" opacity="0.7">
                    {v.toFixed(0)}
                  </text>
                </g>
              ))}

              {/* X축 날짜 */}
              {recent.map((d, i) => (
                <text key={i} x={pl + i * xs} y={h - 3} fill="#6b7280" fontSize="7" textAnchor="middle" fontFamily="monospace">
                  {(d.date || "").slice(8)}
                </text>
              ))}
            </svg>

            {/* 하단 범례 */}
            <div className="flex items-center justify-between mt-0.5">
              <span className={`text-[8px] font-bold ${winning ? "text-emerald-400" : "text-rose-500"}`}>
                {winning ? "우세" : "열세"}
              </span>
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-0.5"><span className="w-3 h-[3px] rounded bg-blue-500" /><span className="text-[7px] text-gray-400">{candidate}</span></span>
                <span className="flex items-center gap-0.5"><span className="w-3 h-[2px] rounded bg-red-500 opacity-70" /><span className="text-[7px] text-gray-400">{opponent}</span></span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function TodayActions({ exec, crisisIssues, alertIssues, trend }: { exec: any; crisisIssues: any[]; alertIssues: any[]; trend: any }) {
  const actions: { text: string; level: "critical" | "high" | "medium" | "low" }[] = [];
  if (crisisIssues.length > 0) {
    actions.push({ text: `"${crisisIssues[0].keyword}" 긴급 대응 — 즉시 입장 표명`, level: "critical" });
    if (crisisIssues.length > 1) actions.push({ text: `외 ${crisisIssues.length - 1}건 위기 이슈 브리핑 필요`, level: "critical" });
  }
  if (trend?.momentum === "losing") actions.push({ text: "지지율 하락세 — 프레임 전환 필요", level: "high" });
  if (alertIssues.length > 0) actions.push({ text: `${alertIssues.length}건 경계 이슈 모니터링`, level: "medium" });
  if (trend?.momentum === "gaining") actions.push({ text: "상승세 유지 — 현재 메시지 강화", level: "low" });
  if (exec?.days_left && exec.days_left <= 30) actions.push({ text: `D-${exec.days_left} 최종 유세 집중`, level: "high" });
  if (actions.length === 0) actions.push({ text: "기본 일정 수행", level: "low" });

  const styles: Record<string, string> = {
    critical: "border-l-red-500 bg-red-950/30 text-red-300",
    high: "border-l-orange-500 bg-orange-950/20 text-orange-300",
    medium: "border-l-yellow-600 bg-yellow-950/10 text-yellow-200/80",
    low: "border-l-emerald-600 bg-emerald-950/10 text-emerald-300/80",
  };
  const dots: Record<string, string> = { critical: "bg-red-500 crisis-pulse", high: "bg-orange-500", medium: "bg-yellow-600", low: "bg-emerald-600" };

  return (
    <div className="space-y-1">
      {actions.slice(0, 4).map((a, i) => (
        <div key={i} className={`flex items-start gap-2 px-2 py-1.5 rounded border-l-2 ${styles[a.level]}`}>
          <span className={`w-1.5 h-1.5 rounded-full mt-1 shrink-0 ${dots[a.level]}`} />
          <span className="text-[11px] leading-tight">{a.text}</span>
        </div>
      ))}
    </div>
  );
}

function RiskGauge({ level, crisisCount }: { level: string; crisisCount: number }) {
  const segments = ["GREEN", "YELLOW", "RED"];
  const activeIdx = segments.indexOf(level);
  return (
    <div className="bg-[#080d16] rounded border border-[#121e33] p-2">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[9px] text-gray-400 uppercase tracking-widest">위험 수준</span>
        {crisisCount > 0 && <span className="text-[9px] text-red-400 font-bold crisis-pulse">{crisisCount}건</span>}
      </div>
      <div className="flex gap-1 h-2">
        {segments.map((s, i) => (
          <div key={s} className={`flex-1 rounded-sm transition-all ${
            i <= activeIdx
              ? i === 2 ? "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.4)]"
                : i === 1 ? "bg-orange-500 shadow-[0_0_6px_rgba(245,158,11,0.3)]"
                : "bg-emerald-500"
              : "bg-[#111d30]"
          }`} />
        ))}
      </div>
      <div className="flex justify-between mt-1 text-[7px] text-gray-400"><span>정상</span><span>경계</span><span>위기</span></div>
    </div>
  );
}

function OpponentAlerts({ alerts, opponent }: { alerts: any[]; opponent: string }) {
  const oppAlerts = alerts.filter((a: any) =>
    a.type === "opponent" || a.category === "opponent" || (a.title || a.message || "").includes(opponent)
  ).slice(0, 3);
  if (oppAlerts.length > 0) return <>{oppAlerts.map((a: any, i: number) => (
    <div key={i} className="text-[10px] text-red-300/70 my-0.5 leading-tight">• {a.title || a.message}</div>
  ))}</>;
  return <div className="text-[10px] text-gray-400">특이 동향 없음</div>;
}

function IssueDrillDown({ data, reactionData }: { data: any; reactionData?: any }) {
  if (!data && !reactionData) return <div className="px-4 py-3 text-[10px] text-gray-400 bg-[#080d16]">로딩...</div>;
  const words = data?.co_words || [];
  const who = data?.who_talks || {};
  const gt = data?.google_trends || {};
  const tone = data?.tone || {};
  const rx = reactionData;

  return (
    <div className="bg-[#080d16] border-l-2 border-l-blue-600 px-3 py-2 text-[10px] space-y-1.5">
      {/* 기존: 감성 + 소스 + 연관키워드 */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-gray-400">감성:</span>
        <span className={tone.score > 0.2 ? "text-emerald-400" : tone.score < -0.2 ? "text-red-400" : "text-yellow-400"}>
          {tone.dominant || "—"} ({tone.score?.toFixed(2) || "—"})
        </span>
        {gt.interest > 0 && <span className="text-gray-400">구글: <span className="text-blue-400">{gt.interest}/100</span></span>}
      </div>
      {Object.entries(who).length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-gray-400">소스:</span>
          {Object.entries(who).map(([ch, v]: [string, any]) => (
            <span key={ch} className="text-gray-400 bg-[#0d1420] px-1.5 py-0.5 rounded">{ch} {typeof v === "object" ? v.total : v}건</span>
          ))}
        </div>
      )}
      {words.length > 0 && (
        <div className="flex gap-1 flex-wrap">
          {words.slice(0, 8).map((w_: any, i: number) => (
            <span key={i} className="bg-blue-950/30 border border-blue-800/30 text-blue-400/70 px-1.5 py-0.5 rounded text-[8px]">{w_.word} {w_.count}</span>
          ))}
        </div>
      )}

      {/* Reaction Index 상세 */}
      {rx && (
        <div className="border-t border-[#1a2844] pt-1.5 mt-1.5 space-y-1.5">
          {/* 5-Layer Breakdown */}
          <div className="flex items-center gap-2">
            <span className="text-purple-400 font-bold">Reaction {rx.final_score?.toFixed(0)}</span>
            <span className={`text-[8px] px-1.5 rounded ${
              rx.grade === "VIRAL" ? "bg-purple-950/40 text-purple-400" :
              rx.grade === "ENGAGED" ? "bg-blue-950/40 text-blue-400" :
              "bg-gray-800/40 text-gray-400"
            }`}>{rx.grade}</span>
            <span className={`text-[8px] ${rx.direction === "positive" ? "text-emerald-400" : rx.direction === "negative" ? "text-red-400" : "text-gray-400"}`}>
              {rx.direction === "positive" ? "▲긍정" : rx.direction === "negative" ? "▼부정" : "●중립"}
            </span>
            <span className="text-gray-400 text-[8px]">신뢰 {(rx.confidence * 100).toFixed(0)}% ({rx.layers_active}/5)</span>
            {rx.velocity_flag && <span className="text-amber-400 text-[8px]">⚡×{rx.velocity_multiplier}</span>}
          </div>

          {/* Layer bars */}
          <div className="space-y-0.5">
            {[
              { key: "community_resonance", label: "커뮤니티", max: 25, color: "#a855f7" },
              { key: "content_creation", label: "콘텐츠", max: 20, color: "#3b82f6" },
              { key: "sentiment_direction", label: "감성방향", max: 20, color: "#2563eb" },
              { key: "search_reaction", label: "검색반응", max: 15, color: "#f59e0b" },
              { key: "youtube_comment", label: "YT댓글", max: 20, color: "#ef4444" },
            ].map((layer) => {
              const val = rx.components?.[layer.key] || 0;
              return (
                <div key={layer.key} className="flex items-center gap-1.5">
                  <span className="w-12 text-[8px] text-gray-400 text-right">{layer.label}</span>
                  <div className="flex-1 h-[4px] bg-[#0a1019] rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${(val / layer.max) * 100}%`, background: layer.color }} />
                  </div>
                  <span className="w-8 text-right text-[8px] font-mono text-gray-400">{val.toFixed(0)}/{layer.max}</span>
                </div>
              );
            })}
          </div>

          {/* 세그먼트 반응 */}
          {rx.segment_reactions?.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              <span className="text-gray-400 text-[8px]">세그먼트:</span>
              {rx.segment_reactions.slice(0, 4).map((sr: any, i: number) => (
                <span key={i} className={`text-[7px] px-1 rounded ${
                  sr.intensity >= 0.5 ? "bg-purple-950/30 text-purple-400" : "bg-gray-800/40 text-gray-400"
                }`}>{sr.label}</span>
              ))}
              {rx.hottest_segment && <span className="text-[8px] text-purple-400">🔥{rx.hottest_segment}</span>}
            </div>
          )}

          {/* 유튜브 댓글 */}
          {rx.yt_comments_total > 0 && (
            <div className="text-[8px]">
              <span className="text-gray-400">YT댓글 {rx.yt_comments_total}건</span>
              <span className={`ml-1 ${rx.yt_comment_sentiment > 0 ? "text-emerald-400" : rx.yt_comment_sentiment < 0 ? "text-red-400" : "text-gray-400"}`}>
                감성 {rx.yt_comment_sentiment?.toFixed(2)}
              </span>
              {rx.mobilization_signal && <span className="ml-1 text-amber-400">⚠동원감지</span>}
            </div>
          )}
          {rx.yt_top_positive && <div className="text-[8px] text-emerald-400/70 truncate">👍 {rx.yt_top_positive}</div>}
          {rx.yt_top_negative && <div className="text-[8px] text-red-400/70 truncate">👎 {rx.yt_top_negative}</div>}

          {/* 톤 + 동원 */}
          <div className="flex items-center gap-2 text-[8px]">
            {rx.dominant_tone && <span className="text-gray-400">톤: {rx.dominant_tone}</span>}
            {rx.dominant_channel && <span className="text-gray-400">주요채널: {rx.dominant_channel}</span>}
            {rx.endorsement_count > 0 && <span className="text-emerald-400">지지선언 {rx.endorsement_count}</span>}
            {rx.withdrawal_count > 0 && <span className="text-red-400">철회 {rx.withdrawal_count}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

function RegionBattleMap({ issues, selectedRegion, onSelect }: { issues: any[]; selectedRegion: string | null; onSelect: (r: string | null) => void }) {
  const rows = [
    [{ n: "밀양", t: "weak" }, { n: "양산", t: "swing" }],
    [{ n: "진주", t: "strong" }, { n: "창원", t: "swing", w: true }, { n: "김해", t: "strong" }],
    [{ n: "사천", t: "strong" }, { n: "거제", t: "swing" }, { n: "통영", t: "weak" }],
  ];

  const getRegionData = (name: string) => {
    const ri = issues.filter((r: any) => r.region === name || r.keyword?.includes(name));
    const pressure = ri.reduce((max: number, r: any) => Math.max(max, r.score || 0), 0);
    const negCount = ri.filter((r: any) => r.sentiment === "negative").length;
    const sentiment = ri.length > 0 ? (negCount > ri.length * 0.5 ? "부정" : negCount > 0 ? "혼재" : "긍정") : "—";
    return { pressure, sentiment };
  };

  const tc: Record<string, { bg: string; bd: string; tx: string }> = {
    strong: { bg: "bg-blue-950/50", bd: "border-blue-700/50", tx: "text-blue-300" },
    swing: { bg: "bg-orange-950/30", bd: "border-orange-700/40", tx: "text-orange-300" },
    weak: { bg: "bg-red-950/30", bd: "border-red-700/40", tx: "text-red-300" },
  };

  return (
    <div className="space-y-1">
      {rows.map((row, ri) => (
        <div key={ri} className="flex gap-1 justify-center">
          {row.map(({ n, t, w }) => {
            const c = tc[t];
            const rd = getRegionData(n);
            const isSelected = selectedRegion === n;
            return (
              <div key={n}
                onClick={() => onSelect(isSelected ? null : n)}
                className={`${w ? "w-[110px]" : "w-[76px]"} rounded border ${c.bg} ${c.bd} flex flex-col items-center justify-center cursor-pointer transition-all ${
                  isSelected ? "ring-1 ring-blue-500 brightness-125" : "hover:brightness-150"
                } py-1.5`}
              >
                <span className={`text-[11px] font-bold ${c.tx}`}>{n}</span>
                <div className="flex items-center gap-1 mt-0.5">
                  <span className={`text-[7px] font-mono ${rd.pressure >= 50 ? "text-red-400" : "text-gray-400"}`}>
                    {rd.pressure > 0 ? rd.pressure.toFixed(0) : "—"}
                  </span>
                  <span className={`text-[7px] ${
                    rd.sentiment === "부정" ? "text-red-400" : rd.sentiment === "혼재" ? "text-yellow-400" : "text-gray-400"
                  }`}>{rd.sentiment}</span>
                </div>
              </div>
            );
          })}
        </div>
      ))}
      <div className="flex justify-center gap-4 mt-1 text-[8px]">
        <span className="text-blue-400">● 우세</span>
        <span className="text-orange-400">● 접전</span>
        <span className="text-red-400">● 열세</span>
      </div>
    </div>
  );
}

function RegionDetail({ region, issues }: { region: string; issues: any[] }) {
  const regionIssues = issues.filter((r: any) => r.region === region || r.keyword?.includes(region)).slice(0, 3);
  return (
    <div className="space-y-1 pt-2">
      <div className="text-[9px] text-blue-400 font-bold">{region} 로컬 토킹포인트</div>
      {regionIssues.length > 0 ? regionIssues.map((r: any, i: number) => (
        <div key={i} className="text-[9px] text-gray-400 leading-tight">
          <span className={r.level === "CRISIS" ? "text-red-400" : r.level === "ALERT" ? "text-orange-400" : "text-blue-400"}>●</span>
          {" "}{r.keyword} — {r.recommended_stance || r.strategy || "모니터링"}
        </div>
      )) : (
        <div className="text-[9px] text-gray-400">지역 특이사항 없음</div>
      )}
    </div>
  );
}

function KPIRow({ icon, label, value, delta, format }: { icon: string; label: string; value: any; delta?: any; format: string }) {
  let display = "—";
  let color = "text-gray-400";
  let deltaStr = "";
  let deltaColor = "text-gray-400";

  if (value !== undefined && value !== null) {
    switch (format) {
      case "score":
        display = Number(value).toFixed(0);
        color = Number(value) >= 60 ? "text-emerald-400" : Number(value) >= 30 ? "text-yellow-400" : "text-red-400";
        break;
      case "sentiment":
        display = Number(value).toFixed(2);
        color = Number(value) >= 0.1 ? "text-emerald-400" : Number(value) <= -0.1 ? "text-red-400" : "text-yellow-400";
        break;
      case "crisis":
        display = String(value);
        color = Number(value) === 0 ? "text-emerald-400" : Number(value) <= 2 ? "text-orange-400" : "text-red-400";
        break;
      case "pct":
        display = Number(value).toFixed(0) + "%";
        color = Number(value) >= 50 ? "text-emerald-400" : Number(value) >= 30 ? "text-yellow-400" : "text-red-400";
        break;
      case "risk":
        display = String(value);
        color = Number(value) <= 3 ? "text-emerald-400" : Number(value) <= 6 ? "text-yellow-400" : "text-red-400";
        break;
      case "ratio":
        display = Number(value).toFixed(1);
        color = Number(value) >= 1 ? "text-emerald-400" : "text-red-400";
        break;
    }
  }

  if (delta !== undefined && delta !== null) {
    const d = Number(delta);
    deltaStr = (d >= 0 ? "+" : "") + (format === "sentiment" ? d.toFixed(2) : d.toFixed(0));
    deltaColor = d > 0 ? (format === "crisis" || format === "risk" ? "text-red-400" : "text-emerald-400") :
                 d < 0 ? (format === "crisis" || format === "risk" ? "text-emerald-400" : "text-red-400") : "text-gray-400";
  }

  return (
    <div className="flex items-center gap-2 px-3 py-[7px] hover:bg-[#0d1420] text-[11px]">
      <span className="w-4 text-center opacity-50 text-[10px]">{icon}</span>
      <span className="flex-1 text-gray-400">{label}</span>
      <span className={`font-mono font-bold ${color}`}>{display}</span>
      {deltaStr && <span className={`font-mono text-[9px] w-7 text-right ${deltaColor}`}>{deltaStr}</span>}
    </div>
  );
}


function SnsBattleBar({ label, our, opp, ourName, oppName }: {
  label: string; our: number; opp: number; ourName: string; oppName: string;
}) {
  const total = our + opp || 1;
  const ourPct = (our / total) * 100;
  const winning = our > opp;
  return (
    <div className="flex items-center gap-1.5 text-[9px]">
      <span className="w-10 text-gray-400 text-right">{label}</span>
      <span className={`w-8 text-right font-mono ${winning ? "text-blue-400 font-bold" : "text-gray-400"}`}>{our}</span>
      <div className="flex-1 h-[6px] bg-[#0a1019] rounded-full overflow-hidden flex">
        <div className="h-full bg-blue-500 rounded-l-full" style={{ width: `${ourPct}%` }} />
        <div className="h-full bg-red-500 rounded-r-full" style={{ width: `${100 - ourPct}%` }} />
      </div>
      <span className={`w-8 text-left font-mono ${!winning ? "text-red-400 font-bold" : "text-gray-400"}`}>{opp}</span>
    </div>
  );
}
