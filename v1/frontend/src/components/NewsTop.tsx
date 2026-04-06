"use client";
import { useStore } from "@/lib/store";
import { fmtTs } from "@/lib/format";

export default function NewsTop() {
  const clusters = useStore((s) => s.newsClusters);
  const indices = useStore((s) => s.indices);
  const clusterTs = (indices as any)?.cluster_updated_at || "";

  const sideBadge = (s: string) =>
    s.includes("우리") ? "bg-blue-500/20 text-blue-400 border-blue-500/40" :
    s.includes("상대") ? "bg-rose-500/20 text-rose-400 border-rose-500/40" :
    "bg-gray-700/30 text-gray-400 border-gray-600/40";

  const sideClass = (s: string) =>
    s.includes("우리") ? "side-우리" : s.includes("상대") ? "side-상대" : "side-중립";

  const items = clusters.slice(0, 10);
  const doubled = [...items, ...items];

  return (
    <div className="wr-card anim-in" style={{ animationDelay: "0.4s" }}>
      <div className="wr-card-header flex justify-between">
        <div className="flex items-center gap-2">
          <span>오늘의 이슈 TOP</span>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 live-dot" />
        </div>
        <span className="timestamp normal-case tracking-normal font-normal">{fmtTs(clusterTs)}</span>
      </div>

      <div className="px-3 py-1.5 border-b border-[#0e1825] flex items-center gap-2">
        <span className="text-[9px] font-bold text-cyan-400">{items.reduce((s: number, c: any) => s + (c.count || 0), 0)}건</span>
        <span className="text-[8px] text-gray-500">11개 채널 뉴스분석</span>
        <span className="text-[7px] text-gray-600 border-l border-[#1a2844] pl-2">60분 주기 갱신</span>
      </div>
      <div className="overflow-hidden" style={{ maxHeight: "45vh" }}>
        {items.length === 0 ? (
          <div className="p-6 text-center text-gray-500 text-xs">이슈 수집 중...</div>
        ) : (
          <div className="ticker-scroll p-1.5 space-y-1">
            {doubled.map((c: any, i: number) => {
              const rank = (i % items.length) + 1;
              const isTop1 = rank === 1;
              const isTrending = (c.count || 0) >= 10;

              return (
                <div
                  key={`${c.name}-${i}`}
                  className={`issue-card ${sideClass(c.side || "")} rounded-lg px-2.5 py-2 ${isTop1 ? "top-card bg-[#081018]" : "bg-[#080d16]"}`}
                >
                  {/* 순위 + 제목 한줄 */}
                  <div className="flex items-start gap-2">
                    <span className={`text-[13px] font-black wr-metric shrink-0 ${isTop1 ? "text-cyan-400" : rank <= 3 ? "text-blue-400" : "text-gray-500"}`}>
                      {rank}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className={`text-[10px] font-bold leading-tight ${isTop1 ? "text-white" : "text-gray-200"}`}>{c.name}</span>
                        {isTrending && <span className="text-[10px] trend-pulse shrink-0" title="10건 이상 트렌딩">🔥</span>}
                      </div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="text-[8px] text-gray-500 font-mono">{c.count}건</span>
                        <span className={`text-[6px] font-bold px-1 py-0.5 rounded border ${sideBadge(c.side || "")}`}>
                          {c.side || "중립"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* 한줄 설명 + 유리/불리 이유 — 전체 순위 */}
                  {(c.summary || c.why) && (
                    <div className="mt-1 px-1 space-y-0.5">
                      {c.summary && <div className="text-[7px] text-gray-400 leading-relaxed">{c.summary}</div>}
                      {c.why && <div className="text-[7px] text-cyan-400/70 leading-relaxed">→ {c.why}</div>}
                    </div>
                  )}
                  {/* AI Tip — 1~3위만 */}
                  {c.tip && rank <= 3 && (
                    <div className="flex items-start gap-1 mt-1 bg-cyan-950/15 border border-cyan-900/20 rounded px-2 py-1">
                      <span className="text-[9px] shrink-0">🤖</span>
                      <span className="text-[7px] text-cyan-400/70 leading-relaxed line-clamp-2">{c.tip}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
