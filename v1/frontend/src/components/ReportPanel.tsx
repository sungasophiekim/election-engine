"use client";
import { useState, useCallback } from "react";
import { useStore } from "@/lib/store";
import { getDailyBriefing, getWeeklyBriefing, getTrainingData } from "@/lib/api";
import { ResearchPage } from "./ResearchTab";

const TABS = ["데일리 리포트", "위클리 리포트", "학습데이터", "리서치"] as const;
type Tab = (typeof TABS)[number];

/* ═══ PDF 출력 — 인라인 스타일 변환 ═══ */
function printReport(title: string) {
  const el = document.getElementById("report-body");
  if (!el) return;

  // 다크 테마 → 인쇄용 컬러 매핑
  const colorMap: Record<string, string> = {
    "text-gray-100": "#1a1a1a", "text-gray-200": "#333", "text-gray-300": "#444",
    "text-gray-400": "#666", "text-gray-500": "#888", "text-gray-600": "#999", "text-gray-700": "#aaa",
    "text-blue-300": "#2563eb", "text-blue-400": "#2563eb", "text-red-300": "#dc2626", "text-red-400": "#dc2626",
    "text-cyan-300": "#0891b2", "text-cyan-400": "#0891b2", "text-amber-300": "#d97706", "text-amber-400": "#d97706",
    "text-emerald-400": "#059669", "text-purple-400": "#7c3aed", "text-pink-300": "#db2777",
  };

  // DOM → 인쇄용 HTML 생성
  const clone = el.cloneNode(true) as HTMLElement;

  // 인라인 스타일 적용: 텍스트 색상 변환
  clone.querySelectorAll("*").forEach((node) => {
    const el = node as HTMLElement;
    const cls = el.className || "";
    if (typeof cls !== "string") return;

    // 배경색 → 흰 배경 호환으로 변환
    if (cls.includes("bg-blue-950") || cls.includes("bg-cyan-950")) el.style.background = "#eff6ff";
    else if (cls.includes("bg-red-950")) el.style.background = "#fef2f2";
    else if (cls.includes("bg-amber-950") || cls.includes("bg-amber-500")) el.style.background = "#fffbeb";
    else if (cls.includes("bg-gray-800") || cls.includes("bg-gray-700")) el.style.background = "#f9fafb";
    else if (cls.includes("bg-emerald-500") || cls.includes("bg-emerald-950")) el.style.background = "#f0fdf4";
    else el.style.background = "transparent";

    // 텍스트 색상
    for (const [tw, hex] of Object.entries(colorMap)) {
      if (cls.includes(tw)) { el.style.color = hex; break; }
    }
    // 기본 텍스트 색상
    if (!el.style.color && (cls.includes("text-gray-100") || cls.includes("text-gray-200"))) el.style.color = "#1a1a1a";

    // 보더
    if (cls.includes("border-gray-700") || cls.includes("border-gray-800") || cls.includes("border-gray-600")) el.style.borderColor = "#e2e8f0";
    if (cls.includes("border-blue-800") || cls.includes("border-blue-500")) el.style.borderColor = "#bfdbfe";
    if (cls.includes("border-red-800") || cls.includes("border-red-900")) el.style.borderColor = "#fecaca";
    if (cls.includes("border-amber-800") || cls.includes("border-amber-500")) el.style.borderColor = "#fde68a";
    if (cls.includes("border-cyan-800")) el.style.borderColor = "#a5f3fc";

    // 재생성 버튼 숨김
    if (el.tagName === "BUTTON") el.style.display = "none";
  });

  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(`<!DOCTYPE html><html><head><title>${title}</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: -apple-system, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
    color: #1a1a1a; padding: 28px 36px; font-size: 11.5px; line-height: 1.65;
    max-width: 780px; margin: 0 auto;
  }
  h1 { font-size: 17px; font-weight: 900; letter-spacing: -0.02em; }
  h2 { font-size: 13.5px; font-weight: 800; margin: 18px 0 8px; padding: 4px 0; border-bottom: 2px solid #1a1a1a; }
  h3 { font-size: 11.5px; font-weight: 700; margin: 10px 0 5px; color: #374151; text-transform: uppercase; letter-spacing: 0.04em; }
  section { margin-bottom: 6px; }
  table { width: 100%; border-collapse: collapse; margin: 6px 0 12px; font-size: 10.5px; }
  th { background: #f8fafc; border: 1px solid #e2e8f0; padding: 5px 8px; text-align: left; font-weight: 700; font-size: 9.5px; color: #64748b; text-transform: uppercase; letter-spacing: 0.04em; }
  td { border: 1px solid #e2e8f0; padding: 5px 8px; vertical-align: top; }
  span[class*="rounded"] { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 9px; }
  div[class*="rounded-lg"] { border-radius: 6px; padding: 8px 12px; margin: 5px 0; border: 1px solid #e5e7eb; }
  div[class*="border-l-4"], div[class*="border-l-2"] { border-left-width: 3px !important; border-left-style: solid !important; }
  div[class*="grid-cols-2"] { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  div[class*="space-y-"] > * + * { margin-top: 6px; }
  .footer, div[class*="footer"] { margin-top: 16px; padding-top: 6px; border-top: 1px solid #e5e7eb; font-size: 8.5px; color: #9ca3af; }
  @page { size: A4; margin: 18mm 14mm; }
  @media print {
    body { padding: 0; }
    section { page-break-inside: avoid; }
    table { page-break-inside: avoid; }
  }
</style></head><body>`);
  w.document.write(clone.innerHTML);
  w.document.write("</body></html>");
  w.document.close();
  setTimeout(() => w.print(), 700);
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
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const dDay = indices?.pandse?.d_day || "?";
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

  const sd = data.situation_diagnosis || {};
  const dl = data.decision_layer || {};
  const eg = sd.exposure_gap || {};
  const st = data.strategy || {};
  const strategies = data.strategies || [];
  const messages = data.messages || [];
  const execution = data.execution || [];
  const kpiMon = data.kpi_monitoring || [];
  const riskMgmt = data.risk_management || [];

  return (
    <div id="report-body" className="space-y-5 max-w-[820px] mx-auto">

      {/* ── 헤더 ── */}
      <div className="flex items-end justify-between border-b border-gray-700 pb-3">
        <div>
          <h1 className="text-lg font-black text-gray-100 tracking-tight">경남도지사 선거 전략대응 리포트</h1>
          <div className="text-xs text-gray-500 mt-0.5">{today} | 선거 D-{dDay}일 | 캠프 내부 한정</div>
        </div>
        <span className="text-[9px] text-gray-600">1일 1회 | Opus 4.6</span>
      </div>

      {/* ── 0. Executive Summary ── */}
      {data.executive_summary && (
        <div className="bg-blue-950/20 border-l-4 border-l-blue-500 rounded-r-lg px-4 py-3">
          <div className="text-[10px] text-blue-400 font-bold uppercase tracking-widest mb-1">종합 요약</div>
          <div className="text-[13px] text-gray-100 leading-[1.8] whitespace-pre-line">{data.executive_summary}</div>
        </div>
      )}

      {/* ══ 1. 상황 진단 ══ */}
      <section>
        <h2 className="text-[14px] font-black text-gray-100 border-b-2 border-gray-600 pb-1 mb-3">1. 상황 진단</h2>

        {/* 이슈 상태 */}
        {sd.issue_state?.length > 0 && (
          <div className="mb-4">
            <h3 className="text-xs text-gray-400 font-bold uppercase tracking-wider mb-2">이슈 상태 — 무엇이 확산되고 있는가</h3>
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
                {sd.issue_top5.map((iss: any) => (
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
              {sd.issue_top5.filter((iss: any) => iss.diagnosis).map((iss: any) => (
                <div key={`diag-${iss.rank}`} className="bg-gray-800/20 rounded-lg px-3 py-2 text-[11px] leading-relaxed">
                  <span className="text-gray-300 font-bold mr-1">{iss.rank}. {iss.name}</span>
                  <span className="text-gray-400">{iss.diagnosis}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 리액션 TOP5 */}
        {sd.reaction_top5?.length > 0 && (
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
                {sd.reaction_top5.map((r: any) => (
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
        {(sd.our_diagnosis || sd.opp_diagnosis) && (
          <div className="grid grid-cols-2 gap-3">
            {sd.our_diagnosis && (
              <div className="rounded-lg border border-blue-800/30 bg-blue-950/10 p-3">
                <div className="text-[10px] text-blue-400 font-bold uppercase tracking-wider mb-1.5">우리 후보 진단</div>
                <div className="text-[11px] text-gray-300 leading-[1.7]">{sd.our_diagnosis}</div>
              </div>
            )}
            {sd.opp_diagnosis && (
              <div className="rounded-lg border border-red-800/30 bg-red-950/10 p-3">
                <div className="text-[10px] text-red-400 font-bold uppercase tracking-wider mb-1.5">상대 후보 진단</div>
                <div className="text-[11px] text-gray-300 leading-[1.7]">{sd.opp_diagnosis}</div>
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
        <span className="text-[9px] text-gray-600">1주 1회 | Opus 4.6</span>
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
   학습데이터 뷰
═══════════════════════════════════════════ */
function TrainingDataView() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<any>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await getTrainingData();
      setData(d);
      if (d.days?.length > 0) setSelected(d.days[0]);
    } catch { }
    setLoading(false);
  }, []);

  if (!data && !loading) return (
    <button onClick={load} className="w-full py-4 text-center text-gray-400 hover:text-white border border-dashed border-gray-700 rounded-lg transition-colors">
      학습데이터 불러오기 ({loading ? "..." : "클릭"})
    </button>
  );
  if (loading) return <div className="text-center py-8 text-gray-500 animate-pulse">불러오는 중...</div>;
  if (!data?.days?.length) return <div className="text-center py-8 text-gray-500">저장된 학습데이터 없음</div>;

  const sideColor = (s: string) => s?.includes("우리") ? "text-blue-400" : s?.includes("상대") ? "text-red-400" : "text-gray-400";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs text-gray-400">총 {data.total}일 기록</div>
        <div className="flex gap-1 flex-wrap">
          {data.days.map((d: any) => (
            <button key={d.date} onClick={() => setSelected(d)}
              className={`text-[9px] px-2 py-1 rounded transition-all ${
                selected?.date === d.date ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40" : "text-gray-500 hover:text-gray-300 border border-gray-800"
              }`}>
              {d.date?.slice(5)}
            </button>
          ))}
        </div>
      </div>

      {selected && (
        <div className="space-y-3">
          <div className="text-sm font-bold text-gray-200">{selected.date} <span className="text-gray-500 font-normal text-xs">D-{selected.d_day}</span></div>

          {/* 3개 지수 */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "이슈지수", val: selected.indices?.issue_index, color: "text-emerald-400" },
              { label: "반응지수", val: selected.indices?.reaction_index, color: "text-amber-400" },
              { label: "판세지수", val: selected.indices?.pandse_index, color: "text-cyan-400" },
            ].map(({ label, val, color }) => (
              <div key={label} className="bg-gray-800/30 rounded-lg px-3 py-2 text-center">
                <div className="text-[9px] text-gray-500">{label}</div>
                <div className={`text-lg font-black ${color}`}>{val?.toFixed(1) || "—"}<span className="text-[8px] text-gray-600">pt</span></div>
              </div>
            ))}
          </div>

          {/* AI 해석 */}
          {selected.ai_summary?.issue && (
            <div className="bg-cyan-950/20 border border-cyan-900/30 rounded-lg px-3 py-2 space-y-1">
              <div className="text-[9px] text-cyan-400 font-bold">AI 해석</div>
              <div className="text-[10px] text-gray-300">이슈: {selected.ai_summary.issue}</div>
              <div className="text-[10px] text-gray-300">반응: {selected.ai_summary.reaction}</div>
            </div>
          )}

          {/* TOP 이슈 */}
          {selected.top_issues?.length > 0 && (
            <div>
              <div className="text-[10px] text-gray-400 font-bold mb-1">TOP 이슈</div>
              <div className="space-y-0.5">
                {selected.top_issues.map((iss: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-[9px] py-0.5 border-b border-gray-800/50 last:border-0">
                    <span className="text-gray-600 w-4">{i + 1}</span>
                    <span className="text-gray-200 flex-1">{iss.name}</span>
                    <span className={`${sideColor(iss.side)} w-14 text-right`}>{iss.side}</span>
                    <span className="text-gray-500 w-8 text-right">{iss.count}건</span>
                    <span className={`w-8 text-right ${iss.sentiment > 0 ? "text-emerald-400" : iss.sentiment < 0 ? "text-rose-400" : "text-gray-500"}`}>{iss.sentiment > 0 ? "+" : ""}{iss.sentiment}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 여론조사 */}
          {selected.poll?.president_approval > 0 && (
            <div className="bg-gray-800/30 rounded-lg px-3 py-2">
              <div className="text-[9px] text-gray-500 mb-1">여론조사</div>
              <div className="text-[10px] text-gray-300">
                대통령 {selected.poll.president_approval}% · 민주 {selected.poll.dem_support}% · 국힘 {selected.poll.ppp_support}%
              </div>
            </div>
          )}

          {/* 판세 팩터 */}
          {selected.pandse_factors?.length > 0 && (
            <div>
              <div className="text-[10px] text-gray-400 font-bold mb-1">판세 9 Factors</div>
              <div className="space-y-0.5">
                {selected.pandse_factors.map((f: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-[9px] py-0.5 border-b border-gray-800/50 last:border-0">
                    <span className="text-gray-300 flex-1">{f.name}</span>
                    <span className={`font-bold w-10 text-right ${f.value > 0 ? "text-blue-400" : f.value < 0 ? "text-red-400" : "text-gray-500"}`}>{f.value > 0 ? "+" : ""}{f.value}</span>
                    <span className="text-gray-600 text-[8px] truncate max-w-[200px]">{f.reason}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
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
          {tab === "학습데이터" && <TrainingDataView />}
          {tab === "리서치" && <ResearchPage />}
        </div>
      </div>
    </div>
  );
}
