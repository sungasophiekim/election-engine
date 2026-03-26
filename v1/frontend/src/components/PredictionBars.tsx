"use client";
import { useStore } from "@/lib/store";
import { fmtDate } from "@/lib/format";

function Bar({ kim, park, label, source, updatedAt, variant = "default", delay = 0 }: {
  kim: number; park: number; label: string; source: string; updatedAt?: string; variant?: string; delay?: number;
}) {
  const gap = kim - park;
  const total = kim + park || 1;
  const kimW = kim / total * 100;

  const kimBg = variant === "dynamic" ? "linear-gradient(135deg, #1e3a5f, #0e7490)" : variant === "base" ? "#1e3a8a" : "#2563eb";
  const parkBg = variant === "dynamic" ? "linear-gradient(135deg, #5b2130, #831843)" : variant === "base" ? "#7f1d1d" : "#dc2626";
  const kimText = variant === "dynamic" ? "text-cyan-200" : variant === "base" ? "text-blue-300" : "text-white";
  const parkText = variant === "dynamic" ? "text-pink-300" : variant === "base" ? "text-red-300" : "text-white";
  const gapColor = gap >= 0 ? (variant === "dynamic" ? "text-cyan-400" : "text-emerald-400") : (variant === "dynamic" ? "text-pink-400" : "text-rose-500");

  return (
    <div className="space-y-1.5 anim-in" style={{ animationDelay: `${delay}s` }}>
      <div className="flex items-center gap-2 mb-0.5">
        <span className="text-[10px] text-gray-300 font-bold">{label}</span>
        {updatedAt && <span className="timestamp">{updatedAt}</span>}
      </div>
      <div className={`flex h-10 rounded-lg overflow-hidden ${variant === "dynamic" ? "border border-cyan-800/40" : ""}`}>
        <div className="flex items-center justify-center anim-bar bar-breath" style={{ width: `${kimW}%`, background: kimBg }}>
          <span className={`text-[16px] font-black ${kimText} anim-num`} style={{ animationDelay: `${delay + 0.4}s` }}>{kim.toFixed(1)}%</span>
        </div>
        <div className="flex items-center justify-center anim-bar bar-breath" style={{ width: `${100 - kimW}%`, background: parkBg, transformOrigin: "right", animationDelay: `${delay + 0.1}s` }}>
          <span className={`text-[16px] font-black ${parkText} anim-num`} style={{ animationDelay: `${delay + 0.5}s` }}>{park.toFixed(1)}%</span>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <span className={`text-[13px] font-black wr-metric gap-blink ${gapColor}`}>
          격차 {gap >= 0 ? "+" : ""}{gap.toFixed(1)}%p
        </span>
      </div>
      <div className="text-[7px] text-gray-600">{source}</div>
    </div>
  );
}

export default function PredictionBars() {
  const pred = useStore((s) => s.prediction);
  const indices = useStore((s) => s.indices);
  const lastUpdated = useStore((s) => s.lastUpdated);
  if (!pred) return null;

  const poll = pred.poll || {};
  const base = pred.base || {};
  const dyn = pred.dynamic || {};
  const pandseUpdatedAt = indices?.pandse?.updated_at;

  return (
    <div className="wr-card border-pulse relative scanline anim-in" style={{ animationDelay: "0.3s" }}>
      <div className="wr-card-header">여론조사 vs 실투표 예측</div>
      <div className="px-4 py-3 grid grid-cols-3 gap-5">
        <Bar
          kim={poll.kim || 0} park={poll.park || 0}
          label={`여론조사 (${poll.label || "최신"})`}
          source={`출처: ${poll.label || ""} (${poll.date || ""})`}
          updatedAt={poll.date ? `마지막업데이트: ${poll.date}` : undefined}
          delay={0.3}
        />
        <Bar
          kim={base.kim || 50} park={base.park || 50}
          label="실투표 예측"
          source="7대 투표율 · 최근 여론조사 3개 지지율 교차"
          updatedAt={fmtDate(base.updated_at)}
          variant="base" delay={0.5}
        />
        <Bar
          kim={dyn.kim || 50} park={dyn.park || 50}
          label="실투표 예측 동향"
          source="자체인덱스 구성 (9 Factors) 및 선거일 남은일수 반영"
          updatedAt={fmtDate(pandseUpdatedAt || dyn.updated_at)}
          variant="dynamic" delay={0.7}
        />
      </div>
    </div>
  );
}
