"use client";
import { useEffect, useState } from "react";
import { getIssueResponses, getKeywordAnalysis, aiAnalyze } from "@/lib/api";

export function MobileIssues() {
  const [responses, setResponses] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [aiResult, setAiResult] = useState<any>(null);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    getIssueResponses().then((d) => setResponses(d?.responses || [])).catch(() => {});
  }, []);

  const selectIssue = (kw: string) => {
    if (selected === kw) { setSelected(null); setDetail(null); return; }
    setSelected(kw);
    setDetail(null);
    setAiResult(null);
    getKeywordAnalysis(kw).then(setDetail).catch(() => {});
  };

  const runAi = () => {
    if (!selected) return;
    setAiLoading(true);
    aiAnalyze(selected).then(setAiResult).catch(() => {}).finally(() => setAiLoading(false));
  };

  const sorted = [...responses].sort((a, b) => b.score - a.score);
  const stanceIcon: Record<string, string> = { push: "🟢", counter: "🔴", avoid: "⚫", monitor: "🟡", pivot: "🔵" };

  return (
    <div className="p-4 space-y-3">
      <div className="text-xs text-gray-500 uppercase tracking-widest">이슈 레이더 ({sorted.length})</div>

      {/* Issue list */}
      <div className="space-y-1.5">
        {sorted.map((r, i) => {
          const isActive = selected === r.keyword;
          const isCrisis = r.level === "CRISIS";
          const isAlert = r.level === "ALERT";

          return (
            <div key={i}>
              <button
                onClick={() => selectIssue(r.keyword)}
                className={`w-full text-left rounded-xl p-3 border transition-all active:scale-[0.98] ${
                  isActive ? "bg-blue-950/30 border-blue-500/50" :
                  isCrisis ? "bg-red-950/15 border-red-800/30" :
                  "bg-[#0a1019] border-[#1a2844]"
                }`}
              >
                <div className="flex items-center gap-2">
                  {/* Rank */}
                  <span className={`text-xs font-mono w-5 text-center ${i < 3 ? "text-orange-400 font-bold" : "text-gray-600"}`}>
                    {i + 1}
                  </span>

                  {/* Status dot */}
                  <span className={`w-2 h-2 rounded-full shrink-0 ${
                    isCrisis ? "bg-red-500" : isAlert ? "bg-orange-500" : r.score >= 50 ? "bg-yellow-500" : "bg-emerald-500"
                  }`} />

                  {/* Keyword */}
                  <span className="flex-1 text-sm font-bold text-gray-200 truncate">{r.keyword}</span>

                  {/* Badges */}
                  {r.anomaly?.is_anomaly && <span className="text-purple-400 text-xs">⚡</span>}
                  {r.readiness?.grade && (
                    <span className={`text-[9px] font-bold px-1.5 rounded ${
                      r.readiness.grade === "A" ? "bg-emerald-950/40 text-emerald-400" :
                      r.readiness.grade === "D" ? "bg-red-950/40 text-red-400" :
                      "bg-gray-800/40 text-gray-500"
                    }`}>{r.readiness.grade}</span>
                  )}

                  {/* Score */}
                  <span className={`text-sm font-mono font-bold ${
                    isCrisis ? "text-red-400" : isAlert ? "text-orange-400" : "text-gray-400"
                  }`}>{r.score.toFixed(0)}</span>
                </div>

                {/* Sub info */}
                <div className="flex items-center gap-2 mt-1.5 ml-7">
                  <span className="text-[10px]">{stanceIcon[r.stance] || "⚪"} {r.stance}</span>
                  <span className="text-[10px] text-gray-600">• {r.lifecycle || "—"}</span>
                  <span className="text-[10px] text-gray-600">• {r.urgency || "—"}</span>
                </div>
              </button>

              {/* Expanded detail */}
              {isActive && (
                <div className="bg-[#060a12] rounded-xl p-4 border border-[#1a2844] mt-1 space-y-3">
                  {/* Response message */}
                  {r.response_message && (
                    <div className="bg-[#0a1019] rounded-lg p-3 border-l-2 border-blue-500">
                      <div className="text-[10px] text-blue-400 font-bold mb-1">대응 메시지</div>
                      <div className="text-xs text-gray-200">{r.response_message}</div>
                    </div>
                  )}

                  {/* Talking points */}
                  {r.talking_points?.length > 0 && (
                    <div>
                      <div className="text-[10px] text-gray-500 mb-1">토킹포인트</div>
                      {r.talking_points.map((t: string, ti: number) => (
                        <div key={ti} className="text-xs text-gray-300 py-0.5">• {t}</div>
                      ))}
                    </div>
                  )}

                  {/* Don't say */}
                  {r.do_not_say?.length > 0 && (
                    <div className="text-[10px] text-red-400/70">
                      🚫 금지: {r.do_not_say.slice(0, 2).join(" / ")}
                    </div>
                  )}

                  {/* Readiness bars */}
                  {r.readiness && (
                    <div className="space-y-1">
                      <div className="text-[10px] text-gray-500">대응 준비도 {r.readiness.grade}</div>
                      {[
                        { label: "팩트", val: r.readiness.fact, color: "#22c55e" },
                        { label: "메시지", val: r.readiness.message, color: "#f59e0b" },
                        { label: "법률", val: r.readiness.legal, color: "#3b82f6" },
                      ].map((d) => (
                        <div key={d.label} className="flex items-center gap-2">
                          <span className="w-10 text-[10px] text-gray-500 text-right">{d.label}</span>
                          <div className="flex-1 h-1.5 bg-[#0a1019] rounded-full overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${Math.round(d.val)}%`, background: d.color }} />
                          </div>
                          <span className="w-6 text-right text-[10px] font-mono" style={{ color: d.color }}>{Math.round(d.val)}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Sentiment from detail */}
                  {detail && (
                    <div className="flex items-center gap-3 text-xs">
                      <span className={`font-bold ${
                        detail.tone?.score > 0.2 ? "text-emerald-400" : detail.tone?.score < -0.2 ? "text-red-400" : "text-yellow-400"
                      }`}>감성: {detail.tone?.dominant} ({detail.tone?.score?.toFixed(2)})</span>
                      <span className="text-gray-500">분석: {detail.total_analyzed}건</span>
                    </div>
                  )}

                  {/* AI analysis button */}
                  <button
                    onClick={runAi}
                    disabled={aiLoading}
                    className="w-full py-2.5 rounded-lg bg-purple-950/30 border border-purple-800/30 text-purple-300 text-xs font-bold active:bg-purple-950/50 disabled:opacity-30"
                  >
                    {aiLoading ? "분석 중..." : "🤖 AI 심층 분석"}
                  </button>

                  {/* AI result */}
                  {aiResult?.analysis && (
                    <div className="bg-purple-950/10 rounded-lg p-3 border border-purple-800/20 space-y-1.5">
                      <div className="text-xs text-gray-200">{aiResult.analysis.summary}</div>
                      {aiResult.analysis.risk && <div className="text-[10px] text-red-300">위험: {aiResult.analysis.risk}</div>}
                      {aiResult.analysis.opportunity && <div className="text-[10px] text-emerald-300">기회: {aiResult.analysis.opportunity}</div>}
                      {aiResult.analysis.recommended_action && (
                        <div className="text-[10px] text-blue-300 font-bold">→ {aiResult.analysis.recommended_action}</div>
                      )}
                    </div>
                  )}

                  {/* Copy response */}
                  <CopyButton text={`[대응] ${r.keyword}\n\n${r.response_message}\n\n${(r.talking_points || []).map((t: string) => `• ${t}`).join("\n")}`} />
                </div>
              )}
            </div>
          );
        })}
        {sorted.length === 0 && <div className="text-center text-gray-600 text-xs py-8">데이터 수집 중</div>}
      </div>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <button onClick={copy} className={`w-full py-2 rounded-lg text-xs font-bold transition ${
      copied ? "bg-emerald-950/30 border border-emerald-700/30 text-emerald-400" : "bg-[#0a1019] border border-[#1a2844] text-gray-400 active:bg-[#0d1420]"
    }`}>
      {copied ? "✅ 복사됨" : "📋 대응 메시지 복사"}
    </button>
  );
}
