"use client";
import { useEffect, useState } from "react";
import { getExecutiveSummary, runStrategy } from "@/lib/api";
import { useAppStore } from "@/lib/store";

export function Header() {
  const [exec, setExec] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const setCandidate = useAppStore((s) => s.setCandidate);

  useEffect(() => {
    getExecutiveSummary().then((d) => {
      setExec(d);
      if (d.candidate) setCandidate(d.candidate);
    }).catch(() => {});
  }, []);

  const onRunStrategy = () => {
    setRunning(true);
    runStrategy().then(() => {
      getExecutiveSummary().then(setExec).catch(() => {});
    }).catch(() => {}).finally(() => setRunning(false));
  };

  const wp = exec?.favorability || 0;

  return (
    <header className="bg-gradient-to-r from-[#0d1117] to-[#1a237e] px-6 py-3 flex justify-between items-center border-b-2 border-border">
      <div>
        <h1 className="text-white text-lg font-bold">Election Engine</h1>
        <p className="text-blue-300 text-xs">AI 선거 캠프 전략 플랫폼 {exec?.candidate ? `— ${exec.candidate}` : ""}</p>
      </div>
      <div className="flex items-center gap-4">
        <div className="text-center">
          <div className={`text-2xl font-bold ${wp >= 50 ? "text-green-400" : "text-red-400"}`}>
            {exec ? `${wp.toFixed(1)}%` : "--"}
          </div>
          <div className="text-[10px] text-gray-500">지지율</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-blue-400">D-{exec?.days_left || "??"}</div>
        </div>
        {exec?.rapid_response_level && exec.rapid_response_level !== "GREEN" && (
          <div className={`text-xs px-2 py-1 rounded font-bold ${exec.rapid_response_level === "RED" ? "bg-red-900 text-red-300" : "bg-orange-900 text-orange-300"}`}>
            {exec.rapid_response_level}
          </div>
        )}
        <button onClick={onRunStrategy} disabled={running}
          className="bg-accent-blue text-white px-4 py-2 rounded-md text-sm font-semibold hover:bg-blue-700 transition disabled:opacity-50">
          {running ? "갱신 중..." : "전략 갱신"}
        </button>
      </div>
    </header>
  );
}
