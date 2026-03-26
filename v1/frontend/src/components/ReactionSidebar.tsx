"use client";
import { useStore } from "@/lib/store";
import { fmtTs } from "@/lib/format";

export default function ReactionSidebar() {
  const reactionRadar = useStore((s) => s.reactionRadar);
  const indices = useStore((s) => s.indices);
  const enrichTs = indices?.reaction?.updated_at || "";

  const dirIcon = (d: string) => d === "positive" ? "▲" : d === "negative" ? "▼" : "●";
  const dirColor = (d: string) => d === "positive" ? "text-emerald-400" : d === "negative" ? "text-rose-400" : "text-gray-400";
  const gradeColor = (g: string) =>
    g === "VIRAL" ? "bg-purple-500/20 text-purple-400 border-purple-500/40" :
    g === "ENGAGED" ? "bg-blue-500/20 text-blue-400 border-blue-500/40" :
    g === "RIPPLE" ? "bg-cyan-500/15 text-cyan-400 border-cyan-500/30" :
    "bg-gray-700/30 text-gray-500 border-gray-600/40";

  // 통계
  const totalChannels = reactionRadar.reduce((s: number, r: any) => s + (r.layers_active || 0), 0);
  const totalMentions = reactionRadar.reduce((s: number, r: any) => {
    const segs = r.segment_reactions || [];
    return s + segs.reduce((ss: number, seg: any) => ss + (seg.mentions || seg.mention_count || 0), 0);
  }, 0);

  const items = reactionRadar.slice(0, 10);
  const doubled = [...items, ...items];

  return (
    <div className="wr-card anim-in" style={{ animationDelay: "0.6s" }}>
      <div className="wr-card-header flex justify-between">
        <div className="flex items-center gap-2">
          <span>리액션 레이더 TOP</span>
          <span className="w-1.5 h-1.5 rounded-full bg-purple-500 live-dot" />
        </div>
        <span className="timestamp normal-case tracking-normal font-normal">{fmtTs(enrichTs)}</span>
      </div>

      <div className="px-3 py-1 text-[7px] text-gray-600 leading-relaxed border-b border-[#0e1825]">
        {reactionRadar.length}개 이슈 · {totalChannels || 22}개 채널 · {totalMentions || "—"}건 분석 · AI 감성 30분 갱신
      </div>

      <div className="overflow-hidden" style={{ maxHeight: "45vh" }}>
        {items.length === 0 ? (
          <div className="p-6 text-center text-gray-500 text-xs">데이터 수집 중...</div>
        ) : (
          <div className="ticker-scroll p-1.5 space-y-1" style={{ animationDuration: "80s" }}>
            {doubled.map((r: any, i: number) => {
              const rank = (i % items.length) + 1;
              const isTop1 = rank === 1;
              const score = r.final_score || r.index || 0;
              const grade = r.grade || "SILENT";
              const dir = r.direction || "";
              const segments = r.segment_reactions || [];
              const channels = r.layers_active || 0;
              const driver = r.dominant_channel || "";

              return (
                <div
                  key={`${r.keyword}-${i}`}
                  className={`issue-card rounded-lg px-2.5 py-2 ${isTop1 ? "top-card bg-[#081018]" : "bg-[#080d16]"}`}
                  style={{ borderLeftColor: dir === "positive" ? "#10b981" : dir === "negative" ? "#ef4444" : "#374151" }}
                >
                  {/* 순위 + 제목 + 점수 */}
                  <div className="flex items-start gap-2">
                    <span className={`text-[13px] font-black wr-metric shrink-0 ${isTop1 ? "text-purple-400" : rank <= 3 ? "text-blue-400" : "text-gray-500"}`}>
                      {rank}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className={`text-[10px] font-bold leading-tight ${isTop1 ? "text-white" : "text-gray-200"}`}>{r.keyword}</span>
                        <span className={`text-[9px] ${dirColor(dir)}`}>{dirIcon(dir)}</span>
                        {score >= 50 && <span className="text-[9px] trend-pulse shrink-0">🔥</span>}
                      </div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className={`text-[9px] font-black wr-metric ${score >= 50 ? "text-purple-400" : score >= 25 ? "text-blue-400" : "text-gray-500"}`}>{score.toFixed(0)}점</span>
                        <span className={`text-[6px] font-bold px-1 py-0.5 rounded border ${gradeColor(grade)}`}>{grade}</span>
                        {driver && <span className="text-[6px] text-gray-600">{driver}</span>}
                        {channels > 0 && <span className="text-[6px] text-gray-600">{channels}채널</span>}
                      </div>
                    </div>
                  </div>

                  {/* 세그먼트 반응 (있으면) */}
                  {segments.length > 0 && rank <= 5 && (
                    <div className="flex gap-1 mt-1.5 flex-wrap">
                      {segments.slice(0, 4).map((seg: any, si: number) => {
                        const segSent = seg.sentiment || 0;
                        const segColor = segSent > 0.1 ? "border-emerald-700/40 text-emerald-400" : segSent < -0.1 ? "border-rose-700/40 text-rose-400" : "border-gray-700/40 text-gray-400";
                        return (
                          <span key={si} className={`text-[6px] px-1 py-0.5 rounded border bg-[#0a1019] ${segColor}`}>
                            {seg.label || seg.name || seg.community_id} {seg.mentions || seg.mention_count || 0}
                          </span>
                        );
                      })}
                      {segments.length > 4 && <span className="text-[6px] text-gray-600">+{segments.length - 4}</span>}
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
