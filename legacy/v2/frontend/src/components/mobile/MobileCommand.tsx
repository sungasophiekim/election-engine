"use client";
import { useEffect, useState } from "react";
import {
  getExecutiveSummary, getPollingHistory, getIssueResponses,
  getAlerts, runStrategy, getV2Forecast,
} from "@/lib/api";

export function MobileCommand() {
  const [exec, setExec] = useState<any>(null);
  const [polls, setPolls] = useState<any>(null);
  const [issues, setIssues] = useState<any>(null);
  const [alerts, setAlerts] = useState<any>(null);
  const [forecast, setForecast] = useState<any>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    refresh();
  }, []);

  const refresh = () => {
    getExecutiveSummary().then(setExec).catch(() => {});
    getPollingHistory().then(setPolls).catch(() => {});
    getIssueResponses().then(setIssues).catch(() => {});
    getAlerts().then(setAlerts).catch(() => {});
    getV2Forecast().then(setForecast).catch(() => {});
  };

  const onRun = () => {
    setRunning(true);
    runStrategy().then(() => refresh()).catch(() => {}).finally(() => setRunning(false));
  };

  const support = exec?.favorability || 0;
  const gap = exec?.favorability_gap || 0;
  const wp = polls?.win_prob;
  const winProb = wp ? wp.win_prob * 100 : 0;
  const daysLeft = exec?.days_left || 0;
  const riskLevel = exec?.rapid_response_level || "GREEN";
  const isCrisis = riskLevel === "RED";
  const resp = issues?.responses || [];
  const crisisIssues = resp.filter((r: any) => r.level === "CRISIS");
  const alertIssues = resp.filter((r: any) => r.level === "ALERT");
  const alertList = alerts?.alerts || [];
  const li = forecast?.leading_index;
  const fc = forecast?.forecast;

  return (
    <div className="p-4 space-y-4">
      {/* Crisis banner */}
      {isCrisis && (
        <div className="bg-red-950/40 border border-red-800/50 rounded-xl p-3 text-center">
          <div className="text-red-400 font-black text-sm">CRISIS — {crisisIssues.length}건 긴급</div>
          {crisisIssues.slice(0, 2).map((r: any, i: number) => (
            <div key={i} className="text-red-300/80 text-xs mt-1">{r.keyword} ({r.score.toFixed(0)})</div>
          ))}
        </div>
      )}

      {/* 3 KPIs */}
      <div className="grid grid-cols-3 gap-3">
        <KPICard
          label="지지율"
          value={`${support.toFixed(1)}%`}
          color={support >= 45 ? "emerald" : support >= 40 ? "orange" : "red"}
        />
        <KPICard
          label="격차"
          value={`${gap >= 0 ? "+" : ""}${gap.toFixed(1)}%p`}
          color={gap >= 0 ? "emerald" : "red"}
          sub={gap < 0 ? "열세" : gap > 0 ? "우세" : ""}
        />
        <KPICard
          label="D-Day"
          value={`${daysLeft}`}
          color="blue"
          sub="일"
        />
      </div>

      {/* Win probability + Leading Index */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-[#0a1019] rounded-xl p-4 border border-[#1a2844]">
          <div className="text-[10px] text-gray-500 uppercase tracking-widest">승률</div>
          <div className={`text-3xl font-black mt-1 ${winProb >= 50 ? "text-emerald-400" : "text-red-400"}`}>
            {winProb.toFixed(1)}%
          </div>
          {winProb < 50 && <div className="text-[10px] text-red-400/70 mt-0.5">역전 필요</div>}
        </div>
        <div className="bg-[#0a1019] rounded-xl p-4 border border-[#1a2844]">
          <div className="text-[10px] text-gray-500 uppercase tracking-widest">선행지수</div>
          {li ? (
            <>
              <div className={`text-3xl font-black mt-1 ${
                li.index >= 55 ? "text-emerald-400" : li.index <= 45 ? "text-red-400" : "text-yellow-400"
              }`}>{li.index?.toFixed(0)}</div>
              <div className={`text-[10px] mt-0.5 ${
                li.direction === "gaining" ? "text-emerald-400" : li.direction === "losing" ? "text-red-400" : "text-gray-500"
              }`}>
                {li.direction === "gaining" ? "▲ 상승" : li.direction === "losing" ? "▼ 하락" : "● 보합"}
              </div>
            </>
          ) : (
            <div className="text-2xl font-black mt-1 text-gray-600">--</div>
          )}
        </div>
      </div>

      {/* Forecast */}
      {fc && fc.predicted_gap_change !== undefined && (
        <div className="bg-[#0a1019] rounded-xl p-4 border border-[#1a2844]">
          <div className="flex items-center justify-between">
            <div className="text-[10px] text-gray-500 uppercase tracking-widest">예측 ({fc.horizon_days}일 후)</div>
            <span className={`text-[9px] px-2 py-0.5 rounded ${
              fc.confidence === "high" ? "bg-emerald-950/40 text-emerald-400" :
              fc.confidence === "medium" ? "bg-yellow-950/40 text-yellow-400" :
              "bg-gray-800/40 text-gray-500"
            }`}>{fc.confidence}</span>
          </div>
          <div className={`text-2xl font-black mt-1 ${
            fc.predicted_gap_change > 0 ? "text-emerald-400" : fc.predicted_gap_change < 0 ? "text-red-400" : "text-gray-400"
          }`}>
            격차 {fc.predicted_gap_change > 0 ? "+" : ""}{fc.predicted_gap_change?.toFixed(1)}%p
          </div>
          <div className="text-xs text-gray-500 mt-0.5">{fc.direction_korean}</div>

          {/* Scenarios */}
          <div className="flex gap-2 mt-3">
            {(fc.scenarios || []).map((s: any) => (
              <div key={s.label} className={`flex-1 rounded-lg p-2 text-center border ${
                s.label === "bear" ? "border-red-800/30 bg-red-950/10" :
                s.label === "bull" ? "border-emerald-800/30 bg-emerald-950/10" :
                "border-blue-800/30 bg-blue-950/10"
              }`}>
                <div className="text-[9px] text-gray-500 uppercase">{s.label}</div>
                <div className={`text-sm font-bold ${
                  s.gap_change > 0 ? "text-emerald-400" : s.gap_change < 0 ? "text-red-400" : "text-gray-400"
                }`}>{s.gap_change > 0 ? "+" : ""}{s.gap_change?.toFixed(1)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top alerts */}
      {alertList.length > 0 && (
        <div className="space-y-2">
          <div className="text-[10px] text-gray-500 uppercase tracking-widest px-1">긴급 알림</div>
          {alertList.slice(0, 3).map((a: any, i: number) => (
            <div key={i} className={`rounded-xl p-3 border ${
              a.severity === "critical" ? "bg-red-950/20 border-red-800/40" : "bg-orange-950/20 border-orange-800/30"
            }`}>
              <div className={`text-xs font-bold ${a.severity === "critical" ? "text-red-400" : "text-orange-400"}`}>
                {a.title}
              </div>
              <div className="text-[10px] text-gray-400 mt-0.5">{a.detail}</div>
              {a.action && <div className="text-[10px] text-blue-400 mt-1">→ {a.action}</div>}
            </div>
          ))}
        </div>
      )}

      {/* Run strategy button */}
      <button
        onClick={onRun}
        disabled={running}
        className="w-full py-3.5 rounded-xl bg-blue-600 text-white font-bold text-sm active:bg-blue-700 disabled:opacity-30 transition"
      >
        {running ? "분석 중..." : "전략 갱신"}
      </button>
    </div>
  );
}

function KPICard({ label, value, color, sub }: { label: string; value: string; color: string; sub?: string }) {
  const colorClass = color === "emerald" ? "text-emerald-400" :
                     color === "red" ? "text-red-400" :
                     color === "orange" ? "text-orange-400" : "text-blue-400";
  return (
    <div className="bg-[#0a1019] rounded-xl p-3 border border-[#1a2844] text-center">
      <div className="text-[9px] text-gray-500 uppercase tracking-widest">{label}</div>
      <div className={`text-xl font-black mt-1 ${colorClass}`}>{value}</div>
      {sub && <div className={`text-[9px] ${colorClass} opacity-70 mt-0.5`}>{sub}</div>}
    </div>
  );
}
