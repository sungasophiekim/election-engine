"use client";
import { useEffect, useState, useCallback } from "react";
import {
  getLearningPending,
  getLearningDecisionsByType,
  getLearningAccuracy,
  getLearningOverrideStats,
  getLearningSummary,
  getLearningAwaiting,
  postLearningOverride,
  postLearningExecuted,
  postLearningManualOutcome,
  postLearningAutoEvaluate,
} from "@/lib/api";

type Tab = "decisions" | "evaluate" | "accuracy" | "patterns";

const TYPE_KO: Record<string, string> = {
  issue_stance: "이슈 대응",
  campaign_mode: "캠페인 모드",
  resource_allocation: "자원 배분",
  leading_index: "선행지수",
  content_strategy: "콘텐츠 전략",
};

const GRADE_STYLE: Record<string, string> = {
  correct: "bg-emerald-600/20 border-emerald-600/50 text-emerald-400",
  partial: "bg-yellow-600/20 border-yellow-600/50 text-yellow-400",
  wrong: "bg-red-600/20 border-red-600/50 text-red-400",
  inconclusive: "bg-gray-600/20 border-gray-600/50 text-gray-400",
};

export function LearningPage() {
  const [tab, setTab] = useState<Tab>("decisions");
  const [summary, setSummary] = useState<any>(null);
  const [pending, setPending] = useState<any[]>([]);
  const [awaiting, setAwaiting] = useState<any[]>([]);
  const [accuracy, setAccuracy] = useState<any>(null);
  const [overrideStats, setOverrideStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [overrideTarget, setOverrideTarget] = useState<string | null>(null);
  const [overrideValue, setOverrideValue] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [historyType, setHistoryType] = useState("");
  const [history, setHistory] = useState<any[]>([]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [sum, pend] = await Promise.all([
        getLearningSummary().catch(() => null),
        getLearningPending().catch(() => []),
      ]);
      setSummary(sum);
      setPending(pend);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const loadEvaluate = useCallback(async () => {
    const data = await getLearningAwaiting().catch(() => []);
    setAwaiting(data);
  }, []);

  const loadAccuracy = useCallback(async () => {
    const [acc, stats] = await Promise.all([
      getLearningAccuracy().catch(() => null),
      getLearningOverrideStats().catch(() => null),
    ]);
    setAccuracy(acc);
    setOverrideStats(stats);
  }, []);

  const loadHistory = useCallback(async (dtype: string) => {
    setHistoryType(dtype);
    const data = await getLearningDecisionsByType(dtype).catch(() => []);
    setHistory(data);
  }, []);

  useEffect(() => {
    if (tab === "evaluate") loadEvaluate();
    if (tab === "accuracy") loadAccuracy();
    if (tab === "patterns") loadAccuracy();
  }, [tab, loadEvaluate, loadAccuracy]);

  // --- actions ---
  const handleExecute = async (id: string) => {
    await postLearningExecuted(id).catch(() => {});
    refresh();
  };

  const handleOverrideSubmit = async () => {
    if (!overrideTarget || !overrideValue) return;
    await postLearningOverride(overrideTarget, overrideValue, overrideReason).catch(() => {});
    setOverrideTarget(null);
    setOverrideValue("");
    setOverrideReason("");
    refresh();
  };

  const handleGrade = async (id: string, grade: string) => {
    await postLearningManualOutcome(id, grade).catch(() => {});
    loadEvaluate();
  };

  const handleAutoEvaluate = async () => {
    await postLearningAutoEvaluate().catch(() => {});
    loadEvaluate();
    loadAccuracy();
  };

  // --- renders ---
  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: "decisions", label: "추천", icon: "📋" },
    { id: "evaluate", label: "평가", icon: "⚖" },
    { id: "accuracy", label: "정확도", icon: "🎯" },
    { id: "patterns", label: "패턴", icon: "📊" },
  ];

  if (loading && !summary) {
    return <div className="text-center py-8 text-gray-500 text-[11px]">로딩...</div>;
  }

  return (
    <div className="space-y-2">
      {/* Summary KPI Cards */}
      {summary && (
        <div className="grid grid-cols-4 gap-2">
          <KpiCard label="오늘 추천" value={summary.today_decisions ?? 0} color="blue" />
          <KpiCard label="오늘 수정" value={summary.today_overrides ?? 0} color="yellow" />
          <KpiCard label="평가 대기" value={summary.awaiting_evaluation ?? 0} color="purple" />
          <KpiCard label="7일 정확도" value={summary.accuracy_7d?.accuracy_rate != null ? `${(summary.accuracy_7d.accuracy_rate * 100).toFixed(0)}%` : "—"} color="emerald" />
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex gap-1 text-[10px]">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 rounded border transition ${
              tab === t.id
                ? "bg-blue-600/20 border-blue-600/50 text-blue-400 font-bold"
                : "border-[#1a2844] text-gray-600 hover:text-gray-400"
            }`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === "decisions" && (
        <DecisionsTab
          pending={pending}
          onExecute={handleExecute}
          onOverride={(id) => { setOverrideTarget(id); setOverrideValue(""); setOverrideReason(""); }}
          overrideTarget={overrideTarget}
          overrideValue={overrideValue}
          overrideReason={overrideReason}
          setOverrideValue={setOverrideValue}
          setOverrideReason={setOverrideReason}
          onOverrideSubmit={handleOverrideSubmit}
          onOverrideCancel={() => setOverrideTarget(null)}
          historyType={historyType}
          history={history}
          onLoadHistory={loadHistory}
        />
      )}
      {tab === "evaluate" && (
        <EvaluateTab awaiting={awaiting} onGrade={handleGrade} onAutoEvaluate={handleAutoEvaluate} />
      )}
      {tab === "accuracy" && <AccuracyTab accuracy={accuracy} />}
      {tab === "patterns" && <PatternsTab stats={overrideStats} />}
    </div>
  );
}

/* ── KPI Card ── */
function KpiCard({ label, value, color }: { label: string; value: string | number; color: string }) {
  const colorMap: Record<string, string> = {
    blue: "border-l-blue-500 text-blue-400",
    yellow: "border-l-yellow-500 text-yellow-400",
    purple: "border-l-purple-500 text-purple-400",
    emerald: "border-l-emerald-500 text-emerald-400",
  };
  return (
    <div className={`wr-card border-l-2 ${colorMap[color] || ""}`}>
      <div className="px-3 py-2.5 text-center">
        <div className="text-[8px] text-gray-600 uppercase">{label}</div>
        <div className={`text-[22px] wr-metric ${colorMap[color]?.split(" ")[1] || "text-gray-200"}`}>{value}</div>
      </div>
    </div>
  );
}

/* ── Decisions Tab ── */
function DecisionsTab({
  pending, onExecute, onOverride, overrideTarget,
  overrideValue, overrideReason, setOverrideValue, setOverrideReason,
  onOverrideSubmit, onOverrideCancel, historyType, history, onLoadHistory,
}: any) {
  return (
    <div className="space-y-2">
      {/* Type filter buttons for history */}
      <div className="flex gap-1 flex-wrap">
        {Object.entries(TYPE_KO).map(([k, v]) => (
          <button key={k} onClick={() => onLoadHistory(k)}
            className={`text-[9px] px-2 py-1 rounded border transition ${
              historyType === k
                ? "bg-purple-600/20 border-purple-600/50 text-purple-400"
                : "border-[#1a2844] text-gray-600 hover:text-gray-400"
            }`}>
            {v}
          </button>
        ))}
      </div>

      {/* Pending decisions */}
      <div className="wr-card">
        <div className="wr-card-header text-blue-400">오늘 추천 ({pending.length}건)</div>
        <div className="divide-y divide-[#0e1825]">
          {pending.length > 0 ? pending.map((d: any) => (
            <div key={d.decision_id} className="px-3 py-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-[9px] bg-blue-950/40 border border-blue-800/30 text-blue-400/80 px-1.5 py-0.5 rounded">
                    {TYPE_KO[d.decision_type] || d.decision_type}
                  </span>
                  <span className="text-[11px] text-gray-200 font-mono">{d.keyword || d.context || "—"}</span>
                </div>
                <div className="text-[9px] text-gray-600">{d.created_at?.slice(11, 16)}</div>
              </div>
              <div className="text-[11px] text-gray-400 mt-1">{d.recommendation}</div>
              <div className="text-[10px] text-gray-600 mt-0.5">근거: {d.reason}</div>

              {/* Action buttons */}
              <div className="flex gap-1.5 mt-2">
                {!d.was_executed && !d.override_value && (
                  <>
                    <button onClick={() => onExecute(d.decision_id)}
                      className="text-[9px] px-2 py-1 rounded bg-emerald-600/20 border border-emerald-600/40 text-emerald-400 hover:bg-emerald-600/30 transition">
                      실행
                    </button>
                    <button onClick={() => onOverride(d.decision_id)}
                      className="text-[9px] px-2 py-1 rounded bg-yellow-600/20 border border-yellow-600/40 text-yellow-400 hover:bg-yellow-600/30 transition">
                      수정
                    </button>
                  </>
                )}
                {d.was_executed && (
                  <span className="text-[9px] text-emerald-500/70">실행됨</span>
                )}
                {d.override_value && (
                  <span className="text-[9px] text-yellow-500/70">수정됨: {d.override_value}</span>
                )}
              </div>

              {/* Override form */}
              {overrideTarget === d.decision_id && (
                <div className="mt-2 p-2 bg-[#0a1019] rounded border border-yellow-800/30 space-y-1.5">
                  <input
                    value={overrideValue} onChange={(e) => setOverrideValue(e.target.value)}
                    placeholder="수정 값"
                    className="w-full text-[10px] bg-[#060a11] border border-[#1a2844] rounded px-2 py-1 text-gray-200 outline-none focus:border-yellow-600/50"
                  />
                  <input
                    value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)}
                    placeholder="수정 사유 (선택)"
                    className="w-full text-[10px] bg-[#060a11] border border-[#1a2844] rounded px-2 py-1 text-gray-200 outline-none focus:border-yellow-600/50"
                  />
                  <div className="flex gap-1">
                    <button onClick={onOverrideSubmit}
                      className="text-[9px] px-2 py-1 rounded bg-yellow-600/20 border border-yellow-600/40 text-yellow-400 hover:bg-yellow-600/30">
                      확인
                    </button>
                    <button onClick={onOverrideCancel}
                      className="text-[9px] px-2 py-1 rounded border border-[#1a2844] text-gray-500 hover:text-gray-400">
                      취소
                    </button>
                  </div>
                </div>
              )}
            </div>
          )) : (
            <div className="px-3 py-8 text-center text-gray-700 text-[11px]">오늘 추천 없음</div>
          )}
        </div>
      </div>

      {/* History by type */}
      {historyType && history.length > 0 && (
        <div className="wr-card">
          <div className="wr-card-header text-purple-400">{TYPE_KO[historyType]} 이력 ({history.length}건)</div>
          <div className="divide-y divide-[#0e1825] max-h-[300px] overflow-y-auto">
            {history.map((d: any, i: number) => (
              <div key={i} className="px-3 py-2 text-[10px]">
                <div className="flex justify-between">
                  <span className="text-gray-300 font-mono">{d.keyword || d.context || "—"}</span>
                  <span className="text-gray-600">{d.created_at?.slice(0, 16)}</span>
                </div>
                <div className="text-gray-500 mt-0.5">{d.recommendation}</div>
                {d.override_value && (
                  <div className="text-yellow-500/70 mt-0.5">수정: {d.override_value}</div>
                )}
                {d.outcome_grade && (
                  <span className={`inline-block mt-0.5 px-1.5 py-0.5 rounded border text-[9px] ${GRADE_STYLE[d.outcome_grade] || ""}`}>
                    {d.outcome_grade}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Evaluate Tab ── */
function EvaluateTab({ awaiting, onGrade, onAutoEvaluate }: any) {
  const grades = ["correct", "partial", "wrong", "inconclusive"];
  const gradeKo: Record<string, string> = { correct: "정확", partial: "부분정확", wrong: "오류", inconclusive: "판단불가" };

  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <button onClick={onAutoEvaluate}
          className="text-[9px] px-3 py-1.5 rounded bg-purple-600/20 border border-purple-600/40 text-purple-400 hover:bg-purple-600/30 transition">
          자동 평가 실행
        </button>
      </div>

      <div className="wr-card">
        <div className="wr-card-header text-purple-400">평가 대기 ({awaiting.length}건)</div>
        <div className="divide-y divide-[#0e1825]">
          {awaiting.length > 0 ? awaiting.map((d: any) => (
            <div key={d.decision_id} className="px-3 py-2.5">
              <div className="flex items-center gap-2">
                <span className="text-[9px] bg-blue-950/40 border border-blue-800/30 text-blue-400/80 px-1.5 py-0.5 rounded">
                  {TYPE_KO[d.decision_type] || d.decision_type}
                </span>
                <span className="text-[11px] text-gray-200 font-mono">{d.keyword || "—"}</span>
                <span className="text-[9px] text-gray-600">{d.created_at?.slice(0, 10)}</span>
              </div>
              <div className="text-[11px] text-gray-400 mt-1">{d.recommendation}</div>
              <div className="flex gap-1.5 mt-2">
                {grades.map((g) => (
                  <button key={g} onClick={() => onGrade(d.decision_id, g)}
                    className={`text-[9px] px-2 py-1 rounded border transition hover:opacity-80 ${GRADE_STYLE[g]}`}>
                    {gradeKo[g]}
                  </button>
                ))}
              </div>
            </div>
          )) : (
            <div className="px-3 py-8 text-center text-gray-700 text-[11px]">평가 대기 항목 없음</div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Accuracy Tab ── */
function AccuracyTab({ accuracy }: { accuracy: any }) {
  if (!accuracy) return <div className="text-center py-8 text-gray-700 text-[11px]">데이터 없음</div>;

  return (
    <div className="space-y-2">
      {/* Overall */}
      <div className="wr-card border-l-2 border-l-emerald-500">
        <div className="wr-card-header text-emerald-400">전체 정확도</div>
        <div className="px-3 py-3 flex items-center gap-4">
          <div className="text-[28px] wr-metric text-emerald-400">
            {accuracy.overall?.accuracy_rate != null ? `${(accuracy.overall.accuracy_rate * 100).toFixed(0)}%` : "—"}
          </div>
          <div className="text-[10px] text-gray-500">
            총 {accuracy.overall?.total || 0}건 평가 완료
          </div>
        </div>
      </div>

      {/* By type */}
      <div className="wr-card">
        <div className="wr-card-header">유형별 정확도</div>
        <div className="px-3 py-2.5 space-y-2">
          {accuracy.by_type && (Array.isArray(accuracy.by_type) ? accuracy.by_type : []).map((row: any) => {
            const pct = row.accuracy_rate != null ? (row.accuracy_rate * 100) : 0;
            return (
              <div key={row.decision_type}>
                <div className="flex justify-between text-[10px] mb-0.5">
                  <span className="text-gray-400">{TYPE_KO[row.decision_type] || row.decision_type}</span>
                  <span className="font-mono text-gray-300">{pct.toFixed(0)}% ({row.total || 0}건)</span>
                </div>
                <div className="h-1.5 bg-[#0a1019] rounded overflow-hidden">
                  <div
                    className={`h-full rounded transition-all ${pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-yellow-500" : "bg-red-500"}`}
                    style={{ width: `${Math.min(pct, 100)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ── Patterns Tab ── */
function PatternsTab({ stats }: { stats: any }) {
  if (!stats) return <div className="text-center py-8 text-gray-700 text-[11px]">데이터 없음</div>;

  return (
    <div className="space-y-2">
      {/* Override stats */}
      {(() => {
        const byType = stats.by_type || {};
        const totalAll = Object.values(byType).reduce((s: number, d: any) => s + (d.total || 0), 0);
        const overriddenAll = Object.values(byType).reduce((s: number, d: any) => s + (d.overridden || 0), 0);
        return (
          <>
            <div className="wr-card border-l-2 border-l-yellow-500">
              <div className="wr-card-header text-yellow-400">수정 패턴 분석</div>
              <div className="px-3 py-2.5 grid grid-cols-3 gap-3 text-center">
                <div>
                  <div className="text-[8px] text-gray-600 uppercase">총 수정</div>
                  <div className="text-[20px] text-yellow-400 wr-metric">{overriddenAll}</div>
                </div>
                <div>
                  <div className="text-[8px] text-gray-600 uppercase">수정률</div>
                  <div className="text-[20px] text-yellow-400 wr-metric">
                    {totalAll > 0 ? `${((overriddenAll / totalAll) * 100).toFixed(0)}%` : "—"}
                  </div>
                </div>
                <div>
                  <div className="text-[8px] text-gray-600 uppercase">총 결정</div>
                  <div className="text-[20px] text-gray-300 wr-metric">{totalAll}</div>
                </div>
              </div>
            </div>

            {Object.keys(byType).length > 0 && (
              <div className="wr-card">
                <div className="wr-card-header">유형별 수정 빈도</div>
                <div className="px-3 py-2.5 space-y-2">
                  {Object.entries(byType).map(([type, data]: [string, any]) => {
                    const pct = data.override_rate != null ? (data.override_rate * 100) : 0;
                    return (
                      <div key={type}>
                        <div className="flex justify-between text-[10px] mb-0.5">
                          <span className="text-gray-400">{TYPE_KO[type] || type}</span>
                          <span className="font-mono text-yellow-400/70">{pct.toFixed(0)}% ({data.overridden || 0}/{data.total || 0})</span>
                        </div>
                        <div className="h-1.5 bg-[#0a1019] rounded overflow-hidden">
                          <div className="h-full rounded bg-yellow-500/70 transition-all" style={{ width: `${Math.min(pct, 100)}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        );
      })()}
    </div>
  );
}
