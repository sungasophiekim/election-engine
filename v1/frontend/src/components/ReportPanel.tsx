"use client";
import { useState, useCallback } from "react";
import { useStore } from "@/lib/store";
import { getDailyBriefing, getWeeklyBriefing } from "@/lib/api";
import { ResearchPage } from "./ResearchTab";

const TABS = ["데일리 리포트", "위클리 리포트", "리서치"] as const;
type Tab = (typeof TABS)[number];

/* ═══ PDF 출력 ═══ */
function printReport(title: string) {
  const el = document.getElementById("report-body");
  if (!el) return;
  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(`<!DOCTYPE html><html><head><title>${title}</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif; color:#1a1a1a; padding:32px 40px; font-size:12px; line-height:1.7; max-width:800px; margin:0 auto; }
  h1 { font-size:18px; font-weight:900; margin-bottom:2px; }
  .subtitle { font-size:11px; color:#888; margin-bottom:16px; }
  .summary-box { background:#f0f7ff; border-left:4px solid #2563eb; padding:12px 16px; margin:16px 0; border-radius:4px; font-size:13px; line-height:1.8; }
  h2 { font-size:14px; font-weight:800; margin:20px 0 8px; padding:6px 0; border-bottom:2px solid #1a1a1a; }
  h3 { font-size:12px; font-weight:700; margin:12px 0 6px; color:#374151; }
  table { width:100%; border-collapse:collapse; margin:8px 0 16px; font-size:11px; }
  th { background:#f8fafc; border:1px solid #e2e8f0; padding:6px 10px; text-align:left; font-weight:700; font-size:10px; color:#64748b; text-transform:uppercase; letter-spacing:0.05em; }
  td { border:1px solid #e2e8f0; padding:6px 10px; vertical-align:top; }
  .our { color:#2563eb; font-weight:600; }
  .opp { color:#dc2626; font-weight:600; }
  .tag { display:inline-block; padding:2px 8px; border-radius:4px; font-size:10px; font-weight:700; }
  .tag-red { background:#fef2f2; color:#dc2626; }
  .tag-amber { background:#fffbeb; color:#d97706; }
  .tag-green { background:#f0fdf4; color:#16a34a; }
  .tag-blue { background:#eff6ff; color:#2563eb; }
  .tag-gray { background:#f9fafb; color:#6b7280; }
  .action-box { background:#fafafa; border:1px solid #e5e7eb; border-radius:6px; padding:10px 14px; margin:6px 0; }
  .action-box .title { font-weight:700; font-size:12px; margin-bottom:4px; }
  .action-box .meta { font-size:10px; color:#6b7280; }
  .msg-box { background:#eff6ff; border:1px solid #bfdbfe; border-radius:6px; padding:10px 14px; margin:6px 0; }
  .msg-text { font-size:13px; font-weight:700; color:#1e40af; }
  .caution-box { background:#fffbeb; border-left:4px solid #f59e0b; padding:8px 12px; margin:10px 0; font-size:11px; }
  .danger-box { background:#fef2f2; border-left:4px solid #dc2626; padding:8px 12px; margin:10px 0; font-size:11px; }
  .diagnosis-box { background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:10px 14px; margin:6px 0; }
  .diagnosis-box .label { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:4px; }
  .footer { margin-top:24px; padding-top:8px; border-top:1px solid #e5e7eb; font-size:9px; color:#9ca3af; }
  @page { size:A4; margin:20mm 15mm; }
  @media print { body { padding:0; } }
</style></head><body>`);

  // Generate clean print HTML from data
  const clone = el.cloneNode(true) as HTMLElement;
  w.document.write(clone.innerHTML);
  w.document.write("</body></html>");
  w.document.close();
  setTimeout(() => w.print(), 600);
}

