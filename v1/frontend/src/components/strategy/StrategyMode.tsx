"use client";
import { useState, useEffect, useCallback } from "react";
import { getDailyBriefing, getWeeklyBriefing, getIndicesCurrent, getNewsClusters, getDailyReports, getTrainingData } from "@/lib/api";
import { ResearchPage } from "../ResearchTab";

type Page = "daily" | "weekly" | "archive" | "training" | "research";
type SubTab = "summary" | "issue" | "strategy" | "message";

export default function StrategyMode({ onExit }: { onExit: () => void }) {
  const [page, setPage] = useState<Page>("daily");
  const [subTab, setSubTab] = useState<SubTab>("summary");
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>({});

  const load = useCallback(async () => {
    setLoading(true);
    const [daily, weekly, indices, clusters, reports, training] = await Promise.all([
      getDailyBriefing().catch(() => null),
      getWeeklyBriefing().catch(() => null),
      getIndicesCurrent().catch(() => null),
      getNewsClusters().catch(() => null),
      getDailyReports().catch(() => null),
      getTrainingData().catch(() => null),
    ]);
    setData({ daily, weekly, indices, clusters, reports, training });
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const dDay = data.indices?.pandse?.d_day || "?";
  const daily = data.daily || {};
  const sd = daily.situation_diagnosis || {};
  const dl = daily.decision_layer || {};

  // Crisis detection
  const urgentItems = (daily.execution || []).filter((e: any) => e.when?.includes("즉시") || e.when?.includes("오늘"));
  const hasCrisis = urgentItems.length > 0;

  return (
    <div className="fixed inset-0 z-[60] flex" style={{ fontFamily: "'Noto Sans KR', sans-serif", background: "#F0F2F5", color: "#111827" }}>
      {/* Sidebar */}
      <aside className="w-[240px] shrink-0 flex flex-col h-screen overflow-y-auto" style={{ background: "#0D1B2A", color: "white" }}>
        <div className="px-5 py-4 border-b border-white/10">
          <div className="text-[9px] tracking-[2px] text-[#E8B84B] font-medium mb-1">GYEONGNAM GOVERNOR CAMPAIGN</div>
          <div className="text-sm font-bold leading-tight">김경수 캠프<br/>전략 리포트 시스템</div>
        </div>
        <div className="px-5 py-3 text-[10px] text-white/50 bg-white/5">
          선거일 D-<span className="text-[#E8B84B] font-bold">{dDay}</span>일 | 2026.06.03
        </div>
        <nav className="flex-1 py-4">
          <div className="px-5 py-1 text-[9px] tracking-[2px] text-white/30 font-medium">REPORT</div>
          <NavItem label="데일리 리포트" icon="📋" active={page === "daily"} badge="NEW" badgeColor="bg-[#1A7A4A]"
            onClick={() => { setPage("daily"); setSubTab("summary"); }} />
          <NavItem label="위클리 리포트" icon="📊" active={page === "weekly"} onClick={() => setPage("weekly")} />
          <NavItem label="리포트 아카이브" icon="🗂" active={page === "archive"} onClick={() => setPage("archive")} />

          <div className="px-5 py-1 mt-3 text-[9px] tracking-[2px] text-white/30 font-medium">ANALYSIS</div>
          <NavItem label="실시간 이슈" icon="📡" badge={String(data.clusters?.clusters?.length || 0)} onClick={() => { setPage("daily"); setSubTab("issue"); }} />
          <NavItem label="위기 알림" icon="⚠️" badge={hasCrisis ? String(urgentItems.length) : undefined} onClick={() => { setPage("daily"); setSubTab("summary"); }} />

          <div className="px-5 py-1 mt-3 text-[9px] tracking-[2px] text-white/30 font-medium">DATA</div>
          <NavItem label="학습데이터" icon="🧠" active={page === "training"} badge={String(data.training?.total || 0)} badgeColor="bg-[#2457A4]" onClick={() => setPage("training")} />
          <NavItem label="리서치" icon="🔍" active={page === "research"} onClick={() => setPage("research")} />
        </nav>
        <div className="px-5 py-4 border-t border-white/10">
          <button onClick={onExit} className="w-full text-left text-[11px] text-white/60 hover:text-white transition-colors">
            ← War Room 복귀
          </button>
        </div>
        <div className="px-5 py-3 text-[10px] text-white/30 leading-relaxed">
          캠프 전략총책임자 전용<br/>AI 분석 기반 · 참고용
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        {/* Crisis Banner */}
        {hasCrisis && (
          <div className="flex items-center gap-2 px-8 py-2 text-[12px] text-white font-medium" style={{ background: "#C0392B" }}>
            <span className="w-2 h-2 rounded-full bg-[#FFD700] animate-pulse" />
            <strong>긴급</strong>
            {urgentItems.slice(0, 2).map((u: any, i: number) => (
              <span key={i}>{i > 0 && " | "}{u.what}</span>
            ))}
          </div>
        )}

        {/* Topbar */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-8 h-14 bg-white border-b border-gray-300">
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold text-[#0D1B2A]">
              {{ daily: "데일리 전략 리포트", weekly: "위클리 전략 리포트", archive: "리포트 아카이브", training: "학습데이터", research: "리서치" }[page]}
            </span>
            <span className="text-[11px] text-gray-500">
              {daily.generated_at?.slice(0, 16)?.replace("T", " ")} | D-{dDay}일
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => window.print()} className="px-3 py-1.5 text-xs text-gray-700 border border-gray-300 rounded-md hover:bg-gray-100">
              🖨 PDF 출력
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-8 py-7">
          {loading ? (
            <div className="text-center py-20 text-gray-500 animate-pulse">데이터 로딩 중...</div>
          ) : page === "daily" ? (
            <>
              {/* Tab Bar */}
              <div className="flex gap-0.5 p-1 mb-6 rounded-lg" style={{ background: "#F3F4F6" }}>
                {(["summary", "issue", "strategy", "message"] as SubTab[]).map((t) => (
                  <button key={t} onClick={() => setSubTab(t)}
                    className={`flex-1 py-2 text-xs font-medium rounded-md transition-all ${subTab === t ? "bg-white text-[#0D1B2A] shadow-sm" : "text-gray-500 hover:text-gray-700"}`}>
                    {{ summary: "종합 브리핑", issue: "이슈 분석", strategy: "대응 전략", message: "메시지 & 일정" }[t]}
                  </button>
                ))}
              </div>

              {subTab === "summary" && <SummaryTab daily={daily} indices={data.indices} />}
              {subTab === "issue" && <IssueTab daily={daily} clusters={data.clusters} />}
              {subTab === "strategy" && <StrategyTab daily={daily} />}
              {subTab === "message" && <MessageTab daily={daily} />}
            </>
          ) : page === "weekly" ? (
            <WeeklyPage weekly={data.weekly} />
          ) : page === "training" ? (
            <TrainingPage training={data.training} />
          ) : page === "research" ? (
            <div className="bg-[#0a0f1a] rounded-xl p-4 -mx-2"><ResearchPage /></div>
          ) : (
            <ArchivePage reports={data.reports} />
          )}
        </div>
      </main>
    </div>
  );
}

/* ── Nav Item ── */
function NavItem({ label, icon, active, badge, badgeColor, onClick }: {
  label: string; icon: string; active?: boolean; badge?: string; badgeColor?: string; onClick?: () => void;
}) {
  return (
    <div onClick={onClick}
      className={`flex items-center gap-2.5 px-5 py-2.5 text-xs cursor-pointer transition-all border-l-[3px] ${
        active ? "bg-[rgba(36,87,164,0.4)] text-white border-[#C8922A]" : "text-white/65 border-transparent hover:bg-white/5 hover:text-white"
      }`}>
      <span className="w-4 text-center text-sm">{icon}</span>
      <span>{label}</span>
      {badge && (
        <span className={`ml-auto text-[9px] font-bold px-1.5 py-0.5 rounded-full text-white ${badgeColor || "bg-[#C0392B]"}`}>{badge}</span>
      )}
    </div>
  );
}

/* ── Summary Tab ── */
function SummaryTab({ daily, indices }: { daily: any; indices: any }) {
  const issue = indices?.issue || {};
  const reaction = indices?.reaction || {};
  const pandse = indices?.pandse || {};

  return (
    <div className="space-y-5">
      {/* Executive Summary Box */}
      <div className="rounded-xl p-5" style={{ background: "linear-gradient(135deg, #0D1B2A 0%, #1B3A6B 100%)", color: "white" }}>
        <div className="text-[10px] tracking-[1px] text-[#E8B84B] font-medium mb-2">DAILY BRIEF · {daily.date || new Date().toISOString().slice(0, 10)}</div>
        <div className="text-[15px] font-bold leading-relaxed mb-3" style={{ fontFamily: "'Noto Serif KR', serif" }}>
          {daily.executive_summary?.split(".")?.[0] || "리포트 생성 대기 중"}
        </div>
        <div className="text-[12px] leading-[1.8] text-white/85">
          {daily.executive_summary || "데일리 리포트를 먼저 생성하세요."}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-3">
        <KpiCard label="이슈지수" value={`${issue.index?.toFixed(1) || "—"}pt`} change={issue.grade} up={issue.index > 55} />
        <KpiCard label="반응지수" value={`${reaction.index?.toFixed(1) || "—"}pt`} change={reaction.grade} up={reaction.index > 55} />
        <KpiCard label="판세지수" value={`${pandse.index?.toFixed(1) || "—"}pt`} change={pandse.grade} up={pandse.index > 55} />
        <KpiCard label="D-Day" value={`D-${pandse.d_day || "?"}`} change="선거일 2026.06.03" />
      </div>

      {/* Candidate Diagnosis */}
      {(daily.situation_diagnosis?.our_candidate || daily.situation_diagnosis?.opp_candidate) && (
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-xl border border-gray-300 overflow-hidden">
            <div className="px-5 py-3 border-b" style={{ background: "#EFF6FF" }}>
              <div className="text-[13px] font-bold text-[#2457A4]">🔵 우리 후보 AI 진단</div>
            </div>
            <div className="px-5 py-4 text-[11px] text-gray-700 leading-[1.9]">
              {daily.situation_diagnosis?.our_candidate || "—"}
            </div>
          </div>
          <div className="rounded-xl border border-gray-300 overflow-hidden">
            <div className="px-5 py-3 border-b" style={{ background: "#FEF2F2" }}>
              <div className="text-[13px] font-bold text-[#C0392B]">🔴 상대 후보 AI 진단</div>
            </div>
            <div className="px-5 py-4 text-[11px] text-gray-700 leading-[1.9]">
              {daily.situation_diagnosis?.opp_candidate || "—"}
            </div>
          </div>
        </div>
      )}

      {/* Urgent Actions */}
      {daily.execution?.length > 0 && (
        <Card title="⚡ 오늘 반드시 해야 할 것" badge={`D-${pandse.d_day || "?"} 긴급`} badgeColor="b-red">
          {daily.execution.filter((e: any) => e.when?.includes("즉시") || e.when?.includes("오늘")).map((e: any, i: number) => (
            <TaskRow key={i} when={e.when} what={e.what} who={e.who} kpi={e.kpi} />
          ))}
        </Card>
      )}
    </div>
  );
}

/* ── Issue Tab ── */
function IssueTab({ daily, clusters }: { daily: any; clusters: any }) {
  const sd = daily.situation_diagnosis || {};
  const issues = sd.issue_state || sd.issue_top5 || [];
  const reactions = sd.reaction_state || sd.reaction_top5 || [];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        {/* Issue TOP */}
        <Card title="이슈 TOP" sub="지난 24시간 · 이슈 영향도 순">
          {issues.map((iss: any, i: number) => (
            <IssueRow key={i} rank={iss.rank || i + 1} name={iss.name} count={iss.count}
              side={iss.side} body={iss.diagnosis || iss.spreading || ""} />
          ))}
          {issues.length === 0 && <div className="text-xs text-gray-400 py-4 text-center">데일리 리포트를 먼저 생성하세요</div>}
        </Card>

        {/* Reaction TOP */}
        <Card title="시민 리액션 TOP" sub="감성 분석 기반">
          {reactions.map((r: any, i: number) => (
            <div key={i} className="flex items-start gap-3 py-3 border-b border-gray-100 last:border-0">
              <div className="shrink-0 w-6 h-6 rounded-md flex items-center justify-center text-white text-[9px] font-bold"
                style={{ background: r.sentiment?.includes("부정") ? "#C0392B" : r.sentiment?.includes("긍정") ? "#1A7A4A" : "#6B7280" }}>
                {r.rank || i + 1}
              </div>
              <div className="flex-1">
                <div className="text-[12px] font-bold text-gray-900">{r.keyword || r.name}</div>
                <div className="text-[11px] text-gray-600 mt-0.5">{r.strategic_meaning} · {r.reacting_segment} · {r.reacting_region}</div>
                <div className="flex items-center gap-2 mt-2">
                  <Badge type={r.sentiment?.includes("부정") ? "red" : r.sentiment?.includes("긍정") ? "green" : "gray"}>
                    {r.sentiment}
                  </Badge>
                  <Badge type={r.volume === "높음" ? "red" : r.volume === "보통" ? "orange" : "gray"}>
                    {r.volume}
                  </Badge>
                  <Badge type={r.stability === "불안정" ? "red" : r.stability === "안정" ? "green" : "orange"}>
                    {r.stability}
                  </Badge>
                </div>
              </div>
            </div>
          ))}
          {reactions.length === 0 && <div className="text-xs text-gray-400 py-4 text-center">데일리 리포트를 먼저 생성하세요</div>}
        </Card>
      </div>

      {/* News Clusters from real-time data */}
      {clusters?.clusters?.length > 0 && (
        <Card title="실시간 뉴스 클러스터" sub="AI 분류 TOP 10">
          <div className="grid grid-cols-2 gap-x-4">
            {clusters.clusters.slice(0, 10).map((c: any, i: number) => (
              <IssueRow key={i} rank={i + 1} name={c.name} count={c.count}
                side={c.side} body={c.tip || ""} sentiment={c.sentiment} />
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

/* ── Strategy Tab ── */
function StrategyTab({ daily }: { daily: any }) {
  const strategies = daily.strategies || [];
  const dl = daily.decision_layer || {};

  return (
    <div className="space-y-5">
      {/* Decision Layer */}
      {dl.moment_type && (
        <div className="rounded-xl p-5 border-2" style={{
          borderColor: dl.moment_type?.includes("공격") ? "#1A7A4A" : dl.moment_type?.includes("방어") ? "#C0392B" : "#C8922A",
          background: dl.moment_type?.includes("공격") ? "#F0FDF4" : dl.moment_type?.includes("방어") ? "#FEF2F2" : "#FFFBEB"
        }}>
          <div className="text-[13px] font-bold mb-2" style={{ color: "#0D1B2A" }}>현재 국면: {dl.moment_type}</div>
          <div className="grid grid-cols-2 gap-4 text-[11px] text-gray-700 leading-relaxed">
            <div><strong className="text-[#C0392B]">반드시 지켜야 할 것:</strong><br/>{dl.must_protect}</div>
            <div><strong className="text-[#1A7A4A]">밀어볼 수 있는 것:</strong><br/>{dl.can_push}</div>
          </div>
        </div>
      )}

      {/* Strategy Cards */}
      {strategies.map((s: any, i: number) => {
        const isUrgent = s.timeline?.includes("즉시") || s.timeline?.includes("오늘");
        const borderColor = isUrgent ? "#C0392B" : s.timeline?.includes("이번 주") ? "#2457A4" : "#C8922A";
        return (
          <div key={i} className="rounded-xl border border-gray-200 bg-white overflow-hidden" style={{ borderLeft: `4px solid ${borderColor}` }}>
            <div className="px-5 py-3 flex items-center gap-2">
              <Badge type={isUrgent ? "red" : s.timeline?.includes("이번 주") ? "blue" : "gold"}>
                {isUrgent ? "긴급" : s.timeline?.includes("이번 주") ? "단기" : "중장기"} · {s.timeline}
              </Badge>
              <span className="text-[13px] font-bold text-[#0D1B2A]">{s.title}</span>
            </div>
            <div className="px-5 pb-4 text-[11px] text-gray-700 leading-[1.9]">
              {s.condition && <div className="mb-2 text-[10px] text-gray-500">조건: {s.condition}</div>}
              <div>{s.action}</div>
              {s.target && <div className="mt-2 text-[10px]">🎯 타겟: {s.target}</div>}
              {s.intended_effect && <div className="text-[10px]">📈 기대: {s.intended_effect}</div>}
              {s.risk && (
                <div className="mt-2 px-3 py-2 rounded-md text-[10px]" style={{ background: "#FEF2F2", color: "#991B1B" }}>
                  ⚠ {s.risk}
                </div>
              )}
            </div>
          </div>
        );
      })}
      {strategies.length === 0 && <div className="text-center py-10 text-gray-400 text-sm">데일리 리포트를 먼저 생성하세요</div>}
    </div>
  );
}

/* ── Message Tab ── */
function MessageTab({ daily }: { daily: any }) {
  const messages = daily.messages || [];
  const execution = daily.execution || [];
  const risks = daily.risk_management || [];

  return (
    <div className="grid grid-cols-2 gap-5">
      {/* Left: Messages */}
      <div className="space-y-3">
        <div className="text-xs font-bold text-[#0D1B2A] mb-2">메시지 우선순위</div>
        {messages.map((m: any, i: number) => (
          <div key={i} className="rounded-xl border border-gray-200 bg-white p-4">
            <div className="text-[10px] font-bold text-[#2457A4] mb-1">PRIORITY {m.priority} · {m.target}</div>
            <div className="text-[14px] font-bold text-[#0D1B2A] mb-2" style={{ fontFamily: "'Noto Serif KR', serif" }}>
              &ldquo;{m.message}&rdquo;
            </div>
            <div className="text-[11px] text-gray-600 leading-relaxed mb-2">{m.sub_message}</div>
            <div className="text-[10px] text-gray-500">채널: {m.channel}</div>
            {m.caution && (
              <div className="mt-2 text-[10px] px-3 py-1.5 rounded-md" style={{ background: "#FFFBEB", color: "#92400E" }}>
                ⚠ {m.caution}
              </div>
            )}
          </div>
        ))}
        {messages.length === 0 && <div className="text-xs text-gray-400 text-center py-4">메시지 데이터 없음</div>}
      </div>

      {/* Right: Execution + Risks */}
      <div className="space-y-4">
        <div className="text-xs font-bold text-[#0D1B2A] mb-2">실행 일정 & KPI</div>
        <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
          <div className="divide-y divide-gray-100">
            {execution.map((e: any, i: number) => (
              <TaskRow key={i} when={e.when} what={e.what} who={e.who} kpi={e.kpi}
                urgent={e.when?.includes("즉시") || e.when?.includes("오늘")} />
            ))}
          </div>
        </div>

        {/* Risk Management */}
        {risks.length > 0 && (
          <div className="rounded-xl border border-red-200 overflow-hidden">
            <div className="px-4 py-3 text-[12px] font-bold text-[#C0392B]" style={{ background: "#FEF2F2" }}>
              ⛔ 위기 관리
            </div>
            <div className="divide-y divide-gray-100">
              {risks.map((r: any, i: number) => (
                <div key={i} className="px-4 py-3 text-[11px] text-gray-700 leading-relaxed">
                  <strong>{r.risk}</strong>
                  {r.trigger && <span className="text-gray-500"> → {r.trigger}</span>}
                  {r.response && <div className="mt-1 text-[#1A7A4A]">대응: {r.response}</div>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* KPI Monitoring */}
        {daily.kpi_monitoring?.length > 0 && (
          <div className="rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 text-[12px] font-bold text-[#0D1B2A]" style={{ background: "#F3F4F6" }}>
              📊 모니터링 지표
            </div>
            <div className="divide-y divide-gray-100">
              {daily.kpi_monitoring.map((k: any, i: number) => (
                <div key={i} className="flex items-center justify-between px-4 py-2.5 text-[11px]">
                  <span className="text-gray-700 font-medium">{k.metric}</span>
                  <span className="text-gray-500">{k.current} → <span className="font-bold text-[#2457A4]">{k.target}</span></span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Weekly Page ── */
function WeeklyPage({ weekly }: { weekly: any }) {
  if (!weekly || weekly.error) return (
    <div className="text-center py-20 text-gray-400">위클리 리포트를 먼저 생성하세요</div>
  );
  const ks = weekly.kpi_review || [];
  const segments = weekly.segment_analysis || [];
  const nw = weekly.next_week || {};

  return (
    <div className="space-y-5">
      <div className="rounded-xl p-5" style={{ background: "linear-gradient(135deg, #0D1B2A 0%, #1B3A6B 100%)", color: "white" }}>
        <div className="text-[10px] tracking-[1px] text-[#E8B84B] font-medium mb-2">WEEKLY REPORT · {weekly.week}</div>
        <div className="text-[12px] leading-[1.8] text-white/85">{weekly.executive_summary}</div>
      </div>

      {/* KPI Review */}
      {ks.length > 0 && (
        <Card title="주간 KPI 달성률" sub="지난 리포트 대비 실적">
          <div className="grid grid-cols-3 gap-3">
            {ks.map((k: any, i: number) => (
              <div key={i} className="rounded-lg border border-gray-200 p-3">
                <div className="text-[10px] text-gray-500 mb-1">{k.metric || k.strategy}</div>
                <div className="text-[11px] font-bold">{k.result || k.executed}</div>
                {k.lesson && <div className="text-[10px] text-gray-500 mt-1">{k.lesson}</div>}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Segments */}
      {segments.length > 0 && (
        <Card title="세그먼트 분석">
          {segments.map((s: any, i: number) => (
            <div key={i} className="flex items-start gap-3 py-3 border-b border-gray-100 last:border-0 text-[11px]">
              <Badge type="blue">{s.segment}</Badge>
              <div className="flex-1">
                <div className="text-gray-700">{s.trend}</div>
                {s.action_needed && <div className="text-[#2457A4] mt-1">→ {s.action_needed}</div>}
              </div>
            </div>
          ))}
        </Card>
      )}

      {/* Next Week */}
      {nw.priority_1 && (
        <Card title="다음 주 핵심 과제">
          <div className="space-y-2 text-[11px] text-gray-700 leading-relaxed">
            <div className="p-3 rounded-lg" style={{ background: "#FEF2F2", borderLeft: "3px solid #C0392B" }}>
              <strong>최우선:</strong> {nw.priority_1}
            </div>
            {nw.priority_2 && <div className="p-3 rounded-lg" style={{ background: "#EFF6FF", borderLeft: "3px solid #2457A4" }}>
              <strong>차우선:</strong> {nw.priority_2}
            </div>}
            {nw.priority_3 && <div className="p-3 rounded-lg" style={{ background: "#FFFBEB", borderLeft: "3px solid #C8922A" }}>
              <strong>보조:</strong> {nw.priority_3}
            </div>}
            {nw.risk_watch && <div className="p-3 rounded-lg" style={{ background: "#F3F4F6" }}>
              <strong>주의 감시:</strong> {nw.risk_watch}
            </div>}
          </div>
        </Card>
      )}
    </div>
  );
}

/* ── Training Page ── */
function TrainingPage({ training }: { training: any }) {
  const [selected, setSelected] = useState<any>(null);
  const days = training?.days || [];

  useEffect(() => { if (days.length > 0 && !selected) setSelected(days[0]); }, [days, selected]);

  const sideColor = (s: string) => s?.includes("우리") ? "green" : s?.includes("상대") ? "red" : "gray";

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-bold text-[#0D1B2A]">학습데이터</div>
          <div className="text-xs text-gray-500">일별 지수 + 이슈 + 여론조사 · 총 {training?.total || 0}일 기록</div>
        </div>
        <div className="flex gap-1 flex-wrap max-w-[500px]">
          {days.map((d: any) => (
            <button key={d.date} onClick={() => setSelected(d)}
              className={`text-[9px] px-2 py-1 rounded transition-all border ${
                selected?.date === d.date ? "bg-[#2457A4] text-white border-[#2457A4]" : "text-gray-500 hover:text-gray-700 border-gray-300"
              }`}>
              {d.date?.slice(5)}
            </button>
          ))}
        </div>
      </div>

      {selected && (
        <div className="space-y-4">
          <div className="text-sm font-bold text-[#0D1B2A]">{selected.date} <span className="text-gray-500 font-normal text-xs">D-{selected.d_day}</span></div>

          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "이슈지수", val: selected.indices?.issue_index, color: "#1A7A4A" },
              { label: "반응지수", val: selected.indices?.reaction_index, color: "#C8922A" },
              { label: "판세지수", val: selected.indices?.pandse_index, color: "#2457A4" },
            ].map(({ label, val, color }) => (
              <div key={label} className="rounded-xl border border-gray-200 bg-white p-4 text-center">
                <div className="text-[10px] text-gray-500">{label}</div>
                <div className="text-xl font-bold" style={{ color }}>{val?.toFixed(1) || "—"}<span className="text-xs text-gray-400">pt</span></div>
              </div>
            ))}
          </div>

          {selected.ai_summary?.issue && (
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="text-[11px] font-bold text-[#2457A4] mb-2">AI 해석</div>
              <div className="text-[11px] text-gray-700 leading-relaxed">이슈: {selected.ai_summary.issue}</div>
              <div className="text-[11px] text-gray-700 leading-relaxed mt-1">반응: {selected.ai_summary.reaction}</div>
            </div>
          )}

          {selected.top_issues?.length > 0 && (
            <Card title="TOP 이슈" sub={selected.date}>
              {selected.top_issues.map((iss: any, i: number) => (
                <IssueRow key={i} rank={i + 1} name={iss.name} count={iss.count} side={iss.side} sentiment={iss.sentiment} />
              ))}
            </Card>
          )}

          {selected.pandse_factors?.length > 0 && (
            <Card title="판세 9 Factors">
              {selected.pandse_factors.map((f: any, i: number) => (
                <div key={i} className="flex items-center gap-3 py-2 border-b border-gray-100 last:border-0 text-[11px]">
                  <span className="text-gray-700 flex-1">{f.name}</span>
                  <span className={`font-bold w-10 text-right ${f.value > 0 ? "text-[#2457A4]" : f.value < 0 ? "text-[#C0392B]" : "text-gray-400"}`}>
                    {f.value > 0 ? "+" : ""}{f.value}
                  </span>
                  <span className="text-gray-500 text-[10px] truncate max-w-[250px]">{f.reason}</span>
                </div>
              ))}
            </Card>
          )}

          {selected.poll?.president_approval > 0 && (
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="text-[11px] font-bold text-[#0D1B2A] mb-1">여론조사</div>
              <div className="text-[11px] text-gray-700">
                대통령 {selected.poll.president_approval}% · 민주 {selected.poll.dem_support}% · 국힘 {selected.poll.ppp_support}%
              </div>
            </div>
          )}
        </div>
      )}
      {days.length === 0 && <div className="text-center py-20 text-gray-400">저장된 학습데이터 없음</div>}
    </div>
  );
}

/* ── Archive Page ── */
function ArchivePage({ reports }: { reports: any }) {
  const list = reports?.reports || [];
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-lg font-bold text-[#0D1B2A]">리포트 아카이브</div>
          <div className="text-xs text-gray-500">저장된 전략 리포트 · 총 {reports?.total || 0}건</div>
        </div>
      </div>
      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden divide-y divide-gray-100">
        {list.map((r: any, i: number) => (
          <div key={i} className="flex items-center gap-3 px-5 py-3.5 hover:bg-gray-50 cursor-pointer transition-colors">
            <span className="text-lg">📄</span>
            <div className="flex-1">
              <div className="text-[12px] font-bold text-[#0D1B2A]">전략대응 데일리 리포트 {i === 0 && <Badge type="red">NEW</Badge>}</div>
              <div className="text-[10px] text-gray-500">{r.date} · D-{r.d_day}</div>
            </div>
            <div className="text-[10px] text-gray-400 max-w-[300px] truncate">{r.summary}</div>
          </div>
        ))}
        {list.length === 0 && <div className="text-center py-8 text-gray-400 text-xs">저장된 리포트 없음</div>}
      </div>
    </div>
  );
}

/* ── Shared Components ── */
function KpiCard({ label, value, change, up }: { label: string; value: string; change?: string; up?: boolean }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="text-[10px] text-gray-500 font-medium tracking-wider mb-1.5">{label}</div>
      <div className="text-[22px] font-bold text-[#0D1B2A] leading-none mb-1">{value}</div>
      {change && <div className={`text-[11px] font-medium ${up ? "text-[#1A7A4A]" : "text-gray-500"}`}>{change}</div>}
    </div>
  );
}

function Card({ title, sub, badge, badgeColor, children }: { title: string; sub?: string; badge?: string; badgeColor?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
        <div>
          <div className="text-[13px] font-bold text-[#0D1B2A]">{title}</div>
          {sub && <div className="text-[11px] text-gray-500 mt-0.5">{sub}</div>}
        </div>
        {badge && <Badge type={badgeColor === "b-red" ? "red" : "gray"}>{badge}</Badge>}
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  );
}

function IssueRow({ rank, name, count, side, body, sentiment }: {
  rank: number; name: string; count?: number; side?: string; body?: string; sentiment?: number;
}) {
  const sideColor = side?.includes("우리") ? "green" : side?.includes("상대") ? "red" : "gray";
  return (
    <div className="flex items-start gap-3 py-3 border-b border-gray-100 last:border-0">
      <div className={`shrink-0 w-6 h-6 rounded-md flex items-center justify-center text-white text-[10px] font-bold ${rank <= 2 ? "bg-[#C0392B]" : "bg-gray-400"}`}>
        {rank}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[12px] font-bold text-gray-900">{name}</div>
        {body && <div className="text-[11px] text-gray-600 mt-0.5 leading-relaxed">{body}</div>}
        <div className="flex items-center gap-1.5 mt-1.5">
          <Badge type={sideColor}>{side}</Badge>
          {count != null && <span className="text-[10px] text-gray-500">{count}건</span>}
          {sentiment != null && sentiment !== 0 && (
            <span className={`text-[10px] font-bold ${sentiment > 0 ? "text-[#1A7A4A]" : "text-[#C0392B]"}`}>
              {sentiment > 0 ? "+" : ""}{sentiment}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function TaskRow({ when, what, who, kpi, urgent }: { when: string; what: string; who?: string; kpi?: string; urgent?: boolean }) {
  return (
    <div className={`flex items-start gap-3 px-4 py-3 ${urgent ? "bg-red-50" : ""}`}>
      <div className={`shrink-0 text-[10px] font-bold w-20 pt-0.5 ${urgent ? "text-[#C0392B]" : "text-gray-500"}`}>{when}</div>
      <div className="flex-1">
        <div className="text-[12px] font-bold text-gray-900">{what}</div>
        {kpi && <div className="text-[10px] text-gray-500 mt-0.5">KPI: {kpi}</div>}
      </div>
      {who && <div className="shrink-0 text-[10px] text-[#2457A4] font-medium">{who}</div>}
    </div>
  );
}

function Badge({ type, children }: { type: string; children: React.ReactNode }) {
  const colors: Record<string, string> = {
    red: "bg-red-100 text-red-800",
    orange: "bg-amber-100 text-amber-800",
    green: "bg-emerald-100 text-emerald-800",
    blue: "bg-blue-100 text-blue-800",
    gold: "bg-amber-100 text-amber-800",
    gray: "bg-gray-100 text-gray-700",
  };
  return (
    <span className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded-full ${colors[type] || colors.gray}`}>
      {children}
    </span>
  );
}
