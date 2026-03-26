"use client";
import { useEffect, useState } from "react";
import { getV2Enrichment, getV2Forecast, getDailyBriefing } from "@/lib/api";

export function MobileStrategy() {
  const [v2Data, setV2Data] = useState<any>(null);
  const [forecast, setForecast] = useState<any>(null);
  const [briefing, setBriefing] = useState<any>(null);

  useEffect(() => {
    getV2Enrichment().then(setV2Data).catch(() => {});
    getV2Forecast().then(setForecast).catch(() => {});
    getDailyBriefing().then(setBriefing).catch(() => {});
  }, []);

  const mode = v2Data?.mode_decision;
  const li = forecast?.leading_index;
  const fc = forecast?.forecast;
  const lag = forecast?.lag_analysis;
  const learning = forecast?.learning;

  const modeColors: Record<string, string> = {
    CRISIS: "bg-red-950/40 border-red-800/50 text-red-400",
    ATTACK: "bg-orange-950/40 border-orange-800/50 text-orange-400",
    DEFENSE: "bg-emerald-950/40 border-emerald-800/50 text-emerald-400",
    INITIATIVE: "bg-blue-950/40 border-blue-800/50 text-blue-400",
  };
  const pressureLabels: Record<string, string> = { crisis: "위기", polling_gap: "여론격차", momentum: "모멘텀", opportunity: "기회" };
  const pressureColors: Record<string, string> = { crisis: "#ef4444", polling_gap: "#f59e0b", momentum: "#3b82f6", opportunity: "#22c55e" };

  return (
    <div className="p-4 space-y-4">
      {/* Mode decision */}
      {mode && (
        <div className={`rounded-xl p-4 border ${modeColors[mode.mode] || modeColors.INITIATIVE}`}>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-widest">전략 모드</div>
              <div className="text-xl font-black mt-0.5">{mode.mode_korean}</div>
            </div>
            <div className="text-right">
              <span className="text-[10px] text-gray-500">신뢰도</span>
              <div className="text-sm font-bold">{mode.confidence}</div>
            </div>
          </div>
          {mode.reasoning && <div className="text-xs text-gray-400 mt-2">{mode.reasoning}</div>}

          {/* Pressure bars */}
          <div className="mt-3 space-y-1.5">
            {Object.entries(mode.pressures || {}).map(([key, val]) => (
              <div key={key} className="flex items-center gap-2">
                <span className="w-14 text-[10px] text-right" style={{ color: pressureColors[key] || "#888" }}>
                  {pressureLabels[key] || key}
                </span>
                <div className="flex-1 h-2 bg-black/30 rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{
                    width: `${Math.min(Math.abs(val as number), 100)}%`,
                    background: pressureColors[key] || "#3b82f6"
                  }} />
                </div>
                <span className="w-8 text-right text-[10px] font-mono text-gray-400">{(val as number).toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Leading Index + Forecast side by side */}
      <div className="grid grid-cols-2 gap-3">
        {li && (
          <div className="bg-[#0a1019] rounded-xl p-3 border border-[#1a2844]">
            <div className="text-[9px] text-gray-500 uppercase tracking-widest">선행지수</div>
            <div className={`text-2xl font-black mt-1 ${
              li.index >= 55 ? "text-emerald-400" : li.index <= 45 ? "text-red-400" : "text-yellow-400"
            }`}>{li.index?.toFixed(0)}</div>
            <div className={`text-[10px] ${
              li.direction === "gaining" ? "text-emerald-400" : li.direction === "losing" ? "text-red-400" : "text-gray-500"
            }`}>
              {li.direction === "gaining" ? "▲ 상승" : li.direction === "losing" ? "▼ 하락" : "● 보합"}
            </div>
          </div>
        )}
        {lag && (
          <div className="bg-[#0a1019] rounded-xl p-3 border border-[#1a2844]">
            <div className="text-[9px] text-gray-500 uppercase tracking-widest">래그 상관</div>
            <div className="text-2xl font-black mt-1 text-blue-400">{lag.best_lag}일</div>
            <div className="text-[10px] text-gray-400">r = {lag.best_correlation?.toFixed(2)}</div>
            <div className={`text-[9px] mt-0.5 px-1.5 rounded inline-block ${
              lag.confidence === "high" ? "bg-emerald-950/40 text-emerald-400" :
              lag.confidence === "medium" ? "bg-yellow-950/40 text-yellow-400" :
              "bg-gray-800/40 text-gray-500"
            }`}>{lag.confidence}</div>
          </div>
        )}
      </div>

      {/* Learning feedback */}
      {learning && learning.total_evaluated > 0 && (
        <div className="bg-[#0a1019] rounded-xl p-4 border border-[#1a2844]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-gray-500 uppercase tracking-widest">학습 피드백</span>
            <span className={`text-sm font-black ${
              learning.overall_accuracy >= 0.7 ? "text-emerald-400" :
              learning.overall_accuracy >= 0.4 ? "text-yellow-400" : "text-red-400"
            }`}>{Math.round(learning.overall_accuracy * 100)}%</span>
          </div>

          {Object.entries(learning.stance_accuracy || {}).map(([stance, data]: [string, any]) => (
            <div key={stance} className="flex items-center gap-2 py-0.5">
              <span className="w-12 text-[10px] text-gray-500">{stance}</span>
              <div className="flex-1 h-1.5 bg-black/30 rounded-full overflow-hidden">
                <div className="h-full rounded-full" style={{
                  width: `${Math.round(data.accuracy * 100)}%`,
                  background: data.modifier === "boost" ? "#22c55e" : data.modifier === "reduce" ? "#ef4444" : "#6b7280"
                }} />
              </div>
              <span className="w-8 text-right text-[10px] font-mono text-gray-400">{Math.round(data.accuracy * 100)}%</span>
            </div>
          ))}

          {(learning.insights || []).slice(0, 2).map((insight: string, i: number) => (
            <div key={i} className="text-[10px] text-gray-500 mt-1.5">💡 {insight}</div>
          ))}
        </div>
      )}

      {/* Daily briefing */}
      {briefing?.report && (
        <details className="bg-[#0a1019] rounded-xl border border-[#1a2844]">
          <summary className="p-3 text-xs text-amber-400 font-bold cursor-pointer">📋 오늘의 브리핑</summary>
          <div className="px-3 pb-3 text-xs text-gray-300 whitespace-pre-line leading-relaxed">
            {briefing.report}
          </div>
        </details>
      )}
    </div>
  );
}
