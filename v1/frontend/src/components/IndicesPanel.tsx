"use client";
import { useStore } from "@/lib/store";
import { fmtTs } from "@/lib/format";

export default function IndicesPanel() {
  const indices = useStore((s) => s.indices);
  const history = useStore((s) => s.history);
  const candidateTrend = useStore((s) => s.candidateTrend);
  const lastUpdated = useStore((s) => s.lastUpdated);
  if (!indices) return null;

  const { issue, reaction, pandse } = indices;
  const gradeColor = (g: string) => g === "우세" ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" : g === "열세" ? "bg-rose-500/15 text-rose-500 border-rose-500/30" : "bg-gray-800/30 text-gray-400 border-gray-700/30";

  return (
    <div className="wr-card anim-in" style={{ animationDelay: "0.5s" }}>
      <div className="wr-card-header">
        <span>주요지표추세</span>
      </div>

      {/* 3개 지수 */}
      <div className="grid grid-cols-3 border-b border-[#0e1825]">
        {/* 이슈지수 */}
        <div className="px-4 py-3 border-r border-[#0e1825]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-gray-300 font-bold">이슈지수 <span className="text-[7px] text-amber-500/60 font-normal">beta</span> <span className="timestamp font-normal ml-1">{fmtTs(issue?.updated_at)}</span></span>
            <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border ${gradeColor(issue?.grade)}`}>{issue?.grade}</span>
          </div>
          <div className="flex items-center justify-between mb-2">
            <div className="text-center">
              <div className="text-[8px] text-blue-400 anim-slide" style={{animationDelay:"0.1s"}}>김경수</div>
              <div className="text-[22px] font-black wr-metric text-blue-400 pulse anim-num" style={{animationDelay:"0.3s"}}>{issue?.kim?.mentions || 0}</div>
              <div className="text-[7px] text-gray-600">{issue?.kim?.keywords || 0}개</div>
            </div>
            <div className={`text-[13px] font-black wr-metric gap-blink anim-num ${(issue?.gap||0) > 0 ? "text-blue-400" : (issue?.gap||0) < 0 ? "text-red-400" : "text-gray-400"}`} style={{animationDelay:"0.5s"}}>
              격차 {issue?.gap > 0 ? "+" : ""}{issue?.gap || 0}
            </div>
            <div className="text-center">
              <div className="text-[8px] text-red-400 anim-slide" style={{animationDelay:"0.2s"}}>박완수</div>
              <div className="text-[22px] font-black wr-metric text-red-400 pulse anim-num" style={{animationDelay:"0.4s"}}>{issue?.park?.mentions || 0}</div>
              <div className="text-[7px] text-gray-600">{issue?.park?.keywords || 0}개</div>
            </div>
          </div>
          <div className="text-[7px] text-gray-600 leading-relaxed">
            {(issue?.kim?.keywords||0) + (issue?.park?.keywords||0)}개 미디어채널에서 후보별 키워드 기반 뉴스 언급량 집계.
            24시간 내 네이버 뉴스 수집 후 후보 연결 기사 수로 점수화.
          </div>
          {/* 미니 차트 — 후보별 2라인 */}
          {candidateTrend.length >= 2 && <DualChart data={candidateTrend} kimField="issue_kim" parkField="issue_park" />}
        </div>

        {/* 반응지수 */}
        <div className="px-4 py-3 border-r border-[#0e1825]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-gray-300 font-bold">반응지수 <span className="text-[7px] text-amber-500/60 font-normal">beta</span> <span className="timestamp font-normal ml-1">{fmtTs(reaction?.updated_at)}</span></span>
            <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border ${gradeColor(reaction?.grade)}`}>{reaction?.grade}</span>
          </div>
          {(() => {
            const kimP = reaction?.kim?.pct || 0;
            const parkP = reaction?.park?.pct || 0;
            const gap = kimP - parkP;
            return (
              <div className="flex items-center justify-between mb-2">
                <div className="text-center">
                  <div className="text-[8px] text-blue-400 anim-slide" style={{animationDelay:"0.1s"}}>김경수</div>
                  <div className={`text-[22px] font-black wr-metric pulse anim-num ${kimP >= 0 ? "text-emerald-400" : "text-rose-400"}`} style={{animationDelay:"0.3s"}}>
                    {kimP > 0 ? "+" : ""}{kimP}
                  </div>
                  <div className="text-[7px] text-gray-600">{reaction?.kim?.keywords||0}개</div>
                </div>
                <div className="text-center px-1">
                  <div className={`text-[13px] font-black wr-metric gap-blink anim-num ${gap > 0 ? "text-blue-400" : gap < 0 ? "text-red-400" : "text-gray-400"}`} style={{animationDelay:"0.5s"}}>
                    격차 {gap > 0 ? "+" : ""}{gap}
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-[8px] text-red-400 anim-slide" style={{animationDelay:"0.2s"}}>박완수</div>
                  <div className={`text-[22px] font-black wr-metric pulse anim-num ${parkP >= 0 ? "text-emerald-400" : "text-rose-400"}`} style={{animationDelay:"0.4s"}}>
                    {parkP > 0 ? "+" : ""}{parkP}
                  </div>
                  <div className="text-[7px] text-gray-600">{reaction?.park?.keywords||0}개</div>
                </div>
              </div>
            );
          })()}
          <div className="text-[7px] text-gray-600 leading-relaxed">
            {(reaction?.kim?.keywords||0) + (reaction?.park?.keywords||0)}개 채널(커뮤니티·댓글·SNS) 감성 분석.
            AI 6분류 · 30분 갱신
          </div>
          {candidateTrend.length >= 2 && <DualChart data={candidateTrend} kimField="reaction_kim" parkField="reaction_park" />}
        </div>

        {/* 판세지수 — 게이지 바 */}
        <div className="px-4 py-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-gray-300 font-bold">판세지수 <span className="text-[7px] text-amber-500/60 font-normal">beta</span> <span className="timestamp font-normal ml-1">{fmtTs(pandse?.updated_at)}</span></span>
            <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border ${gradeColor(pandse?.grade)}`}>{pandse?.grade}</span>
          </div>
          {(() => {
            const idx = pandse?.index || 50;
            const delta = idx - 50;
            const color = idx >= 55 ? "text-emerald-400" : idx <= 45 ? "text-rose-500" : "text-cyan-400";
            const barColor = idx >= 55 ? "#10b981" : idx <= 45 ? "#ef4444" : "#06b6d4";
            const direction = delta > 0 ? "김경수 유리" : delta < 0 ? "박완수 유리" : "중립";
            return (
              <>
                <div className="text-center mb-2">
                  <div className={`text-[28px] font-black wr-metric leading-none pulse ${color}`}>
                    {idx.toFixed(1)}<span className="text-[9px] text-gray-500 ml-0.5">pt</span>
                  </div>
                  <div className={`text-[9px] font-bold mt-0.5 gap-blink ${delta > 0 ? "text-blue-400" : delta < 0 ? "text-red-400" : "text-gray-400"}`}>
                    {direction} ({delta > 0 ? "+" : ""}{delta.toFixed(1)})
                  </div>
                </div>
                {/* 게이지 바 */}
                <div className="relative h-3 bg-[#0e1825] rounded-full overflow-hidden mb-2">
                  <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-600 z-10" />
                  <div className="flex h-full">
                    <div className="bg-red-900/40" style={{ width: "50%" }} />
                    <div className="bg-blue-900/40" style={{ width: "50%" }} />
                  </div>
                  {/* 인디케이터 */}
                  <div
                    className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2 z-20 pulse"
                    style={{
                      left: `${idx}%`,
                      transform: `translate(-50%, -50%)`,
                      backgroundColor: barColor,
                      borderColor: barColor,
                      boxShadow: `0 0 6px ${barColor}80`,
                    }}
                  />
                </div>
                <div className="flex justify-between text-[7px] text-gray-600">
                  <span className="text-red-400/60">← 박 유리</span>
                  <span>50</span>
                  <span className="text-blue-400/60">김 유리 →</span>
                </div>
              </>
            );
          })()}
          <div className="text-[7px] text-gray-600 leading-relaxed mt-1">
            9개 독립 팩터 기반. 50pt = 중립. D-{pandse?.d_day||"?"}
          </div>
          {/* 판세 변동 Alert */}
          {(indices as any)?.pandse_alert && (() => {
            const alert = (indices as any).pandse_alert;
            const isUp = alert.direction === "up";
            return (
              <div className="mt-2 bg-amber-950/20 border border-amber-700/40 rounded-lg px-2 py-1.5 alert-flash">
                <div className="flex items-center gap-1 mb-0.5">
                  <span className="text-[9px]">⚡</span>
                  <span className={`text-[9px] font-black ${isUp ? "text-cyan-400" : "text-rose-400"}`}>
                    {alert.delta > 0 ? "+" : ""}{alert.delta?.toFixed(1)}pt 변동 감지
                  </span>
                </div>
                <div className="text-[8px] text-amber-300/90 leading-relaxed">
                  🤖 {alert.memo}
                </div>
              </div>
            );
          })()}
          {candidateTrend.length >= 2 && <MiniChart data={candidateTrend} field="pandse" color="#06b6d4" label="판세" />}
        </div>
      </div>
    </div>
  );
}

function DualChart({ data, kimField, parkField }: { data: any[]; kimField: string; parkField: string }) {
  const n = data.length;
  const w = 220, h = 55, pl = 4, pr = 4, pt = 6, pb = 14;
  const kimVals = data.map(d => d[kimField] || 0);
  const parkVals = data.map(d => d[parkField] || 0);
  const allVals = [...kimVals, ...parkVals];
  if (allVals.every(v => v === 0)) return null;
  const mn = Math.min(...allVals) - 3, mx = Math.max(...allVals) + 3, rng = mx - mn || 1;
  const xs = (w - pl - pr) / Math.max(n - 1, 1);
  const Y = (v: number) => pt + (1 - (v - mn) / rng) * (h - pt - pb);

  // 라인 길이 계산
  const calcLen = (vals: number[]) => {
    let l = 0;
    for (let i = 1; i < vals.length; i++) {
      const dx = xs, dy = Y(vals[i]) - Y(vals[i-1]);
      l += Math.sqrt(dx*dx + dy*dy);
    }
    return Math.ceil(l);
  };
  const kimLen = calcLen(kimVals);
  const parkLen = calcLen(parkVals);

  return (
    <div className="mt-2">
      <svg width="100%" viewBox={`0 0 ${w} ${h}`}>
        <style>{`
          .dual-kim { stroke-dasharray:${kimLen}; stroke-dashoffset:${kimLen}; animation: drawLine 1.2s ease-out 0.3s forwards; }
          .dual-park { stroke-dasharray:${parkLen}; stroke-dashoffset:${parkLen}; animation: drawLine 1.2s ease-out 0.5s forwards; }
          .dual-dot { opacity:0; animation: dotFade 0.3s ease-out forwards; }
          @keyframes drawLine { to { stroke-dashoffset:0; } }
          @keyframes dotFade { to { opacity:1; } }
        `}</style>
        {/* 격차 영역 (반투명) */}
        <polygon
          points={kimVals.map((v,i)=>`${pl+i*xs},${Y(v)}`).join(" ") + " " + [...parkVals].reverse().map((v,i)=>`${pl+(n-1-i)*xs},${Y(v)}`).join(" ")}
          fill={kimVals[n-1] > parkVals[n-1] ? "rgba(37,99,235,0.06)" : "rgba(239,68,68,0.06)"}
          className="dual-dot" style={{animationDelay:"1s"}}
        />
        <polyline points={parkVals.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ")} fill="none" stroke="#ef4444" strokeWidth="1.5" strokeLinejoin="round" opacity="0.7" strokeDasharray="3,2" className="dual-park" />
        <polyline points={kimVals.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ")} fill="none" stroke="#2563eb" strokeWidth="2" strokeLinejoin="round" className="dual-kim" />
        {kimVals.map((v, i) => (
          <circle key={`k${i}`} cx={pl + i * xs} cy={Y(v)} r={i === n - 1 ? 3 : 1} fill={i === n - 1 ? "#2563eb" : "#1e3a5f"} className="dual-dot" style={{animationDelay:`${0.8+i*0.1}s`}} />
        ))}
        {parkVals.map((v, i) => (
          <circle key={`p${i}`} cx={pl + i * xs} cy={Y(v)} r={i === n - 1 ? 2.5 : 1} fill={i === n - 1 ? "#ef4444" : "#5b2130"} className="dual-dot" style={{animationDelay:`${0.9+i*0.1}s`}} />
        ))}
        <text x={pl + (n - 1) * xs + 3} y={Y(kimVals[n - 1]) + 3} fill="#2563eb" fontSize="7" fontWeight="bold" fontFamily="monospace" className="dual-dot" style={{animationDelay:"1.5s"}}>{kimVals[n - 1]}</text>
        <text x={pl + (n - 1) * xs + 3} y={Y(parkVals[n - 1]) + 3} fill="#ef4444" fontSize="7" fontWeight="bold" fontFamily="monospace" className="dual-dot" style={{animationDelay:"1.5s"}}>{parkVals[n - 1]}</text>
        {data.map((d, i) => (
          i % Math.max(1, Math.floor(n / 4)) === 0 || i === n - 1 ? (
            <text key={i} x={pl + i * xs} y={h - 2} fill="#4b5563" fontSize="5" textAnchor="middle" fontFamily="monospace" className="dual-dot" style={{animationDelay:`${1+i*0.05}s`}}>{(d.date || "").slice(0, 5)}</text>
          ) : null
        ))}
      </svg>
      <div className="flex justify-end gap-2 text-[6px] mt-0.5">
        <span className="flex items-center gap-0.5"><span className="w-2 h-[2px] bg-blue-500 inline-block" />김경수</span>
        <span className="flex items-center gap-0.5"><span className="w-2 h-[2px] bg-red-500 inline-block opacity-60" />박완수</span>
      </div>
    </div>
  );
}

function MiniChart({ data, field, color, label }: { data: any[]; field: string; color: string; label: string }) {
  const n = data.length;
  const w = 220, h = 50, pl = 4, pr = 4, pt = 6, pb = 14;
  const vals = data.map(d => d[field] || 0);
  if (vals.every(v => v === 0)) return null;
  const mn = Math.min(...vals) - 3, mx = Math.max(...vals) + 3, rng = mx - mn || 1;
  const xs = (w - pl - pr) / Math.max(n - 1, 1);
  const Y = (v: number) => pt + (1 - (v - mn) / rng) * (h - pt - pb);

  return (
    <div className="mt-2">
      <svg width="100%" viewBox={`0 0 ${w} ${h}`}>
        <polyline points={vals.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ")} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" opacity="0.7" />
        {vals.map((v, i) => (
          <g key={i}>
            <circle cx={pl + i * xs} cy={Y(v)} r={i === n - 1 ? 2.5 : 1} fill={i === n - 1 ? color : "#0e4158"} />
            <text x={pl + i * xs} y={h - 2} fill="#4b5563" fontSize="6" textAnchor="middle" fontFamily="monospace">{(data[i].date || "").slice(5)}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}
