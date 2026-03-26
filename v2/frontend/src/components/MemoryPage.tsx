"use client";
import { useEffect, useState, useCallback } from "react";
import { getV3Memory, getV3DecisionPatterns } from "@/lib/api";

export function MemoryPage() {
  const [memories, setMemories] = useState<any[]>([]);
  const [patterns, setPatterns] = useState<any>(null);
  const [tab, setTab] = useState<string>("candidate");

  const refresh = useCallback(() => {
    getV3Memory().then(setMemories).catch(() => {});
    getV3DecisionPatterns().then(setPatterns).catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const typeLabels: Record<string, string> = {
    candidate: "👤 후보 프로필",
    campaign: "📊 캠페인 전략",
    director: "🧠 실장 패턴",
    field: "🗺 현장 데이터",
    decision: "📋 의사결정 이력",
  };

  const filtered = memories.filter((m) => m.memory_type === tab);

  const renderValue = (val: string) => {
    try {
      const parsed = JSON.parse(val);
      if (Array.isArray(parsed)) {
        return (
          <div className="flex flex-wrap gap-1 mt-1">
            {parsed.map((item: any, i: number) => (
              <span key={i} className="text-[9px] bg-blue-950/30 border border-blue-800/30 text-blue-400/80 px-1.5 py-0.5 rounded">
                {typeof item === "object" ? JSON.stringify(item) : String(item)}
              </span>
            ))}
          </div>
        );
      }
      if (typeof parsed === "object") {
        return (
          <div className="mt-1 space-y-0.5">
            {Object.entries(parsed).map(([k, v]) => (
              <div key={k} className="text-[10px] flex gap-2">
                <span className="text-gray-500 shrink-0">{k}:</span>
                <span className="text-gray-300">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
              </div>
            ))}
          </div>
        );
      }
      return <div className="text-[11px] text-gray-300 mt-1">{String(parsed)}</div>;
    } catch {
      return <div className="text-[11px] text-gray-300 mt-1">{val}</div>;
    }
  };

  return (
    <div className="space-y-2">
      {/* Decision Patterns Summary */}
      {patterns && (
        <div className="wr-card border-l-2 border-l-purple-500">
          <div className="wr-card-header text-purple-400">🧠 의사결정 패턴 분석</div>
          <div className="px-3 py-2.5 grid grid-cols-4 gap-3 text-center">
            <div>
              <div className="text-[8px] text-gray-600 uppercase">총 결정</div>
              <div className="text-[20px] text-gray-200 wr-metric">{patterns.total_decisions || 0}</div>
            </div>
            <div>
              <div className="text-[8px] text-gray-600 uppercase">승인율</div>
              <div className="text-[20px] text-emerald-400 wr-metric">
                {patterns.approval_rate ? (patterns.approval_rate * 100).toFixed(0) : 0}%
              </div>
            </div>
            <div>
              <div className="text-[8px] text-gray-600 uppercase">수정율</div>
              <div className="text-[20px] text-blue-400 wr-metric">
                {patterns.edit_rate ? (patterns.edit_rate * 100).toFixed(0) : 0}%
              </div>
            </div>
            <div>
              <div className="text-[8px] text-gray-600 uppercase">거부율</div>
              <div className="text-[20px] text-red-400 wr-metric">
                {patterns.rejection_rate ? (patterns.rejection_rate * 100).toFixed(0) : 0}%
              </div>
            </div>
          </div>
          {patterns.common_rejection_reasons && patterns.common_rejection_reasons.length > 0 && (
            <div className="px-3 pb-2.5">
              <div className="text-[9px] text-gray-600 mb-1">주요 거부 사유:</div>
              <div className="flex flex-wrap gap-1">
                {patterns.common_rejection_reasons.map((r: string, i: number) => (
                  <span key={i} className="text-[9px] bg-red-950/30 border border-red-800/30 text-red-400/70 px-1.5 py-0.5 rounded">{r}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Memory Type Tabs */}
      <div className="flex gap-1 text-[10px]">
        {Object.entries(typeLabels).map(([key, label]) => {
          const count = memories.filter((m) => m.memory_type === key).length;
          return (
            <button key={key}
              onClick={() => setTab(key)}
              className={`px-3 py-1.5 rounded border transition ${
                tab === key
                  ? "bg-blue-600/20 border-blue-600/50 text-blue-400 font-bold"
                  : "border-[#1a2844] text-gray-600 hover:text-gray-400"
              }`}>
              {label} <span className="font-mono ml-1">{count}</span>
            </button>
          );
        })}
      </div>

      {/* Memory Items */}
      <div className="wr-card">
        <div className="wr-card-header">{typeLabels[tab] || tab} 메모리</div>
        <div className="divide-y divide-[#0e1825]">
          {filtered.length > 0 ? filtered.map((m: any, i: number) => (
            <div key={i} className="px-3 py-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="text-gray-200 font-medium font-mono">{m.memory_key}</span>
                  <span className="text-[9px] text-gray-600">{m.source}</span>
                </div>
                <div className="flex items-center gap-2 text-[9px]">
                  <span className="text-gray-600">신뢰도</span>
                  <span className={`font-mono ${
                    (m.confidence || 0) >= 0.7 ? "text-emerald-400" : (m.confidence || 0) >= 0.4 ? "text-yellow-400" : "text-red-400"
                  }`}>
                    {((m.confidence || 0) * 100).toFixed(0)}%
                  </span>
                  <span className="text-gray-700">{m.updated_at?.slice(5, 16)}</span>
                </div>
              </div>
              {renderValue(m.value_json || "{}")}
            </div>
          )) : (
            <div className="px-3 py-8 text-center text-gray-700 text-[11px]">
              {tab} 타입 메모리 없음
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