/* ═══ 생성 버튼 ═══ */
function GenerateBtn({ loading, onClick, label }: { loading: boolean; onClick: () => void; label: string }) {
  return (
    <div className="py-12 text-center">
      {loading ? (
        <>
          <div className="text-cyan-400 text-sm animate-pulse mb-2">AI 전략 분석 생성 중...</div>
          <div className="text-xs text-gray-600">뉴스·판세·여론 데이터 기반 브리핑 작성 (30~60초)</div>
        </>
      ) : (
        <>
          <div className="text-xs text-gray-500 mb-4">AI가 현재 수집 데이터를 분석하여 전략 리포트를 생성합니다.</div>
          <button onClick={onClick} className="text-sm font-bold text-cyan-300 bg-cyan-900/30 border border-cyan-700/40 px-6 py-3 rounded-lg hover:bg-cyan-800/40 transition">
            {label}
          </button>
        </>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════
   데일리 리포트
═══════════════════════════════════════════ */
function DailyReport() {
  const indices = useStore((s) => s.indices);
  const prediction = useStore((s) => s.prediction);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const pandse = indices?.pandse;
  const poll = prediction?.poll || {};
  const dDay = pandse?.d_day || "?";
  const today = new Date().toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit" });

  const generate = useCallback(async (force = false) => {
    setLoading(true);
    try { setData(await getDailyBriefing(force)); } catch (e) { setData({ error: String(e) }); }
    finally { setLoading(false); }
  }, []);

  if (!data && !loading) return <GenerateBtn loading={false} onClick={() => generate()} label="데일리 리포트 생성" />;
  if (loading) return <GenerateBtn loading={true} onClick={() => {}} label="" />;
  if (data?.error) return (
    <div className="py-8 text-center">
      <div className="text-sm text-red-400 mb-3">생성 실패: {data.error}</div>
      <button onClick={() => generate(true)} className="text-xs text-cyan-300 underline">재시도</button>
    </div>
  );

  const ir = data.issue_review || {};
  const st = data.strategy || {};

  return (
    <div id="report-body" className="space-y-5 max-w-[820px] mx-auto">

      {/* ── 헤더 ── */}
      <div className="flex items-end justify-between border-b border-gray-700 pb-3">
        <div>
          <h1 className="text-lg font-black text-gray-100 tracking-tight">경남도지사 선거 전략대응 리포트</h1>
          <div className="subtitle text-xs text-gray-500 mt-0.5">{today} | 선거 D-{dDay}일 | 캠프 내부 한정</div>
        </div>
        <button onClick={() => generate(true)} className="text-[10px] text-gray-600 hover:text-gray-400 border border-gray-700 px-2.5 py-1 rounded transition">재생성</button>
      </div>

      {/* ── 종합요약 ── */}
      {data.summary && (
        <div className="summary-box bg-blue-950/20 border-l-4 border-l-blue-500 rounded-r-lg px-4 py-3">
          <div className="text-[10px] text-blue-400 font-bold uppercase tracking-widest mb-1">한줄 요약</div>
          <div className="text-[13px] text-gray-100 leading-[1.8] whitespace-pre-line">{data.summary}</div>
        </div>
      )}

      {/* ══ 1. 24시간 이슈 점검 ══ */}
      <section>
        <h2 className="text-[14px] font-black text-gray-100 border-b-2 border-gray-600 pb-1 mb-3">1. 지난 24시간 이슈 점검</h2>

        {/* 이슈 TOP5 테이블 */}
        {ir.issue_top5?.length > 0 && (
          <div className="mb-4">
            <h3 className="text-xs text-gray-400 font-bold uppercase tracking-wider mb-2">이슈 TOP 5</h3>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b-2 border-gray-700">
                  <th className="py-2 px-2 text-gray-500 text-center w-8">#</th>
                  <th className="py-2 px-2 text-gray-500 text-left">이슈</th>
                  <th className="py-2 px-2 text-gray-500 text-center w-12">기사</th>
                  <th className="py-2 px-2 text-gray-500 text-center w-16">진영</th>
                  <th className="py-2 px-2 text-gray-500 text-left">지표 영향</th>
                </tr>
              </thead>
              <tbody>
                {ir.issue_top5.map((iss: any) => (
                  <tr key={iss.rank} className="border-b border-gray-800/50">
                    <td className="py-2.5 px-2 text-center text-gray-500 font-bold">{iss.rank}</td>
                    <td className="py-2.5 px-2 text-gray-100 font-bold">{iss.name}</td>
                    <td className="py-2.5 px-2 text-center font-mono text-gray-400">{iss.count}건</td>
                    <td className="py-2.5 px-2 text-center">
                      <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                        iss.side?.includes("우리") ? "bg-blue-500/15 text-blue-400" :
                        iss.side?.includes("상대") ? "bg-red-500/15 text-red-400" :
                        "bg-gray-700/30 text-gray-500"
                      }`}>{iss.side}</span>
                    </td>
                    <td className="py-2.5 px-2 text-gray-400 text-[11px]">{iss.impact}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* 이슈별 세그먼트 진단 */}
            <div className="space-y-1.5 mt-2">
              {ir.issue_top5.filter((iss: any) => iss.diagnosis).map((iss: any) => (
                <div key={`diag-${iss.rank}`} className="bg-gray-800/20 rounded-lg px-3 py-2 text-[11px] leading-relaxed">
                  <span className="text-gray-300 font-bold mr-1">{iss.rank}. {iss.name}</span>
                  <span className="text-gray-400">{iss.diagnosis}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 리액션 TOP5 */}
        {ir.reaction_top5?.length > 0 && (
          <div className="mb-4">
            <h3 className="text-xs text-gray-400 font-bold uppercase tracking-wider mb-2">시민 리액션 TOP 5</h3>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b-2 border-gray-700">
                  <th className="py-2 px-2 text-gray-500 text-center w-8">#</th>
                  <th className="py-2 px-2 text-gray-500 text-left w-28">키워드</th>
                  <th className="py-2 px-2 text-gray-500 text-center w-14">감성</th>
                  <th className="py-2 px-2 text-gray-500 text-center w-14">볼륨</th>
                  <th className="py-2 px-2 text-gray-500 text-left">인사이트</th>
                </tr>
              </thead>
              <tbody>
                {ir.reaction_top5.map((r: any) => (
                  <tr key={r.rank} className="border-b border-gray-800/50">
                    <td className="py-2 px-2 text-center text-gray-500">{r.rank}</td>
                    <td className="py-2 px-2 text-gray-100 font-bold">{r.keyword}</td>
                    <td className="py-2 px-2 text-center">
                      <span className={`text-[10px] font-bold ${r.sentiment === "긍정" ? "text-emerald-400" : r.sentiment === "부정" ? "text-red-400" : "text-amber-400"}`}>{r.sentiment}</span>
                    </td>
                    <td className="py-2 px-2 text-center text-gray-400">{r.volume}</td>
                    <td className="py-2 px-2 text-gray-400 text-[11px]">{r.insight}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 후보별 진단 — 2컬럼 */}
        {(ir.our_diagnosis || ir.opp_diagnosis) && (
          <div className="grid grid-cols-2 gap-3">
            {ir.our_diagnosis && (
              <div className="rounded-lg border border-blue-800/30 bg-blue-950/10 p-3">
                <div className="text-[10px] text-blue-400 font-bold uppercase tracking-wider mb-1.5">우리 후보 진단</div>
                <div className="text-[11px] text-gray-300 leading-[1.7]">{ir.our_diagnosis}</div>
              </div>
            )}
            {ir.opp_diagnosis && (
              <div className="rounded-lg border border-red-800/30 bg-red-950/10 p-3">
                <div className="text-[10px] text-red-400 font-bold uppercase tracking-wider mb-1.5">상대 후보 진단</div>
                <div className="text-[11px] text-gray-300 leading-[1.7]">{ir.opp_diagnosis}</div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* ══ 2. 대응전략 ══ */}
      <section>
        <h2 className="text-[14px] font-black text-gray-100 border-b-2 border-gray-600 pb-1 mb-3">2. 대응전략</h2>

        {/* 단기 */}
        {st.short_term?.length > 0 && (
          <div className="mb-4">
            <h3 className="text-xs text-amber-400 font-bold mb-2">단기 전략 — 이슈 대응</h3>
            <div className="space-y-2">
              {st.short_term.map((s: any, i: number) => (
                <div key={i} className="rounded-lg border border-gray-700/50 bg-gray-800/15 p-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="text-[12px] text-gray-100 font-bold">{s.title}</div>
                    <span className="text-[10px] text-gray-500 bg-gray-800/50 px-2 py-0.5 rounded">{s.timeline}</span>
                  </div>
                  <div className="text-[10px] text-gray-500 mb-1">{s.issue_context}</div>
                  <div className="text-[11px] text-gray-300 leading-[1.7] mb-2">{s.action}</div>
                  <div className="text-[11px] text-emerald-400/90 mb-1">
                    <span className="font-bold">예상 효과:</span> {s.expected_impact}
                  </div>
                  {s.risk && (
                    <div className="bg-amber-500/5 border-l-2 border-l-amber-500/50 pl-2.5 py-1 text-[10px] text-amber-300/80">
                      <span className="font-bold">리스크:</span> {s.risk}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 중장기 */}
        {st.mid_long_term?.length > 0 && (
          <div>
            <h3 className="text-xs text-cyan-400 font-bold mb-2">중장기 전략 — 판세·후보 커리어</h3>
            <div className="space-y-2">
              {st.mid_long_term.map((s: any, i: number) => (
                <div key={i} className="rounded-lg border border-cyan-800/20 bg-cyan-950/10 p-3">
                  <div className="text-[12px] text-gray-100 font-bold mb-1">{s.title}</div>
                  <div className="text-[10px] text-gray-500 mb-1">{s.rationale}</div>
                  <div className="text-[11px] text-gray-300 leading-[1.7] mb-1.5">{s.action}</div>
                  <div className="flex gap-4 text-[10px]">
                    <span className="text-purple-400">대상: {s.target_segment}</span>
                    <span className="text-gray-500">단기 연계: {s.synergy}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* ══ 3. 메시지 ══ */}
      {data.messages?.length > 0 && (
        <section>
          <h2 className="text-[14px] font-black text-gray-100 border-b-2 border-gray-600 pb-1 mb-3">3. 메시지 및 우선순위</h2>
          <div className="space-y-2.5">
            {data.messages.map((m: any) => (
              <div key={m.priority} className="rounded-lg border border-gray-700/50 bg-gray-800/10 p-3">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="bg-blue-500/20 text-blue-400 text-[10px] font-black px-2 py-0.5 rounded">우선순위 {m.priority}</span>
                  <span className="text-[10px] text-gray-500">{m.target}</span>
                  <span className="text-[10px] text-gray-600 ml-auto">{m.channel}</span>
                </div>
                <div className="bg-blue-950/15 border border-blue-800/20 rounded px-3 py-2 mb-1.5">
                  <div className="text-[13px] font-bold text-blue-300">&ldquo;{m.message}&rdquo;</div>
                  {m.sub_message && <div className="text-[10px] text-gray-400 mt-0.5">{m.sub_message}</div>}
                </div>
                {m.caution && (
                  <div className="text-[10px] text-amber-400/80 pl-1">
                    &#x26A0; {m.caution}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ══ 4. 일정 및 실행 ══ */}
      {data.execution?.length > 0 && (
        <section>
          <h2 className="text-[14px] font-black text-gray-100 border-b-2 border-gray-600 pb-1 mb-3">4. 일정 및 실행 제안</h2>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b-2 border-gray-700">
                <th className="py-2 px-2 text-gray-500 text-left w-24">언제</th>
                <th className="py-2 px-2 text-gray-500 text-left">무엇을</th>
                <th className="py-2 px-2 text-gray-500 text-left w-16">담당</th>
                <th className="py-2 px-2 text-gray-500 text-left w-36">측정 기준 (KPI)</th>
              </tr>
            </thead>
            <tbody>
              {data.execution.map((e: any, i: number) => (
                <tr key={i} className={`border-b border-gray-800/50 ${e.when?.includes("즉시") ? "bg-red-950/10" : ""}`}>
                  <td className={`py-2.5 px-2 font-mono text-[11px] ${
                    e.when?.includes("즉시") ? "text-red-400 font-bold" :
                    e.when?.includes("오늘") ? "text-amber-400 font-bold" :
                    "text-gray-400"
                  }`}>{e.when}</td>
                  <td className="py-2.5 px-2 text-gray-200 text-[11px]">{e.what}</td>
                  <td className="py-2.5 px-2 text-gray-500 text-[11px]">{e.who}</td>
                  <td className="py-2.5 px-2 text-gray-400 text-[10px]">{e.kpi}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* ══ 주의사항 ══ */}
      <div className="rounded-lg border border-red-900/30 bg-red-950/5 px-4 py-3 space-y-1.5 text-[11px]">
        <div className="text-red-400 font-bold text-xs mb-1">주의사항</div>
        <div className="flex gap-2 text-gray-400"><span className="text-red-400 shrink-0">&#x26D4;</span>상대 현직 성과 직접 부정 금지. &ldquo;더 잘할 수 있다&rdquo; 확장 프레임으로만 대응.</div>
        <div className="flex gap-2 text-gray-400"><span className="text-red-400 shrink-0">&#x26D4;</span>중앙당 이슈 편승 금지. &ldquo;경남만 보고 간다&rdquo; 원칙. 즉시 지역 의제로 전환.</div>
        <div className="flex gap-2 text-gray-400"><span className="text-amber-400 shrink-0">&#x26A0;</span>60대 고투표율 구조적 불리. 3040 사전투표 동원 캠페인 병행 필수.</div>
      </div>

      {/* ── 출처 ── */}
      <div className="footer text-[9px] text-gray-700 border-t border-gray-800 pt-2">
        네이버뉴스 11쿼리 24h + 커뮤니티 19+곳 + 블로그·카페·유튜브 + AI 감성분석 | 생성: {data.generated_at?.slice(0,16)} | AI 분석 기반, 참고용
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   위클리 리포트
═══════════════════════════════════════════ */
function WeeklyReport() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const generate = useCallback(async (force = false) => {
    setLoading(true);
    try { setData(await getWeeklyBriefing(force)); } catch (e) { setData({ error: String(e) }); }
    finally { setLoading(false); }
  }, []);

  if (!data && !loading) return <GenerateBtn loading={false} onClick={() => generate()} label="위클리 리포트 생성" />;
  if (loading) return <GenerateBtn loading={true} onClick={() => {}} label="" />;
  if (data?.error) return (
    <div className="py-8 text-center">
      <div className="text-sm text-red-400 mb-3">생성 실패: {data.error}</div>
      <button onClick={() => generate(true)} className="text-xs text-cyan-300 underline">재시도</button>
    </div>
  );

  return (
    <div id="report-body" className="space-y-5 max-w-[820px] mx-auto">

      {/* 헤더 */}
      <div className="flex items-end justify-between border-b border-gray-700 pb-3">
        <div>
          <h1 className="text-lg font-black text-gray-100">주간 성과 리포트</h1>
          <div className="text-xs text-gray-500 mt-0.5">{data.week} | 캠프 내부 한정</div>
        </div>
        <button onClick={() => generate(true)} className="text-[10px] text-gray-600 hover:text-gray-400 border border-gray-700 px-2.5 py-1 rounded transition">재생성</button>
      </div>

      {/* 주간 종합 */}
      {data.week_summary && (
        <div className="bg-amber-950/15 border-l-4 border-l-amber-500 rounded-r-lg px-4 py-3">
          <div className="text-[10px] text-amber-400 font-bold uppercase tracking-widest mb-1">주간 종합</div>
          <div className="text-[13px] text-gray-100 leading-[1.8] whitespace-pre-line">{data.week_summary}</div>
        </div>
      )}

      {/* KPI */}
      {data.kpi_review?.length > 0 && (
        <section>
          <h2 className="text-[14px] font-black text-gray-100 border-b-2 border-gray-600 pb-1 mb-3">KPI 달성 현황</h2>
          <table className="w-full text-xs">
            <thead><tr className="border-b-2 border-gray-700">
              <th className="py-2 px-2 text-gray-500 text-left">지표</th>
              <th className="py-2 px-2 text-gray-500 text-center w-14">주초</th>
              <th className="py-2 px-2 text-gray-500 text-center w-14">주말</th>
              <th className="py-2 px-2 text-gray-500 text-center w-14">변동</th>
              <th className="py-2 px-2 text-gray-500 text-center w-14">평가</th>
              <th className="py-2 px-2 text-gray-500 text-left">해석</th>
            </tr></thead>
            <tbody>
              {data.kpi_review.map((k: any, i: number) => (
                <tr key={i} className="border-b border-gray-800/50">
                  <td className="py-2.5 px-2 text-gray-200 font-bold">{k.metric}</td>
                  <td className="py-2.5 px-2 text-center font-mono text-gray-500">{k.start}</td>
                  <td className="py-2.5 px-2 text-center font-mono text-gray-200">{k.end}</td>
                  <td className="py-2.5 px-2 text-center font-mono font-bold text-cyan-400">{k.change}</td>
                  <td className="py-2.5 px-2 text-center">
                    <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                      k.grade === "달성" ? "bg-emerald-500/15 text-emerald-400" :
                      k.grade === "미달" ? "bg-red-500/15 text-red-400" :
                      "bg-gray-700/30 text-gray-400"
                    }`}>{k.grade}</span>
                  </td>
                  <td className="py-2.5 px-2 text-gray-400 text-[11px]">{k.analysis}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* 전략 실행 리뷰 */}
      {data.strategy_review?.length > 0 && (
        <section>
          <h2 className="text-[14px] font-black text-gray-100 border-b-2 border-gray-600 pb-1 mb-3">전략 실행 리뷰</h2>
          <div className="space-y-2">
            {data.strategy_review.map((s: any, i: number) => (
              <div key={i} className="rounded-lg border border-gray-700/50 bg-gray-800/10 p-3">
                <div className="text-[12px] text-gray-100 font-bold mb-1">{s.strategy}</div>
                <div className="text-[11px] text-gray-400 mb-1">{s.executed}</div>
                <div className="text-[11px] text-emerald-400/90">결과: {s.result}</div>
                <div className="text-[11px] text-amber-400/80">교훈: {s.lesson}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 세그먼트 분석 */}
      {data.segment_analysis?.length > 0 && (
        <section>
          <h2 className="text-[14px] font-black text-gray-100 border-b-2 border-gray-600 pb-1 mb-3">세그먼트별 분석</h2>
          <table className="w-full text-xs">
            <thead><tr className="border-b-2 border-gray-700">
              <th className="py-2 px-2 text-gray-500 text-left w-24">세그먼트</th>
              <th className="py-2 px-2 text-gray-500 text-left">이번 주 변화</th>
              <th className="py-2 px-2 text-gray-500 text-left">다음 주 조치</th>
            </tr></thead>
            <tbody>
              {data.segment_analysis.map((s: any, i: number) => (
                <tr key={i} className="border-b border-gray-800/50">
                  <td className="py-2.5 px-2 text-gray-200 font-bold">{s.segment}</td>
                  <td className="py-2.5 px-2 text-gray-400 text-[11px]">{s.trend}</td>
                  <td className="py-2.5 px-2 text-cyan-400/80 text-[11px]">{s.action_needed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* 다음 주 과제 */}
      {data.next_week && (
        <section>
          <h2 className="text-[14px] font-black text-gray-100 border-b-2 border-gray-600 pb-1 mb-3">다음 주 과제</h2>
          <div className="space-y-2">
            <div className="flex gap-3 items-start bg-amber-950/10 rounded-lg p-3">
              <span className="text-amber-400 font-black text-sm shrink-0">1</span>
              <div className="text-[12px] text-gray-200 leading-relaxed">{data.next_week.priority_1}</div>
            </div>
            <div className="flex gap-3 items-start bg-gray-800/20 rounded-lg p-3">
              <span className="text-gray-400 font-black text-sm shrink-0">2</span>
              <div className="text-[12px] text-gray-300 leading-relaxed">{data.next_week.priority_2}</div>
            </div>
            <div className="flex gap-3 items-start bg-gray-800/10 rounded-lg p-3">
              <span className="text-gray-500 font-black text-sm shrink-0">3</span>
              <div className="text-[12px] text-gray-400 leading-relaxed">{data.next_week.priority_3}</div>
            </div>
            {data.next_week.risk_watch && (
              <div className="bg-red-950/10 border-l-4 border-l-red-500/50 rounded-r-lg px-4 py-2.5 text-[11px] text-red-300/80">
                &#x26A0; 주의 감시: {data.next_week.risk_watch}
              </div>
            )}
          </div>
        </section>
      )}

      <div className="text-[9px] text-gray-700 border-t border-gray-800 pt-2">
        생성: {data.generated_at?.slice(0,16)} | AI 분석 기반, 참고용
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   메인 패널
═══════════════════════════════════════════ */
export default function ReportPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("데일리 리포트");
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div className="relative w-[920px] max-h-[92vh] bg-[#0a0f1a] border border-gray-800 rounded-xl shadow-2xl overflow-hidden anim-in"
        onClick={(e) => e.stopPropagation()}>

        {/* 상단 바 */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800 bg-[#080d16]">
          <div className="flex items-center gap-3">
            {TABS.map((t) => (
              <button key={t} onClick={() => setTab(t)}
                className={`text-xs font-bold px-3 py-1.5 rounded transition-all ${
                  tab === t
                    ? "text-white bg-gray-700/50"
                    : "text-gray-500 hover:text-gray-300"
                }`}>
                {t}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            {tab !== "리서치" && (
              <button
                onClick={() => printReport(tab === "데일리 리포트" ? "전략대응 리포트" : "주간 성과 리포트")}
                className="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 px-3 py-1.5 rounded transition-all">
                PDF 출력
              </button>
            )}
            <button onClick={onClose} className="text-gray-500 hover:text-white text-sm px-2 transition-colors">&#x2715;</button>
          </div>
        </div>

        {/* 본문 */}
        <div className="px-6 py-5 overflow-y-auto max-h-[calc(92vh-56px)]">
          {tab === "데일리 리포트" && <DailyReport />}
          {tab === "위클리 리포트" && <WeeklyReport />}
          {tab === "리서치" && <ResearchPage />}
        </div>
      </div>
    </div>
  );
}
