"use client";
import { useEffect, useState } from "react";
import {
  getV3Proposals, approveV3Proposal, rejectV3Proposal,
  getV3Signals, getAlerts,
} from "@/lib/api";

export function MobileActions() {
  const [proposals, setProposals] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => {
    refresh();
  }, []);

  const refresh = () => {
    getV3Proposals("pending").then(setProposals).catch(() => {});
    getV3Signals().then(setSignals).catch(() => {});
    getAlerts().then((d) => setAlerts(d?.alerts || [])).catch(() => {});
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
    <div className="p-4 space-y-4">
      {/* Pending proposals */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] text-gray-500 uppercase tracking-widest">승인 대기</span>
          {proposals.length > 0 && (
            <span className="bg-orange-950/40 text-orange-400 text-[10px] font-bold px-2 py-0.5 rounded-full">
              {proposals.length}
            </span>
          )}
        </div>

        {proposals.length === 0 && (
          <div className="text-center text-gray-600 text-xs py-6 bg-[#0a1019] rounded-xl border border-[#1a2844]">
            대기 중인 제안 없음
          </div>
        )}

        {proposals.map((p: any) => (
          <div key={p.id} className="bg-[#0a1019] rounded-xl p-4 border border-[#1a2844] mb-2">
            <div className="flex items-center justify-between mb-2">
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                p.urgency === "urgent" ? "bg-red-950/40 text-red-400" : "bg-blue-950/40 text-blue-400"
              }`}>{p.proposal_type || "전략"}</span>
              <span className="text-[9px] text-gray-600">{p.confidence ? `${p.confidence}%` : ""}</span>
            </div>
            <div className="text-sm text-gray-200 font-bold mb-1">{p.title || p.content?.substring(0, 50)}</div>
            <div className="text-xs text-gray-400 mb-3">{p.content || p.reasoning || ""}</div>

            <div className="flex gap-2">
              <button
                onClick={() => handleApprove(p.id)}
                disabled={loading === p.id}
                className="flex-1 py-2.5 rounded-lg bg-emerald-600 text-white text-xs font-bold active:bg-emerald-700 disabled:opacity-30"
              >
                {loading === p.id ? "..." : "✓ 승인"}
              </button>
              <button
                onClick={() => handleReject(p.id)}
                disabled={loading === p.id}
                className="flex-1 py-2.5 rounded-lg bg-[#1a2844] text-gray-300 text-xs font-bold active:bg-[#243352] disabled:opacity-30"
              >
                ✕ 거부
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Critical alerts */}
      {alerts.filter((a) => a.severity === "critical").length > 0 && (
        <div>
          <div className="text-[10px] text-red-400 uppercase tracking-widest mb-2">긴급 알림</div>
          {alerts.filter((a) => a.severity === "critical").map((a, i) => (
            <div key={i} className="bg-red-950/20 border border-red-800/30 rounded-xl p-3 mb-2">
              <div className="text-xs text-red-300 font-bold">{a.title}</div>
              <div className="text-[10px] text-gray-400 mt-0.5">{a.detail}</div>
              {a.action && <div className="text-[10px] text-blue-400 mt-1 font-bold">→ {a.action}</div>}
            </div>
          ))}
        </div>
      )}

      {/* Recent signals */}
      {signals.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-2">최근 시그널</div>
          {signals.slice(0, 5).map((s: any, i: number) => (
            <div key={i} className="bg-[#0a1019] rounded-xl p-3 border border-[#1a2844] mb-1.5">
              <div className="flex items-center gap-2">
                <span className={`text-[9px] px-1.5 rounded ${
                  s.signal_type === "order" ? "bg-red-950/40 text-red-400" :
                  s.signal_type === "field_report" ? "bg-blue-950/40 text-blue-400" :
                  "bg-gray-800/40 text-gray-400"
                }`}>{s.signal_type}</span>
                <span className="text-xs text-gray-300 flex-1 truncate">{s.content || s.issue || ""}</span>
              </div>
              {s.region && <div className="text-[10px] text-gray-500 mt-0.5">📍 {s.region}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
