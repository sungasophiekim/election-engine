"use client";
import { useEffect, useState, useCallback } from "react";
import {
  getV3StatusBar, getV3CommandBox, getV3Signals, getV3Proposals,
  getV3Overrides, approveV3Proposal, rejectV3Proposal, editV3Proposal,
} from "@/lib/api";

// ════════════════════════════════════════════════════════════════
// Campaign Status Bar (상단 바)
// ════════════════════════════════════════════════════════════════

export function CampaignStatusBar({
  mode = "NORMAL",
  winProb = 50,
  gap = 0,
  crisisLevel = "NORMAL",
  dday = 0,
}: {
  mode?: string;
  winProb?: number;
  gap?: number;
  crisisLevel?: string;
  dday?: number;
}) {
  const [v3, setV3] = useState<any>(null);
  useEffect(() => { getV3StatusBar().then(setV3).catch(() => {}); }, []);

  const modeColors: Record<string, string> = {
    CRISIS: "bg-red-600 text-white",
    ATTACK: "bg-orange-600 text-white",
    DEFENSE: "bg-yellow-600 text-black",
    INITIATIVE: "bg-emerald-600 text-white",
    NORMAL: "bg-blue-600 text-white",
  };

  const crisisColors: Record<string, string> = {
    CRISIS: "text-red-400",
    ALERT: "text-orange-400",
    WATCH: "text-yellow-400",
    NORMAL: "text-emerald-400",
  };

  const now = new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="flex items-center justify-between bg-[#060a12] border border-[#1a2844] rounded px-4 py-2 mb-1.5">
      <div className="flex items-center gap-4">
        <span className={`px-3 py-1 rounded font-bold text-xs ${modeColors[mode] || modeColors.NORMAL}`}>
          {mode}
        </span>
        <div className="text-center">
          <div className="text-[9px] text-gray-600 uppercase">Win%</div>
          <div className={`text-sm font-mono font-bold ${winProb >= 50 ? "text-emerald-400" : "text-red-400"}`}>
            {winProb.toFixed(1)}%
          </div>
        </div>
        <div className="text-center">
          <div className="text-[9px] text-gray-600 uppercase">Gap</div>
          <div className={`text-sm font-mono font-bold ${gap >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {gap >= 0 ? "+" : ""}{gap.toFixed(1)}%p
          </div>
        </div>
        <div className="text-center">
          <div className="text-[9px] text-gray-600 uppercase">Crisis</div>
          <div className={`text-sm font-bold ${crisisColors[crisisLevel] || "text-gray-400"}`}>
            {crisisLevel}
          </div>
        </div>
        <div className="text-center">
          <div className="text-[9px] text-gray-600 uppercase">D-Day</div>
          <div className="text-sm font-mono font-bold text-blue-400">D-{dday}</div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {v3 && (
          <div className="flex items-center gap-3 text-[10px]">
            {v3.pending_proposals > 0 && (
              <span className="bg-orange-950/40 border border-orange-700/40 text-orange-400 px-2 py-0.5 rounded">
                📋 대기 {v3.pending_proposals}
              </span>
            )}
            {v3.active_overrides > 0 && (
              <span className="bg-red-950/40 border border-red-700/40 text-red-400 px-2 py-0.5 rounded">
                ⚡ Override {v3.active_overrides}
              </span>
            )}
            {v3.active_signals > 0 && (
              <span className="bg-blue-950/40 border border-blue-700/40 text-blue-400 px-2 py-0.5 rounded">
                📡 시그널 {v3.active_signals}
              </span>
            )}
          </div>
        )}
        <span className="text-gray-600 text-xs font-mono">{now}</span>
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
// Internal Signal Feed (내부 시그널 패널)
// ════════════════════════════════════════════════════════════════

export function InternalSignalFeed() {
  const [signals, setSignals] = useState<any[]>([]);
  useEffect(() => { getV3Signals().then(setSignals).catch(() => {}); }, []);

  const typeIcons: Record<string, string> = {
    field_report: "📡",
    order: "⚡",
    hypothesis: "🔬",
    block: "🚫",
    narrative: "📖",
    override: "⚠️",
  };

  const confColors: Record<string, string> = {
    high: "text-emerald-400",
    medium: "text-yellow-400",
    low: "text-gray-500",
  };

  return (
    <div className="wr-card border-t-2 border-t-purple-600">
      <div className="wr-card-header flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-purple-500 live-dot" />
        내부 시그널
        {signals.length > 0 && <span className="text-[9px] text-purple-400 ml-auto">{signals.length}건</span>}
      </div>
      <div className="h-[180px] overflow-y-auto feed-scroll">
        {signals.length > 0 ? signals.slice(0, 15).map((s: any, i: number) => (
          <div key={i} className="flex items-start gap-2 px-2.5 py-1.5 border-b border-[#0e1825] hover:bg-[#0d1420] text-[10px]">
            <span className="shrink-0">{typeIcons[s.signal_type] || "📌"}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-gray-400 font-medium">{s.signal_type}</span>
                {s.issue_id && <span className="text-blue-400">#{s.issue_id}</span>}
                {s.region && <span className="text-orange-400/70">{s.region}</span>}
              </div>
              <div className="text-gray-500 truncate mt-0.5">{s.content}</div>
            </div>
            <div className="shrink-0 text-right">
              <div className={`text-[8px] ${confColors[s.confidence] || "text-gray-600"}`}>{s.confidence}</div>
              <div className="text-[8px] text-gray-700 font-mono">
                {s.timestamp?.slice(5, 16)}
              </div>
            </div>
          </div>
        )) : (
          <div className="flex items-center justify-center h-full text-gray-800 text-[10px]">
            텔레그램에서 /report, /order 등으로 시그널 입력
          </div>
        )}
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
// Strategic Override Board (Override 패널)
// ════════════════════════════════════════════════════════════════

export function OverrideBoard() {
  const [overrides, setOverrides] = useState<any[]>([]);
  useEffect(() => { getV3Overrides().then(setOverrides).catch(() => {}); }, []);

  if (overrides.length === 0) return null;

  return (
    <div className="wr-card border-l-2 border-l-red-500">
      <div className="wr-card-header text-red-400 flex items-center gap-1.5">
        ⚡ ACTIVE OVERRIDES
        <span className="text-[9px] ml-auto bg-red-950/50 px-1.5 rounded">{overrides.length}</span>
      </div>
      <div className="divide-y divide-[#0e1825]">
        {overrides.map((ov: any, i: number) => {
          const meta = ov.metadata || {};
          return (
            <div key={i} className="px-2.5 py-2 text-[10px]">
              <div className="flex items-center justify-between">
                <span className="text-gray-300 font-medium">{ov.issue_id || "전체"}</span>
                <span className="text-[8px] text-gray-600 font-mono">
                  ~{ov.expiry ? new Date(ov.expiry).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }) : "무기한"}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-orange-400">AI: {meta.ai_stance || "?"}</span>
                <span className="text-gray-600">→</span>
                <span className="text-emerald-400 font-bold">실장: {meta.my_stance || "?"}</span>
              </div>
              {meta.reason && <div className="text-gray-600 mt-0.5">사유: {meta.reason}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
// Execution Queue (대기 중 제안)
// ════════════════════════════════════════════════════════════════

export function ExecutionQueue() {
  const [proposals, setProposals] = useState<any[]>([]);
  const [loading, setLoading] = useState<string | null>(null);

  const refresh = useCallback(() => {
    getV3Proposals("pending").then(setProposals).catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const urgencyIcons: Record<string, string> = {
    immediate: "🔴",
    today: "🟠",
    "48h": "🟡",
    monitoring: "🟢",
  };

  const handleApprove = async (id: string) => {
    setLoading(id);
    await approveV3Proposal(id).catch(() => {});
    refresh();
    setLoading(null);
  };

  const handleReject = async (id: string) => {
    const reason = prompt("거부 사유:");
    if (!reason) return;
    setLoading(id);
    await rejectV3Proposal(id, reason).catch(() => {});
    refresh();
    setLoading(null);
  };

  return (
    <div className="wr-card border-t-2 border-t-orange-600">
      <div className="wr-card-header flex items-center gap-1.5">
        📋 EXECUTION QUEUE
        {proposals.length > 0 && (
          <span className="text-[9px] text-orange-400 ml-auto bg-orange-950/50 px-1.5 rounded">
            {proposals.length} 대기
          </span>
        )}
      </div>
      <div className="h-[180px] overflow-y-auto feed-scroll">
        {proposals.length > 0 ? proposals.map((p: any, i: number) => (
          <div key={i} className={`px-2.5 py-2 border-b border-[#0e1825] ${loading === p.id ? "opacity-50" : ""}`}>
            <div className="flex items-center justify-between text-[10px]">
              <div className="flex items-center gap-1.5">
                <span>{urgencyIcons[p.urgency] || "⚪"}</span>
                <span className="text-gray-400 font-mono">{p.id}</span>
                {p.issue_id && <span className="text-blue-400">#{p.issue_id}</span>}
              </div>
              {p.conflict_with_override && (
                <span className="text-[8px] text-red-400 bg-red-950/30 px-1 rounded">OVERRIDE 충돌</span>
              )}
            </div>
            <div className="text-[11px] text-gray-300 mt-1">{p.ai_recommendation}</div>
            <div className="text-[9px] text-gray-600 mt-0.5">{p.ai_reasoning}</div>
            <div className="flex items-center gap-1.5 mt-1.5">
              <button
                onClick={() => handleApprove(p.id)}
                className="text-[9px] bg-emerald-950/50 border border-emerald-700/40 text-emerald-400 px-2 py-0.5 rounded hover:bg-emerald-900/50"
              >
                ✅ 승인
              </button>
              <button
                onClick={() => handleReject(p.id)}
                className="text-[9px] bg-red-950/50 border border-red-700/40 text-red-400 px-2 py-0.5 rounded hover:bg-red-900/50"
              >
                ❌ 거부
              </button>
              <span className="text-[8px] text-gray-700 ml-auto">
                신뢰도: {(p.ai_confidence * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        )) : (
          <div className="flex items-center justify-center h-full text-gray-800 text-[10px]">
            대기 중 제안 없음
          </div>
        )}
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
// Command Box (오늘의 승인된 지시 Top 3)
// ════════════════════════════════════════════════════════════════

export function CommandBox() {
  const [commands, setCommands] = useState<any[]>([]);
  useEffect(() => { getV3CommandBox().then(setCommands).catch(() => {}); }, []);

  return (
    <div className={`wr-card ${commands.length > 0 ? "border-l-2 border-l-emerald-500" : ""}`}>
      <div className="wr-card-header text-emerald-400">
        🎯 TODAY&apos;S COMMANDS
      </div>
      <div className="p-2.5 space-y-1.5">
        {commands.length > 0 ? commands.slice(0, 3).map((cmd: any, i: number) => (
          <div key={i} className="flex items-start gap-2 text-[11px]">
            <span className="w-5 h-5 rounded-full bg-emerald-950/50 border border-emerald-700/40 flex items-center justify-center text-emerald-400 text-[10px] font-bold shrink-0">
              {i + 1}
            </span>
            <div className="flex-1">
              <div className="text-gray-300">{cmd.final_recommendation || cmd.ai_recommendation}</div>
              {cmd.assigned_owner && (
                <div className="text-[9px] text-gray-600 mt-0.5">담당: {cmd.assigned_owner}</div>
              )}
            </div>
          </div>
        )) : (
          <div className="text-[10px] text-gray-700 text-center py-2">
            승인된 지시 없음 — 텔레그램 /approve 로 승인
          </div>
        )}
      </div>
    </div>
  );
}
