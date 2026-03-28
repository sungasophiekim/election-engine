"use client";
import { useStore } from "@/lib/store";
import { fmtTs } from "@/lib/format";

export default function ReactionSidebar() {
  const reactionRadar = useStore((s) => s.reactionRadar);
  const indices = useStore((s) => s.indices);
  const enrichTs = indices?.reaction?.updated_at || "";

  const sideColor = (s: string) =>
    s?.includes("우리") ? "border-l-blue-500" : s?.includes("상대") ? "border-l-red-500" : "border-l-gray-600";
  const sideText = (s: string) =>
    s?.includes("우리") ? "text-blue-400" : s?.includes("상대") ? "text-red-400" : "text-gray-500";
  const toneColor = (t: string) =>
    t === "긍정" ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30" :
    t === "부정" ? "text-red-400 bg-red-500/10 border-red-500/30" :
    "text-gray-400 bg-gray-700/20 border-gray-600/30";
  const reactionBg = (r: string) =>
    r === "높음" ? "bg-amber-400" : r === "보통" ? "bg-gray-500" : "bg-gray-700";

  const items = reactionRadar.slice(0, 10);
  const doubled = [...items, ...items];

  return (
    <div className="wr-card anim-in" style={{ animationDelay: "0.6s" }}>
      <div className="wr-card-header flex justify-between">
        <div className="flex items-center gap-2">
          <span>민심 반응 레이더</span>
          <span className="text-[7px] text-amber-500/60 font-normal normal-case tracking-normal">beta</span>
          <span className="w-1.5 h-1.5 rounded-full bg-purple-500 live-dot" />
        </div>
        <span className="timestamp normal-case tracking-normal font-normal">{fmtTs(enrichTs)}</span>
      </div>

      <div className="px-3 py-1.5 text-[7px] text-gray-600 leading-relaxed border-b border-[#0e1825] space-y-0.5">
        <div>이슈별 시민 반응 · 기사수 기반 관심도 정렬 · 세그먼트 커뮤니티 기반</div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-0.5"><span className="w-1.5 h-1.5 rounded-sm bg-emerald-500/40 border border-emerald-500/60 inline-block" /> 긍정</span>
          <span className="flex items-center gap-0.5"><span className="w-1.5 h-1.5 rounded-sm bg-red-500/40 border border-red-500/60 inline-block" /> 부정</span>
          <span className="flex items-center gap-0.5"><span className="w-1.5 h-1.5 rounded-sm bg-gray-600/40 border border-gray-500/60 inline-block" /> 혼합</span>
          <span className="flex items-center gap-0.5"><span className="w-1.5 h-1.5 rounded-sm bg-purple-500/40 border border-purple-500/60 inline-block" /> 📍지역</span>
          <span className="text-gray-700">· 숫자=언급수</span>
        </div>
      </div>

      <div className="overflow-hidden" style={{ maxHeight: "45vh" }}>
        {items.length === 0 ? (
          <div className="p-6 text-center text-gray-500 text-xs">데이터 수집 중...</div>
        ) : (
          <div className="ticker-scroll p-1.5 space-y-1" style={{ animationDuration: "80s" }}>
            {doubled.map((r: any, i: number) => {
              const rank = (i % items.length) + 1;
              const isTop3 = rank <= 3;
              const segments = r.segments || [];
              const hasComments = (r.comments || 0) > 0;

              return (
                <div
                  key={`${r.name}-${i}`}
                  className={`issue-card rounded-lg px-2.5 py-2 border-l-2 ${sideColor(r.side)} ${isTop3 ? "bg-[#081018]" : "bg-[#080d16]"}`}
                >
                  {/* 순위 + 이슈명 + 진영 */}
                  <div className="flex items-start gap-2">
                    <span className={`text-[13px] font-black wr-metric shrink-0 ${rank === 1 ? "text-purple-400" : isTop3 ? "text-blue-400" : "text-gray-500"}`}>
                      {rank}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className={`text-[10px] font-bold leading-tight ${isTop3 ? "text-white" : "text-gray-200"}`}>
                          {r.name}
                        </span>
                        <span className={`text-[8px] ${sideText(r.side)}`}>{r.side}</span>
                      </div>

                      {/* 기사수 + 댓글수 */}
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[8px] text-gray-500">{r.count}건</span>
                        {hasComments && (
                          <span className="text-[8px] text-amber-400 font-bold">댓글 {r.comments}</span>
                        )}
                        {/* 댓글 0이면 표시 안 함 */}
                        {/* 민심 톤: 세그먼트 실데이터 기반 */}
                        {(() => {
                          const tones = (r.segments || []).map((s: any) => s.tone);
                          const pos = tones.filter((t: string) => t === "긍정").length;
                          const neg = tones.filter((t: string) => t === "부정").length;
                          const label = pos > neg ? "긍정" : neg > pos ? "부정" : tones.length > 0 ? "혼합" : "";
                          if (!label) return null;
                          return (
                            <span className={`text-[7px] ${label === "긍정" ? "text-emerald-500" : label === "부정" ? "text-red-400" : "text-gray-500"}`}>
                              민심 {label}
                            </span>
                          );
                        })()}
                      </div>
                    </div>
                  </div>

                  {/* 세그먼트 반응 — 커뮤니티 실데이터 기반 */}
                  {segments.length > 0 && (
                    <div className="mt-1.5 space-y-0.5">
                      <div className="flex gap-1 flex-wrap">
                        {segments.filter((s: any) => s.reaction !== "낮음").map((seg: any, si: number) => (
                          <span
                            key={si}
                            className={`text-[7px] px-1.5 py-0.5 rounded border font-bold ${
                              seg.type === "지역"
                                ? "border-purple-500/40 text-purple-300 bg-purple-500/10"
                                : toneColor(seg.tone)
                            }`}
                          >
                            {seg.type === "지역" && <span className="mr-0.5">📍</span>}
                            {seg.label}
                            {seg.mentions > 0 && <span className="ml-0.5 font-mono font-normal">{seg.mentions}</span>}
                            {seg.reaction === "높음" && <span className="ml-0.5">●</span>}
                            {seg.reaction === "추정" && <span className="ml-0.5 text-gray-600">?</span>}
                          </span>
                        ))}
                      </div>
                      {/* 상위 3개 이슈에 커뮤니티명 표시 */}
                      {isTop3 && segments.some((s: any) => s.communities?.length > 0) && (
                        <div className="text-[6px] text-gray-600 pl-0.5">
                          {segments.flatMap((s: any) => s.communities || []).slice(0, 4).join(" · ")}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 시민 의견 (AI 본문 분석) — "무관" 필터링 */}
                  {r.opinions?.filter((op: any) => op.opinion && op.opinion !== "무관" && op.sentiment !== 0).length > 0 && (
                    <div className="mt-1 space-y-0.5">
                      {r.opinions.filter((op: any) => op.opinion && op.opinion !== "무관" && op.sentiment !== 0).slice(0, isTop3 ? 3 : 1).map((op: any, oi: number) => (
                        <div key={oi} className="text-[7px] text-gray-400 flex gap-1">
                          <span className={`shrink-0 ${op.sentiment > 0 ? "text-emerald-500" : op.sentiment < 0 ? "text-red-400" : "text-gray-500"}`}>
                            {op.sentiment > 0 ? "👍" : op.sentiment < 0 ? "👎" : "•"}
                          </span>
                          <span className="text-gray-500">{op.community}</span>
                          <span className="text-gray-300">{op.opinion}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 대응 Tip (상위 3개만, 시민 의견 없을 때) */}
                  {isTop3 && r.tip && !r.opinions?.length && (
                    <div className="mt-1.5 text-[7px] text-cyan-400/70 leading-relaxed">
                      💡 {r.tip}
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
