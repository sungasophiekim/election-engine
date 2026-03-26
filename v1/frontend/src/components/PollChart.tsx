"use client";
import { useStore } from "@/lib/store";

export default function PollChart() {
  const polls = useStore((s) => s.polls);
  if (!polls.length) return null;

  const n = polls.length;
  const w = 900, h = 200, pl = 35, pr = 10, pt = 16, pb = 38;
  const xs = (w - pl - pr) / (n - 1);
  const mn = 25, mx = 70, rng = mx - mn;
  const Y = (v: number) => pt + (1 - (v - mn) / rng) * (h - pt - pb);

  // 실제득표 구분선 (3번째=8기 이후)
  const dividerX = pl + 2.5 * xs;

  // 라인 길이 계산
  const calcLen = (pts: {x:number;y:number}[]) => {
    let l = 0;
    for (let i = 1; i < pts.length; i++) l += Math.sqrt((pts[i].x-pts[i-1].x)**2 + (pts[i].y-pts[i-1].y)**2);
    return Math.ceil(l);
  };
  const kimPts = polls.map((d: any, i: number) => ({ x: pl + i * xs, y: Y(d.kim) }));
  const parkPts = polls.map((d: any, i: number) => ({ x: pl + i * xs, y: Y(d.park) }));
  const kimLen = calcLen(kimPts);
  const parkLen = calcLen(parkPts);

  return (
    <div className="wr-card anim-in">
      <div className="wr-card-header flex justify-between">
        <span>역대 득표율 + 9대 여론조사</span>
        <div className="flex gap-3 text-[8px] normal-case tracking-normal font-normal">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500"/><span className="text-gray-400">김경수</span></span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500"/><span className="text-gray-400">박완수</span></span>
          <span className="text-gray-500">●실제득표 ○여론조사</span>
        </div>
      </div>
      <div className="p-3">
        <svg width="100%" viewBox={`0 0 ${w} ${h}`}>
          <style>{`
            .line-kim { stroke-dasharray:${kimLen}; stroke-dashoffset:${kimLen}; animation:drawLine 1.5s ease-out forwards; }
            .line-park { stroke-dasharray:${parkLen}; stroke-dashoffset:${parkLen}; animation:drawLine 1.5s ease-out 0.3s forwards; }
            .dot-fade { opacity:0; animation:fadeInUp 0.3s ease-out forwards; }
            @keyframes drawLine { to { stroke-dashoffset:0; } }
            @keyframes fadeInUp { to { opacity:1; } }
          `}</style>

          {[30,40,50,60].map(v => (
            <g key={v}>
              <line x1={pl} y1={Y(v)} x2={w-pr} y2={Y(v)} stroke="#111d30" strokeWidth="0.5"/>
              <text x={pl-4} y={Y(v)+3} fill="#4b6a9b" fontSize="7" textAnchor="end" fontFamily="monospace">{v}</text>
            </g>
          ))}

          <line x1={dividerX} y1={pt} x2={dividerX} y2={h-pb} stroke="#374151" strokeWidth="1" strokeDasharray="4,4"/>

          <polyline points={parkPts.map(p=>`${p.x},${p.y}`).join(" ")} fill="none" stroke="#ef4444" strokeWidth="2" strokeLinejoin="round" className="line-park"/>
          <polyline points={kimPts.map(p=>`${p.x},${p.y}`).join(" ")} fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinejoin="round" className="line-kim"/>

          {polls.map((d: any, i: number) => {
            const isE = d.type === "election";
            const delay = `${0.8 + i * 0.08}s`;
            return (
              <g key={i}>
                <circle cx={pl+i*xs} cy={Y(d.kim)} r={isE?4.5:3} fill={isE?"#2563eb":"none"} stroke="#2563eb" strokeWidth={isE?2:1.5} className="dot-fade" style={{animationDelay:delay}}/>
                <text x={pl+i*xs} y={Y(d.kim)-6} fill="#2563eb" fontSize={isE?"9":"8"} fontWeight="bold" textAnchor="middle" className="dot-fade" style={{animationDelay:delay}}>{d.kim}</text>
                <circle cx={pl+i*xs} cy={Y(d.park)} r={isE?4.5:3} fill={isE?"#ef4444":"none"} stroke="#ef4444" strokeWidth={isE?2:1.5} className="dot-fade" style={{animationDelay:delay}}/>
                <text x={pl+i*xs} y={Y(d.park)+13} fill="#ef4444" fontSize={isE?"9":"8"} fontWeight="bold" textAnchor="middle" className="dot-fade" style={{animationDelay:delay}}>{d.park}</text>
                <text x={pl+i*xs} y={h-pb+12} fill="#6b7280" fontSize="7" textAnchor="middle" className="dot-fade" style={{animationDelay:delay}}>{d.label}</text>
                <text x={pl+i*xs} y={h-4} fill="#6b7280" fontSize="6" textAnchor="middle" fontFamily="monospace" className="dot-fade" style={{animationDelay:delay}}>{d.date}</text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
