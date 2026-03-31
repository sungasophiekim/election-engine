"use client";
import { useState, useEffect, useCallback } from "react";
import { getDailyBriefing, generateDailyBriefing, getWeeklyBriefing, getIndicesCurrent, getIndicesHistory, getNewsClusters, getDailyReports, getTrainingData } from "@/lib/api";
import { ResearchPage } from "../ResearchTab";

type Page = "daily" | "weekly" | "archive" | "training" | "research";

function exportPDF(data: any) {
  const daily = data.daily || {};
  const sd = daily.situation_diagnosis || {};
  const dl = daily.decision_layer || {};
  const indices = data.indices || {};
  const issue = indices.issue || {};
  const reaction = indices.reaction || {};
  const pandse = indices.pandse || {};
  const issues = sd.issue_state || sd.issue_top5 || [];
  const reactions = sd.reaction_state || sd.reaction_top5 || [];
  const strategies = daily.strategies || [];
  const fieldSchedule = daily.field_schedule || daily.messages || [];
  const execution = daily.execution || [];
  const risks = daily.risk_management || [];
  const kpis = daily.kpi_monitoring || [];
  const dDay = pandse.d_day || "?";
  const today = daily.date || new Date().toISOString().slice(0, 10);

  const sideBadge = (s: string) => {
    const base = "font-size:9px;font-weight:600;padding:1px 8px;border-radius:10px;white-space:nowrap;display:inline-block";
    if (s?.includes("우리")) return `<span style="background:#D1FAE5;color:#065F46;${base}">우리유리</span>`;
    if (s?.includes("상대")) return `<span style="background:#FEE2E2;color:#991B1B;${base}">상대유리</span>`;
    return `<span style="background:#F3F4F6;color:#374151;${base}">중립</span>`;
  };
  const gradeBadge = (g: string) => {
    if (g === "우세") return '<span style="background:#D1FAE5;color:#065F46;font-size:9px;font-weight:600;padding:1px 8px;border-radius:10px">우세</span>';
    if (g === "열세") return '<span style="background:#FEE2E2;color:#991B1B;font-size:9px;font-weight:600;padding:1px 8px;border-radius:10px">열세</span>';
    return '<span style="background:#F3F4F6;color:#374151;font-size:9px;font-weight:600;padding:1px 8px;border-radius:10px">접전</span>';
  };

  // 문장 분리 헬퍼
  const splitSentences = (t: string) => t.split(/(?<=다\.|음\.|중\.|요\.|임\.|됨\.|함\.|성\.|니다\.|세요\.|있다\.|없다\.|하다\.|된다\.|이다\.)\s*/g).filter(Boolean);

  // 후보 진단 분리 — 강점/약점/기회/위협 키워드 기반
  const splitDiagnosis = (t: string) => {
    if (!t) return "";
    // "강점:" "약점:" 등 키워드 앞에서 분리
    const parts = t.split(/(?=강점\s*[:：]|약점\s*[:：]|기회\s*[:：]|위협\s*[:：]|공략[^\s]*\s*[:：]|주의\s*[:：])/g).filter(Boolean);
    if (parts.length <= 1) {
      // 키워드 없으면 문장 분리 폴백
      return splitSentences(t).map((s: string) => `<p style="margin-bottom:6px">${s.trim()}</p>`).join("");
    }
    return parts.map((p: string) => {
      const trimmed = p.trim();
      // 라벨 추출
      const labelMatch = trimmed.match(/^(강점|약점|기회|위협|공략[^\s:：]*|주의)\s*[:：]\s*/);
      if (labelMatch) {
        const label = labelMatch[1];
        const content = trimmed.slice(labelMatch[0].length);
        const colors: Record<string,string> = { "강점": "#065F46", "약점": "#991B1B", "기회": "#1E40AF", "위협": "#92400E" };
        const bgs: Record<string,string> = { "강점": "#D1FAE5", "약점": "#FEE2E2", "기회": "#DBEAFE", "위협": "#FEF3C7" };
        const labelColor = colors[label] || "#374151";
        const labelBg = bgs[label] || "#F3F4F6";
        // 내용도 문장 분리
        const sentences = splitSentences(content);
        return `<div style="margin-bottom:8px">
          <span style="display:inline-block;font-size:9px;font-weight:700;padding:1px 7px;border-radius:10px;background:${labelBg};color:${labelColor};margin-bottom:3px">${label}</span>
          ${sentences.map((s: string) => `<div style="font-size:10px;line-height:1.8;color:#374151;padding-left:2px">${s.trim()}</div>`).join("")}
        </div>`;
      }
      return `<p style="margin-bottom:6px">${trimmed}</p>`;
    }).join("");
  };

  const html = `<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<title>전략대응 데일리 리포트 ${today}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Noto Sans KR', sans-serif; color: #111827; background: white; padding: 32px 40px; font-size: 10.5px; line-height: 1.7; }
@media print { body { padding: 0; } @page { size: A4; margin: 14mm 14mm; } }

/* 타이틀 */
.doc-header { margin-bottom: 28px; padding-bottom: 14px; border-bottom: 2px solid #0D1B2A; }
.doc-title { font-size: 16px; font-weight: 900; color: #0D1B2A; letter-spacing: -0.3px; }
.doc-sub { font-size: 10px; color: #6B7280; margin-top: 4px; }

/* 섹션 */
.section { margin-bottom: 20px; }
.s-title { font-size: 12px; font-weight: 700; color: #0D1B2A; margin-bottom: 10px; padding-left: 10px; border-left: 3px solid #C8922A; }

/* 핵심 명제 박스 */
.thesis { background: #F8FAFC; border-left: 3px solid #C8922A; padding: 10px 14px; margin-bottom: 10px; font-size: 10.5px; line-height: 1.8; }
.thesis p { margin-bottom: 5px; }
.thesis p:last-child { margin-bottom: 0; }
.thesis strong { color: #0D1B2A; }

/* 테이블 */
table { width: 100%; border-collapse: collapse; margin-bottom: 12px; font-size: 10px; }
thead th { text-align: left; padding: 6px 8px; background: #F9FAFB; border-bottom: 1.5px solid #D1D5DB; font-size: 9px; color: #6B7280; font-weight: 600; letter-spacing: 0.3px; }
tbody td { padding: 7px 8px; border-bottom: 1px solid #F3F4F6; vertical-align: top; line-height: 1.7; }
tbody tr:last-child td { border-bottom: none; }

/* KPI 행 */
.kpi-strip { display: flex; gap: 8px; margin-bottom: 10px; }
.kpi-item { flex: 1; border: 1px solid #E5E7EB; border-radius: 6px; padding: 6px 10px; }
.kpi-item .label { font-size: 8px; color: #6B7280; letter-spacing: 0.5px; font-weight: 500; }
.kpi-item .val { font-size: 16px; font-weight: 900; margin: 1px 0; }

/* 후보 진단 */
.diag-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px; }
.diag-card { border: 1px solid #E5E7EB; border-radius: 6px; overflow: hidden; font-size: 10px; }
.diag-card .head { padding: 5px 12px; font-size: 11px; font-weight: 700; }
.diag-card .body { padding: 8px 12px; line-height: 1.7; }

/* 전략 행 */
.strat-row { border: 1px solid #E5E7EB; border-radius: 6px; padding: 8px 12px; margin-bottom: 6px; }
.strat-row.urgent { border-left: 3px solid #C0392B; }
.strat-row.short { border-left: 3px solid #2457A4; }
.strat-row.mid { border-left: 3px solid #C8922A; }
.strat-name { font-size: 11px; font-weight: 700; color: #0D1B2A; margin-bottom: 3px; }
.strat-detail { font-size: 10px; line-height: 1.8; color: #374151; }
.strat-risk { background: #FEF2F2; border-radius: 4px; padding: 4px 8px; margin-top: 5px; font-size: 9.5px; color: #991B1B; }

/* 메시지 */
.msg-item { border: 1px solid #E5E7EB; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; }
.msg-label { font-size: 9px; font-weight: 700; color: #2457A4; }
.msg-quote { font-size: 12px; font-weight: 700; color: #0D1B2A; margin: 3px 0; }
.msg-desc { font-size: 10px; color: #374151; line-height: 1.7; }
.msg-warn { background: #FFFBEB; border-radius: 4px; padding: 3px 8px; margin-top: 4px; font-size: 9px; color: #92400E; }

/* 배지 */
.badge { font-size: 8.5px; font-weight: 600; padding: 1px 7px; border-radius: 10px; display: inline-block; vertical-align: middle; }

/* 푸터 */
.doc-footer { margin-top: 32px; padding-top: 10px; border-top: 1px solid #D1D5DB; font-size: 8.5px; color: #9CA3AF; text-align: center; letter-spacing: 0.3px; }
</style></head><body>

<div class="doc-header" style="margin-bottom:14px">
  <div class="doc-title">경남도지사 선거 전략대응 ${today.replace(/-/g, "/")} 리포트</div>
  <div class="doc-sub">D-${dDay}일 · 대외비</div>
</div>
<!-- 1. 핵심 진단 -->
<div class="section">
  <div class="s-title">1. 핵심 진단 — 종합 브리핑</div>
  <div class="thesis">
    ${splitSentences(daily.executive_summary || "리포트 데이터 없음").map((s: string) => `<p>${s.trim()}</p>`).join("")}
  </div>

  <div class="kpi-strip">
    <div class="kpi-item"><div class="label">이슈지수</div><div class="val" style="color:#1A7A4A">${issue.index?.toFixed(1) || "—"}<span style="font-size:10px;color:#9CA3AF">pt</span></div>${gradeBadge(issue.grade)}</div>
    <div class="kpi-item"><div class="label">반응지수</div><div class="val" style="color:#C8922A">${reaction.index?.toFixed(1) || "—"}<span style="font-size:10px;color:#9CA3AF">pt</span></div>${gradeBadge(reaction.grade)}</div>
    <div class="kpi-item"><div class="label">판세지수</div><div class="val" style="color:#2457A4">${pandse.index?.toFixed(1) || "—"}<span style="font-size:10px;color:#9CA3AF">pt</span></div>${gradeBadge(pandse.grade)}</div>
    <div class="kpi-item"><div class="label">D-DAY</div><div class="val" style="color:#0D1B2A">D-${dDay}</div><span class="badge" style="background:#F3F4F6;color:#374151">2026.06.03</span></div>
  </div>

  <!-- 오늘 반드시 해야 할 것 -->
  ${execution.filter((e: any) => e.when?.includes("즉시") || e.when?.includes("오늘")).length > 0 ? `
  <div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:6px;padding:12px 16px;margin-bottom:14px">
    <div style="font-size:11px;font-weight:700;color:#991B1B;margin-bottom:8px">⚡ 오늘 반드시 해야 할 것</div>
    ${execution.filter((e: any) => e.when?.includes("즉시") || e.when?.includes("오늘")).map((e: any, i: number) => {
      const nums = ["①","②","③","④","⑤","⑥","⑦","⑧","⑨","⑩"];
      return `
    <div style="margin-bottom:8px;padding-left:14px;border-left:2px solid #C0392B">
      <div style="font-size:10.5px;font-weight:600;color:#0D1B2A">${nums[i] || (i+1)+"."} ${e.what}</div>
      ${e.kpi ? `<div style="font-size:9px;color:#6B7280;margin-top:2px">KPI: ${e.kpi}</div>` : ""}
      ${e.who ? `<div style="font-size:9px;color:#2457A4">담당: ${e.who}</div>` : ""}
    </div>`;
    }).join("")}
  </div>` : ""}

  <!-- 후보 진단 -->
  ${sd.our_candidate ? `
  <div class="diag-card" style="margin-bottom:10px">
    <div class="head" style="background:#EFF6FF;color:#2457A4">우리 후보 진단</div>
    <div class="body">${splitDiagnosis(sd.our_candidate)}</div>
  </div>` : ""}
  ${sd.opp_candidate ? `
  <div class="diag-card" style="margin-bottom:10px">
    <div class="head" style="background:#FEF2F2;color:#C0392B">상대 후보 진단</div>
    <div class="body">${splitDiagnosis(sd.opp_candidate)}</div>
  </div>` : ""}
</div>

<!-- 2. 이슈 분석 -->
<div class="section">
  <div class="s-title">2. 이슈 분석 — 무엇이 확산되고, 어떻게 반응하는가</div>
  ${issues.length > 0 ? `
  <table>
    <thead><tr><th style="width:20px">#</th><th>이슈명</th><th style="width:30px">기사</th><th style="width:70px;text-align:center">진영</th><th style="width:55px">확산</th><th>진단</th></tr></thead>
    <tbody>${issues.map((iss: any, i: number) => `<tr>
      <td style="text-align:center;font-weight:700;color:#0D1B2A">${iss.rank || i + 1}</td>
      <td style="font-weight:600">${iss.name}</td>
      <td style="text-align:center;font-variant-numeric:tabular-nums">${iss.count || "—"}</td>
      <td style="text-align:center;white-space:nowrap">${sideBadge(iss.side)}</td>
      <td style="font-size:9.5px">${iss.spreading || "—"}</td>
      <td style="color:#374151">${iss.diagnosis || "—"}</td>
    </tr>`).join("")}</tbody>
  </table>` : ""}

  ${reactions.length > 0 ? `
  <div style="margin-top:14px;font-size:11px;font-weight:700;color:#0D1B2A;margin-bottom:8px">민심 리액션 분석</div>
  <table>
    <thead><tr><th style="width:24px">#</th><th>키워드</th><th>감성</th><th>볼륨</th><th>안정성</th><th>반응 세그먼트</th><th>전략적 의미</th></tr></thead>
    <tbody>${reactions.map((r: any, i: number) => {
      const sentBg = r.sentiment?.includes("부정") ? "#FEE2E2;color:#991B1B" : r.sentiment?.includes("긍정") ? "#D1FAE5;color:#065F46" : "#F3F4F6;color:#374151";
      return `<tr>
      <td style="text-align:center;font-weight:700">${r.rank || i + 1}</td>
      <td style="font-weight:600">${r.keyword || r.name}</td>
      <td><span class="badge" style="background:${sentBg}">${r.sentiment || "—"}</span></td>
      <td style="font-size:9.5px">${r.volume || "—"}</td>
      <td style="font-size:9.5px">${r.stability || "—"}</td>
      <td style="font-size:9.5px">${r.reacting_segment || "—"}${r.reacting_region ? " · " + r.reacting_region : ""}</td>
      <td style="font-size:9.5px;font-weight:500">${r.strategic_meaning || "—"}</td>
    </tr>`;
    }).join("")}</tbody>
  </table>` : ""}
</div>

<!-- 3. 대응 전략 -->
<div class="section">
  <div class="s-title">3. 대응 전략 — 조건 기반 실행 방안</div>
  ${dl.moment_type ? `
  <div class="thesis" style="margin-bottom:14px">
    <p><strong>현재 국면:</strong> ${dl.moment_type}</p>
    <p style="color:#991B1B"><strong>지켜야 할 것:</strong> ${dl.must_protect || "—"}</p>
    <p style="color:#065F46"><strong>밀어볼 것:</strong> ${dl.can_push || "—"}</p>
  </div>` : ""}

  ${strategies.map((s: any, i: number) => {
    const isUrgent = s.timeline?.includes("즉시") || s.timeline?.includes("오늘");
    const borderColor = isUrgent ? "#C0392B" : s.timeline?.includes("이번 주") ? "#2457A4" : "#C8922A";
    const urgBg = isUrgent ? "background:#FEE2E2;color:#991B1B" : s.timeline?.includes("이번 주") ? "background:#DBEAFE;color:#1E40AF" : "background:#FEF3C7;color:#92400E";
    return `
  <div class="strat-row" style="border-left:3px solid ${borderColor}">
    <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">
      <span class="badge" style="${urgBg}">${isUrgent ? "긴급" : s.timeline?.includes("이번 주") ? "단기" : "중장기"} · ${s.timeline}</span>
    </div>
    <div class="strat-name">${s.title}</div>
    ${s.condition ? `<div style="font-size:9.5px;color:#6B7280;font-style:italic;margin-bottom:4px">조건: ${s.condition}</div>` : ""}
    <div class="strat-detail">
      ${splitSentences(s.action || "").map((sent: string) => `<p style="margin-bottom:4px">${sent.trim()}</p>`).join("")}
    </div>
    <div style="display:flex;gap:16px;margin-top:6px;font-size:9.5px">
      ${s.target ? `<div>🎯 <strong>타겟:</strong> ${s.target}</div>` : ""}
      ${s.intended_effect ? `<div style="color:#2457A4">📈 <strong>기대:</strong> ${s.intended_effect}</div>` : ""}
    </div>
    ${s.risk ? `<div class="strat-risk">⚠ 리스크: ${s.risk}</div>` : ""}
  </div>`;
  }).join("")}
</div>

<!-- 4. 현장 방문 일정 -->
<div class="section">
  <div class="s-title">4. 현장 방문 일정</div>
  ${daily.daily_theme ? `
  <div class="thesis" style="margin-bottom:12px">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
      <span style="font-size:9px;font-weight:700;background:#0D1B2A;color:#E8B84B;padding:2px 10px;border-radius:10px;letter-spacing:1px">TODAY&apos;S THEME</span>
      <span style="font-size:14px;font-weight:900;color:#0D1B2A">${daily.daily_theme.keyword}</span>
    </div>
    <p style="font-size:10.5px;color:#374151">${daily.daily_theme.rationale}</p>
  </div>` : ""}
  ${fieldSchedule.map((m: any) => `
  <div style="border:1px solid #E5E7EB;border-radius:6px;padding:12px 16px;margin-bottom:8px;page-break-inside:avoid">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
      <span style="font-size:9px;font-weight:700;color:#2457A4">PRIORITY ${m.priority}</span>
      ${m.when ? `<span style="font-size:9px;font-weight:600;color:#991B1B">${m.when}</span>` : ""}
      ${m.region ? `<span style="font-size:9px;font-weight:600;background:#DBEAFE;color:#1E40AF;padding:1px 7px;border-radius:10px">${m.region}</span>` : ""}
    </div>
    ${m.theme ? `<div style="font-size:10px;margin-bottom:4px"><span style="background:#FEF3C7;color:#92400E;font-size:9px;font-weight:600;padding:1px 7px;border-radius:10px">#${m.theme}</span>${m.theme_reason ? ` <span style="color:#6B7280;font-size:9.5px">— ${m.theme_reason}</span>` : ""}</div>` : ""}
    ${m.location ? `<div style="font-size:10px;color:#6B7280;margin-bottom:4px">📍 ${m.location}</div>` : ""}
    ${m.concept ? `<div style="font-size:10px;color:#374151;margin-bottom:4px">🎯 컨셉: ${m.concept}</div>` : ""}
    <div style="font-size:12px;font-weight:700;color:#0D1B2A;margin-bottom:4px">&ldquo;${m.message}&rdquo;</div>
    <div style="font-size:10px;color:#374151;line-height:1.8;margin-bottom:4px">${m.sub_message || ""}</div>
    ${m.target_segment ? `<div style="font-size:9px;color:#6B7280">타겟: ${m.target_segment}</div>` : m.target ? `<div style="font-size:9px;color:#6B7280">타겟: ${m.target}</div>` : ""}
    ${m.media_plan ? `<div style="font-size:9px;color:#6B7280">미디어: ${m.media_plan}</div>` : m.channel ? `<div style="font-size:9px;color:#6B7280">채널: ${m.channel}</div>` : ""}
    ${m.caution ? `<div style="background:#FFFBEB;border-radius:4px;padding:4px 8px;margin-top:6px;font-size:9px;color:#92400E">⚠ ${m.caution}</div>` : ""}
    ${m.kpi ? `<div style="font-size:9px;color:#065F46;margin-top:3px">KPI: ${m.kpi}</div>` : ""}
  </div>`).join("")}
</div>

<div class="section">
  <div class="s-title">5. 실행 일정 & KPI</div>
  <table>
    <thead><tr><th style="width:70px">시점</th><th>할 일</th><th style="width:60px">담당</th><th>KPI</th></tr></thead>
    <tbody>${execution.map((e: any) => `<tr${e.when?.includes("즉시") || e.when?.includes("오늘") ? ' style="background:#FEF2F2"' : ""}>
      <td style="font-weight:600;white-space:nowrap;${e.when?.includes("즉시") ? "color:#C0392B" : ""}">${e.when}</td>
      <td style="font-weight:500">${e.what}</td>
      <td style="font-size:9.5px;color:#2457A4">${e.who || "—"}</td>
      <td style="font-size:9px;color:#6B7280">${e.kpi || "—"}</td>
    </tr>`).join("")}</tbody>
  </table>

  ${risks.length > 0 ? `
  <div style="margin-top:14px;font-size:11px;font-weight:700;color:#C0392B;margin-bottom:6px">위기 관리 매트릭스</div>
  <table>
    <thead><tr><th>위험 요소</th><th>트리거</th><th>대응</th><th style="width:60px">담당</th></tr></thead>
    <tbody>${risks.map((r: any) => `<tr>
      <td style="font-weight:600">${r.risk}</td>
      <td style="font-size:9.5px">${r.trigger || "—"}</td>
      <td style="font-size:9.5px;color:#065F46">${r.response || "—"}</td>
      <td style="font-size:9.5px">${r.owner || "—"}</td>
    </tr>`).join("")}</tbody>
  </table>` : ""}
</div>

<div class="doc-footer">
  김경수 경남도지사 캠프 · 전략대응 ${today.replace(/-/g, "/")} 리포트 · D-${dDay} · 대외비
</div>

</body></html>`;

  const win = window.open("", "_blank");
  if (win) {
    win.document.write(html);
    win.document.close();
    setTimeout(() => win.print(), 500);
  }
}
function exportResearchPDF() {
  // 리서치 탭의 DOM을 캡처해서 인쇄용 새 창으로
  const el = document.getElementById("research-content");
  if (!el) { window.print(); return; }
  const clone = el.cloneNode(true) as HTMLElement;

  // 다크 테마 → 라이트 테마 변환
  clone.querySelectorAll("*").forEach((node) => {
    const e = node as HTMLElement;
    const cls = e.className || "";
    if (typeof cls !== "string") return;
    // 배경
    if (cls.includes("bg-[#0e1825]") || cls.includes("bg-[#080e18]") || cls.includes("wr-card")) e.style.background = "#fff";
    if (cls.includes("bg-cyan-600") || cls.includes("bg-cyan-950")) e.style.background = "#eff6ff";
    if (cls.includes("bg-amber-600") || cls.includes("bg-amber-950")) e.style.background = "#fffbeb";
    if (cls.includes("bg-emerald-600") || cls.includes("bg-emerald-950")) e.style.background = "#f0fdf4";
    if (cls.includes("bg-purple-600")) e.style.background = "#faf5ff";
    if (cls.includes("bg-blue-950") || cls.includes("bg-blue-900")) e.style.background = "#eff6ff";
    if (cls.includes("bg-red-950") || cls.includes("bg-red-900")) e.style.background = "#fef2f2";
    // 텍스트
    if (cls.includes("text-cyan-300") || cls.includes("text-cyan-400")) e.style.color = "#0891b2";
    if (cls.includes("text-amber-300") || cls.includes("text-amber-400")) e.style.color = "#d97706";
    if (cls.includes("text-emerald-400")) e.style.color = "#059669";
    if (cls.includes("text-blue-400") || cls.includes("text-blue-300")) e.style.color = "#2563eb";
    if (cls.includes("text-red-400") || cls.includes("text-red-300")) e.style.color = "#dc2626";
    if (cls.includes("text-purple-400")) e.style.color = "#7c3aed";
    if (cls.includes("text-gray-100") || cls.includes("text-gray-200") || cls.includes("text-gray-300")) e.style.color = "#1a1a1a";
    if (cls.includes("text-gray-400") || cls.includes("text-gray-500")) e.style.color = "#666";
    if (cls.includes("text-gray-600")) e.style.color = "#888";
    if (cls.includes("text-white")) e.style.color = "#1a1a1a";
    // 보더
    if (cls.includes("border-[#1a2844]") || cls.includes("border-gray-800")) e.style.borderColor = "#e5e7eb";
    if (cls.includes("border-cyan")) e.style.borderColor = "#0891b2";
  });

  const html = `<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<title>선거 전략 리서치</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');
* { box-sizing: border-box; }
body { font-family: 'Noto Sans KR', sans-serif; color: #111827; background: white; padding: 32px 40px; font-size: 11px; line-height: 1.7; }
@media print { body { padding: 0; } @page { size: A4; margin: 14mm; } }
.doc-header { margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #0D1B2A; }
.doc-title { font-size: 16px; font-weight: 900; color: #0D1B2A; }
.doc-sub { font-size: 10px; color: #6B7280; margin-top: 3px; }
.doc-footer { margin-top: 24px; padding-top: 8px; border-top: 1px solid #d1d5db; font-size: 8.5px; color: #9ca3af; text-align: center; }
</style></head><body>
<div class="doc-header">
  <div class="doc-title">경남도지사 선거 전략 리서치</div>
  <div class="doc-sub">${new Date().toISOString().slice(0, 10)} · 학술연구 + 캠프전략 + 해외연구 종합 · 대외비</div>
</div>
${clone.innerHTML}
<div class="doc-footer">김경수 경남도지사 캠프 · 전략 리서치 · 대외비</div>
</body></html>`;

  const win = window.open("", "_blank");
  if (win) {
    win.document.write(html);
    win.document.close();
    setTimeout(() => win.print(), 500);
  }
}

