"use client";
import { useStore } from "@/lib/store";

export function NationalTrendChart() {
  const data = useStore((s) => s.nationalTrend);
  if (!data || data.length < 2) return null;

  const n = data.length;
  const w = 900, h = 160, pl = 35, pr = 50, pt = 16, pb = 32;
  const xs = (w - pl - pr) / (n - 1);
  const mn = 10, mx = 75, rng = mx - mn;
  const Y = (v: number) => pt + (1 - (v - mn) / rng) * (h - pt - pb);

  const presVals = data.map((d: any) => d.president || 0);
  const demVals = data.map((d: any) => d.dem || 0);
  const pppVals = data.map((d: any) => d.ppp || 0);

  const calcLen = (vals: number[]) => {
    let l = 0;
    for (let i = 1; i < vals.length; i++) l += Math.sqrt(xs * xs + (Y(vals[i]) - Y(vals[i - 1])) ** 2);
    return Math.ceil(l);
  };

  const latest = data[n - 1];
  const gap = (latest.dem || 0) - (latest.ppp || 0);

  return (
    <div className="wr-card anim-in" style={{ animationDelay: "0.15s" }}>
      <div className="wr-card-header flex justify-between">
        <div className="flex items-center gap-2">
          <span>전국 정당 지지율 · 대통령 지지율</span>
          <span className="text-[8px] text-gray-500 font-normal normal-case tracking-normal">한국갤럽</span>
        </div>
        <div className="flex gap-3 text-[8px] normal-case tracking-normal font-normal">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400" /><span className="text-gray-400">대통령</span></span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" /><span className="text-gray-400">민주당</span></span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /><span className="text-gray-400">국힘</span></span>
        </div>
      </div>
      <div className="p-3">
        <svg width="100%" viewBox={`0 0 ${w} ${h}`}>
          <style>{`
            .nt-pres { stroke-dasharray:${calcLen(presVals)}; stroke-dashoffset:${calcLen(presVals)}; animation:drawLine 1.5s ease-out forwards; }
            .nt-dem { stroke-dasharray:${calcLen(demVals)}; stroke-dashoffset:${calcLen(demVals)}; animation:drawLine 1.5s ease-out 0.2s forwards; }
            .nt-ppp { stroke-dasharray:${calcLen(pppVals)}; stroke-dashoffset:${calcLen(pppVals)}; animation:drawLine 1.5s ease-out 0.4s forwards; }
            .nt-dot { opacity:0; animation:fadeInUp 0.3s ease-out forwards; }
            @keyframes drawLine { to { stroke-dashoffset:0; } }
            @keyframes fadeInUp { to { opacity:1; } }
          `}</style>

          {[20, 30, 40, 50, 60, 70].map(v => (
            <g key={v}>
              <line x1={pl} y1={Y(v)} x2={w - pr} y2={Y(v)} stroke="#111d30" strokeWidth="0.5" />
              <text x={pl - 4} y={Y(v) + 3} fill="#4b6a9b" fontSize="7" textAnchor="end" fontFamily="monospace">{v}</text>
            </g>
          ))}

          {/* 격차 영역 */}
          <polygon
            points={demVals.map((v: number, i: number) => `${pl + i * xs},${Y(v)}`).join(" ") + " " + [...pppVals].reverse().map((v: number, i: number) => `${pl + (n - 1 - i) * xs},${Y(v)}`).join(" ")}
            fill="rgba(37,99,235,0.06)"
            className="nt-dot" style={{ animationDelay: "1s" }}
          />

          {/* Lines */}
          <polyline points={presVals.map((v: number, i: number) => `${pl + i * xs},${Y(v)}`).join(" ")} fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinejoin="round" strokeDasharray="6,3" className="nt-pres" />
          <polyline points={demVals.map((v: number, i: number) => `${pl + i * xs},${Y(v)}`).join(" ")} fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinejoin="round" className="nt-dem" />
          <polyline points={pppVals.map((v: number, i: number) => `${pl + i * xs},${Y(v)}`).join(" ")} fill="none" stroke="#ef4444" strokeWidth="2" strokeLinejoin="round" className="nt-ppp" />

          {/* Dots + Labels */}
          {data.map((d: any, i: number) => {
            const delay = `${0.8 + i * 0.1}s`;
            const isLast = i === n - 1;
            return (
              <g key={i}>
                <circle cx={pl + i * xs} cy={Y(d.president)} r={isLast ? 4.5 : 3.5} fill={isLast ? "#f59e0b" : "none"} stroke="#f59e0b" strokeWidth={isLast ? 2 : 1.5} className="nt-dot" style={{ animationDelay: delay }} />
                <circle cx={pl + i * xs} cy={Y(d.dem)} r={isLast ? 4.5 : 3.5} fill={isLast ? "#2563eb" : "none"} stroke="#2563eb" strokeWidth={isLast ? 2 : 1.5} className="nt-dot" style={{ animationDelay: delay }} />
                <circle cx={pl + i * xs} cy={Y(d.ppp)} r={isLast ? 4.5 : 3.5} fill={isLast ? "#ef4444" : "none"} stroke="#ef4444" strokeWidth={isLast ? 2 : 1.5} className="nt-dot" style={{ animationDelay: delay }} />
                <text x={pl + i * xs} y={Y(d.president) - 8} fill="#f59e0b" fontSize={isLast ? "9" : "8"} fontWeight="bold" textAnchor="middle" fontFamily="monospace" className="nt-dot" style={{ animationDelay: delay }}>{d.president}</text>
                <text x={pl + i * xs} y={Y(d.dem) - 8} fill="#2563eb" fontSize={isLast ? "9" : "8"} fontWeight="bold" textAnchor="middle" fontFamily="monospace" className="nt-dot" style={{ animationDelay: delay }}>{d.dem}</text>
                <text x={pl + i * xs} y={Y(d.ppp) + 14} fill="#ef4444" fontSize={isLast ? "9" : "8"} fontWeight="bold" textAnchor="middle" fontFamily="monospace" className="nt-dot" style={{ animationDelay: delay }}>{d.ppp}</text>
                <text x={pl + i * xs} y={h - 6} fill="#6b7280" fontSize="7" textAnchor="middle" fontFamily="monospace" className="nt-dot" style={{ animationDelay: delay }}>{d.date}</text>
              </g>
            );
          })}
        </svg>

        {/* 하단 요약 */}
        <div className="flex items-center justify-between mt-1 px-1">
          <div className="flex items-center gap-3 text-[9px]">
            <span className="text-amber-400 font-bold">대통령 {latest.president}%</span>
            <span className="text-blue-400 font-bold">민주 {latest.dem}%</span>
            <span className="text-red-400 font-bold">국힘 {latest.ppp}%</span>
          </div>
          <span className="text-[10px] font-black text-blue-400">격차 +{gap}%p</span>
        </div>
      </div>
    </div>
  );
}

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
