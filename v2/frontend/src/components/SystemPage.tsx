"use client";
import { useState, useEffect, useCallback } from "react";
import { getSystemHealth, getApiStatus } from "@/lib/api";

export function SystemPage() {
  const [health, setHealth] = useState<any>(null);
  const [apiStatus, setApiStatus] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState("");

  const refresh = useCallback(() => {
    setLoading(true);
    getSystemHealth()
      .then(d => { setHealth(d); setLastRefresh(new Date().toLocaleTimeString("ko-KR")); })
      .catch(() => setHealth(null))
      .finally(() => setLoading(false));
    getApiStatus().then(d => setApiStatus(d?.apis || [])).catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // 30초마다 자동 갱신
  useEffect(() => {
    const iv = setInterval(refresh, 30000);
    return () => clearInterval(iv);
  }, [refresh]);

  if (loading && !health) return <div className="text-center py-8 text-gray-500">시스템 점검 중...</div>;
  if (!health) return <div className="text-center py-8 text-red-400">시스템 상태 조회 실패</div>;

  const s = health.summary || {};
  const overallColor = s.overall === "healthy" ? "text-emerald-400" : s.overall === "degraded" ? "text-amber-400" : "text-red-400";
  const overallBg = s.overall === "healthy" ? "bg-emerald-950/20 border-emerald-800/40" : s.overall === "degraded" ? "bg-amber-950/20 border-amber-800/40" : "bg-red-950/20 border-red-800/40";
  const overallLabel = s.overall === "healthy" ? "HEALTHY" : s.overall === "degraded" ? "DEGRADED" : "CRITICAL";

  return (
    <div className="space-y-2 max-w-5xl mx-auto pb-12">
      {/* Header */}
      <div className={`wr-card border-t-2 ${s.overall === "healthy" ? "border-t-emerald-600" : s.overall === "degraded" ? "border-t-amber-600" : "border-t-red-600"}`}>
        <div className="px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-[14px] font-bold text-gray-200">System Health</h2>
              <div className="text-[9px] text-gray-600 mt-0.5">30초 자동 갱신 | 마지막: {lastRefresh}</div>
            </div>
            <div className={`px-3 py-1.5 rounded border font-black text-[11px] tracking-wider ${overallBg} ${overallColor}`}>
              {s.overall === "healthy" && <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1.5 animate-pulse" />}
              {overallLabel}
            </div>
          </div>
          <button onClick={refresh} disabled={loading}
            className="text-[10px] bg-[#0d1420] border border-[#1a2844] text-gray-400 px-3 py-1.5 rounded hover:text-white transition disabled:opacity-30">
            {loading ? "점검 중..." : "새로고침"}
          </button>
        </div>
      </div>

      {/* 요약 카드 */}
      <div className="grid grid-cols-5 gap-1.5">
        {[
          { label: "엔진", ok: s.engines_ok, total: s.engines_total, icon: "⚙" },
          { label: "수집기", ok: s.collectors_ok, total: s.collectors_total, icon: "📡" },
          { label: "API 키", ok: s.api_keys_ok, total: s.api_keys_total, icon: "🔑" },
          { label: "스냅샷", ok: health.snapshots?.count || 0, total: null, icon: "📁" },
          { label: "오류", ok: null, total: s.error_count, icon: "⚠" },
        ].map((c, i) => (
          <div key={i} className="wr-card">
            <div className="p-3 text-center">
              <div className="text-[8px] text-gray-600 uppercase">{c.label}</div>
              <div className={`text-2xl font-black wr-metric mt-0.5 ${
                i === 4 ? (c.total === 0 ? "text-emerald-400" : "text-red-400") :
                (c.total !== null && c.ok === c.total) ? "text-emerald-400" :
                c.ok > 0 ? "text-amber-400" : "text-red-400"
              }`}>
                {i === 4 ? c.total : c.total !== null ? `${c.ok}/${c.total}` : c.ok}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 오류 배너 */}
      {health.errors && health.errors.length > 0 && (
        <div className="wr-card border-l-2 border-l-red-500">
          <div className="px-4 py-2.5">
            <div className="text-[9px] text-red-400 font-bold uppercase tracking-widest mb-1.5">오류 {health.errors.length}건</div>
            {health.errors.map((err: string, i: number) => (
              <div key={i} className="flex items-start gap-2 text-[10px] py-0.5">
                <span className="text-red-500 shrink-0">●</span>
                <span className="text-red-300/80">{err}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 엔진 모듈 */}
      <div className="wr-card">
        <div className="wr-card-header flex justify-between">
          <span>엔진 모듈 ({s.engines_ok}/{s.engines_total})</span>
          <span className={`text-[9px] font-bold ${s.engines_ok === s.engines_total ? "text-emerald-400" : "text-amber-400"}`}>
            {s.engines_ok === s.engines_total ? "ALL OK" : `${s.engines_total - s.engines_ok} ERROR`}
          </span>
        </div>
        <div className="divide-y divide-[#0e1825]">
          {(health.engines || []).map((e: any, i: number) => (
            <div key={i} className="flex items-center gap-2 px-3 py-1.5 text-[10px]">
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${e.status === "ok" ? "bg-emerald-500" : "bg-red-500"}`} />
              <span className="text-gray-300 w-28 shrink-0">{e.name}</span>
              <span className="text-gray-600 text-[8px] font-mono flex-1 truncate">{e.module}</span>
              {e.error && <span className="text-red-400 text-[8px] truncate max-w-[200px]">{e.error}</span>}
            </div>
          ))}
        </div>
      </div>

      {/* 수집기 */}
      <div className="wr-card">
        <div className="wr-card-header flex justify-between">
          <span>수집기 ({s.collectors_ok}/{s.collectors_total})</span>
          <span className={`text-[9px] font-bold ${s.collectors_ok === s.collectors_total ? "text-emerald-400" : "text-amber-400"}`}>
            {s.collectors_ok === s.collectors_total ? "ALL OK" : `${s.collectors_total - s.collectors_ok} ERROR`}
          </span>
        </div>
        <div className="divide-y divide-[#0e1825]">
          {(health.collectors || []).map((c: any, i: number) => (
            <div key={i} className="flex items-center gap-2 px-3 py-1.5 text-[10px]">
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${c.status === "ok" ? "bg-emerald-500" : "bg-red-500"}`} />
              <span className="text-gray-300 w-28 shrink-0">{c.name}</span>
              <span className="text-gray-600 text-[8px] font-mono flex-1 truncate">{c.module}</span>
              {c.error && <span className="text-red-400 text-[8px] truncate max-w-[200px]">{c.error}</span>}
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        {/* API 키 */}
        <div className="wr-card">
          <div className="wr-card-header">API 키</div>
          <div className="divide-y divide-[#0e1825]">
            {(health.api_keys || []).map((k: any, i: number) => (
              <div key={i} className="flex items-center gap-2 px-3 py-2 text-[10px]">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${k.status === "ok" ? "bg-emerald-500" : "bg-red-500"}`} />
                <span className="text-gray-300 flex-1">{k.name}</span>
                {k.status === "ok" ? (
                  <span className="text-[8px] text-gray-600 font-mono">{k.preview}</span>
                ) : (
                  <span className="text-[8px] text-red-400">미설정</span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 데이터 소스 */}
        <div className="wr-card">
          <div className="wr-card-header">데이터 소스</div>
          <div className="divide-y divide-[#0e1825]">
            {(health.data_sources || []).map((d: any, i: number) => (
              <div key={i} className="flex items-center gap-2 px-3 py-2 text-[10px]">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${d.status === "ok" ? "bg-emerald-500" : "bg-red-500"}`} />
                <span className="text-gray-300 w-24 shrink-0">{d.name}</span>
                {d.status === "ok" ? (
                  <>
                    <span className="text-gray-500 text-[8px]">{d.latest}</span>
                    <span className="text-gray-400 text-[9px] ml-auto">{d.value}</span>
                  </>
                ) : (
                  <span className="text-red-400 text-[8px]">{d.error}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 스냅샷 + 실시간 테스트 */}
      <div className="grid grid-cols-2 gap-1.5">
        <div className="wr-card">
          <div className="wr-card-header">인덱스 스냅샷</div>
          <div className="px-3 py-2 space-y-1.5">
            {health.snapshots ? (
              <>
                <div className="flex justify-between text-[10px]">
                  <span className="text-gray-500">저장 수</span>
                  <span className="text-gray-200 font-bold">{health.snapshots.count}건</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-gray-500">범위</span>
                  <span className="text-gray-400">{health.snapshots.oldest} ~ {health.snapshots.newest}</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-gray-500">최종 수정</span>
                  <span className="text-gray-400">{health.snapshots.last_modified?.slice(0, 19).replace("T", " ")}</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-gray-500">최신 LI</span>
                  <span className={`font-bold ${(health.snapshots.latest_li || 50) >= 50 ? "text-cyan-400" : "text-red-400"}`}>
                    {health.snapshots.latest_li}
                  </span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-gray-500">데이터 품질</span>
                  <span className={`font-bold ${health.snapshots.latest_quality === "high" ? "text-emerald-400" : "text-amber-400"}`}>
                    {health.snapshots.latest_quality}
                  </span>
                </div>
              </>
            ) : (
              <div className="text-[10px] text-red-400">스냅샷 없음</div>
            )}
          </div>
        </div>

        <div className="wr-card">
          <div className="wr-card-header">실시간 수집 테스트</div>
          <div className="px-3 py-2">
            {health.live_test ? (
              health.live_test.status === "ok" ? (
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2 text-[10px]">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                    <span className="text-emerald-400 font-bold">네이버 뉴스 수집 정상</span>
                  </div>
                  <div className="text-[9px] text-gray-500">{health.live_test.articles}건 수집</div>
                  <div className="text-[9px] text-gray-400 truncate">{health.live_test.latest_title}</div>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-[10px]">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
                  <span className="text-red-400">{health.live_test.error}</span>
                </div>
              )
            ) : (
              <div className="text-[10px] text-gray-600">테스트 미실행</div>
            )}
          </div>
        </div>
      </div>

      {/* API 호출 상태 */}
      {apiStatus.length > 0 && (
        <div className="wr-card">
          <div className="wr-card-header flex justify-between">
            <span>API 호출 상태</span>
            <span className="text-[9px] text-gray-400 normal-case tracking-normal font-normal">캐시 TTL · 일일 한도 · 마지막 데이터 수집</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-gray-400 border-b border-[#1a2844]">
                  <th className="text-left py-2 px-3">API</th>
                  <th className="text-center py-2 px-2">상태</th>
                  <th className="text-right py-2 px-2">호출/한도</th>
                  <th className="text-center py-2 px-2">캐시</th>
                  <th className="text-center py-2 px-2">마지막 호출</th>
                  <th className="text-center py-2 px-2">마지막 수집</th>
                  <th className="text-left py-2 px-2">에러</th>
                </tr>
              </thead>
              <tbody>
                {apiStatus.map((api: any, i: number) => (
                  <tr key={i} className="border-b border-[#0e1825]">
                    <td className="py-1.5 px-3 text-gray-200 font-bold">{api.api}</td>
                    <td className="py-1.5 px-2 text-center">
                      <span className={`w-2 h-2 rounded-full inline-block ${api.status === "ok" ? "bg-emerald-500" : "bg-rose-500"}`} />
                    </td>
                    <td className="py-1.5 px-2 text-right text-gray-300 font-mono">
                      {api.calls_today} / {api.daily_limit}
                    </td>
                    <td className="py-1.5 px-2 text-center text-gray-400">{api.cache_ttl}</td>
                    <td className="py-1.5 px-2 text-center text-gray-400 font-mono">{api.last_call}</td>
                    <td className="py-1.5 px-2 text-center font-mono">
                      <span className={api.last_data_update === "—" ? "text-gray-400" : "text-emerald-400"}>
                        {api.last_data_update || "—"}
                      </span>
                    </td>
                    <td className="py-1.5 px-2 text-rose-400 text-[9px] truncate max-w-[150px]">{api.last_error || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 마지막 수집 시각 */}
      {health.last_run && Object.keys(health.last_run).length > 0 && (
        <div className="wr-card">
          <div className="wr-card-header flex justify-between">
            <span>마지막 수집/실행 시각</span>
            <span className="text-[8px] text-gray-600">갱신 버튼 실행 시 기록</span>
          </div>
          <div className="divide-y divide-[#0e1825]">
            {Object.entries(health.last_run)
              .sort(([,a]: any, [,b]: any) => (b as string).localeCompare(a as string))
              .map(([name, ts]: [string, any]) => {
                const label: Record<string, string> = {
                  naver_news: "📰 네이버 뉴스", social_collector: "📝 블로그/카페",
                  community: "💬 커뮤니티 22곳", youtube: "📺 유튜브",
                  trends: "📈 구글 트렌드", pretrigger: "⚔ Pre-Trigger",
                  ai_sentiment: "🤖 AI 감성", national_poll: "🏛 대통령 지지율",
                  economic: "💰 경제 지표", regional_media: "📺 지역 언론",
                  news_comment: "💬 뉴스 댓글", leading_index: "🧭 선행지수",
                  index_tracker: "📁 스냅샷 저장",
                };
                const elapsed = ts ? Math.round((Date.now() - new Date(ts).getTime()) / 60000) : null;
                return (
                  <div key={name} className="flex items-center gap-2 px-3 py-1.5 text-[10px]">
                    <span className="text-gray-300 w-36 shrink-0">{label[name] || name}</span>
                    <span className="text-gray-500 text-[9px] font-mono flex-1">{(ts as string).slice(11, 19)}</span>
                    {elapsed !== null && (
                      <span className={`text-[8px] font-mono ${elapsed <= 5 ? "text-emerald-400" : elapsed <= 60 ? "text-amber-400" : "text-red-400"}`}>
                        {elapsed < 1 ? "방금" : elapsed < 60 ? `${elapsed}분 전` : `${Math.round(elapsed / 60)}시간 전`}
                      </span>
                    )}
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* 점검 시각 */}
      <div className="text-[8px] text-gray-700 text-right px-2">
        점검: {health.checked_at?.slice(0, 19).replace("T", " ")} | 자동 갱신 30초
      </div>
    </div>
  );
}
