"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import {
  getIndicesCurrent,
  getNewsClusters,
  getDailyBriefing,
  getIndicesHistory,
} from "@/lib/api";

/* ───────────────────── Types ───────────────────── */

interface IndexData {
  index: number;
  grade: string;
  gap?: number;
  kim?: { mentions: number; score: number };
  park?: { mentions: number; score: number };
  total_mentions?: number;
  d_day?: number;
  updated_at?: string;
}

interface IndicesPayload {
  issue: IndexData;
  reaction: IndexData;
  pandse: IndexData;
  ai_issue_summary?: string;
  ai_reaction_summary?: string;
  pandse_alert?: { delta: number; direction?: string; memo: string };
}

interface NewsCluster {
  name: string;
  count: number;
  side: string;
  sentiment: number;
  tip: string;
}

interface Execution {
  when: string;
  what: string;
  who: string;
}

interface DailyBriefing {
  executive_summary: string;
  execution: Execution[];
}

interface TrendPoint {
  date: string;
  issue_index: number;
  reaction_index: number;
  pandse: number;
}

/* ───────────────────── Mobile Login ───────────────────── */

function MobileLogin() {
  const { login, loading, error } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await login(username, password);
  };

  return (
    <div className="min-h-screen bg-[#080e18] flex items-center justify-center px-4">
      <div className="w-full max-w-[360px]">
        <div className="text-center mb-8">
          <div className="text-[11px] text-cyan-400/60 font-mono uppercase tracking-[0.3em] mb-2">
            Election Engine
          </div>
          <h1 className="text-[18px] font-black text-blue-300 uppercase tracking-wider">
            Mobile War Room
          </h1>
          <div className="text-[10px] text-gray-600 mt-1">
            경남도지사 선거 전략 대시보드
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-[#0e1825] rounded-xl border border-[#1a2844] p-6 space-y-4"
        >
          <div>
            <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider block mb-1.5">
              ID
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-[#060c16] border border-[#1a2844] rounded-lg px-3 py-3 text-[14px] text-gray-200 focus:outline-none focus:border-cyan-700 transition-colors placeholder-gray-700"
              placeholder="아이디를 입력하세요"
              autoFocus
              autoComplete="username"
            />
          </div>
          <div>
            <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider block mb-1.5">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-[#060c16] border border-[#1a2844] rounded-lg px-3 py-3 text-[14px] text-gray-200 focus:outline-none focus:border-cyan-700 transition-colors placeholder-gray-700"
              placeholder="비밀번호를 입력하세요"
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="text-[12px] text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username || !password}
            className="w-full py-3 rounded-lg text-[14px] font-bold uppercase tracking-wider transition-all disabled:opacity-30 disabled:cursor-not-allowed bg-cyan-900/40 border border-cyan-700/40 text-cyan-300 hover:bg-cyan-800/40 hover:border-cyan-600/50 min-h-[44px]"
          >
            {loading ? "인증 중..." : "로그인"}
          </button>
        </form>

        <div className="text-center mt-4 text-[10px] text-gray-700">
          Authorized access only
        </div>
      </div>
    </div>
  );
}

/* ───────────────────── Gauge Bar ───────────────────── */

function GaugeBar({ value }: { value: number }) {
  const idx = value || 50;
  const barColor =
    idx >= 55 ? "#10b981" : idx <= 45 ? "#ef4444" : "#06b6d4";

  return (
    <div className="mt-2">
      <div className="relative h-4 bg-[#060c16] rounded-full overflow-hidden">
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-600 z-10" />
        <div className="flex h-full">
          <div className="bg-red-900/40" style={{ width: "50%" }} />
          <div className="bg-blue-900/40" style={{ width: "50%" }} />
        </div>
        <div
          className="absolute top-1/2 w-4 h-4 rounded-full border-2 z-20"
          style={{
            left: `${idx}%`,
            transform: "translate(-50%, -50%)",
            backgroundColor: barColor,
            borderColor: barColor,
            boxShadow: `0 0 8px ${barColor}80`,
          }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-gray-600 mt-1">
        <span className="text-red-400/60">박 유리</span>
        <span>50</span>
        <span className="text-blue-400/60">김 유리</span>
      </div>
    </div>
  );
}

/* ───────────────────── Grade Badge ───────────────────── */

function GradeBadge({ grade }: { grade: string }) {
  const cls =
    grade === "우세"
      ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
      : grade === "열세"
      ? "bg-rose-500/15 text-rose-400 border-rose-500/30"
      : "bg-gray-800/30 text-gray-400 border-gray-700/30";

  return (
    <span
      className={`text-[12px] font-black px-2 py-0.5 rounded border ${cls}`}
    >
      {grade}
    </span>
  );
}

/* ───────────────────── Index Card ───────────────────── */

function IndexCard({
  label,
  data,
  suffix,
}: {
  label: string;
  data: IndexData;
  suffix?: string;
}) {
  const idx = data.index || 50;
  const delta = idx - 50;
  const valueColor =
    idx >= 55
      ? "text-emerald-400"
      : idx <= 45
      ? "text-rose-500"
      : "text-cyan-400";
  const direction =
    delta > 0 ? "김경수 유리" : delta < 0 ? "박완수 유리" : "중립";
  const dirColor =
    delta > 0 ? "text-blue-400" : delta < 0 ? "text-red-400" : "text-gray-400";

  return (
    <div className="bg-[#0e1825] rounded-xl p-4 border border-[#1a2844]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[14px] text-gray-300 font-bold">{label}</span>
        <GradeBadge grade={data.grade} />
      </div>
      <div className="text-center mb-1">
        <span className={`text-[24px] font-black leading-none ${valueColor}`}>
          {idx.toFixed(1)}
          <span className="text-[12px] text-gray-500 ml-0.5">pt</span>
        </span>
      </div>
      <div className={`text-center text-[12px] font-bold mb-1 ${dirColor}`}>
        {direction} ({delta > 0 ? "+" : ""}
        {delta.toFixed(1)})
      </div>
      <GaugeBar value={idx} />
      {suffix && (
        <div className="text-[10px] text-gray-600 mt-2 text-center">
          {suffix}
        </div>
      )}
    </div>
  );
}

/* ───────────────────── Mini Trend Chart (SVG, 3 lines) ───────────────────── */

function TrendChart({ data }: { data: TrendPoint[] }) {
  if (!data || data.length < 2) {
    return (
      <div className="bg-[#0e1825] rounded-xl p-4 border border-[#1a2844]">
        <div className="text-[14px] font-bold text-gray-300 mb-3">
          24시간 추세
        </div>
        <div className="text-[12px] text-gray-600 text-center py-6">
          데이터 수집 중...
        </div>
      </div>
    );
  }

  const n = data.length;
  const w = 320;
  const h = 140;
  const pl = 30;
  const pr = 10;
  const pt = 10;
  const pb = 24;

  const fields: { key: keyof TrendPoint; color: string; label: string }[] = [
    { key: "issue_index", color: "#10b981", label: "이슈" },
    { key: "reaction_index", color: "#f59e0b", label: "반응" },
    { key: "pandse", color: "#06b6d4", label: "판세" },
  ];

  const allVals = data.flatMap((d) =>
    fields.map((f) => (d[f.key] as number) || 0)
  );
  const mn = Math.min(...allVals) - 3;
  const mx = Math.max(...allVals) + 3;
  const rng = mx - mn || 1;
  const xStep = (w - pl - pr) / Math.max(n - 1, 1);
  const Y = (v: number) => pt + (1 - (v - mn) / rng) * (h - pt - pb);

  // Y-axis tick values
  const yMid = Math.round((mn + mx) / 2);
  const yTicks = [Math.round(mx) - 1, yMid, Math.round(mn) + 1];

  return (
    <div className="bg-[#0e1825] rounded-xl p-4 border border-[#1a2844]">
      <div className="text-[14px] font-bold text-gray-300 mb-3">
        24시간 추세
      </div>
      <svg
        width="100%"
        viewBox={`0 0 ${w} ${h}`}
        className="overflow-visible"
      >
        {/* Grid lines */}
        {yTicks.map((v) => (
          <g key={v}>
            <line
              x1={pl}
              y1={Y(v)}
              x2={w - pr}
              y2={Y(v)}
              stroke="#1a2844"
              strokeWidth="0.5"
            />
            <text
              x={pl - 4}
              y={Y(v) + 3}
              fill="#4b5563"
              fontSize="8"
              textAnchor="end"
              fontFamily="monospace"
            >
              {v}
            </text>
          </g>
        ))}
        {/* 50 baseline */}
        {50 >= mn && 50 <= mx && (
          <line
            x1={pl}
            y1={Y(50)}
            x2={w - pr}
            y2={Y(50)}
            stroke="#374151"
            strokeWidth="0.5"
            strokeDasharray="3,3"
          />
        )}

        {/* Lines */}
        {fields.map(({ key, color }) => {
          const vals = data.map((d) => (d[key] as number) || 0);
          const points = vals
            .map((v, i) => `${pl + i * xStep},${Y(v)}`)
            .join(" ");
          return (
            <polyline
              key={key}
              points={points}
              fill="none"
              stroke={color}
              strokeWidth="2"
              strokeLinejoin="round"
              strokeLinecap="round"
              opacity="0.85"
            />
          );
        })}

        {/* End dots + values */}
        {fields.map(({ key, color }) => {
          const vals = data.map((d) => (d[key] as number) || 0);
          const lastVal = vals[n - 1];
          const lastX = pl + (n - 1) * xStep;
          const lastY = Y(lastVal);
          return (
            <g key={`dot-${key}`}>
              <circle cx={lastX} cy={lastY} r="3.5" fill={color} />
              <text
                x={lastX}
                y={lastY - 6}
                fill={color}
                fontSize="8"
                fontWeight="bold"
                textAnchor="middle"
                fontFamily="monospace"
              >
                {lastVal}
              </text>
            </g>
          );
        })}

        {/* X-axis labels */}
        {data.map((d, i) => {
          const show =
            i === 0 ||
            i === n - 1 ||
            i % Math.max(1, Math.floor(n / 5)) === 0;
          if (!show) return null;
          return (
            <text
              key={i}
              x={pl + i * xStep}
              y={h - 4}
              fill="#4b5563"
              fontSize="7"
              textAnchor="middle"
              fontFamily="monospace"
            >
              {(d.date || "").slice(0, 5)}
            </text>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="flex justify-center gap-4 mt-2">
        {fields.map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1">
            <span
              className="w-3 h-[3px] rounded-full inline-block"
              style={{ backgroundColor: color }}
            />
            <span className="text-[10px] text-gray-500">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ───────────────────── Side Badge ───────────────────── */

function SideBadge({ side }: { side: string }) {
  const isOurs =
    side.includes("우리") || side.includes("김") || side.includes("아군");
  return (
    <span
      className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
        isOurs
          ? "bg-blue-500/15 text-blue-400"
          : "bg-red-500/15 text-red-400"
      }`}
    >
      {side}
    </span>
  );
}

/* ───────────────────── Main Mobile Page ───────────────────── */

type MobileView = "dashboard" | "strategy" | "system";

export default function MobileDashboard() {
  const { token, tier, checkSession, logout } = useAuth();
  const [authChecked, setAuthChecked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState("");
  const [view, setView] = useState<MobileView>("dashboard");

  const [indices, setIndices] = useState<IndicesPayload | null>(null);
  const [clusters, setClusters] = useState<NewsCluster[]>([]);
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);

  const fetchData = useCallback(async () => {
    try {
      setError(null);
      const [indicesRes, clustersRes, briefingRes, historyRes] =
        await Promise.all([
          getIndicesCurrent().catch(() => null),
          getNewsClusters().catch(() => ({ clusters: [] })),
          getDailyBriefing().catch(() => null),
          getIndicesHistory().catch(() => ({ candidate_trend: [] })),
        ]);

      setIndices(indicesRes as IndicesPayload);
      setClusters(
        ((clustersRes as any)?.clusters || []).slice(0, 5)
      );
      setBriefing(briefingRes as DailyBriefing);
      setTrend(
        (historyRes as any)?.candidate_trend || []
      );
      setLastUpdated(
        new Date().toLocaleString("ko-KR", {
          hour: "2-digit",
          minute: "2-digit",
        })
      );
    } catch {
      setError("데이터 로딩 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  // Auth check
  useEffect(() => {
    checkSession().finally(() => setAuthChecked(true));
  }, [checkSession]);

  // Fetch + auto-refresh
  useEffect(() => {
    if (!token) return;
    fetchData();
    const interval = setInterval(fetchData, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, [token, fetchData]);

  /* ── Auth gate ── */
  if (!authChecked) {
    return (
      <div className="min-h-screen bg-[#080e18] flex items-center justify-center">
        <div className="text-cyan-400 text-[14px] animate-pulse">
          인증 확인 중...
        </div>
      </div>
    );
  }

  if (!token) return <MobileLogin />;

  /* ── Loading ── */
  if (loading) {
    return (
      <div className="min-h-screen bg-[#080e18] flex items-center justify-center">
        <div className="text-center">
          <div className="text-cyan-400 text-[14px] animate-pulse mb-2">
            Election Engine
          </div>
          <div className="text-gray-600 text-[12px]">모바일 로딩 중...</div>
        </div>
      </div>
    );
  }

  /* ── Error fallback ── */
  if (error && !indices) {
    return (
      <div className="min-h-screen bg-[#080e18] flex items-center justify-center px-4">
        <div className="text-center">
          <div className="text-rose-400 text-[14px] mb-4">{error}</div>
          <button
            onClick={() => {
              setLoading(true);
              fetchData();
            }}
            className="px-6 py-3 bg-cyan-900/40 border border-cyan-700/40 text-cyan-300 rounded-lg text-[14px] font-bold min-h-[44px]"
          >
            다시 시도
          </button>
        </div>
      </div>
    );
  }

  /* ── Derived data ── */
  const urgentActions =
    briefing?.execution?.filter(
      (e) => e.when?.includes("즉시") || e.when?.includes("오늘")
    ) || [];

  const dDay = indices?.pandse?.d_day;

  return (
    <div className="min-h-screen bg-[#080e18] text-gray-200">
      {/* ── Top Bar ── */}
      <div className="sticky top-0 z-50 bg-[#080e18]/95 backdrop-blur-sm border-b border-[#1a2844]">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-[14px] font-black text-blue-300">
              {{ dashboard: "김경수 캠프", strategy: "전략모드", system: "시스템" }[view]}
            </span>
            {dDay != null && (
              <span className="text-[10px] font-bold bg-cyan-900/40 text-cyan-400 border border-cyan-700/30 px-2 py-0.5 rounded-full">
                D-{dDay}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {lastUpdated && (
              <span className="text-[10px] text-gray-600">
                {lastUpdated} 갱신
              </span>
            )}
            <button
              onClick={logout}
              className="text-[10px] text-gray-600 min-w-[44px] min-h-[44px] flex items-center justify-center"
              aria-label="로그아웃"
            >
              로그아웃
            </button>
          </div>
        </div>
      </div>

      {/* ── Content ── */}
      {view === "strategy" ? (
        <div className="px-4 py-4 pb-24"><MobileStrategyView onBack={() => setView("dashboard")} /></div>
      ) : view === "system" ? (
        <div className="px-4 py-4 pb-24"><MobileSystemView /></div>
      ) : (
      <div className="px-4 py-4 space-y-3 pb-8">
        {/* ── Index Cards ── */}
        {indices && (
          <>
            <IndexCard
              label="이슈지수"
              data={indices.issue}
              suffix={
                indices.issue?.kim && indices.issue?.park
                  ? `우리 ${indices.issue.kim.mentions || 0}건(${
                      indices.issue.kim.score || 0
                    }) / 상대 ${indices.issue.park.mentions || 0}건(${
                      indices.issue.park.score || 0
                    })`
                  : undefined
              }
            />
            <IndexCard
              label="반응지수"
              data={indices.reaction}
              suffix={
                indices.reaction?.total_mentions
                  ? `${indices.reaction.total_mentions.toLocaleString()}건 수집`
                  : undefined
              }
            />
            <IndexCard label="판세지수" data={indices.pandse} />

            {/* ── Pandse Alert ── */}
            {indices.pandse_alert && (
              <div className="bg-amber-950/20 border border-amber-700/40 rounded-xl px-4 py-3">
                <div className="flex items-center gap-1 mb-1">
                  <span className="text-[12px] font-black text-amber-400">
                    {indices.pandse_alert.delta > 0 ? "+" : ""}
                    {indices.pandse_alert.delta?.toFixed(1)}pt 변동 감지
                  </span>
                </div>
                <div className="text-[12px] text-amber-300/90 leading-relaxed">
                  {indices.pandse_alert.memo}
                </div>
              </div>
            )}
          </>
        )}

        {/* ── AI Summary ── */}
        {(indices?.ai_issue_summary || indices?.ai_reaction_summary) && (
          <div className="bg-[#0e1825] rounded-xl p-4 border border-[#1a2844]">
            <div className="text-[14px] font-bold text-cyan-400 mb-2">
              AI 한줄 해석
            </div>
            {indices.ai_issue_summary && (
              <div className="text-[12px] text-gray-300 leading-relaxed mb-2">
                <span className="text-[10px] text-gray-500 font-bold mr-1">
                  이슈
                </span>
                {indices.ai_issue_summary}
              </div>
            )}
            {indices.ai_reaction_summary && (
              <div className="text-[12px] text-gray-300 leading-relaxed">
                <span className="text-[10px] text-gray-500 font-bold mr-1">
                  반응
                </span>
                {indices.ai_reaction_summary}
              </div>
            )}
          </div>
        )}

        {/* ── Urgent Actions ── */}
        {urgentActions.length > 0 && (
          <div className="bg-[#0e1825] rounded-xl p-4 border border-rose-500/30">
            <div className="text-[14px] font-bold text-rose-400 mb-3">
              긴급 액션
            </div>
            <div className="space-y-3">
              {urgentActions.map((action, i) => (
                <div
                  key={i}
                  className="bg-rose-500/5 rounded-lg p-3 border border-rose-500/10"
                >
                  <div className="flex items-start gap-2">
                    <span className="text-[10px] font-bold text-rose-400 bg-rose-500/15 px-1.5 py-0.5 rounded shrink-0 mt-0.5">
                      {action.when}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-[12px] text-gray-200 leading-relaxed">
                        {action.what}
                      </div>
                      {action.who && (
                        <div className="text-[10px] text-gray-500 mt-1">
                          담당: {action.who}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── TOP Issues ── */}
        {clusters.length > 0 && (
          <div className="bg-[#0e1825] rounded-xl p-4 border border-[#1a2844]">
            <div className="text-[14px] font-bold text-gray-300 mb-3">
              TOP 이슈
            </div>
            <div className="space-y-2">
              {clusters.map((c, i) => (
                <div
                  key={i}
                  className="bg-[#080e18] rounded-lg p-3 border border-[#1a2844]"
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <span className="text-[14px] font-black text-gray-500 shrink-0">
                        {i + 1}
                      </span>
                      <span className="text-[12px] font-bold text-gray-200 leading-snug">
                        {c.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <SideBadge side={c.side} />
                      <span className="text-[10px] text-gray-500">
                        {c.count}건
                      </span>
                    </div>
                  </div>
                  {c.tip && (
                    <div className="text-[12px] text-cyan-400/70 leading-relaxed ml-5">
                      {c.tip}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Executive Summary ── */}
        {briefing?.executive_summary && (
          <div className="bg-[#0e1825] rounded-xl p-4 border border-[#1a2844]">
            <div className="text-[14px] font-bold text-gray-300 mb-2">
              오늘의 전략 요약
            </div>
            <div className="text-[12px] text-gray-400 leading-relaxed whitespace-pre-line">
              {briefing.executive_summary}
            </div>
          </div>
        )}

        {/* ── 24h Trend Chart ── */}
        <TrendChart data={trend} />

        {/* ── Refresh Button ── */}
        <button
          onClick={() => {
            setLoading(true);
            fetchData();
          }}
          className="w-full py-3 rounded-xl text-[14px] font-bold bg-[#0e1825] border border-[#1a2844] text-cyan-400 min-h-[44px] active:bg-[#1a2844] transition-colors"
        >
          새로고침
        </button>

        <div className="h-20" /> {/* 하단 네비 여백 */}
      </div>
      )}

      {/* ── Bottom Navigation ── */}
      <div className="fixed bottom-0 left-0 right-0 z-50 bg-[#080e18]/95 backdrop-blur-sm border-t border-[#1a2844]">
        <div className="flex">
          <button onClick={() => setView("dashboard")}
            className={`flex-1 py-3 flex flex-col items-center gap-1 min-h-[56px] transition-colors ${view === "dashboard" ? "text-cyan-400" : "text-gray-600"}`}>
            <span className="text-[16px]">📊</span>
            <span className="text-[9px] font-bold">대시보드</span>
          </button>
          {tier === 1 && (
            <button onClick={() => setView("strategy")}
              className={`flex-1 py-3 flex flex-col items-center gap-1 min-h-[56px] transition-colors ${view === "strategy" ? "text-[#E8B84B]" : "text-gray-600"}`}>
              <span className="text-[16px]">📋</span>
              <span className="text-[9px] font-bold">전략모드</span>
            </button>
          )}
          <button onClick={() => setView("system")}
            className={`flex-1 py-3 flex flex-col items-center gap-1 min-h-[56px] transition-colors ${view === "system" ? "text-cyan-400" : "text-gray-600"}`}>
            <span className="text-[16px]">⚙️</span>
            <span className="text-[9px] font-bold">시스템</span>
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Mobile Strategy View ── */
function MobileStrategyView({ onBack }: { onBack: () => void }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getDailyBriefing().catch(() => null),
      getIndicesCurrent().catch(() => null),
    ]).then(([daily, indices]) => {
      setData({ daily, indices });
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="py-20 text-center text-gray-500 animate-pulse text-sm">전략 데이터 로딩 중...</div>;

  const daily = data?.daily || {};
  const sd = daily.situation_diagnosis || {};
  const dl = daily.decision_layer || {};
  const strategies = daily.strategies || [];
  const fieldSchedule = daily.field_schedule || daily.messages || [];
  const indices = data?.indices || {};

  return (
    <div className="space-y-3">
      {/* Daily Theme */}
      {daily.daily_theme && (
        <div className="bg-[#0e1825] rounded-xl border border-[#1a2844] p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[9px] font-bold tracking-wider px-2 py-0.5 rounded-full bg-[#C8922A] text-white">THEME</span>
            <span className="text-[16px] font-black text-white">{daily.daily_theme.keyword}</span>
          </div>
          <div className="text-[11px] text-gray-400 leading-relaxed">{daily.daily_theme.rationale}</div>
        </div>
      )}

      {/* Executive Summary */}
      {daily.executive_summary && (
        <div className="bg-[#0e1825] rounded-xl border border-[#1a2844] p-4">
          <div className="text-[10px] text-cyan-400 font-bold mb-2">종합 브리핑</div>
          <div className="text-[12px] text-gray-300 leading-[1.9]">{daily.executive_summary}</div>
        </div>
      )}

      {/* Decision Layer */}
      {dl.moment_type && (
        <div className="bg-[#0e1825] rounded-xl border border-[#1a2844] p-4">
          <div className="text-[11px] font-bold text-amber-400 mb-2">현재 국면: {dl.moment_type}</div>
          <div className="text-[10px] text-rose-400 mb-1">🛡 {dl.must_protect}</div>
          <div className="text-[10px] text-emerald-400">⚔ {dl.can_push}</div>
        </div>
      )}

      {/* Strategies */}
      {strategies.length > 0 && (
        <div className="bg-[#0e1825] rounded-xl border border-[#1a2844] p-4">
          <div className="text-[10px] text-cyan-400 font-bold mb-3">대응 전략</div>
          {strategies.map((s: any, i: number) => {
            const isUrgent = s.timeline?.includes("즉시") || s.timeline?.includes("오늘");
            return (
              <div key={i} className={`mb-3 pb-3 border-b border-[#1a2844] last:border-0 last:mb-0 last:pb-0 ${isUrgent ? "pl-3 border-l-2 border-l-rose-500" : ""}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-full ${isUrgent ? "bg-rose-500/20 text-rose-400" : "bg-blue-500/20 text-blue-400"}`}>
                    {isUrgent ? "긴급" : "단기"} · {s.timeline}
                  </span>
                </div>
                <div className="text-[12px] font-bold text-gray-200">{s.title}</div>
                <div className="text-[10px] text-gray-400 mt-1 leading-relaxed">{s.action}</div>
              </div>
            );
          })}
        </div>
      )}

      {/* Field Schedule */}
      {fieldSchedule.length > 0 && (
        <div className="bg-[#0e1825] rounded-xl border border-[#1a2844] p-4">
          <div className="text-[10px] text-[#E8B84B] font-bold mb-3">현장 방문 일정</div>
          {fieldSchedule.map((m: any, i: number) => (
            <div key={i} className="mb-3 pb-3 border-b border-[#1a2844] last:border-0 last:mb-0 last:pb-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[9px] font-bold text-blue-400">P{m.priority}</span>
                {m.when && <span className="text-[9px] text-rose-400">{m.when}</span>}
                {m.region && <span className="text-[8px] px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-400">{m.region}</span>}
                {m.theme && <span className="text-[8px] px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400">#{m.theme}</span>}
              </div>
              {m.location && <div className="text-[10px] text-gray-500">📍 {m.location}</div>}
              <div className="text-[12px] font-bold text-gray-200 mt-1">&ldquo;{m.message}&rdquo;</div>
              <div className="text-[10px] text-gray-400 mt-1">{m.sub_message}</div>
            </div>
          ))}
        </div>
      )}

      {!daily.executive_summary && <div className="text-center py-10 text-gray-500 text-sm">데일리 리포트를 먼저 생성하세요</div>}
    </div>
  );
}

/* ── Mobile System View ── */
function MobileSystemView() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    getIndicesCurrent().then(setData).catch(() => {});
  }, []);

  const issue = data?.issue || {};
  const reaction = data?.reaction || {};
  const pandse = data?.pandse || {};

  return (
    <div className="space-y-3">
      {/* 이슈지수 */}
      <div className="bg-[#0e1825] rounded-xl border border-[#1a2844] p-4">
        <div className="text-[11px] text-emerald-400 font-bold mb-2">이슈지수</div>
        <div className="text-[10px] text-gray-400 leading-relaxed mb-3">
          광역 뉴스 수집(~250건) → AI 클러스터링(TOP 10) → 기사수 × 감성강도 가중 → 50pt 기준 지수화. &gt;55pt 우세, &lt;45pt 열세.
        </div>
        <div className="text-[10px] text-gray-500">
          현재: {issue.index?.toFixed(1) || "—"}pt ({issue.grade || "—"})
        </div>
        <div className="text-[9px] text-gray-600 mt-1">소스: 뉴스 (Naver API 11쿼리) + AI 클러스터링 (Haiku)</div>
        <div className="text-[9px] text-gray-600">주기: 1시간</div>
      </div>

      {/* 반응지수 */}
      <div className="bg-[#0e1825] rounded-xl border border-[#1a2844] p-4">
        <div className="text-[11px] text-amber-400 font-bold mb-2">반응지수</div>
        <div className="text-[10px] text-gray-400 leading-relaxed mb-3">
          이슈 TOP 10 키워드 → 블로그·카페·유튜브·커뮤니티(10곳)·뉴스댓글 수집 → 감성 분석 → 50pt 기준.
        </div>
        <div className="text-[10px] text-gray-500">
          현재: {reaction.index?.toFixed(1) || "—"}pt ({reaction.grade || "—"}) · {reaction.total_mentions?.toLocaleString() || 0}건 수집
        </div>
        <div className="text-[9px] text-gray-600 mt-1">소스: 블로그·카페·유튜브·커뮤니티·뉴스댓글·맘카페</div>
        <div className="text-[9px] text-gray-600">주기: 1시간 (이슈 수집 직후)</div>
      </div>

      {/* 판세지수 */}
      <div className="bg-[#0e1825] rounded-xl border border-[#1a2844] p-4">
        <div className="text-[11px] text-cyan-400 font-bold mb-2">판세지수</div>
        <div className="text-[10px] text-gray-400 leading-relaxed mb-3">
          9개 독립 팩터(대통령효과·보수기저·현직프리미엄·여론관성 등) → 실데이터 자동 연동 → 50pt 기준. Alert: 1pt 이상 변동 시 AI 분석.
        </div>
        <div className="text-[10px] text-gray-500">
          현재: {pandse.index?.toFixed(1) || "—"}pt ({pandse.grade || "—"}) · D-{pandse.d_day || "?"}
        </div>
        <div className="text-[9px] text-gray-600 mt-1">소스: 갤럽·클러스터·여론조사·이슈/반응지수</div>
        <div className="text-[9px] text-gray-600">주기: 1시간</div>
      </div>

      {/* 시스템 정보 */}
      <div className="bg-[#0e1825] rounded-xl border border-[#1a2844] p-4">
        <div className="text-[11px] text-gray-300 font-bold mb-2">시스템 정보</div>
        <div className="text-[10px] text-gray-500 leading-relaxed space-y-1">
          <div>데이터 수집: 1시간 주기 자동</div>
          <div>데일리 리포트: Opus · 1일 1회</div>
          <div>위클리 리포트: Opus · 주 1회</div>
          <div>AI 클러스터링: Haiku · 시간당 1회</div>
          <div>학습데이터: 매일 08:00 자동 저장</div>
        </div>
      </div>
    </div>
  );
}
