"use client";
import { useEffect, useState, useCallback } from "react";
import { getPollingHistory, syncNesdcPolls, getV2Enrichment, getIndexTrend, getAutoPolls } from "@/lib/api";
import { POLL_DATA, mergeAutoPolls } from "@/lib/pollData";

export function PollingPage() {
  const [data, setData] = useState<any>(null);
  const [enrichment, setEnrichment] = useState<any>(null);
  const [trendData, setTrendData] = useState<any[]>([]);
  const [autoPolls, setAutoPolls] = useState<any[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<any>(null);
  const [tab, setTab] = useState("polling");

  const load = useCallback(() => {
    getPollingHistory().then(setData).catch(() => {});
    getV2Enrichment().then(setEnrichment).catch(() => {});
    getIndexTrend(30).then(r => setTrendData(r?.trend || [])).catch(() => {});
    getAutoPolls().then(d => setAutoPolls(d?.polls || [])).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const r = await syncNesdcPolls();
      setSyncResult(r);
      load();
    } catch {
      setSyncResult({ error: "동기화 실패" });
    } finally {
      setSyncing(false);
    }
  };

  if (!data) return <div className="text-center py-8 text-gray-500">로딩...</div>;

  const polls = data.polls || [];
  const wp = data.win_prob;
  const trend = data.trend;

  return (
    <div className="space-y-3 max-w-6xl mx-auto">
      {/* Tab Header */}
      <div className="flex items-center gap-2 px-1">
        {[
          { id: "polling", label: "📊 여론조사" },
          { id: "index-trend", label: "📈 인덱스 추세" },
          { id: "accuracy", label: "🎯 예측 정확도" },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 rounded text-[10px] font-bold transition ${
              tab === t.id
                ? "bg-blue-600/30 text-blue-400 border border-blue-500/40"
                : "text-gray-600 hover:text-gray-400 border border-transparent"
            }`}>{t.label}</button>
        ))}
      </div>

      {tab === "polling" && (
      <div className="space-y-4">

      {/* 역대 득표율 + 여론조사 통합 차트 */}
      <div className="wr-card">
        <div className="wr-card-header flex justify-between">
          <span>역대 지선 득표율 + 9대 여론조사</span>
          <span className="text-[8px] text-gray-600 normal-case tracking-normal font-normal">6기~8기 실제 득표 + 2025.09~2026.03 여론조사</span>
        </div>
        <div className="p-3">
          <HistoricalPollChart autoPolls={autoPolls} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 모멘텀 */}
        <div className="bg-bg-card border border-border rounded-lg p-4 text-center">
          <h3 className="text-blue-400 text-sm font-semibold mb-2">모멘텀</h3>
          {trend && (
            <>
              <div className={`text-3xl font-bold ${trend.momentum === "gaining" ? "text-green-400" : trend.momentum === "losing" ? "text-red-400" : "text-yellow-400"}`}>
                {trend.momentum === "gaining" ? "상승" : trend.momentum === "losing" ? "하락" : "유지"}
              </div>
              <div className="text-sm text-gray-500 mt-2">
                일일 변화: <span className={trend.our_trend >= 0 ? "text-green-400" : "text-red-400"}>
                  {trend.our_trend >= 0 ? "+" : ""}{trend.our_trend?.toFixed(2)}%p
                </span>
              </div>
            </>
          )}
        </div>

        {/* 부동층 */}
        {data.swing && (
          <div className="bg-bg-card border border-border rounded-lg p-4 text-center">
            <h3 className="text-blue-400 text-sm font-semibold mb-2">부동층</h3>
            <div className="text-3xl font-bold text-yellow-400">{data.swing.undecided_pct?.toFixed(1)}%</div>
            <div className="text-xs text-gray-500 mt-2">{data.swing.strategy || ""}</div>
          </div>
        )}
      </div>

      {/* 조사 테이블 */}
      <div className="bg-bg-card border border-border rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-blue-400 text-sm font-semibold">조사 이력</h3>
          <div className="flex items-center gap-2">
            {syncResult && !syncResult.error && (
              <span className="text-xs text-green-400">
                {syncResult.parsed}건 수집 완료
              </span>
            )}
            {syncResult?.error && (
              <span className="text-xs text-red-400">{syncResult.error}</span>
            )}
            <button
              onClick={handleSync}
              disabled={syncing}
              className="px-3 py-1 text-xs bg-blue-600/20 text-blue-400 border border-blue-600/40 rounded hover:bg-blue-600/30 disabled:opacity-50 transition-colors"
            >
              {syncing ? "수집 중..." : "nesdc 동기화"}
            </button>
          </div>
        </div>
        <div className="text-xs text-gray-600 mb-3">
          출처: 중앙선거여론조사심의위원회 (nesdc.go.kr)
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-border">
                <th className="text-left py-2">날짜</th>
                <th className="text-left py-2">조사기관</th>
                <th className="text-left py-2">출처</th>
                <th className="text-right py-2">우리</th>
                <th className="text-right py-2">상대</th>
                <th className="text-right py-2">격차</th>
                <th className="text-right py-2">오차</th>
              </tr>
            </thead>
            <tbody>
              {[...polls].reverse().map((p: any, i: number) => {
                const oppVal = p.opponent ? (Object.values(p.opponent)[0] as number) || 0 : 0;
                const diff = p.our - oppVal;
                const source = parseSource(p.pollster);
                return (
                  <tr key={i} className="border-b border-border/50 hover:bg-white/[0.02]">
                    <td className="py-1.5 text-gray-400 whitespace-nowrap">{p.date}</td>
                    <td className="py-1.5 text-gray-300">{source.name}</td>
                    <td className="py-1.5">
                      {source.nesdcId ? (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
                          nesdc:{source.nesdcId}
                        </span>
                      ) : (
                        <span className="text-[10px] text-gray-600">수동</span>
                      )}
                    </td>
                    <td className="py-1.5 text-right text-green-400 font-bold">{p.our}%</td>
                    <td className="py-1.5 text-right text-red-400 font-bold">{oppVal}%</td>
                    <td className={`py-1.5 text-right font-bold ${diff >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {diff >= 0 ? "+" : ""}{diff.toFixed(1)}
                    </td>
                    <td className="py-1.5 text-right text-gray-500">{p.moe ? `±${p.moe}` : ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      </div>
      )}

      {/* ══════════ TAB 2: 인덱스 추세 ══════════ */}
      {tab === "index-trend" && (
      <div className="space-y-3">
        {/* Leading Index 추세 차트 */}
        <div className="wr-card">
          <div className="wr-card-header flex justify-between">
            <span className="text-cyan-300">🧭 선행지수 추세</span>
            <span className="text-[8px] text-gray-600">Leading Index — 50 이상 유리, 이하 불리</span>
          </div>
          <div className="p-3">
            <LeadingIndexChart trendData={trendData} />
          </div>
        </div>

        {/* Issue × Reaction 듀얼 차트 */}
        <div className="wr-card">
          <div className="wr-card-header flex justify-between">
            <span className="text-amber-300">🔥 이슈 × 반응 추세</span>
            <span className="text-[8px] text-gray-600">이슈 크기 vs 반응 깊이 — 괴리 시 주의</span>
          </div>
          <div className="p-3">
            <IssueReactionTrendChart trendData={trendData} />
          </div>
        </div>

        {/* 예측 격차 vs 여론조사 실측 */}
        <div className="wr-card">
          <div className="wr-card-header flex justify-between">
            <span className="text-red-300">📊 예측 vs 실제</span>
            <span className="text-[8px] text-gray-600">우리 예측 라인 + 여론조사 실측 포인트</span>
          </div>
          <div className="p-3">
            <ForecastVsActualChart enrichment={enrichment} polls={polls} />
          </div>
        </div>

        {/* Attribution 추세 */}
        <div className="wr-card">
          <div className="wr-card-header flex justify-between">
            <span className="text-blue-300">🔗 귀인 신뢰도 추세</span>
            <span className="text-[8px] text-gray-600">행동 효과성 — 올라가야 좋은 것</span>
          </div>
          <div className="p-3">
            <AttributionChart enrichment={enrichment} />
          </div>
        </div>
      </div>
      )}

      {/* ══════════ TAB 3: 예측 정확도 ══════════ */}
      {tab === "accuracy" && (
      <div className="space-y-3">
        <div className="wr-card border-t-2 border-t-emerald-600">
          <div className="px-4 py-3 space-y-3">
            <h3 className="text-[13px] font-bold text-emerald-300">🎯 예측 정확도 추적</h3>
            <p className="text-[10px] text-gray-500">
              매주 여론조사가 나올 때마다 우리 예측과 비교합니다.
              오차를 줄여 여론조사보다 정확한 선행 예측을 만드는 것이 목표.
            </p>

            {/* Phase 목표 */}
            <div className="grid grid-cols-3 gap-2">
              {[
                { phase: "Phase 1", target: "5%p", desc: "데이터 축적", color: "text-gray-300", bg: "bg-gray-800/30 border-gray-700/30" },
                { phase: "Phase 2", target: "3%p", desc: "학습 보정", color: "text-amber-300", bg: "bg-amber-950/10 border-amber-800/20" },
                { phase: "Phase 3", target: "2%p", desc: "여론조사 대체", color: "text-emerald-300", bg: "bg-emerald-950/10 border-emerald-800/20" },
              ].map((p, i) => (
                <div key={i} className={`rounded-lg border p-3 text-center ${p.bg}`}>
                  <div className="text-[8px] text-gray-600">{p.phase}</div>
                  <div className={`text-xl font-black mt-0.5 ${p.color}`}>±{p.target}</div>
                  <div className="text-[8px] text-gray-500 mt-0.5">{p.desc}</div>
                </div>
              ))}
            </div>

            {/* 현재 정확도 */}
            <div className="bg-[#080d16] rounded-lg p-3">
              <div className="text-[10px] text-cyan-400 font-bold mb-2">현재 상태</div>
              <div className="text-[10px] text-gray-400">
                아직 비교 데이터가 충분하지 않습니다. 여론조사 결과가 입력될 때마다 자동으로 학습합니다.
              </div>
              <div className="mt-2 grid grid-cols-4 gap-2">
                {[
                  { label: "비교 횟수", value: "—" },
                  { label: "평균 오차", value: "—" },
                  { label: "2%p 이내", value: "—" },
                  { label: "추세", value: "축적 중" },
                ].map((m, i) => (
                  <div key={i} className="text-center">
                    <div className="text-[8px] text-gray-600">{m.label}</div>
                    <div className="text-[12px] font-bold text-gray-400 mt-0.5">{m.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* 학습 원리 */}
            <div className="bg-[#080d16] rounded-lg p-3">
              <div className="text-[10px] text-amber-400 font-bold mb-1.5">학습 원리</div>
              <div className="text-[10px] text-gray-400 leading-relaxed font-mono">
                여론조사 발표 → 우리 예측과 비교 → 오차 기록<br/>
                → 오차 패턴 분석 (어떤 상황에서 틀리는가)<br/>
                → 모델 가중치 자동 보정<br/>
                → 다음 예측에 반영 → 정확도 향상
              </div>
            </div>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════
// 차트 컴포넌트들
// ════════════════════════════════════════════════════════════════════

function LeadingIndexChart({ trendData }: { trendData: any[] }) {
  if (!trendData || trendData.length < 2) {
    return <div className="h-40 flex items-center justify-center text-gray-700 text-xs">스냅샷 데이터 축적 중 (2일 이상 필요)</div>;
  }

  const points = trendData.map(d => d.leading_index || 50);
  const dates = trendData.map(d => (d.date || "").slice(5)); // MM-DD

  const w = 650, h = 200, pl = 40, pr = 50, pt = 20, pb = 30;
  const mn = 35, mx = 65, rng = mx - mn;
  const Y = (v: number) => pt + (1 - (v - mn) / rng) * (h - pt - pb);
  const xs = (w - pl - pr) / Math.max(points.length - 1, 1);
  const lastVal = points[points.length - 1];
  const firstVal = points[0];
  const delta = lastVal - firstVal;

  return (
    <div>
      <svg width="100%" viewBox={`0 0 ${w} ${h}`}>
        {/* gaining / losing 영역 */}
        <rect x={pl} y={Y(65)} width={w - pl - pr} height={Y(57) - Y(65)} fill="#064e3b" opacity="0.08" />
        <rect x={pl} y={Y(43)} width={w - pl - pr} height={Y(35) - Y(43)} fill="#7f1d1d" opacity="0.08" />
        {/* 기준선 */}
        <line x1={pl} y1={Y(50)} x2={w - pr} y2={Y(50)} stroke="#374151" strokeWidth="1" strokeDasharray="4,4" />
        <line x1={pl} y1={Y(57)} x2={w - pr} y2={Y(57)} stroke="#10b981" strokeWidth="0.5" strokeDasharray="2,4" opacity="0.4" />
        <line x1={pl} y1={Y(43)} x2={w - pr} y2={Y(43)} stroke="#ef4444" strokeWidth="0.5" strokeDasharray="2,4" opacity="0.4" />
        {/* Y축 라벨 */}
        {[40, 45, 50, 55, 60].map(v => (
          <text key={v} x={pl - 5} y={Y(v) + 3} fill="#3f3f46" fontSize="8" textAnchor="end" fontFamily="monospace">{v}</text>
        ))}
        <text x={w - pr + 5} y={Y(57) + 3} fill="#10b981" fontSize="7">gaining</text>
        <text x={w - pr + 5} y={Y(43) + 3} fill="#ef4444" fontSize="7">losing</text>
        {/* 면적 */}
        <polygon
          points={`${pl},${Y(50)} ${points.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ")} ${pl + (points.length - 1) * xs},${Y(50)}`}
          fill={lastVal >= 50 ? "rgba(6,182,212,0.08)" : "rgba(239,68,68,0.08)"}
        />
        {/* 라인 */}
        <polyline points={points.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ")}
          fill="none" stroke="#06b6d4" strokeWidth="2.5" strokeLinejoin="round" />
        {/* 점 */}
        {points.map((v, i) => (
          <circle key={i} cx={pl + i * xs} cy={Y(v)} r={i === points.length - 1 ? 5 : 3}
            fill={v >= 57 ? "#10b981" : v <= 43 ? "#ef4444" : "#06b6d4"}
            stroke="#04070d" strokeWidth={i === points.length - 1 ? 2 : 1} />
        ))}
        {/* 값 라벨 (처음, 끝) */}
        <text x={pl} y={Y(firstVal) - 8} fill="#6b7280" fontSize="9" fontWeight="bold" textAnchor="start">{firstVal.toFixed(1)}</text>
        <text x={pl + (points.length - 1) * xs} y={Y(lastVal) - 8} fill="#06b6d4" fontSize="12" fontWeight="bold" textAnchor="end">{lastVal.toFixed(1)}</text>
        {/* X축 날짜 */}
        {dates.map((d, i) => (
          <text key={i} x={pl + i * xs} y={h - 5} fill="#3f3f46" fontSize="7" textAnchor="middle" fontFamily="monospace">{d}</text>
        ))}
      </svg>
      {/* 요약 */}
      <div className="flex items-center justify-between mt-2 px-1">
        <span className="text-[9px] text-gray-500">{trendData.length}일간 추세</span>
        <span className={`text-[10px] font-bold ${delta >= 0 ? "text-emerald-400" : "text-red-400"}`}>
          {delta > 0 ? "+" : ""}{delta.toFixed(1)} ({delta >= 2 ? "상승 추세" : delta <= -2 ? "하락 추세" : "보합"})
        </span>
      </div>
    </div>
  );
}

function IssueReactionTrendChart({ trendData }: { trendData: any[] }) {
  if (!trendData || trendData.length < 2) {
    return <div className="h-32 flex items-center justify-center text-gray-700 text-xs">스냅샷 데이터 축적 중</div>;
  }

  const issues = trendData.map(d => d.issue_index_avg || 0);
  const reactions = trendData.map(d => d.reaction_index_avg || 0);
  const dates = trendData.map(d => (d.date || "").slice(5));

  const w = 650, h = 180, pl = 40, pr = 50, pt = 15, pb = 30;
  const allVals = [...issues, ...reactions];
  const mn = Math.max(0, Math.min(...allVals) - 5);
  const mx = Math.max(...allVals) + 5;
  const rng = mx - mn || 1;
  const Y = (v: number) => pt + (1 - (v - mn) / rng) * (h - pt - pb);
  const xs = (w - pl - pr) / Math.max(trendData.length - 1, 1);

  return (
    <div>
      <svg width="100%" viewBox={`0 0 ${w} ${h}`}>
        {/* 그리드 */}
        {[0, 25, 50, 75, 100].filter(v => v >= mn && v <= mx).map(v => (
          <g key={v}>
            <line x1={pl} y1={Y(v)} x2={w - pr} y2={Y(v)} stroke="#111d30" strokeWidth="0.5" />
            <text x={pl - 5} y={Y(v) + 3} fill="#3f3f46" fontSize="8" textAnchor="end">{v}</text>
          </g>
        ))}
        {/* Issue 면적 */}
        <polygon
          points={`${pl},${Y(mn)} ${issues.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ")} ${pl + (issues.length - 1) * xs},${Y(mn)}`}
          fill="rgba(245,158,11,0.08)"
        />
        {/* Reaction 면적 */}
        <polygon
          points={`${pl},${Y(mn)} ${reactions.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ")} ${pl + (reactions.length - 1) * xs},${Y(mn)}`}
          fill="rgba(168,85,247,0.08)"
        />
        {/* 라인 */}
        <polyline points={issues.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ")}
          fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinejoin="round" />
        <polyline points={reactions.map((v, i) => `${pl + i * xs},${Y(v)}`).join(" ")}
          fill="none" stroke="#a855f7" strokeWidth="2" strokeLinejoin="round" />
        {/* 끝점 */}
        <circle cx={pl + (issues.length - 1) * xs} cy={Y(issues[issues.length - 1])} r="4" fill="#f59e0b" stroke="#04070d" strokeWidth="1.5" />
        <circle cx={pl + (reactions.length - 1) * xs} cy={Y(reactions[reactions.length - 1])} r="4" fill="#a855f7" stroke="#04070d" strokeWidth="1.5" />
        {/* 끝값 */}
        <text x={w - pr + 5} y={Y(issues[issues.length - 1]) + 3} fill="#f59e0b" fontSize="10" fontWeight="bold">{issues[issues.length - 1].toFixed(0)}</text>
        <text x={w - pr + 5} y={Y(reactions[reactions.length - 1]) + 3} fill="#a855f7" fontSize="10" fontWeight="bold">{reactions[reactions.length - 1].toFixed(0)}</text>
        {/* X축 */}
        {dates.map((d, i) => (
          <text key={i} x={pl + i * xs} y={h - 5} fill="#3f3f46" fontSize="7" textAnchor="middle" fontFamily="monospace">{d}</text>
        ))}
        {/* 범례 */}
        <line x1={pl} y1={8} x2={pl + 15} y2={8} stroke="#f59e0b" strokeWidth="2" />
        <text x={pl + 18} y={11} fill="#f59e0b" fontSize="8" fontWeight="bold">이슈</text>
        <line x1={pl + 45} y1={8} x2={pl + 60} y2={8} stroke="#a855f7" strokeWidth="2" />
        <text x={pl + 63} y={11} fill="#a855f7" fontSize="8" fontWeight="bold">반응</text>
      </svg>
    </div>
  );
}

function ForecastVsActualChart({ enrichment, polls }: { enrichment: any; polls: any[] }) {
  const forecast = enrichment?.forecast;
  const turnout = enrichment?.turnout;

  if (!forecast && polls.length < 2) {
    return <div className="h-32 flex items-center justify-center text-gray-700 text-xs">데이터 축적 중</div>;
  }

  // 여론조사 실측 + 예측값 비교
  const forecastGap = forecast?.scenarios?.[1]?.gap ?? 0;
  const turnoutGap = turnout?.base?.gap ?? 0;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-[#080d16] rounded-lg p-3 text-center">
          <div className="text-[8px] text-gray-600">여론조사 격차</div>
          <div className={`text-xl font-black ${(polls[polls.length - 1]?.our - (Object.values(polls[polls.length - 1]?.opponent || {})[0] as number || 0)) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {(() => {
              const lastPoll = polls[polls.length - 1];
              if (!lastPoll) return "—";
              const oppVal = lastPoll.opponent ? (Object.values(lastPoll.opponent)[0] as number) || 0 : 0;
              const gap = lastPoll.our - oppVal;
              return `${gap >= 0 ? "+" : ""}${gap.toFixed(1)}%p`;
            })()}
          </div>
          <div className="text-[8px] text-gray-600 mt-0.5">"지지 의향" 기반</div>
        </div>
        <div className="bg-[#080d16] rounded-lg p-3 text-center">
          <div className="text-[8px] text-gray-600">예측 모델 격차</div>
          <div className={`text-xl font-black ${forecastGap >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {forecastGap >= 0 ? "+" : ""}{forecastGap.toFixed(1)}%p
          </div>
          <div className="text-[8px] text-gray-600 mt-0.5">Leading Index 기반</div>
        </div>
        <div className="bg-[#080d16] rounded-lg p-3 text-center">
          <div className="text-[8px] text-gray-600">투표율 반영 격차</div>
          <div className={`text-xl font-black ${turnoutGap >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {turnoutGap >= 0 ? "+" : ""}{turnoutGap.toFixed(1)}%p
          </div>
          <div className="text-[8px] text-gray-600 mt-0.5">세대별 투표율 교차</div>
        </div>
      </div>
      <div className="bg-amber-950/10 border border-amber-800/20 rounded-lg p-2.5 text-[10px] text-amber-300/80">
        여론조사 격차와 투표율 모델 격차의 차이가 "투표율 효과"입니다.
        이 차이가 클수록 3040 투표율 동원이 승패를 결정합니다.
      </div>
    </div>
  );
}

function AttributionChart({ enrichment }: { enrichment: any }) {
  const attr = enrichment?.attribution;
  if (!attr || attr.total_actions === 0) {
    return <div className="h-20 flex items-center justify-center text-gray-700 text-xs">전략 갱신 후 귀인 분석 결과 표시</div>;
  }

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-[#080d16] rounded-lg p-2.5 text-center">
          <div className="text-[8px] text-gray-600">총 행동</div>
          <div className="text-lg font-black text-gray-300">{attr.total_actions}</div>
        </div>
        <div className="bg-[#080d16] rounded-lg p-2.5 text-center">
          <div className="text-[8px] text-gray-600">귀인 성공</div>
          <div className="text-lg font-black text-emerald-400">{attr.attributed_count}</div>
        </div>
        <div className="bg-[#080d16] rounded-lg p-2.5 text-center">
          <div className="text-[8px] text-gray-600">귀인율</div>
          <div className="text-lg font-black text-cyan-400">
            {attr.total_actions > 0 ? `${(attr.attributed_count / attr.total_actions * 100).toFixed(0)}%` : "—"}
          </div>
        </div>
      </div>
      {attr.strongest && (
        <div className="bg-emerald-950/10 border border-emerald-800/20 rounded-lg p-2.5 text-[10px] text-emerald-300/80">
          최강 귀인: {attr.strongest}
        </div>
      )}
      {attr.top && attr.top.length > 0 && (
        <div className="space-y-1">
          {attr.top.slice(0, 3).map((a: any, i: number) => (
            <div key={i} className="flex items-center gap-2 text-[9px] bg-[#080d16] rounded px-2.5 py-1.5">
              <span className="text-gray-400 truncate flex-1">{a.action}</span>
              <span className="text-gray-500">→ {a.keyword}</span>
              <span className={`font-mono font-bold ${a.confidence >= 0.5 ? "text-emerald-400" : "text-amber-400"}`}>
                {a.confidence.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** pollster 문자열에서 기관명과 nesdc 등록번호 파싱 */
function parseSource(pollster: string): { name: string; nesdcId: string | null } {
  const m = pollster.match(/\(nesdc:(\d+)\)/);
  if (m) {
    return { name: pollster.replace(/\s*\(nesdc:\d+\)/, "").trim(), nesdcId: m[1] };
  }
  return { name: pollster, nesdcId: null };
}

// ════════════════════════════════════════════════════════════════════
// 역대 득표율 + 9대 여론조사 통합 차트
// ════════════════════════════════════════════════════════════════════

function HistoricalPollChart({ autoPolls = [] }: { autoPolls?: any[] }) {
  const data = mergeAutoPolls(autoPolls);
  const n = data.length;
  const w = 800, h = 260, pl = 38, pr = 15, pt = 20, pb = 55;
  const xs = (w - pl - pr) / (n - 1);
  const mn = 20, mx = 70, rng = mx - mn;
  const Y = (v: number) => pt + (1 - (v - mn) / rng) * (h - pt - pb);

  // 역대 지선 / 여론조사 구분선
  const dividerIdx = 2.5; // 8기와 MBC경남 사이

  return (
    <div>
      <svg width="100%" viewBox={`0 0 ${w} ${h}`}>
        {/* 그리드 */}
        {[20, 30, 40, 50, 60, 70].map(v => (
          <g key={v}>
            <line x1={pl} y1={Y(v)} x2={w - pr} y2={Y(v)} stroke="#111d30" strokeWidth="0.5" />
            <text x={pl - 4} y={Y(v) + 3} fill="#2a3f5f" fontSize="8" textAnchor="end" fontFamily="monospace">{v}</text>
          </g>
        ))}

        {/* 구분선 — 역대 vs 여론조사 */}
        <line x1={pl + dividerIdx * xs} y1={pt} x2={pl + dividerIdx * xs} y2={h - pb}
          stroke="#374151" strokeWidth="1" strokeDasharray="4,4" />
        <text x={pl + dividerIdx * xs - 5} y={pt + 8} fill="#374151" fontSize="7" textAnchor="end">역대 득표</text>
        <text x={pl + dividerIdx * xs + 5} y={pt + 8} fill="#374151" fontSize="7">9대 여론조사</text>

        {/* 격차 영역 */}
        <polygon
          points={data.map((d, i) => `${pl + i * xs},${Y(d.kim)}`).join(" ") + " " +
            [...data].reverse().map((d, i) => `${pl + (n - 1 - i) * xs},${Y(d.park)}`).join(" ")}
          fill="rgba(100,100,100,0.04)"
        />

        {/* 박완수(상대) 라인 */}
        <polyline points={data.map((d, i) => `${pl + i * xs},${Y(d.park)}`).join(" ")}
          fill="none" stroke="#ef4444" strokeWidth="2" strokeLinejoin="round" />

        {/* 김경수(우리) 라인 */}
        <polyline points={data.map((d, i) => `${pl + i * xs},${Y(d.kim)}`).join(" ")}
          fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinejoin="round" />

        {/* 포인트 + 값 */}
        {data.map((d, i) => {
          const isElection = d.type === "election";
          return (
            <g key={i}>
              {/* 김경수 */}
              <circle cx={pl + i * xs} cy={Y(d.kim)} r={isElection ? 5 : 3.5}
                fill={isElection ? "#2563eb" : "none"} stroke="#2563eb" strokeWidth={isElection ? 2 : 1.5} />
              <text x={pl + i * xs} y={Y(d.kim) - 7} fill="#2563eb"
                fontSize={isElection ? "10" : "8"} fontWeight="bold" textAnchor="middle">{d.kim}</text>

              {/* 박완수 */}
              <circle cx={pl + i * xs} cy={Y(d.park)} r={isElection ? 5 : 3.5}
                fill={isElection ? "#ef4444" : "none"} stroke="#ef4444" strokeWidth={isElection ? 2 : 1.5} />
              <text x={pl + i * xs} y={Y(d.park) + 14} fill="#ef4444"
                fontSize={isElection ? "10" : "8"} fontWeight="bold" textAnchor="middle">{d.park}</text>

              {/* X축 라벨 */}
              {d.label.split("\n").map((line, li) => (
                <text key={li} x={pl + i * xs} y={h - pb + 12 + li * 9} fill={isElection ? "#6b7280" : "#4b5563"}
                  fontSize="7" textAnchor="middle" fontWeight={isElection ? "bold" : "normal"}>{line}</text>
              ))}
              <text x={pl + i * xs} y={h - 4} fill="#3f3f46" fontSize="6" textAnchor="middle" fontFamily="monospace">
                {d.date}
              </text>
            </g>
          );
        })}

        {/* 범례 */}
        <circle cx={pl} cy={10} r="3" fill="#2563eb" />
        <text x={pl + 6} y={13} fill="#2563eb" fontSize="9" fontWeight="bold">김경수</text>
        <circle cx={pl + 55} cy={10} r="3" fill="#ef4444" />
        <text x={pl + 61} y={13} fill="#ef4444" fontSize="9" fontWeight="bold">박완수</text>
        <circle cx={pl + 110} cy={10} r="4" fill="#2563eb" stroke="#2563eb" strokeWidth="2" />
        <text x={pl + 117} y={13} fill="#6b7280" fontSize="7">실제 득표</text>
        <circle cx={pl + 165} cy={10} r="3" fill="none" stroke="#2563eb" strokeWidth="1.5" />
        <text x={pl + 172} y={13} fill="#6b7280" fontSize="7">여론조사</text>
      </svg>
    </div>
  );
}

function PollChart({ polls }: { polls: any[] }) {
  const ours = polls.map((p) => p.our);
  const opps = polls.map((p) => { const v = p.opponent || {}; return (Object.values(v)[0] as number) || 0; });
  const all = [...ours, ...opps];
  const mn = Math.min(...all) - 3, mx = Math.max(...all) + 3, rng = mx - mn || 1;
  const w = 500, h = 200, pd = 40;
  const xs = (w - pd * 2) / (polls.length - 1 || 1);
  const Y = (v: number) => pd + (1 - (v - mn) / rng) * (h - pd * 2);
  const gridLines = [];
  for (let v = Math.ceil(mn); v <= Math.floor(mx); v += 2) {
    gridLines.push(v);
  }
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`}>
      {gridLines.map(v => (
        <g key={v}>
          <line x1={pd} y1={Y(v)} x2={w - pd} y2={Y(v)} stroke="#1e293b" strokeWidth="0.5" />
          <text x={pd - 5} y={Y(v) + 3} fill="#64748b" fontSize="9" textAnchor="end">{v}%</text>
        </g>
      ))}
      <polyline points={ours.map((v, i) => `${pd + i * xs},${Y(v)}`).join(" ")} fill="none" stroke="#4caf50" strokeWidth="2.5" />
      <polyline points={opps.map((v, i) => `${pd + i * xs},${Y(v)}`).join(" ")} fill="none" stroke="#f44336" strokeWidth="2.5" />
      {ours.map((v, i) => <circle key={`o${i}`} cx={pd + i * xs} cy={Y(v)} r="3.5" fill="#4caf50" />)}
      {opps.map((v, i) => <circle key={`e${i}`} cx={pd + i * xs} cy={Y(v)} r="3.5" fill="#f44336" />)}
      {polls.map((p, i) => (
        <text key={`d${i}`} x={pd + i * xs} y={h - 5} fill="#64748b" fontSize="8" textAnchor="middle">{p.date?.slice(5)}</text>
      ))}
      <text x={w - pd} y={12} fill="#4caf50" fontSize="10" textAnchor="end">우리</text>
      <text x={w - pd} y={24} fill="#f44336" fontSize="10" textAnchor="end">상대</text>
    </svg>
  );
}
