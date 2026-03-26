"use client";
import { useEffect, useState } from "react";
import { getExecutiveSummary, getPollingHistory, runStrategy, getV3StatusBar, getCalendar, getAutoPolls } from "@/lib/api";
import { useAppStore } from "@/lib/store";

export function CommandStrip() {
  const [exec, setExec] = useState<any>(null);
  const [polls, setPolls] = useState<any>(null);
  const [v3Status, setV3Status] = useState<any>(null);
  const [cal, setCal] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [refreshResult, setRefreshResult] = useState<string | null>(null);
  const [newPolls, setNewPolls] = useState<any[]>([]);
  const [pollAlert, setPollAlert] = useState(false);
  const setCandidate = useAppStore((s) => s.setCandidate);
  const setActivePage = useAppStore((s) => s.setActivePage);
  const dashboardMode = useAppStore((s) => s.dashboardMode);
  const setDashboardMode = useAppStore((s) => s.setDashboardMode);

  useEffect(() => {
    getExecutiveSummary().then((d) => { setExec(d); if (d.candidate) setCandidate(d.candidate); }).catch(() => {});
    getPollingHistory().then(setPolls).catch(() => {});
    getV3StatusBar().then(setV3Status).catch(() => {});
    getCalendar().then(setCal).catch(() => {});
    // 여론조사 자동 체크
    getAutoPolls().then(d => {
      const polls = d?.polls || [];
      if (polls.length > 0) { setNewPolls(polls); setPollAlert(true); }
    }).catch(() => {});
    const iv = setInterval(() => {
      getV3StatusBar().then(setV3Status).catch(() => {});
      // 5분마다 새 여론조사 체크
      getAutoPolls().then(d => {
        const polls = d?.polls || [];
        if (polls.length > 0 && polls.length !== newPolls.length) {
          setNewPolls(polls); setPollAlert(true);
        }
      }).catch(() => {});
    }, 300000); // 5분
    return () => clearInterval(iv);
  }, []);

  const onRun = () => {
    setRunning(true);
    setRefreshResult(null);
    const startTime = Date.now();
    runStrategy().then(() => {
      getExecutiveSummary().then(setExec).catch(() => {});
      getPollingHistory().then(setPolls).catch(() => {});
      getCalendar().then(setCal).catch(() => {});
      const elapsed = Math.round((Date.now() - startTime) / 1000);
      setRefreshResult(`✅ 갱신 완료 (${elapsed}초) — 모든 인덱스 업데이트됨`);
      setTimeout(() => setRefreshResult(null), 8000);
    }).catch(() => {
      setRefreshResult("❌ 갱신 실패 — 백엔드 연결 확인");
      setTimeout(() => setRefreshResult(null), 5000);
    }).finally(() => setRunning(false));
  };

  const support = exec?.favorability || 0;
  const gap = exec?.favorability_gap || 0;
  const wp = polls?.win_prob;
  const winProb = wp ? wp.win_prob * 100 : 0;
  const daysLeft = exec?.days_left;
  const riskLevel = exec?.rapid_response_level || "GREEN";
  const crisisCount = exec?.crisis_count || 0;
  const isLosing = gap < 0;
  const isCrisis = riskLevel === "RED";

  return (
    <div className="shrink-0">
      {/* Crisis Banner */}
      {isCrisis && (
        <div className="h-7 bg-red-950/60 border-b border-red-800/40 flex items-center justify-center gap-2 danger-strip">
          <span className="w-1.5 h-1.5 rounded-full bg-red-500 crisis-pulse" />
          <span className="text-[10px] font-bold text-red-400 tracking-widest uppercase">
            위기 상태 — {crisisCount}건 긴급 대응 필요
          </span>
          <span className="w-1.5 h-1.5 rounded-full bg-red-500 crisis-pulse" />
        </div>
      )}

      <header className={`h-[68px] bg-[#060a11] border-b flex items-center px-4 ${isCrisis ? "border-red-900/50" : "border-[#121e33]"}`}>
        {/* LEFT — Branding */}
        <div className="w-36 shrink-0">
          <div className="text-white font-black text-[13px] tracking-[0.08em]">ELECTION ENGINE</div>
          <div className="text-[8px] tracking-[0.2em] text-blue-500/40 uppercase mt-0.5">Campaign Command</div>
        </div>

        <div className="w-px h-8 bg-[#121e33] mx-3" />

        <div className="flex-1" />

        <div className="w-px h-8 bg-[#121e33] mx-3" />

        {/* RIGHT — V3 Badges + D-Day + Risk + Mode + Action */}
        <div className="flex items-center gap-2 shrink-0">
          {/* V3 Live Badges */}
          {v3Status && (
            <div className="flex items-center gap-1.5 mr-1">
              {v3Status.pending_proposals > 0 && (
                <button onClick={() => setActivePage("signals")}
                  className="flex items-center gap-1 bg-orange-950/40 border border-orange-700/40 text-orange-400 px-2 py-1 rounded text-[9px] font-bold hover:bg-orange-900/40 transition">
                  <span className="w-1.5 h-1.5 rounded-full bg-orange-500 crisis-pulse" />
                  {v3Status.pending_proposals} 대기
                </button>
              )}
              {v3Status.active_overrides > 0 && (
                <button onClick={() => setActivePage("signals")}
                  className="flex items-center gap-1 bg-red-950/40 border border-red-700/40 text-red-400 px-2 py-1 rounded text-[9px] font-bold hover:bg-red-900/40 transition">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                  {v3Status.active_overrides} Override
                </button>
              )}
              {v3Status.active_signals > 0 && (
                <span className="text-[9px] text-blue-400/60 font-mono">{v3Status.active_signals} sig</span>
              )}
            </div>
          )}

          <div className="w-px h-6 bg-[#121e33]" />

          {/* D-Day */}
          <div className="text-center px-1.5">
            <div className="text-[8px] text-gray-400 uppercase tracking-widest">D-Day</div>
            <div className="text-[24px] leading-none wr-metric text-blue-400 mt-0.5">
              {daysLeft || "??"}<span className="text-[11px] text-blue-400/50 ml-0.5">일</span>
            </div>
          </div>

          {/* Risk Level */}
          <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded border text-[10px] font-black ${
            isCrisis ? "bg-red-950/50 border-red-800/60 text-red-400 threat-glow"
            : riskLevel === "YELLOW" ? "bg-orange-950/40 border-orange-800/50 text-orange-400"
            : "bg-emerald-950/30 border-emerald-800/40 text-emerald-400"
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${isCrisis ? "bg-red-500 crisis-pulse" : riskLevel === "YELLOW" ? "bg-orange-500" : "bg-emerald-500"}`} />
            {isCrisis ? "CRISIS" : riskLevel === "YELLOW" ? "ALERT" : "NORMAL"}
          </div>

          {/* Dashboard Mode Toggle */}
          <div className="flex rounded border border-[#1a2844] overflow-hidden">
            {(["monitoring", "strategy", "command"] as const).map((m) => (
              <button key={m} onClick={() => setDashboardMode(m)}
                className={`px-2 py-1.5 text-[8px] font-bold uppercase tracking-wider transition ${
                  dashboardMode === m
                    ? "bg-blue-600/30 text-blue-400 border-blue-500"
                    : "text-gray-400 hover:text-gray-400 hover:bg-white/[0.02]"
                }`}>
                {m === "monitoring" ? "MON" : m === "strategy" ? "STR" : "CMD"}
              </button>
            ))}
          </div>

          <button onClick={onRun} disabled={running}
            className="bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white px-3 py-1.5 rounded text-[10px] font-bold transition disabled:opacity-30">
            {running ? "⟳" : "갱신"}
          </button>
        </div>
      </header>

      {/* 갱신 결과 배너 */}
      {refreshResult && (
        <div className={`h-7 flex items-center justify-center text-[11px] font-bold ${
          refreshResult.startsWith("✅") ? "bg-emerald-950/40 text-emerald-400 border-b border-emerald-800/30"
            : "bg-red-950/40 text-red-400 border-b border-red-800/30"
        }`}>
          {refreshResult}
        </div>
      )}

      {/* 새 여론조사 알림 */}
      {pollAlert && newPolls.length > 0 && (
        <div className="bg-blue-950/40 border-b border-blue-800/30 px-4 py-2 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-[12px] font-bold text-blue-400 animate-pulse">📊 새 여론조사 감지!</span>
            {newPolls.slice(0, 2).map((p: any, i: number) => (
              <span key={i} className="text-[11px] text-gray-200">
                {p.org || p.source}: <span className="text-blue-400 font-bold">{p.kim}%</span> vs <span className="text-red-400 font-bold">{p.park}%</span>
                <span className={`ml-1 font-bold ${p.gap >= 0 ? "text-emerald-400" : "text-rose-400"}`}>({p.gap >= 0 ? "+" : ""}{p.gap}%p)</span>
              </span>
            ))}
            <span className="text-[9px] text-gray-400">신뢰도 {((newPolls[0]?.confidence || 0) * 100).toFixed(0)}%</span>
          </div>
          <button onClick={() => setPollAlert(false)} className="text-[10px] text-gray-400 hover:text-white">✕</button>
        </div>
      )}

      {/* D-Day 타임라인 — 가로 */}
      <div className="h-8 bg-[#060a11] border-b border-[#121e33] flex items-center px-4 gap-2 overflow-x-auto">
        <span className="text-[10px] text-gray-300 font-bold uppercase tracking-wider shrink-0 mr-1">Timeline</span>
        {(() => {
          const events = (cal?.events || []).filter((e: any) => !e.done).slice(0, 8);
          if (events.length === 0) return <span className="text-[11px] text-gray-400">일정 없음</span>;
          return events.map((ev: any, i: number) => (
            <div key={i} className="flex items-center gap-1.5 shrink-0">
              {i > 0 && <span className="text-[10px] text-gray-400">→</span>}
              <span className={`text-[11px] font-mono font-bold ${ev.type === "election" ? "text-red-400" : "text-gray-400"}`}>
                {ev.date?.slice(5)}
              </span>
              <span className={`text-[11px] ${ev.type === "election" ? "text-red-400 font-bold" : "text-gray-300"} truncate max-w-[140px]`}>
                {ev.event}
              </span>
            </div>
          ));
        })()}
        {daysLeft && (
          <div className="ml-auto flex items-center gap-1 shrink-0">
            <span className="text-[11px] text-gray-300 font-bold">D-</span>
            <span className="text-[16px] font-black wr-metric text-blue-400">{daysLeft}</span>
          </div>
        )}
      </div>
    </div>
  );
}
