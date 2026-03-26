"use client";
import { useEffect, useState, useCallback } from "react";
import {
  getV3Proposals, approveV3Proposal, rejectV3Proposal, editV3Proposal,
} from "@/lib/api";

export function QueuePage() {
  const [proposals, setProposals] = useState<any[]>([]);
  const [filter, setFilter] = useState<string>("pending");
  const [loading, setLoading] = useState<string | null>(null);

  const refresh = useCallback(() => {
    getV3Proposals(filter === "all" ? undefined : filter).then(setProposals).catch(() => {});
  }, [filter]);

  useEffect(() => { refresh(); }, [refresh]);

  const urgencyIcons: Record<string, string> = {
    immediate: "🔴", today: "🟠", "48h": "🟡", monitoring: "🟢",
  };
  const statusColors: Record<string, string> = {
    pending: "text-orange-400 bg-orange-950/30 border-orange-700/30",
    approved: "text-emerald-400 bg-emerald-950/30 border-emerald-700/30",
    rejected: "text-red-400 bg-red-950/30 border-red-700/30",
    edited: "text-blue-400 bg-blue-950/30 border-blue-700/30",
    expired: "text-gray-500 bg-gray-950/30 border-gray-700/30",
  };

  const handleApprove = async (id: string) => {
    setLoading(id);
    await approveV3Proposal(id).catch(() => {});
    refresh(); setLoading(null);
  };
  const handleReject = async (id: string) => {
    const reason = prompt("거부 사유:");
    if (!reason) return;
    setLoading(id);
    await rejectV3Proposal(id, reason).catch(() => {});
    refresh(); setLoading(null);
  };
  const handleEdit = async (id: string) => {
    const humanVersion = prompt("수정 내용:");
    if (!humanVersion) return;
    const owner = prompt("담당자 (대변인/전략팀/후보/여론분석팀/일정팀):");
    setLoading(id);
    await editV3Proposal(id, humanVersion, owner || undefined).catch(() => {});
    refresh(); setLoading(null);
  };

  return (
    <div className="space-y-2">
      {/* Filter Tabs */}
      <div className="flex gap-1 text-[10px]">
        {(["pending", "approved", "rejected", "edited", "all"] as const).map((f) => (
          <button key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded border transition ${
              filter === f
                ? "bg-blue-600/20 border-blue-600/50 text-blue-400 font-bold"
                : "border-[#1a2844] text-gray-600 hover:text-gray-400"
            }`}>
            {f === "all" ? "전체" : f.toUpperCase()}
          </button>
        ))}
        <button onClick={refresh}
          className="ml-auto px-3 py-1.5 rounded border border-[#1a2844] text-gray-600 hover:text-gray-400 transition">
          ↻ 새로고침
        </button>
      </div>

      {/* Proposals List */}
      <div className="wr-card">
        <div className="wr-card-header flex items-center gap-2">
          📋 승인 큐
          <span className="ml-auto text-[9px] bg-blue-950/50 px-2 py-0.5 rounded font-mono">{proposals.length}건</span>
        </div>
        <div className="divide-y divide-[#0e1825]">
          {proposals.length > 0 ? proposals.map((p: any) => (
            <div key={p.id} className={`px-3 py-3 ${loading === p.id ? "opacity-40" : ""}`}>
              {/* Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[11px]">
                  <span>{urgencyIcons[p.urgency] || "⚪"}</span>
                  <span className="font-mono text-gray-500">{p.id}</span>
                  <span className={`text-[9px] px-1.5 py-0.5 rounded border ${statusColors[p.status] || ""}`}>
                    {p.status?.toUpperCase()}
                  </span>
                  {p.issue_id && <span className="text-blue-400 font-medium">#{p.issue_id}</span>}
                  {p.proposal_type && (
                    <span className="text-[9px] text-gray-600 bg-gray-900/50 px-1.5 rounded">{p.proposal_type}</span>
                  )}
                  {p.conflict_with_override ? (
                    <span className="text-[9px] bg-red-950/40 border border-red-700/30 text-red-400 px-1.5 rounded">OVERRIDE 충돌</span>
                  ) : null}
                </div>
                <span className="text-[9px] text-gray-600 font-mono">{p.created_at?.slice(5, 16)}</span>
              </div>

              {/* AI Recommendation */}
              <div className="text-[12px] text-gray-200 mt-2 font-medium">{p.ai_recommendation}</div>
              <div className="text-[10px] text-gray-500 mt-0.5">{p.ai_reasoning}</div>

              {/* Human Version (if edited) */}
              {p.human_version && (
                <div className="mt-2 bg-blue-950/20 border border-blue-800/20 rounded px-2 py-1.5">
                  <div className="text-[9px] text-blue-400/60 mb-0.5">수정본:</div>
                  <div className="text-[11px] text-blue-300">{p.human_version}</div>
                </div>
              )}

              {/* Rejection reason */}
              {p.rejection_reason && (
                <div className="mt-2 bg-red-950/20 border border-red-800/20 rounded px-2 py-1.5">
                  <div className="text-[9px] text-red-400/60 mb-0.5">거부 사유:</div>
                  <div className="text-[11px] text-red-300">{p.rejection_reason}</div>
                </div>
              )}

              {/* Footer */}
              <div className="flex items-center gap-2 mt-2">
                {p.status === "pending" && (
                  <>
                    <button onClick={() => handleApprove(p.id)}
                      className="text-[10px] bg-emerald-950/50 border border-emerald-700/40 text-emerald-400 px-3 py-1 rounded hover:bg-emerald-900/50 font-bold transition">
                      ✅ 승인
                    </button>
                    <button onClick={() => handleEdit(p.id)}
                      className="text-[10px] bg-blue-950/50 border border-blue-700/40 text-blue-400 px-3 py-1 rounded hover:bg-blue-900/50 font-bold transition">
                      ✏️ 수정
                    </button>
                    <button onClick={() => handleReject(p.id)}
                      className="text-[10px] bg-red-950/50 border border-red-700/40 text-red-400 px-3 py-1 rounded hover:bg-red-900/50 font-bold transition">
                      ❌ 거부
                    </button>
                  </>
                )}
                <span className="text-[9px] text-gray-700 ml-auto font-mono">
                  confidence {((p.ai_confidence || 0) * 100).toFixed(0)}% | {p.urgency}
                  {p.assigned_owner && ` | ${p.assigned_owner}`}
                </span>
              </div>
            </div>
          )) : (
            <div className="px-3 py-8 text-center text-gray-700 text-[11px]">
              {filter === "pending" ? "대기 중인 제안 없음" : "해당 조건의 제안 없음"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