type SubTab = "summary" | "issue" | "strategy" | "message";

export default function StrategyMode({ onExit }: { onExit: () => void }) {
  const [page, setPage] = useState<Page>("daily");
  const [subTab, setSubTab] = useState<SubTab>("summary");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [data, setData] = useState<any>({});

  const load = useCallback(async () => {
    setLoading(true);
    // 핵심 데이터만 먼저 로드 (위클리는 lazy)
    const [daily, indices, history, clusters, reports, training] = await Promise.all([
      getDailyBriefing().catch(() => null),
      getIndicesCurrent().catch(() => null),
      getIndicesHistory().catch(() => null),
      getNewsClusters().catch(() => null),
      getDailyReports().catch(() => null),
      getTrainingData().catch(() => null),
    ]);
    setData((prev: any) => ({ ...prev, daily, indices, history, clusters, reports, training }));
    // 위클리는 탭 클릭 시 로드 (비용 절약)
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    try {
      await generateDailyBriefing();
      await load();
    } finally {
      setGenerating(false);
    }
  }, [load]);

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

          <div className="px-5 py-1 mt-3 text-[9px] tracking-[2px] text-white/30 font-medium">DATA</div>
          <NavItem label="학습데이터" icon="🧠" active={page === "training"} badge={String(data.training?.total || 0)} badgeColor="bg-[#2457A4]" onClick={() => setPage("training")} />
          <NavItem label="리서치" icon="🔍" active={page === "research"} onClick={() => setPage("research")} />
        </nav>
        <div className="px-4 py-4 border-t border-white/10">
          <button onClick={onExit} className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-[12px] font-bold text-white bg-[#2457A4] hover:bg-[#1B3A6B] transition-colors">
            <span>◀</span> War Room 복귀
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
            <button onClick={handleGenerate} disabled={generating}
              className="px-3 py-1.5 text-xs font-medium text-white bg-[#2457A4] rounded-md hover:bg-[#1B3A6B] transition disabled:opacity-50">
              {generating ? "AI 생성 중..." : "리포트 갱신"}
            </button>
            <button onClick={() => page === "research" ? exportResearchPDF() : exportPDF(data)} className="px-3 py-1.5 text-xs text-gray-700 border border-gray-300 rounded-md hover:bg-gray-100">
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
                    {{ summary: "종합 브리핑", issue: "이슈 분석", strategy: "대응 전략", message: "현장 일정" }[t]}
                  </button>
                ))}
              </div>

              {subTab === "summary" && <SummaryTab daily={daily} indices={data.indices} history={data.history} />}
              {subTab === "issue" && <IssueTab daily={daily} clusters={data.clusters} />}
              {subTab === "strategy" && <StrategyTab daily={daily} />}
              {subTab === "message" && <MessageTab daily={daily} />}
            </>
          ) : page === "weekly" ? (
            <WeeklyPage weekly={data.weekly} />
          ) : page === "training" ? (
            <TrainingPage training={data.training} />
          ) : page === "research" ? (
            <div id="research-content" className="bg-[#0a0f1a] rounded-xl p-4 -mx-2"><ResearchPage /></div>
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
function SummaryTab({ daily, indices, history }: { daily: any; indices: any; history: any }) {
  const issue = indices?.issue || {};
  const reaction = indices?.reaction || {};
  const pandse = indices?.pandse || {};
  const trend = (history?.candidate_trend || []).slice(-24);

  return (
    <div className="space-y-5">
      {/* Executive Summary Box */}
      <div className="rounded-xl overflow-hidden" style={{ background: "linear-gradient(135deg, #0D1B2A 0%, #1B3A6B 100%)", color: "white" }}>
        <div className="px-6 pt-5 pb-4">
          <div className="text-[9px] tracking-[2px] text-[#E8B84B] font-medium mb-3 uppercase">Daily Brief · {daily.date || new Date().toISOString().slice(0, 10)}</div>
          {(() => {
            const text = daily.executive_summary || "";
            if (!text) return <div className="text-[13px] text-white/60">데일리 리포트를 먼저 생성하세요.</div>;
            const sentences = text.split(/(?<=다\.|음\.|중\.|요\.|임\.|됨\.|함\.|성\.|니다\.|세요\.|있다\.|없다\.|하다\.|된다\.|이다\.)\s*/g).filter(Boolean);
            const headline = sentences[0] || text;
            const body = sentences.slice(1);
            return (
              <>
                <div className="text-[14px] font-bold leading-[1.8] mb-4 max-w-[90%]" style={{ fontFamily: "'Noto Serif KR', serif" }}>
                  {headline}
                </div>
                {body.length > 0 && (
                  <div className="text-[12px] leading-[1.9] text-white/80 space-y-3 border-t border-white/10 pt-4">
                    {body.map((s: string, i: number) => (
                      <p key={i} className="pl-3" style={{ borderLeft: "2px solid rgba(232,184,75,0.4)" }}>{s.trim()}</p>
                    ))}
                  </div>
                )}
              </>
            );
          })()}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "이슈지수", val: issue.index, grade: issue.grade, color: "#1A7A4A" },
          { label: "반응지수", val: reaction.index, grade: reaction.grade, color: "#C8922A" },
          { label: "판세지수", val: pandse.index, grade: pandse.grade, color: "#2457A4" },
        ].map(({ label, val, grade, color }) => {
          const gradeStyle = grade === "우세" ? { bg: "#D1FAE5", text: "#065F46" } : grade === "열세" ? { bg: "#FEE2E2", text: "#991B1B" } : { bg: "#F3F4F6", text: "#374151" };
          return (
            <div key={label} className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="text-[10px] text-gray-500 font-medium tracking-wider">{label}</div>
                <span className="text-[9px] font-bold px-2 py-0.5 rounded-full" style={{ background: gradeStyle.bg, color: gradeStyle.text }}>{grade}</span>
              </div>
              <div className="text-[24px] font-black leading-none" style={{ color }}>{val?.toFixed(1) || "—"}<span className="text-[11px] text-gray-400 ml-0.5">pt</span></div>
              <div className="mt-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                <div className="h-full rounded-full transition-all" style={{ width: `${val || 50}%`, background: color }} />
              </div>
            </div>
          );
        })}
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="text-[10px] text-gray-500 font-medium tracking-wider mb-2">D-Day</div>
          <div className="text-[24px] font-black text-[#0D1B2A] leading-none">D-{pandse.d_day || "?"}</div>
          <div className="text-[10px] text-gray-400 mt-2">선거일 2026.06.03</div>
        </div>
      </div>

      {/* 24시간 지표 추세 */}
      {trend.length >= 2 && (
        <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
            <div>
              <div className="text-[13px] font-bold text-[#0D1B2A]">24시간 지표 추세</div>
              <div className="text-[11px] text-gray-500 mt-0.5">{trend[0]?.date} ~ {trend[trend.length - 1]?.date} · {trend.length}건</div>
            </div>
            <div className="flex items-center gap-4 text-[10px]">
              <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#1A7A4A]" />이슈</span>
              <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#C8922A]" />반응</span>
              <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#2457A4]" />판세</span>
            </div>
          </div>
          <div className="px-5 py-4">
            <TrendChart data={trend} />
          </div>
        </div>
      )}

      {/* Candidate Diagnosis */}
      {(daily.situation_diagnosis?.our_candidate || daily.situation_diagnosis?.opp_candidate) && (
        <div className="grid grid-cols-2 gap-4">
          <CandidateCard
            title="우리 후보 AI 진단"
            icon="🔵"
            color="#2457A4"
            bgColor="#EFF6FF"
            text={daily.situation_diagnosis?.our_candidate}
          />
          <CandidateCard
            title="상대 후보 AI 진단"
            icon="🔴"
            color="#C0392B"
            bgColor="#FEF2F2"
            text={daily.situation_diagnosis?.opp_candidate}
          />
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
        <Card title="민심 리액션 TOP" sub="감성 분석 기반">
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
            <div className="px-5 pb-4 text-[11px] text-gray-700 leading-[2.0] space-y-2">
              {s.condition && <div className="text-[10px] text-gray-500 italic">조건: {s.condition}</div>}
              <SplitText text={s.action} />
              {s.target && <div className="text-[10px]">🎯 타겟: {s.target}</div>}
              {s.intended_effect && <div className="text-[10px]">📈 기대: {s.intended_effect}</div>}
              {s.risk && (
                <div className="px-3 py-2 rounded-md text-[10px] leading-[1.8]" style={{ background: "#FEF2F2", color: "#991B1B" }}>
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
  const fieldSchedule = daily.field_schedule || daily.messages || [];
  const execution = daily.execution || [];
  const risks = daily.risk_management || [];

  return (
    <div className="grid grid-cols-2 gap-5">
      {/* Left: Field Schedule */}
      <div className="space-y-3">
        {/* Daily Theme */}
        {daily.daily_theme && (
          <div className="rounded-xl p-4" style={{ background: "linear-gradient(135deg, #0D1B2A 0%, #1B3A6B 100%)" }}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[9px] font-bold tracking-wider px-2 py-0.5 rounded-full" style={{ background: "#C8922A", color: "white" }}>TODAY&apos;S THEME</span>
              <span className="text-[16px] font-black text-white">{daily.daily_theme.keyword}</span>
            </div>
            <div className="text-[11px] text-white/80 leading-relaxed">{daily.daily_theme.rationale}</div>
          </div>
        )}
        <div className="text-xs font-bold text-[#0D1B2A] mb-2">현장 방문 일정</div>
        {fieldSchedule.map((m: any, i: number) => (
          <div key={i} className="rounded-xl border border-gray-200 bg-white p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-bold text-[#2457A4]">PRIORITY {m.priority}</span>
              {m.when && <span className="text-[9px] font-bold text-[#C0392B]">{m.when}</span>}
              {m.region && <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800">{m.region}</span>}
            </div>
            {m.theme && (
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">#{m.theme}</span>
                {m.theme_reason && <span className="text-[9px] text-gray-500">{m.theme_reason}</span>}
              </div>
            )}
            {m.location && <div className="text-[10px] text-gray-500 mb-1">📍 {m.location}</div>}
            {m.concept && <div className="text-[10px] text-gray-600 mb-2">🎯 {m.concept}</div>}
            <div className="text-[14px] font-bold text-[#0D1B2A] mb-2" style={{ fontFamily: "'Noto Serif KR', serif" }}>
              &ldquo;{m.message}&rdquo;
            </div>
            <div className="text-[11px] text-gray-600 leading-relaxed mb-2">{m.sub_message}</div>
            {(m.target_segment || m.target) && <div className="text-[10px] text-gray-500">타겟: {m.target_segment || m.target}</div>}
            {(m.media_plan || m.channel) && <div className="text-[10px] text-gray-500">미디어: {m.media_plan || m.channel}</div>}
            {m.caution && (
              <div className="mt-2 text-[10px] px-3 py-1.5 rounded-md" style={{ background: "#FFFBEB", color: "#92400E" }}>
                ⚠ {m.caution}
              </div>
            )}
            {m.kpi && <div className="mt-1 text-[9px] text-emerald-700">KPI: {m.kpi}</div>}
          </div>
        ))}
        {fieldSchedule.length === 0 && <div className="text-xs text-gray-400 text-center py-4">일정 데이터 없음</div>}
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
function WeeklyPage({ weekly: initialWeekly }: { weekly: any }) {
  const [weekly, setWeekly] = useState<any>(initialWeekly);
  const [wLoading, setWLoading] = useState(false);

  const loadWeekly = useCallback(async () => {
    setWLoading(true);
    try { setWeekly(await getWeeklyBriefing()); } catch {}
    setWLoading(false);
  }, []);

  if (wLoading) return <div className="text-center py-20 text-gray-400 animate-pulse">위클리 리포트 생성 중...</div>;
  if (!weekly || weekly.error) return (
    <div className="text-center py-20">
      <div className="text-gray-400 mb-4">위클리 리포트가 없습니다</div>
      <button onClick={loadWeekly} className="px-4 py-2 text-sm font-bold text-white bg-[#2457A4] rounded-lg hover:bg-[#1B3A6B]">위클리 리포트 생성</button>
    </div>
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

/* ── 24h Trend Chart ── */
function TrendChart({ data }: { data: any[] }) {
  const n = data.length;
  if (n < 2) return null;
  const w = 700, h = 160, pl = 35, pr = 10, pt = 10, pb = 25;
  const cw = w - pl - pr, ch = h - pt - pb;

  const issueVals = data.map(d => d.issue_index ?? 50);
  const reactionVals = data.map(d => d.reaction_index ?? 50);
  const pandseVals = data.map(d => d.pandse ?? 50);
  const allVals = [...issueVals, ...reactionVals, ...pandseVals];
  const mn = Math.min(...allVals, 30) - 5;
  const mx = Math.max(...allVals, 70) + 5;
  const rng = mx - mn || 1;

  const X = (i: number) => pl + (i / Math.max(n - 1, 1)) * cw;
  const Y = (v: number) => pt + (1 - (v - mn) / rng) * ch;

  const line = (vals: number[]) => vals.map((v, i) => `${X(i)},${Y(v)}`).join(" ");

  const lines = [
    { vals: issueVals, color: "#1A7A4A", label: "이슈" },
    { vals: reactionVals, color: "#C8922A", label: "반응" },
    { vals: pandseVals, color: "#2457A4", label: "판세" },
  ];

  // Y축 눈금
  const yTicks = [30, 40, 50, 60, 70, 80, 90].filter(v => v >= mn && v <= mx);

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      {/* 50pt 기준선 */}
      <line x1={pl} y1={Y(50)} x2={w - pr} y2={Y(50)} stroke="#D1D5DB" strokeWidth="1" strokeDasharray="4,3" />
      <text x={pl - 4} y={Y(50) + 3} fill="#9CA3AF" fontSize="9" textAnchor="end" fontFamily="monospace">50</text>

      {/* Y축 눈금 */}
      {yTicks.filter(v => v !== 50).map(v => (
        <g key={v}>
          <line x1={pl} y1={Y(v)} x2={w - pr} y2={Y(v)} stroke="#F3F4F6" strokeWidth="0.5" />
          <text x={pl - 4} y={Y(v) + 3} fill="#D1D5DB" fontSize="8" textAnchor="end" fontFamily="monospace">{v}</text>
        </g>
      ))}

      {/* X축 시간 라벨 */}
      {data.map((d, i) => (
        (i % Math.max(1, Math.floor(n / 6)) === 0 || i === n - 1) ? (
          <text key={i} x={X(i)} y={h - 4} fill="#9CA3AF" fontSize="8" textAnchor="middle" fontFamily="monospace">
            {(d.date || "").slice(-5)}
          </text>
        ) : null
      ))}

      {/* 3개 라인 */}
      {lines.map(({ vals, color }) => (
        <g key={color}>
          <polyline points={line(vals)} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
          {/* 마지막 점 강조 */}
          <circle cx={X(n - 1)} cy={Y(vals[n - 1])} r="4" fill={color} />
          <text x={X(n - 1) + 6} y={Y(vals[n - 1]) + 3} fill={color} fontSize="9" fontWeight="bold" fontFamily="monospace">
            {vals[n - 1]?.toFixed(1)}
          </text>
        </g>
      ))}
    </svg>
  );
}

/* ── Candidate Diagnosis Card ── */
function CandidateCard({ title, icon, color, bgColor, text }: {
  title: string; icon: string; color: string; bgColor: string; text?: string;
}) {
  if (!text) return null;

  // 강점/약점/기회/위협 키워드로 분리 시도
  const sections: { label: string; badge: string; badgeColor: string; content: string }[] = [];
  const patterns = [
    { key: "강점", badge: "강점", badgeColor: "bg-emerald-100 text-emerald-800" },
    { key: "약점", badge: "약점", badgeColor: "bg-red-100 text-red-800" },
    { key: "기회", badge: "기회", badgeColor: "bg-blue-100 text-blue-800" },
    { key: "위협", badge: "위협", badgeColor: "bg-amber-100 text-amber-800" },
    { key: "공략", badge: "공략점", badgeColor: "bg-amber-100 text-amber-800" },
  ];

  // "강점:" 또는 "강점 :" 패턴으로 분리
  let remaining = text;
  for (const { key, badge, badgeColor } of patterns) {
    const regex = new RegExp(`${key}[:\\s：]+`, "g");
    const match = regex.exec(remaining);
    if (match) {
      // 이 키워드 이후 ~ 다음 키워드 전까지
      const start = match.index + match[0].length;
      const nextPattern = patterns.find(p => p.key !== key && remaining.indexOf(p.key + ":") > start);
      const end = nextPattern ? remaining.indexOf(nextPattern.key + ":") : undefined;
      const content = remaining.slice(start, end).trim().replace(/\.$/, "");
      if (content) sections.push({ label: badge, badge, badgeColor, content });
    }
  }

  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden">
      <div className="px-5 py-3 border-b flex items-center gap-2" style={{ background: bgColor }}>
        <span>{icon}</span>
        <span className="text-[13px] font-bold" style={{ color }}>{title}</span>
      </div>
      <div className="px-5 py-4">
        {sections.length > 0 ? (
          <div className="space-y-3">
            {sections.map((s, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className={`shrink-0 text-[9px] font-bold px-2 py-0.5 rounded-full mt-0.5 ${s.badgeColor}`}>{s.badge}</span>
                <span className="text-[11px] text-gray-700 leading-[1.8]">{s.content}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-[11px] text-gray-700 leading-[2.0] space-y-2">
            <SplitText text={text} />
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Text Formatter ── */
function SplitText({ text }: { text?: string }) {
  if (!text) return <span className="text-gray-400">—</span>;
  // 한국어 문장 끝 패턴으로 분리
  const sentences = text.split(/(?<=다\.|음\.|중\.|요\.|임\.|됨\.|함\.|성\.|니다\.|세요\.|있다\.|없다\.|하다\.|된다\.|이다\.)\s*/g).filter(Boolean);
  if (sentences.length <= 1) return <p>{text}</p>;
  return <>{sentences.map((s: string, i: number) => <p key={i}>{s.trim()}</p>)}</>;
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
