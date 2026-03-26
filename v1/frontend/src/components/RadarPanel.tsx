"use client";
import { useStore } from "@/lib/store";
import { fmtTs } from "@/lib/format";

function RadarList({ title, items, type, updatedAt }: { title: string; items: any[]; type: "issue" | "reaction"; updatedAt?: string }) {
  const gradeColors: Record<string, string> = {
    EXPLOSIVE: "text-red-400", HOT: "text-orange-400", ACTIVE: "text-yellow-400",
    VIRAL: "text-purple-400", ENGAGED: "text-blue-400", RIPPLE: "text-gray-400",
  };

  return (
    <div className="wr-card">
      <div className="wr-card-header flex justify-between">
        <span>{title}</span>
        <span className="timestamp normal-case tracking-normal font-normal">{fmtTs(updatedAt)}</span>
      </div>
      <div className="divide-y divide-[#0e1825] max-h-[300px] overflow-y-auto">
        {items.map((r: any, i: number) => {
          const score = type === "issue" ? (r.index || 0) : (r.final_score || r.index || 0);
          const grade = r.grade || "";
          const gradeC = gradeColors[grade] || "text-gray-400";
          const dir = r.direction;
          const dirIcon = dir === "positive" ? "▲" : dir === "negative" ? "▼" : "●";
          const dirColor = dir === "positive" ? "text-emerald-400" : dir === "negative" ? "text-rose-500" : "text-gray-400";

          return (
            <div key={i} className="flex items-center gap-1.5 px-3 py-[6px] text-[11px] hover:bg-[#0d1420] transition-all duration-200 flash">
              <span className={`w-4 text-center font-mono text-[9px] ${i < 3 ? "text-orange-400 font-bold" : "text-gray-500"}`}>{i + 1}</span>
              <span className="flex-1 truncate text-gray-300">{r.keyword}</span>
              <span className={`text-[9px] font-mono font-bold ${gradeC}`}>{score.toFixed(0)}</span>
              {grade && <span className={`text-[7px] px-1 rounded ${gradeC}`}>{grade}</span>}
              {type === "reaction" && <span className={`text-[8px] ${dirColor}`}>{dirIcon}</span>}
            </div>
          );
        })}
        {items.length === 0 && <div className="p-4 text-center text-gray-500 text-xs">데이터 수집 중</div>}
      </div>
    </div>
  );
}

export default function RadarPanel() {
  const issueRadar = useStore((s) => s.issueRadar);
  const reactionRadar = useStore((s) => s.reactionRadar);
  const indices = useStore((s) => s.indices);
  const enrichTs = indices?.issue?.updated_at || "";

  return (
    <div className="grid grid-cols-2 gap-3 anim-in" style={{ animationDelay: "0.8s" }}>
      <RadarList title="이슈 레이더" items={issueRadar} type="issue" updatedAt={enrichTs} />
      <RadarList title="리액션 레이더" items={reactionRadar} type="reaction" updatedAt={enrichTs} />
    </div>
  );
}
