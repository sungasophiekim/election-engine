"use client";
import { useEffect, useState, useCallback } from "react";
import {
  getV3Signals, getV3Overrides, getV3Narratives, getV3BlockedTerms,
  getV3Proposals, approveV3Proposal, rejectV3Proposal,
} from "@/lib/api";

export function SignalsPage() {
  const [signals, setSignals] = useState<any[]>([]);
  const [overrides, setOverrides] = useState<any[]>([]);
  const [narratives, setNarratives] = useState<any[]>([]);
  const [blocked, setBlocked] = useState<any[]>([]);
  const [proposals, setProposals] = useState<any[]>([]);
  const [loading, setLoading] = useState<string | null>(null);
  const [tab, setTab] = useState<"signals" | "overrides" | "narratives" | "blocked">("signals");

  const refresh = useCallback(() => {
    getV3Signals().then(setSignals).catch(() => {});
    getV3Overrides().then(setOverrides).catch(() => {});
    getV3Narratives().then(setNarratives).catch(() => {});
    getV3BlockedTerms().then(setBlocked).catch(() => {});
    getV3Proposals("pending").then(setProposals).catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const typeIcons: Record<string, string> = {
    field_report: "📡", order: "⚡", hypothesis: "🔬",
    block: "🚫", narrative: "📖", override: "⚠️",
  };
  const confColors: Record<string, string> = {
    high: "text-emerald-400", medium: "text-yellow-400", low: "text-gray-500",
  };
  const urgencyIcons: Record<string, string> = {
    immediate: "🔴", today: "🟠", "48h": "🟡", monitoring: "🟢",
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

  return (
    <div className="space-y-2">
      {/* ── Execution Queue ────────────────────────────── */}
      {proposals.length > 0 && (
        <div className="wr-card border-l-2 border-l-orange-500">
          <div className="wr-card-header text-orange-400 flex items-center gap-2">
            📋 EXECUTION QUEUE
            <span className="ml-auto text-[9px] bg-orange-950/50 px-2 py-0.5 rounded font-mono">{proposals.length} 대기</span>
          </div>
          <div className="divide-y divide-[#0e1825]">
            {proposals.map((p: any) => (
              <div key={p.id} className={`px-3 py-2.5 ${loading === p.id ? "opacity-40" : ""}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-[11px]">
                    <span>{urgencyIcons[p.urgency] || "⚪"}</span>
                    <span className="font-mono text-gray-500">{p.id}</span>
                    {p.issue_id && <span className="text-blue-400 font-medium">#{p.issue_id}</span>}
                    {p.conflict_with_override && (
                      <span className="text-[9px] bg-red-950/40 border border-red-700/30 text-red-400 px-1.5 rounded">OVERRIDE 충돌</span>
                    )}
                  </div>
                  <span className="text-[9px] text-gray-600 font-mono">{p.created_at?.slice(5, 16)}</span>
                </div>
                <div className="text-[12px] text-gray-200 mt-1.5 font-medium">{p.ai_recommendation}</div>
                <div className="text-[10px] text-gray-500 mt-0.5">{p.ai_reasoning}</div>
                <div className="flex items-center gap-2 mt-2">
                  <button onClick={() => handleApprove(p.id)}
                    className="text-[10px] bg-emerald-950/50 border border-emerald-700/40 text-emerald-400 px-3 py-1 rounded hover:bg-emerald-900/50 font-bold transition">
                    ✅ 승인
                  </button>
                  <button onClick={() => handleReject(p.id)}
                    className="text-[10px] bg-red-950/50 border border-red-700/40 text-red-400 px-3 py-1 rounded hover:bg-red-900/50 font-bold transition">
                    ❌ 거부
                  </button>
                  <span className="text-[9px] text-gray-700 ml-auto font-mono">
                    confidence {(p.ai_confidence * 100).toFixed(0)}% | {p.urgency}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Active Overrides ───────────────────────────── */}
      {overrides.length > 0 && (
        <div className="wr-card border-l-2 border-l-red-500">
          <div className="wr-card-header text-red-400 flex items-center gap-2">
            ⚡ ACTIVE OVERRIDES
            <span className="ml-auto text-[9px] bg-red-950/50 px-2 py-0.5 rounded">{overrides.length}</span>
          </div>
          <div className="divide-y divide-[#0e1825]">
            {overrides.map((ov: any, i: number) => {
              const meta = ov.metadata || {};
              return (
                <div key={i} className="px-3 py-2.5">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-gray-200 font-medium">{ov.issue_id || "전체"}</span>
                    <span className="text-[9px] text-gray-600 font-mono">
                      ~{ov.expiry ? new Date(ov.expiry).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }) : "무기한"}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-[11px]">
                    <span className="text-orange-400 bg-orange-950/30 px-2 py-0.5 rounded">AI: {meta.ai_stance || "?"}</span>
                    <span className="text-gray-600">→</span>
                    <span className="text-emerald-400 bg-emerald-950/30 px-2 py-0.5 rounded font-bold">실장: {meta.my_stance || "?"}</span>
                  </div>
                  {meta.reason && <div className="text-[10px] text-gray-600 mt-1">사유: {meta.reason}</div>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Tabs ──────────────────────────────────────── */}
      <div className="flex gap-1 text-[10px]">
        {([
          ["signals", "📡 시그널", signals.length],
          ["overrides", "⚡ Override", overrides.length],
          ["narratives", "📖 서사", narratives.length],
          ["blocked", "🚫 차단어", blocked.length],
        ] as const).map(([key, label, count]) => (
          <button key={key}
            onClick={() => setTab(key as any)}
            className={`px-3 py-1.5 rounded border transition ${
              tab === key
                ? "bg-blue-600/20 border-blue-600/50 text-blue-400 font-bold"
                : "border-[#1a2844] text-gray-600 hover:text-gray-400"
            }`}>
            {label} <span className="font-mono ml-1">{count}</span>
          </button>
        ))}
      </div>

      {/* ── Signal List ───────────────────────────────── */}
      {tab === "signals" && (
        <div className="wr-card">
          <div className="wr-card-header">📡 내부 시그널 전체</div>
          <div className="divide-y divide-[#0e1825]">
            {signals.length > 0 ? signals.map((s: any, i: number) => (
              <div key={i} className="px-3 py-2.5 hover:bg-[#0d1420]">
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="text-base">{typeIcons[s.signal_type] || "📌"}</span>
                  <span className="text-gray-400 font-medium">{s.signal_type}</span>
                  {s.issue_id && <span className="text-blue-400">#{s.issue_id}</span>}
                  {s.region && <span className="text-orange-400/70 bg-orange-950/20 px-1.5 rounded">{s.region}</span>}
                  <span className={`ml-auto text-[9px] ${confColors[s.confidence] || ""}`}>{s.confidence}</span>
                  <span className="text-[9px] text-gray-700 font-mono">{s.timestamp?.slice(5, 16)}</span>
                </div>
                <div className="text-[11px] text-gray-300 mt-1">{s.content}</div>
                {s.expiry && (
                  <div className="text-[9px] text-gray-600 mt-0.5">
                    만료: {new Date(s.expiry).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </div>
                )}
              </div>
            )) : (
              <div className="px-3 py-8 text-center text-gray-700 text-[11px]">
                텔레그램에서 /report, /order, /hypo, /block, /narrative, /override 로 시그널을 입력하세요
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Narratives ────────────────────────────────── */}
      {tab === "narratives" && (
        <div className="wr-card">
          <div className="wr-card-header">📖 활성 서사</div>
          <div className="divide-y divide-[#0e1825]">
            {narratives.length > 0 ? narratives.map((n: any, i: number) => (
              <div key={i} className="px-3 py-2.5">
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="w-6 h-6 rounded-full bg-blue-950/50 border border-blue-700/40 flex items-center justify-center text-blue-400 text-[10px] font-bold">
                    {n.priority}
                  </span>
                  <span className="text-gray-200 font-medium flex-1">{n.frame}</span>
                </div>
                {n.keywords_json && (
                  <div className="flex gap-1 mt-1.5 flex-wrap">
                    {JSON.parse(n.keywords_json || "[]").map((kw: string, j: number) => (
                      <span key={j} className="text-[9px] bg-blue-950/30 border border-blue-800/30 text-blue-400/70 px-1.5 py-0.5 rounded">{kw}</span>
                    ))}
                  </div>
                )}
              </div>
            )) : (
              <div className="px-3 py-8 text-center text-gray-700 text-[11px]">
                텔레그램 /narrative 로 서사를 설정하세요
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Blocked Terms ─────────────────────────────── */}
      {tab === "blocked" && (
        <div className="wr-card">
          <div className="wr-card-header">🚫 차단어</div>
          <div className="divide-y divide-[#0e1825]">
            {blocked.length > 0 ? blocked.map((b: any, i: number) => (
              <div key={i} className="flex items-center gap-3 px-3 py-2 text-[11px]">
                <span className="text-red-400 font-bold bg-red-950/30 px-2 py-0.5 rounded">{b.term}</span>
                <span className="text-gray-500 flex-1">{b.reason}</span>
                <span className="text-[9px] text-gray-700">scope: {b.scope}</span>
              </div>
            )) : (
              <div className="px-3 py-8 text-center text-gray-700 text-[11px]">
                텔레그램 /block 으로 차단어를 등록하세요
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Override tab shows same as top, but historical */}
      {tab === "overrides" && overrides.length === 0 && (
        <div className="wr-card">
          <div className="wr-card-header">⚡ Override</div>
          <div className="px-3 py-8 text-center text-gray-700 text-[11px]">
            활성 Override 없음 — 텔레그램 /override 로 AI 판단을 덮어쓸 수 있습니다
          </div>
        </div>
      )}
    </div>
  );
}
