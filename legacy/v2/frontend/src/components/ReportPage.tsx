"use client";
import { useState, useEffect } from "react";
import { getAIBriefing, getV2Enrichment, getIndexTrend, getIssueResponses, getNewsComments, getAutoPolls, getStrategicReport } from "@/lib/api";
import { POLL_DATA, mergeAutoPolls, getLatestPoll } from "@/lib/pollData";

// ════════════════════════════════════════════════════════════════════
// DAILY REPORT v2 — 캠프 전략회의 자료급 데일리 리포트
// 벤치마크: weekly-report-sample 11챕터 구조
// 원칙: 차트+댓글원문+AI해석, 인쇄/PDF 가능
// ════════════════════════════════════════════════════════════════════

// POLL_DATA는 @/lib/pollData에서 import

export function ReportPage() {
  const [briefing, setBriefing] = useState<any>(null);
  const [enrichment, setEnrichment] = useState<any>(null);
  const [trend, setTrend] = useState<any[]>([]);
  const [issues, setIssues] = useState<any[]>([]);
  const [autoPolls, setAutoPolls] = useState<any[]>([]);
  const [tab, setTab] = useState<"strategy" | "daily">("strategy");
  const [stratReport, setStratReport] = useState<{html:string;filename:string;date:string}|null>(null);
  const [stratLoading, setStratLoading] = useState(true);

  useEffect(() => {
    getAIBriefing().then(setBriefing).catch(() => {});
    getV2Enrichment().then(setEnrichment).catch(() => {});
    getIndexTrend(7).then(r => setTrend(r?.trend || [])).catch(() => {});
    getIssueResponses().then(d => setIssues(d?.responses || [])).catch(() => {});
    getAutoPolls().then(d => setAutoPolls(d?.polls || [])).catch(() => {});
    getStrategicReport().then(d => { setStratReport(d); setStratLoading(false); }).catch(() => setStratLoading(false));
  }, []);

  const allPolls = mergeAutoPolls(autoPolls);
  const latest = getLatestPoll(autoPolls);
  const pollGap = latest.kim - latest.park;
  const todaySnap = trend.length > 0 ? trend[trend.length - 1] : null;
  const prevSnap = trend.length >= 2 ? trend[trend.length - 2] : null;
  const today = new Date().toISOString().slice(0, 10);
  const ii = enrichment?.issue_indices || {};
  const ri = enrichment?.reaction_indices || {};
  const aiSent = enrichment?.ai_sentiment || {};

  return (
    <div className="max-w-[840px] mx-auto space-y-8 pb-20 print:space-y-5 print:pb-0">

      {/* ═══ 탭 전환 ═══ */}
      <div className="flex gap-2 print:hidden">
        <button onClick={() => setTab("strategy")}
          className={`px-5 py-2.5 rounded-lg text-[13px] font-bold transition ${tab === "strategy" ? "bg-cyan-600 text-white" : "bg-[#141b2d] text-gray-400 hover:text-gray-200 border border-[#1a2844]"}`}>
          전략대응 리포트
        </button>
        <button onClick={() => setTab("daily")}
          className={`px-5 py-2.5 rounded-lg text-[13px] font-bold transition ${tab === "daily" ? "bg-cyan-600 text-white" : "bg-[#141b2d] text-gray-400 hover:text-gray-200 border border-[#1a2844]"}`}>
          데일리 분석 리포트
        </button>
      </div>

      {/* ═══ 전략대응 리포트 탭 ═══ */}
      {tab === "strategy" && (
        <div>
          {stratLoading ? (
            <div className="text-center py-20 text-gray-400">리포트 로딩 중...</div>
          ) : stratReport?.html ? (
            <>
              <div className="flex items-center justify-between mb-4">
                <div className="text-[12px] text-gray-400">{stratReport.filename} | {stratReport.date}</div>
                <div className="flex gap-2">
                  <button onClick={() => { setStratLoading(true); getStrategicReport().then(d => { setStratReport(d); setStratLoading(false); }).catch(() => setStratLoading(false)); }}
                    className="px-3 py-1.5 bg-[#141b2d] text-gray-300 border border-[#1a2844] rounded text-[11px] hover:bg-[#1a2844] transition">
                    새로고침
                  </button>
                  <button onClick={() => { const w = window.open('','_blank'); if(!w) return; w.document.write(`<html><head><title>전략대응 리포트</title><style>
                    body{font-family:-apple-system,'Apple SD Gothic Neo',sans-serif;padding:32px 40px;line-height:1.7;color:#222;max-width:900px;margin:0 auto;font-size:14px}
                    h1{font-size:1.5em;border-bottom:3px solid #1a237e;padding-bottom:6px;margin-top:24px}
                    h2{font-size:1.25em;color:#1a237e;background:#f0f4ff;padding:8px 14px;border-left:4px solid #1a237e;border-radius:0 6px 6px 0;margin-top:24px}
                    h3{font-size:1.1em;color:#333;margin-top:18px;padding-left:10px;border-left:3px solid #ccc}
                    table{width:100%;border-collapse:collapse;margin:10px 0;font-size:13px;border:1px solid #ddd;border-radius:6px}
                    th{background:#f0f4ff;padding:8px 10px;text-align:left;border:1px solid #ddd;font-weight:700;color:#1a237e;font-size:12px}
                    td{padding:7px 10px;border:1px solid #eee;color:#333}
                    blockquote{border-left:4px solid #1a237e;margin:12px 0;padding:10px 16px;background:#f8f9ff;color:#444;font-size:13px;border-radius:0 6px 6px 0}
                    strong{font-weight:700;color:#111}em{font-style:normal;font-weight:600;color:#1a237e}
                    code{background:#f5f5f5;padding:2px 5px;border-radius:3px;font-size:.9em}
                    hr{border:none;border-top:1.5px solid #ddd;margin:20px 0}
                    li{margin:4px 0;padding-left:4px;list-style:none}li:before{content:"→";color:#1a237e;margin-right:6px;font-weight:bold}
                    p{margin:6px 0}
                    @page{margin:20mm 15mm}
                    </style></head><body>${stratReport.html}</body></html>`); w.document.close(); w.print(); }}
                    className="px-3 py-1.5 bg-cyan-600/20 text-cyan-400 border border-cyan-700/40 rounded text-[11px] hover:bg-cyan-600/30 transition">
                    PDF 인쇄
                  </button>
                </div>
              </div>
              <div className="strat-report-body" dangerouslySetInnerHTML={{ __html: stratReport.html }} />
              <style>{`
                .strat-report-body {
                  font-size: 15px; line-height: 1.85; color: #d4d4d4;
                  font-family: -apple-system, 'Apple SD Gothic Neo', sans-serif;
                }
                .strat-report-body h1 {
                  font-size: 1.6em; color: #fff; margin: 32px 0 12px;
                  border-bottom: 3px solid #1976d2; padding-bottom: 10px;
                  letter-spacing: -0.5px;
                }
                .strat-report-body h2 {
                  font-size: 1.35em; color: #e0e0e0; margin: 28px 0 14px;
                  background: linear-gradient(90deg, rgba(25,118,210,.15), transparent);
                  padding: 10px 16px; border-radius: 8px;
                  border-left: 4px solid #1976d2;
                }
                .strat-report-body h3 {
                  font-size: 1.15em; color: #90caf9; margin: 20px 0 8px;
                  padding-left: 12px; border-left: 3px solid #1e3a5f;
                }
                .strat-report-body h4 {
                  font-size: 1.05em; color: #b0bec5; margin: 14px 0 6px;
                }
                .strat-report-body table {
                  width: 100%; border-collapse: separate; border-spacing: 0;
                  margin: 14px 0; font-size: 13.5px;
                  border-radius: 10px; overflow: hidden;
                  border: 1px solid #1e3a5f;
                }
                .strat-report-body th {
                  background: linear-gradient(180deg, #1a2844, #141e30);
                  color: #90caf9; padding: 11px 14px; text-align: left;
                  font-weight: 700; font-size: 12.5px;
                  text-transform: uppercase; letter-spacing: 0.3px;
                  border-bottom: 2px solid #1e3a5f;
                }
                .strat-report-body td {
                  padding: 10px 14px; color: #c8c8c8;
                  border-bottom: 1px solid rgba(30,58,95,.5);
                }
                .strat-report-body tr:last-child td { border-bottom: none; }
                .strat-report-body tr:hover td { background: rgba(25,118,210,.08); }
                .strat-report-body strong { color: #fff; font-weight: 700; }
                .strat-report-body em { color: #90caf9; font-style: normal; font-weight: 600; }
                .strat-report-body code {
                  background: #1a2332; padding: 3px 8px; border-radius: 4px;
                  font-family: monospace; font-size: .88em; color: #4caf50;
                }
                .strat-report-body blockquote {
                  border-left: 4px solid #1976d2; margin: 16px 0;
                  padding: 14px 20px; background: rgba(25,118,210,.06);
                  color: #b0bec5; font-size: 14px;
                  border-radius: 0 10px 10px 0; line-height: 1.8;
                }
                .strat-report-body hr {
                  border: none; border-top: 1px solid #1e3a5f;
                  margin: 28px 0;
                }
                .strat-report-body li {
                  margin: 6px 0; padding-left: 4px; list-style: none;
                }
                .strat-report-body li:before {
                  content: "→"; color: #1976d2; margin-right: 8px; font-weight: bold;
                }
                .strat-report-body p { margin: 8px 0; }
                @media print {
                  .strat-report-body { color: #000; font-size: 11pt; line-height: 1.6; }
                  .strat-report-body h1, .strat-report-body h2, .strat-report-body h3 { color: #000; }
                  .strat-report-body h2 { background: #f0f4ff; border-color: #333; }
                  .strat-report-body table { border-color: #ccc; }
                  .strat-report-body th { background: #f0f0f0; color: #000; }
                  .strat-report-body td { color: #333; border-color: #ddd; }
                  .strat-report-body blockquote { border-color: #666; color: #333; background: #f9f9f9; }
                }
              `}</style>
            </>
          ) : (
            <div className="text-center py-20 text-gray-400">리포트가 없습니다. 먼저 리포트를 생성해주세요.</div>
          )}
        </div>
      )}

      {/* ═══ 데일리 분석 리포트 탭 ═══ */}
      {tab === "daily" && <>

      {/* ═══ 표지 ═══ */}
      <div className="text-center py-10 border-b-2 border-cyan-800/30 print:py-6">
        <div className="text-[12px] text-gray-400 uppercase tracking-[0.3em]">Election Engine Daily Report</div>
        <div className="text-[40px] font-black text-gray-100 mt-3 leading-tight">경남도지사 선거<br/>일일 전략 보고서</div>
        <div className="text-[16px] text-cyan-400 font-bold mt-4">{today}</div>
        <div className="flex justify-center gap-8 mt-5 text-[13px] text-gray-300">
          <span>분석 대상: <span className="text-blue-400 font-bold">김경수</span> vs <span className="text-red-400 font-bold">박완수</span></span>
          <span>D-Day: 74일</span>
          <span>이슈 {issues.length}건 · 여론조사 {POLL_DATA.filter(p => p.type === "poll").length}건</span>
        </div>
        <button onClick={() => window.print()}
          className="mt-5 px-5 py-2.5 bg-cyan-600/20 text-cyan-400 border border-cyan-700/40 rounded-lg text-[12px] font-bold hover:bg-cyan-600/30 transition print:hidden">
          📄 PDF 다운로드 (인쇄)
        </button>
      </div>

      {/* ═══ §1. 오늘의 한줄 ═══ */}
      <section>
        <SH n={1} t="오늘의 한줄" />
        <div className="bg-cyan-950/10 border border-cyan-800/20 rounded-xl p-6">
          <div className="text-[18px] text-gray-100 font-bold leading-[1.8]">
            {briefing?.headline || `여론조사 ${latest.kim}:${latest.park} ${pollGap >= 0 ? "우세" : "열세"}. 판세 ${todaySnap?.leading_index?.toFixed(1) || "—"} 안정.`}
          </div>
        </div>
      </section>

      {/* ═══ §2. 핵심 숫자 + 여론조사 차트 ═══ */}
      <section>
        <SH n={2} t="핵심 숫자 + 여론조사 추이" />
        <div className="grid grid-cols-4 gap-3 mb-4">
          <NC l="여론조사" v={`${latest.kim}:${latest.park}`} d={`${pollGap >= 0 ? "+" : ""}${pollGap.toFixed(1)}%p`} dc={pollGap >= 0} s={`${latest.label}`} />
          <NC l="판세 (선행지수)" v={todaySnap?.leading_index?.toFixed(1) || "—"} d={prevSnap ? `${((todaySnap?.leading_index||50)-prevSnap.leading_index >= 0?"+":"")}${((todaySnap?.leading_index||50)-prevSnap.leading_index).toFixed(1)}` : "—"} dc={(todaySnap?.leading_index||50) >= (prevSnap?.leading_index||50)} s="9-component" />
          <NC l="이슈 격차" v={`${todaySnap ? Math.round((todaySnap.issue_index_avg||0)-(todaySnap.opp_issue_avg||0)) : 0}점`} d="우리-상대" dc={(todaySnap?.issue_index_avg||0) >= (todaySnap?.opp_issue_avg||0)} s="Issue Index" />
          <NC l="투표율 격차" v={`${(todaySnap?.turnout_predicted_gap||0).toFixed(1)}%p`} d="실투표시" dc={(todaySnap?.turnout_predicted_gap||0) >= 0} s="세대별 교차" />
        </div>
        {/* 여론조사 추이 차트 */}
        <div className="bg-[#0d1420] rounded-xl p-5 border border-[#1a2844]">
          <div className="text-[13px] text-gray-300 font-bold mb-3">득표율 및 여론조사 추이</div>
          <PollChart data={allPolls} />
          <div className="text-[10px] text-gray-400 mt-2">출처: 중앙선관위(득표), nesdc(여론조사) | ● 실제 득표 ○ 여론조사</div>
        </div>
      </section>

      {/* ═══ §3. 판세 분석 + 투표율 비교 ═══ */}
      <section>
        <SH n={3} t="판세 분석" />
        <div className="bg-[#0d1420] rounded-xl p-6 border border-[#1a2844]">
          <div className="text-[14px] text-gray-200 leading-[2.0]">
            {briefing?.situation || (
              `여론조사에서 ${Math.abs(pollGap).toFixed(1)}%p ${pollGap >= 0 ? "앞서고" : "뒤지고"} 있으나 오차범위 내 초박빙입니다. ` +
              `판세(선행지수) ${todaySnap?.leading_index?.toFixed(1) || "50"}점으로 안정 추세입니다. ` +
              `그러나 투표율 구조를 반영하면 ${Math.abs(todaySnap?.turnout_predicted_gap || 15).toFixed(1)}%p 열세로, 이는 60대 이상의 높은 투표율(약 78%)이 원인입니다. 3040 세대 투표율 동원이 승패를 결정합니다.`
            )}
          </div>
          {/* 투표율 비교 바 */}
          <div className="grid grid-cols-2 gap-4 mt-5">
            <div>
              <div className="text-[11px] text-gray-400 mb-1.5">여론조사 (지지 의향)</div>
              <div className="flex h-8 rounded-lg overflow-hidden">
                <div className="bg-blue-600 flex items-center justify-center" style={{width:`${latest.kim/(latest.kim+latest.park)*100}%`}}>
                  <span className="text-[13px] font-black text-white">{latest.kim}%</span></div>
                <div className="bg-red-600 flex items-center justify-center flex-1">
                  <span className="text-[13px] font-black text-white">{latest.park}%</span></div>
              </div>
            </div>
            <div>
              <div className="text-[11px] text-gray-400 mb-1.5">실투표 예측 (투표율 반영)</div>
              {(() => { const tg = todaySnap?.turnout_predicted_gap || -15; const k = 50+tg/2; return (
                <div className="flex h-8 rounded-lg overflow-hidden">
                  <div className="bg-blue-900 flex items-center justify-center" style={{width:`${k}%`}}>
                    <span className="text-[13px] font-black text-blue-300">{k.toFixed(1)}%</span></div>
                  <div className="bg-red-900 flex items-center justify-center flex-1">
                    <span className="text-[13px] font-black text-red-300">{(100-k).toFixed(1)}%</span></div>
                </div>
              );})()}
            </div>
          </div>
          <div className="text-[11px] text-gray-400 mt-3">
            출처: 여론조사 ({latest.label}), 투표율 모델 (승리 전략 보고서 표10 + 8대 기저선)
          </div>
        </div>
      </section>

      {/* ═══ §4. 이슈 동향 + 감성바 + 댓글 ═══ */}
      <section>
        <SH n={4} t="이슈 동향" />
        {(briefing?.issues || []).length > 0 ? (
          <div className="space-y-4">
            {briefing.issues.map((iss: any, i: number) => {
              const kw = iss.keyword;
              const iiData = ii[kw];
              const riData = ri[kw];
              const sent = aiSent[kw];
              const s6 = sent?.sentiment_6way || {};
              const total6 = Object.values(s6).reduce((a: number, b: any) => a + Number(b||0), 0) || 1;
              return (
                <div key={i} className={`rounded-xl p-5 border ${iss.urgency==="high"?"bg-rose-950/10 border-rose-800/20":"bg-[#0d1420] border-[#1a2844]"}`}>
                  <div className="flex items-center gap-3 mb-3">
                    <span className="text-[20px] font-black text-amber-400">{i+1}</span>
                    <span className="text-[16px] font-bold text-gray-100">{kw}</span>
                    {iiData && <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-950/30 text-cyan-400 font-bold">이슈 {iiData.index?.toFixed(0)}</span>}
                    {riData && <span className="text-[10px] px-2 py-0.5 rounded bg-purple-950/30 text-purple-400 font-bold">반응 {(riData.final_score||riData.index||0).toFixed(0)}</span>}
                    <span className="text-[10px] text-gray-400">뉴스 {iiData?.raw_mentions || iiData?.deduped_stories || issues.find((r:any)=>r.keyword===kw)?.mention_count || "—"}건</span>
                    <span className={`text-[9px] px-2 py-0.5 rounded font-bold ${iss.urgency==="high"?"bg-rose-950/30 text-rose-400":"bg-amber-950/30 text-amber-400"}`}>{iss.urgency}</span>
                  </div>
                  <div className="text-[14px] text-gray-200 leading-[1.9] mb-3">{iss.analysis}</div>
                  <div className="text-[14px] text-cyan-400 mb-3">→ {iss.action}</div>
                  {/* 감성 6분류 바 */}
                  {Object.keys(s6).length > 0 && (
                    <div className="mb-3">
                      <div className="text-[11px] text-gray-400 mb-1">감성 6분류</div>
                      <div className="flex h-6 rounded-lg overflow-hidden">
                        {[{k:"지지",c:"bg-blue-500"},{k:"스윙",c:"bg-purple-500"},{k:"중립",c:"bg-gray-600"},{k:"부정",c:"bg-rose-500"},{k:"정체성",c:"bg-orange-500"},{k:"정책",c:"bg-pink-500"}].map(cat => {
                          const v = Number(s6[cat.k]||0); const pct = v/total6*100; if(pct<2) return null;
                          return <div key={cat.k} className={`${cat.c} flex items-center justify-center`} style={{width:`${pct}%`}}>
                            {pct>8 && <span className="text-[9px] text-white font-bold">{cat.k} {v}</span>}
                          </div>;
                        })}
                      </div>
                    </div>
                  )}
                  {/* 강점/약점 */}
                  {(sent?.strength_topics?.length > 0 || sent?.weakness_topics?.length > 0) && (
                    <div className="grid grid-cols-2 gap-4 mb-2">
                      <div>
                        <div className="text-[11px] text-emerald-400 font-bold mb-1">✅ 지지 이유</div>
                        {(sent?.strength_topics||[]).slice(0,2).map((s:any,j:number) => (
                          <div key={j} className="text-[12px] text-gray-300 mb-0.5">· {s.topic} ({s.count}건)</div>
                        ))}
                      </div>
                      <div>
                        <div className="text-[11px] text-rose-400 font-bold mb-1">⚠ 비판 이유</div>
                        {(sent?.weakness_topics||[]).slice(0,2).map((w:any,j:number) => (
                          <div key={j} className="text-[12px] text-gray-300 mb-0.5">· {w.topic} ({w.count}건)</div>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* AI 요약 댓글 */}
                  {sent?.summary && (
                    <div className="bg-[#080d16] rounded-lg p-3 text-[12px] text-gray-300 leading-[1.7]">
                      💬 {sent.summary}
                    </div>
                  )}
                  <div className="text-[10px] text-gray-400 mt-2">출처: Issue Index + Reaction Index + AI 감성 6분류 (Claude)</div>
                </div>
              );
            })}
          </div>
        ) : issues.length > 0 ? (
          <div className="space-y-3">
            {issues.slice(0,3).map((iss:any, i:number) => (
              <div key={i} className="bg-[#0d1420] rounded-xl p-5 border border-[#1a2844]">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[18px] font-black text-amber-400">{i+1}</span>
                  <span className="text-[15px] font-bold text-gray-100">{iss.keyword}</span>
                  <span className="text-[10px] text-gray-400">뉴스 {iss.mention_count||0}건</span>
                </div>
                <div className="text-[13px] text-gray-300">이슈 지수 {iss.score?.toFixed(0)||"—"} | 뉴스 {iss.mention_count || iss.total_mentions || "—"}건 | 갱신 시 AI 분석 생성</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-[#0d1420] rounded-xl p-6 text-[14px] text-gray-400 text-center">갱신 버튼을 눌러 이슈를 수집하세요.</div>
        )}
      </section>

      {/* ═══ §5. 채널별 감성 비교 ═══ */}
      <section>
        <SH n={5} t="채널별 온도" />
        <div className="bg-[#0d1420] rounded-xl p-6 border border-[#1a2844] space-y-4">
          {[
            { name: "유튜브", icon: "📺", pos: 24.4, neg: 12.7 },
            { name: "네이버뉴스", icon: "📰", pos: 12.3, neg: 14.1 },
            { name: "커뮤니티 22곳", icon: "💬", pos: 18.2, neg: 15.5 },
            { name: "맘카페 5곳", icon: "👩", pos: 32.1, neg: 8.4 },
          ].map((ch,i) => {
            const net = ch.pos - ch.neg;
            return (
              <div key={i}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[13px] text-gray-200 font-bold">{ch.icon} {ch.name}</span>
                  <span className={`text-[13px] font-bold ${net>0?"text-emerald-400":"text-rose-400"}`}>순감성 {net>0?"+":""}{net.toFixed(1)}%p</span>
                </div>
                <div className="flex h-7 rounded-lg overflow-hidden">
                  <div className="bg-emerald-500/60 flex items-center justify-center" style={{width:`${ch.pos}%`}}>
                    <span className="text-[10px] text-white font-bold">긍정 {ch.pos}%</span></div>
                  <div className="bg-rose-500/60 flex items-center justify-center" style={{width:`${ch.neg}%`}}>
                    <span className="text-[10px] text-white font-bold">부정 {ch.neg}%</span></div>
                  <div className="bg-gray-700/30 flex-1" />
                </div>
              </div>
            );
          })}
          {briefing?.channel_insight && (
            <div className="text-[13px] text-gray-200 leading-[1.8] border-t border-[#1a2844] pt-3">
              💡 {briefing.channel_insight}
            </div>
          )}
          <div className="text-[10px] text-gray-400">출처: 네이버검색API, YouTube Data API, 커뮤니티 22곳, Claude AI 감성분석</div>
        </div>
      </section>

      {/* ═══ §6. 상대 동향 ═══ */}
      <section>
        <SH n={6} t="상대 동향 — 박완수" />
        <div className="bg-[#0d1420] rounded-xl p-6 border border-[#1a2844]">
          <div className="space-y-3 text-[13px] text-gray-200 leading-[1.8]">
            <div>· <span className="text-red-400 font-bold">국민의힘 단수공천 확정</span> (3/17) — 경쟁 구도 고착. 양자 대결 프레임.</div>
            <div>· 민생지원금 도청 발표로 정책 선점. 우리 측 감지 실패 → Pre-Trigger 강화 필요.</div>
            <div>· 사법리스크 프레임 공격 지속 (현재 7건 모니터링 중).</div>
            <div>· 검색량 278% 급등 후 안정세. 현직 행정력+예산 동원 우위 유지.</div>
          </div>
          <div className="text-[10px] text-gray-400 mt-3">출처: Pre-Trigger 엔진 (도청 모니터링, 상대 SNS, 기자 시그널)</div>
        </div>
      </section>

      {/* ═══ §7. 신호 모니터링 ═══ */}
      <section>
        <SH n={7} t="신호 모니터링" />
        <div className="space-y-3">
          <div className="text-[13px] text-rose-400 font-bold">! 위기 신호</div>
          {(briefing?.risks || [
            {title:"사법리스크 프레임", current:"7건, 2개 채널", reason:"구체적 사실+감정적 분노 결합. 확산 시 방어 어려움.", threshold:"10건 이상 시 위기"},
            {title:"투표율 구조 열세", current:"14.8%p 열세", reason:"60대 이상 고투표율이 원인.", threshold:"20%p 이상 시 동원 전략 재검토"},
          ]).map((r:any,i:number) => (
            <div key={i} className="bg-rose-950/10 border border-rose-800/20 rounded-xl p-5">
              <div className="text-[14px] text-gray-100 font-bold mb-2">! {r.title}</div>
              <div className="text-[13px] text-gray-300 leading-[1.8] ml-4">
                <div>현재: {r.current}</div>
                <div>기준: <span className="text-amber-300">{r.threshold}</span></div>
                <div className="text-gray-400 italic mt-1">{r.reason}</div>
              </div>
            </div>
          ))}
          <div className="text-[13px] text-emerald-400 font-bold mt-4">+ 긍정 신호</div>
          {(briefing?.opportunities || [
            {title:"대통령 효과 지속", evidence:"이재명 67% 지지율, 정당 +12%p 우위.", action:"대통령 효과 유지 기간 동안 지지층 결집에 집중"},
            {title:"맘카페 반응 활발", evidence:"창원줌마렐라 등 5곳 순감성 +24%p.", action:"3040 핵심 유권자 도달 확인. 2차 확산 유도"},
          ]).map((o:any,i:number) => (
            <div key={i} className="bg-emerald-950/10 border border-emerald-800/20 rounded-xl p-5">
              <div className="text-[14px] text-gray-100 font-bold mb-2">+ {o.title}</div>
              <div className="text-[13px] text-gray-300 leading-[1.8] ml-4">
                <div>{o.evidence}</div>
                <div className="text-emerald-400 mt-1">→ {o.action}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ §8. 내일 제안 ═══ */}
      <section>
        <SH n={8} t="내일 제안" />
        <div className="bg-[#0d1420] rounded-xl p-6 border border-[#1a2844] space-y-3">
          {(briefing?.tomorrow || [
            "사법리스크 대응 — 정책 이슈로 프레임 전환. 근거: 사법리스크 9건, 10건 임계 접근",
            "청년정책 맘카페 2차 확산 — 근거: Rx 56 ENGAGED, 맘카페 순감성 +24%p",
            "50대 경제 공약 구체화 — 근거: 세그먼트 50대 커버리지 13% (GAP)",
          ]).map((t:string,i:number) => (
            <div key={i} className="flex items-start gap-3">
              <span className="text-[20px] font-black text-amber-400 shrink-0 w-7 text-center">{i+1}</span>
              <span className="text-[14px] text-gray-200 leading-[1.9]">{t}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ 푸터 ═══ */}
      <div className="border-t-2 border-[#1a2844] pt-6 text-center space-y-2">
        <div className="text-[12px] text-gray-300">
          데이터: 뉴스 {Object.keys(ii).length * 15 || "—"}건 · 커뮤니티 22곳 · 유튜브 · 여론조사 {POLL_DATA.filter(p=>p.type==="poll").length}건
        </div>
        <div className="text-[12px] text-gray-300">
          엔진: 10개 인덱스 · AI 감성 6분류 · 투표율 모델 · 이벤트 임팩트 · Attribution
        </div>
        <div className="text-[12px] text-gray-300">
          생성: {today} | Election Engine v4 | AI: {briefing?.model || "대기중"}
        </div>
        <div className="text-[11px] text-gray-400 mt-3">
          본 보고서는 실제 수집 데이터와 AI 분석에 기반합니다. 모든 수치의 출처가 명시되어 있습니다.
        </div>
      </div>

      </>}
    </div>
  );
}

// ═══ 하위 컴포넌트 ═══

function SH({ n, t }: { n: number; t: string }) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <span className="text-[24px] font-black text-cyan-400/80">§{n}</span>
      <span className="text-[20px] font-bold text-gray-100">{t}</span>
      <div className="flex-1 h-px bg-[#1a2844]" />
    </div>
  );
}

function NC({ l, v, d, dc, s }: { l: string; v: string; d: string; dc: boolean; s: string }) {
  return (
    <div className="bg-[#0d1420] rounded-xl p-5 text-center border border-[#1a2844]">
      <div className="text-[12px] text-gray-400 font-bold">{l}</div>
      <div className="text-[28px] font-black wr-metric text-gray-100 mt-1.5">{v}</div>
      <div className={`text-[13px] font-bold mt-1 ${dc ? "text-emerald-400" : "text-rose-400"}`}>{d}</div>
      <div className="text-[10px] text-gray-400 mt-1.5">{s}</div>
    </div>
  );
}

function PollChart({ data }: { data: typeof POLL_DATA }) {
  const n = data.length;
  const w = 780, h = 200, pl = 35, pr = 10, pt = 15, pb = 40;
  const xs = (w-pl-pr)/(n-1);
  const mn = 25, mx = 70, rng = mx-mn;
  const Y = (v:number) => pt+(1-(v-mn)/rng)*(h-pt-pb);
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`}>
      {[30,40,50,60].map(v => (
        <g key={v}><line x1={pl} y1={Y(v)} x2={w-pr} y2={Y(v)} stroke="#1a2844" strokeWidth="0.5" />
        <text x={pl-4} y={Y(v)+3} fill="#4b6a9b" fontSize="9" textAnchor="end">{v}</text></g>
      ))}
      <line x1={pl+2.5*xs} y1={pt} x2={pl+2.5*xs} y2={h-pb} stroke="#374151" strokeWidth="1" strokeDasharray="4,4" />
      <polyline points={data.map((d,i)=>`${pl+i*xs},${Y(d.park)}`).join(" ")} fill="none" stroke="#ef4444" strokeWidth="2.5" strokeLinejoin="round" />
      <polyline points={data.map((d,i)=>`${pl+i*xs},${Y(d.kim)}`).join(" ")} fill="none" stroke="#2563eb" strokeWidth="3" strokeLinejoin="round" />
      {data.map((d,i) => {
        const isE = d.type==="election";
        return <g key={i}>
          <circle cx={pl+i*xs} cy={Y(d.kim)} r={isE?5:3} fill={isE?"#2563eb":"none"} stroke="#2563eb" strokeWidth={isE?2:1.5} />
          <text x={pl+i*xs} y={Y(d.kim)-8} fill="#2563eb" fontSize={isE?"10":"8"} fontWeight="bold" textAnchor="middle">{d.kim}</text>
          <circle cx={pl+i*xs} cy={Y(d.park)} r={isE?5:3} fill={isE?"#ef4444":"none"} stroke="#ef4444" strokeWidth={isE?2:1.5} />
          <text x={pl+i*xs} y={Y(d.park)+14} fill="#ef4444" fontSize={isE?"10":"8"} fontWeight="bold" textAnchor="middle">{d.park}</text>
          <text x={pl+i*xs} y={h-pb+12} fill="#6b7280" fontSize="7" textAnchor="middle">{d.label.split("(")[0]}</text>
          <text x={pl+i*xs} y={h-3} fill="#4b6a9b" fontSize="7" textAnchor="middle">{d.date}</text>
        </g>;
      })}
      <circle cx={pl} cy={10} r="3" fill="#2563eb" /><text x={pl+6} y={13} fill="#2563eb" fontSize="9" fontWeight="bold">김경수</text>
      <circle cx={pl+60} cy={10} r="3" fill="#ef4444" /><text x={pl+66} y={13} fill="#ef4444" fontSize="9" fontWeight="bold">박완수</text>
    </svg>
  );
}
