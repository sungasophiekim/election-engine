"use client";
import { useEffect, useState } from "react";
import { getRegions, getV2Enrichment, getOrgScan, getIssueResponses } from "@/lib/api";
import { useAppStore } from "@/lib/store";

// ════════════════════════════════════════════════════════════════════
// 지역/조직 전략 패널 — 3-Panel Layout
// Panel 1: 지역 전투맵 (Region Battle Map)
// Panel 2: 세그먼트 대시보드 (Segment Shift)
// Panel 3: 조직 시그널 타임라인 (Org Movement)
// ════════════════════════════════════════════════════════════════════

const REGION_LAYOUT = [
  ["밀양시", "양산시"],
  ["함안군", "창원시", "김해시"],
  ["의령군", "진주시", "거제시"],
  ["산청군", "사천시", "통영시"],
  ["합천군", "거창군", "하동군", "남해군"],
  ["함양군", "창녕군", "고성군"],
];

export function RegionsPage() {
  const [regions, setRegions] = useState<any[]>([]);
  const [enrichment, setEnrichment] = useState<any>(null);
  const [orgData, setOrgData] = useState<any>(null);
  const [issues, setIssues] = useState<any>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const candidate = useAppStore((s) => s.candidate) || "김경수";
  const opponent = useAppStore((s) => s.opponent) || "박완수";

  useEffect(() => {
    getRegions().then((d) => setRegions(Array.isArray(d) ? d : d?.regions || [])).catch(() => {});
    getV2Enrichment().then(setEnrichment).catch(() => {});
    getOrgScan().then(setOrgData).catch(() => {});
    getIssueResponses().then(setIssues).catch(() => {});
  }, []);

  const getRegion = (name: string) => regions.find((r: any) => r.region === name);
  const maxPriority = Math.max(...regions.map((r: any) => r.priority_score || 0), 0.01);
  const segments = enrichment?.segments || {};
  const orgSignals = orgData?.results || [];
  const resp = issues?.responses || [];

  // 후보별 이슈 분류
  const ourIssues = resp.filter((r: any) => r.keyword?.includes(candidate));
  const oppIssues = resp.filter((r: any) => r.keyword?.includes(opponent));

  // 세그먼트 집계
  const segmentAgg = aggregateSegments(segments);

  return (
    <div className="space-y-1.5">

      {/* ═══ PANEL 1: 지역 전투맵 + 후보 비교 ═══ */}
      <div className="grid grid-cols-12 gap-1.5">
        {/* Battle Map (7/12) */}
        <div className="col-span-7 wr-card">
          <div className="wr-card-header flex items-center justify-between">
            <span>지역 전투맵</span>
            <div className="flex items-center gap-2 text-[8px] normal-case tracking-normal">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" />경합 높음</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-500" />경합 중</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" />경합 낮음</span>
            </div>
          </div>
          <div className="p-3 space-y-1.5">
            {REGION_LAYOUT.map((row, ri) => (
              <div key={ri} className="flex gap-1.5 justify-center">
                {row.map((name) => {
                  const r = getRegion(name);
                  if (!r) return <div key={name} className="w-20 h-14 rounded bg-[#0a1019] border border-[#1a2844] flex items-center justify-center text-[9px] text-gray-700">{name.replace("시","").replace("군","")}</div>;
                  const swing = r.swing_index || 0;
                  const isActive = selected === name;
                  const isMetro = name === "창원시";
                  const borderColor = swing >= 0.65 ? "border-red-500/60" : swing >= 0.45 ? "border-yellow-500/40" : "border-blue-500/30";
                  const bgColor = swing >= 0.65 ? "bg-red-950/30" : swing >= 0.45 ? "bg-yellow-950/20" : "bg-blue-950/20";
                  const size = Math.max(14, Math.min(20, r.voter_count * 0.2));
                  return (
                    <button key={name} onClick={() => setSelected(name)}
                      className={`${isMetro ? "w-28" : "w-20"} h-14 rounded-lg border transition-all flex flex-col items-center justify-center
                        ${isActive ? "ring-1 ring-blue-400 " : ""}${borderColor} ${bgColor} hover:brightness-125`}>
                      <span className="text-white font-bold text-[10px]">{name.replace("시","").replace("군","")}</span>
                      <span className="text-gray-400 text-[8px]">{r.voter_count}만</span>
                      <span className={`text-[7px] font-mono ${swing >= 0.65 ? "text-red-400" : swing >= 0.45 ? "text-yellow-400" : "text-blue-400"}`}>
                        경합 {(swing * 100).toFixed(0)}
                      </span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>

        {/* Region Detail + 후보 비교 (5/12) */}
        <div className="col-span-5 wr-card">
          <div className="wr-card-header">{selected ? `📍 ${selected}` : "지역 선택"}</div>
          {selected && (() => {
            const r = getRegion(selected);
            if (!r) return <div className="p-3 text-gray-700 text-xs">데이터 없음</div>;
            return (
              <div className="p-3 space-y-2.5">
                {/* 기본 정보 */}
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div><div className="text-[8px] text-gray-600">유권자</div><div className="text-sm font-bold text-white">{r.voter_count}만</div></div>
                  <div><div className="text-[8px] text-gray-600">인구</div><div className="text-sm font-bold text-white">{(r.population || 0).toLocaleString()}</div></div>
                  <div><div className="text-[8px] text-gray-600">유형</div><div className="text-sm font-bold text-white">{r.type || "-"}</div></div>
                </div>

                {/* 2018 김경수 득표 비교 바 */}
                <div>
                  <div className="text-[8px] text-gray-600 mb-1">2018 도지사 (김경수 당선)</div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] text-blue-400 w-16 text-right">김경수 {(r["2018_kim_pct"] || 0).toFixed(1)}%</span>
                    <div className="flex-1 h-2 rounded-full overflow-hidden flex bg-[#0a1019]">
                      <div className="h-full bg-blue-500 rounded-l-full" style={{ width: `${r["2018_kim_pct"] || 0}%` }} />
                      <div className="h-full bg-red-500 rounded-r-full" style={{ width: `${r["2018_opp_pct"] || 0}%` }} />
                    </div>
                    <span className="text-[9px] text-red-400 w-16">김태호 {(r["2018_opp_pct"] || 0).toFixed(1)}%</span>
                  </div>
                </div>

                {/* 2022 양문석 vs 박완수 */}
                <div>
                  <div className="text-[8px] text-gray-600 mb-1">2022 도지사 (박완수 당선)</div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] text-blue-400 w-16 text-right">양문석 {(r["2022_yang_pct"] || 0).toFixed(1)}%</span>
                    <div className="flex-1 h-2 rounded-full overflow-hidden flex bg-[#0a1019]">
                      <div className="h-full bg-blue-500 rounded-l-full" style={{ width: `${r["2022_yang_pct"] || 0}%` }} />
                      <div className="h-full bg-red-500 rounded-r-full" style={{ width: `${r["2022_park_pct"] || 0}%` }} />
                    </div>
                    <span className="text-[9px] text-red-400 w-16">{opponent} {(r["2022_park_pct"] || 0).toFixed(1)}%</span>
                  </div>
                </div>

                {/* 변화 분석 */}
                {r["2018_kim_pct"] > 0 && r["2022_yang_pct"] > 0 && (() => {
                  const swing = (r["2018_kim_pct"] || 0) - (r["2022_yang_pct"] || 0);
                  return (
                    <div className={`text-[9px] px-2 py-1 rounded border ${
                      swing > 20 ? "bg-red-950/20 border-red-800/30 text-red-400" :
                      swing > 10 ? "bg-orange-950/20 border-orange-800/30 text-orange-400" :
                      "bg-blue-950/20 border-blue-800/30 text-blue-400"
                    }`}>
                      민주당 이탈폭: {swing.toFixed(1)}%p {swing > 20 ? "— 대규모 이탈" : swing > 10 ? "— 상당한 이탈" : "— 소폭 이탈"}
                    </div>
                  );
                })()}

                {/* 경합도 + 우선순위 */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-[#0a1019] rounded p-2">
                    <div className="text-[8px] text-gray-600">경합도</div>
                    <div className={`text-lg font-bold ${(r.swing_index || 0) >= 0.65 ? "text-red-400" : (r.swing_index || 0) >= 0.45 ? "text-yellow-400" : "text-blue-400"}`}>
                      {((r.swing_index || 0) * 100).toFixed(0)}
                    </div>
                  </div>
                  <div className="bg-[#0a1019] rounded p-2">
                    <div className="text-[8px] text-gray-600">전략 우선순위</div>
                    <div className="text-lg font-bold text-white">{(r.priority_score || 0).toFixed(2)}</div>
                  </div>
                </div>

                {/* 핵심 이슈 */}
                <div>
                  <div className="text-[8px] text-gray-600 mb-0.5">핵심 이슈</div>
                  <div className="text-[10px] text-gray-300">{r.key_issue || "-"}</div>
                </div>

                {/* 이 지역 관련 이슈 반응 */}
                {resp.filter((is: any) => is.keyword?.includes(selected.replace("시","").replace("군",""))).length > 0 && (
                  <div>
                    <div className="text-[8px] text-gray-600 mb-0.5">관련 이슈</div>
                    {resp.filter((is: any) => is.keyword?.includes(selected.replace("시","").replace("군",""))).slice(0, 3).map((is: any, i: number) => (
                      <div key={i} className="flex items-center justify-between text-[9px] py-0.5">
                        <span className="text-gray-300">{is.keyword}</span>
                        <span className={`font-mono ${is.level === "CRISIS" ? "text-red-400" : "text-gray-500"}`}>{is.score?.toFixed(0)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })()}
          {!selected && (
            <div className="p-4 text-center text-gray-700 text-xs">맵에서 지역을 클릭하세요</div>
          )}
        </div>
      </div>

      {/* ═══ PANEL 2: 세그먼트 대시보드 ═══ */}
      <div className="grid grid-cols-12 gap-1.5">
        <div className="col-span-7 wr-card">
          <div className="wr-card-header flex items-center justify-between">
            <span>유권자 세그먼트 반응</span>
            <div className="flex items-center gap-3 text-[8px] normal-case tracking-normal">
              <span className="text-blue-400">{candidate}</span>
              <span className="text-gray-600">vs</span>
              <span className="text-red-400">{opponent}</span>
            </div>
          </div>
          <div className="divide-y divide-[#0e1825]">
            {segmentAgg.map((seg, i) => (
              <div key={i} className="flex items-center gap-2 px-3 py-[7px]">
                <span className="w-20 text-[10px] text-gray-300 font-bold truncate">{seg.label}</span>
                {/* 반응 바 */}
                <div className="flex-1 flex items-center gap-1">
                  <div className="flex-1 h-[6px] bg-[#0a1019] rounded-full overflow-hidden flex">
                    <div className="h-full bg-blue-500 rounded-l-full" style={{ width: `${seg.ourPct}%` }} />
                    <div className="h-full bg-red-500 rounded-r-full" style={{ width: `${seg.oppPct}%` }} />
                  </div>
                </div>
                <span className={`text-[9px] font-mono w-6 text-right ${seg.ourPct > seg.oppPct ? "text-blue-400" : "text-red-400"}`}>
                  {seg.intensity.toFixed(0)}
                </span>
                <span className={`text-[8px] w-5 ${seg.direction === "positive" ? "text-emerald-400" : seg.direction === "negative" ? "text-red-400" : "text-gray-600"}`}>
                  {seg.direction === "positive" ? "▲" : seg.direction === "negative" ? "▼" : "●"}
                </span>
                <span className="text-[8px] text-gray-600 w-12 truncate">{seg.topIssue}</span>
              </div>
            ))}
            {segmentAgg.length === 0 && <div className="p-4 text-center text-gray-700 text-xs">전략 갱신 후 표시</div>}
          </div>
        </div>

        {/* 세그먼트 × 지역 매트릭스 (5/12) */}
        <div className="col-span-5 wr-card">
          <div className="wr-card-header">세그먼트 × 지역</div>
          <div className="p-2 overflow-x-auto">
            <table className="w-full text-[8px]">
              <thead>
                <tr className="text-gray-600">
                  <th className="text-left py-1 px-1">세그먼트</th>
                  {["창원", "김해", "진주", "거제", "양산"].map((r) => (
                    <th key={r} className="text-center py-1 px-1">{r}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {segmentAgg.slice(0, 6).map((seg, i) => (
                  <tr key={i} className="border-t border-[#0e1825]">
                    <td className="py-1 px-1 text-gray-400">{seg.label.split(" ")[0]}</td>
                    {["창원", "김해", "진주", "거제", "양산"].map((region) => {
                      const val = seg.regionDist?.[region] || 0;
                      const cellColor = val > 50 ? "text-emerald-400 font-bold" : val > 20 ? "text-blue-400" : "text-gray-700";
                      return <td key={region} className={`text-center py-1 px-1 font-mono ${cellColor}`}>{val > 0 ? val.toFixed(0) : "·"}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ═══ PANEL 3: 조직 시그널 ═══ */}
      <div className="grid grid-cols-12 gap-1.5">
        <div className="col-span-8 wr-card">
          <div className="wr-card-header flex items-center justify-between">
            <span>조직 움직임</span>
            {orgData && (
              <span className="text-[8px] normal-case tracking-normal text-gray-500">
                {orgData.org_database}개 단체 스캔 · {orgData.with_signals}건 감지
              </span>
            )}
          </div>
          <div className="divide-y divide-[#0e1825] max-h-[300px] overflow-y-auto feed-scroll">
            {orgSignals.length > 0 ? orgSignals.map((summary: any, si: number) => (
              <div key={si} className="px-3 py-2">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] text-blue-400 font-bold">{summary.keyword}</span>
                  <span className="text-[8px] text-gray-600">
                    지지:{summary.endorsement} 철회:{summary.withdrawal} 성명:{summary.statement} 연대:{summary.alliance}
                  </span>
                </div>
                {(summary.signals || []).slice(0, 5).map((sig: any, i: number) => {
                  const stanceIcon = sig.stance === "support" ? "🟢" : sig.stance === "oppose" ? "🔴" : "🟡";
                  const typeLabel: Record<string, string> = {
                    endorsement: "지지", withdrawal: "철회", protest: "규탄",
                    alliance: "연대", meeting: "간담", statement: "성명",
                  };
                  const isOur = sig.candidate_linked;
                  const isOpp = sig.opponent_linked;
                  return (
                    <div key={i} className="flex items-center gap-2 text-[9px] py-0.5">
                      <span>{stanceIcon}</span>
                      <span className="text-gray-200 font-bold">{sig.organization_name}</span>
                      <span className={`text-[8px] px-1 rounded ${
                        sig.movement_type === "endorsement" ? "bg-emerald-950/40 text-emerald-400" :
                        sig.movement_type === "withdrawal" ? "bg-red-950/40 text-red-400" :
                        "bg-gray-800/40 text-gray-400"
                      }`}>{typeLabel[sig.movement_type] || sig.movement_type}</span>
                      {sig.region && <span className="text-gray-600">📍{sig.region}</span>}
                      <span className="text-gray-600 font-mono">영향력:{sig.influence_score?.toFixed(0)}</span>
                      {isOur && <span className="text-blue-400 text-[8px]">→{candidate}</span>}
                      {isOpp && <span className="text-red-400 text-[8px]">→{opponent}</span>}
                    </div>
                  );
                })}
              </div>
            )) : (
              <div className="p-6 text-center text-gray-700 text-xs">
                조직 움직임 미감지 — 전략 갱신 또는 선거 기간 접근 시 활성화
              </div>
            )}
          </div>
        </div>

        {/* 카테고리별 영향력 요약 (4/12) */}
        <div className="col-span-4 wr-card">
          <div className="wr-card-header">조직 카테고리별</div>
          <div className="p-3 space-y-2">
            {[
              { type: "labor", label: "노동", icon: "🔧" },
              { type: "business", label: "경제", icon: "💼" },
              { type: "religion", label: "종교", icon: "⛪" },
              { type: "civic", label: "시민", icon: "🏛" },
              { type: "education", label: "교육", icon: "📚" },
              { type: "local", label: "지역", icon: "📍" },
            ].map((cat) => {
              const catSignals = orgSignals.flatMap((s: any) =>
                (s.signals || []).filter((sig: any) => sig.organization_type === cat.type)
              );
              const totalInfluence = catSignals.reduce((sum: number, s: any) => sum + (s.influence_score || 0), 0);
              const supportCount = catSignals.filter((s: any) => s.stance === "support").length;
              const opposeCount = catSignals.filter((s: any) => s.stance === "oppose").length;
              const maxInfluence = 50;
              return (
                <div key={cat.type}>
                  <div className="flex items-center justify-between text-[9px]">
                    <span className="text-gray-400">{cat.icon} {cat.label}</span>
                    <div className="flex items-center gap-1.5">
                      {supportCount > 0 && <span className="text-emerald-400">+{supportCount}</span>}
                      {opposeCount > 0 && <span className="text-red-400">-{opposeCount}</span>}
                      <span className="text-gray-500 font-mono w-6 text-right">{totalInfluence.toFixed(0)}</span>
                    </div>
                  </div>
                  <div className="h-1.5 bg-[#0a1019] rounded-full overflow-hidden mt-0.5">
                    <div className="h-full rounded-full" style={{
                      width: `${Math.min(100, (totalInfluence / maxInfluence) * 100)}%`,
                      background: supportCount > opposeCount ? "#22c55e" : opposeCount > 0 ? "#ef4444" : "#3b82f6",
                    }} />
                  </div>
                </div>
              );
            })}
          </div>

          {/* 후보별 순 영향력 */}
          <div className="px-3 pb-3 pt-1 border-t border-[#0e1825]">
            <div className="text-[8px] text-gray-600 uppercase tracking-widest mb-1.5">순 조직 영향력</div>
            {(() => {
              const allSigs = orgSignals.flatMap((s: any) => s.signals || []);
              const ourInfluence = allSigs.filter((s: any) => s.stance === "support").reduce((sum: number, s: any) => sum + (s.influence_score || 0), 0);
              const oppInfluence = allSigs.filter((s: any) => s.stance === "oppose").reduce((sum: number, s: any) => sum + (s.influence_score || 0), 0);
              const net = ourInfluence - oppInfluence;
              return (
                <div className="flex items-center gap-2">
                  <span className="text-blue-400 text-[9px]">{candidate}</span>
                  <div className="flex-1 h-2 bg-[#0a1019] rounded-full overflow-hidden flex">
                    <div className="h-full bg-blue-500 rounded-l-full" style={{ width: `${ourInfluence / Math.max(ourInfluence + oppInfluence, 1) * 100}%` }} />
                    <div className="h-full bg-red-500 rounded-r-full" style={{ width: `${oppInfluence / Math.max(ourInfluence + oppInfluence, 1) * 100}%` }} />
                  </div>
                  <span className="text-red-400 text-[9px]">{opponent}</span>
                </div>
              );
            })()}
          </div>
        </div>
      </div>

      {/* ═══ 지역 우선순위 테이블 ═══ */}
      <div className="wr-card">
        <div className="wr-card-header flex items-center justify-between">
          <span>전체 지역 우선순위</span>
          <span className="text-[8px] normal-case tracking-normal text-gray-500">{regions.length}개 시군</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-gray-600 border-b border-[#1a2844]">
                <th className="text-left py-1.5 px-2">순위</th>
                <th className="text-left py-1.5 px-2">지역</th>
                <th className="text-right py-1.5 px-2">유권자</th>
                <th className="text-right py-1.5 px-2">인구</th>
                <th className="text-center py-1.5 px-2">유형</th>
                <th className="text-right py-1.5 px-2">경합도</th>
                <th className="text-center py-1.5 px-2">2018 김경수</th>
                <th className="text-center py-1.5 px-2">2022 양문석</th>
                <th className="text-center py-1.5 px-2">2022 {opponent}</th>
                <th className="text-right py-1.5 px-2">우선순위</th>
              </tr>
            </thead>
            <tbody>
              {regions.map((r: any, i: number) => (
                  <tr key={i}
                    onClick={() => setSelected(r.region)}
                    className={`border-b border-[#0e1825] cursor-pointer hover:bg-white/[0.02] ${selected === r.region ? "bg-blue-950/20" : ""}`}>
                    <td className="py-1.5 px-2 text-gray-500">{i + 1}</td>
                    <td className="py-1.5 px-2 text-white font-bold">{r.region}</td>
                    <td className="py-1.5 px-2 text-right text-gray-400">{r.voter_count}만</td>
                    <td className="py-1.5 px-2 text-right text-gray-500">{(r.population || 0).toLocaleString()}</td>
                    <td className="py-1.5 px-2 text-center">
                      <span className={`text-[8px] px-1.5 rounded ${
                        r.type === "metro" ? "bg-blue-950/40 text-blue-400" :
                        r.type === "city" ? "bg-emerald-950/40 text-emerald-400" :
                        "bg-gray-800/40 text-gray-500"
                      }`}>{r.type || "-"}</span>
                    </td>
                    <td className={`py-1.5 px-2 text-right font-mono ${(r.swing_index || 0) >= 0.65 ? "text-red-400 font-bold" : (r.swing_index || 0) >= 0.45 ? "text-yellow-400" : "text-gray-500"}`}>
                      {((r.swing_index || 0) * 100).toFixed(0)}
                    </td>
                    <td className="py-1.5 px-2 text-center text-blue-400 font-mono">{(r["2018_kim_pct"] || 0).toFixed(1)}%</td>
                    <td className="py-1.5 px-2 text-center text-blue-300 font-mono">{(r["2022_yang_pct"] || 0).toFixed(1)}%</td>
                    <td className="py-1.5 px-2 text-center text-red-400 font-mono">{(r["2022_park_pct"] || 0).toFixed(1)}%</td>
                    <td className="py-1.5 px-2 text-right font-mono text-white font-bold">{(r.priority_score || 0).toFixed(3)}</td>
                  </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}


// ════════════════════════════════════════════════════════════════════
// Helper: 세그먼트 집계
// ════════════════════════════════════════════════════════════════════

function aggregateSegments(segments: Record<string, any>) {
  const segMap: Record<string, { label: string; total: number; positive: number; negative: number; issues: string[]; regions: Record<string, number> }> = {};

  for (const [keyword, data] of Object.entries(segments)) {
    for (const seg of (data as any)?.segments || []) {
      const label = seg.label || seg.age_group || "unknown";
      if (!segMap[label]) {
        segMap[label] = { label, total: 0, positive: 0, negative: 0, issues: [], regions: {} };
      }
      segMap[label].total += seg.confidence || 0;
      if (!segMap[label].issues.includes(keyword)) {
        segMap[label].issues.push(keyword);
      }
      // region distribution
      const rd = (data as any)?.region_distribution || {};
      for (const [region, pct] of Object.entries(rd)) {
        segMap[label].regions[region] = (segMap[label].regions[region] || 0) + (pct as number) * (seg.confidence || 0) * 100;
      }
    }
  }

  return Object.values(segMap)
    .sort((a, b) => b.total - a.total)
    .slice(0, 8)
    .map((s) => ({
      label: s.label,
      intensity: s.total * 10,
      ourPct: Math.min(90, 40 + s.total * 5),
      oppPct: Math.max(10, 60 - s.total * 5),
      direction: s.total > 1 ? "positive" : "neutral" as string,
      topIssue: s.issues[0]?.split(" ").pop() || "",
      regionDist: s.regions,
    }));
}
