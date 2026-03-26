"use client";
import { useState, useEffect, useCallback } from "react";
import { getV2Enrichment, getPreTriggers } from "@/lib/api";

// ════════════════════════════════════════════════════════════════════
// OPPONENT PAGE — 상대 분석 전용
// Pre-Trigger 경고 + 상대 행보 + 이벤트 임팩트 시뮬레이션
// ════════════════════════════════════════════════════════════════════

export function OpponentPage() {
  const [pretrigger, setPretrigger] = useState<any>(null);
  const [enrichment, setEnrichment] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [simEvent, setSimEvent] = useState("policy");
  const [simSeverity, setSimSeverity] = useState("standard");

  const refresh = useCallback(() => {
    getV2Enrichment().then(setEnrichment).catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const runPreTrigger = () => {
    setLoading(true);
    getPreTriggers()
      .then(setPretrigger)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  const oppPoll = enrichment?.national_poll;
  const oppTurnout = enrichment?.turnout;

  // 이벤트 임팩트 시뮬레이션 데이터
  const EVENT_TYPES = [
    { id: "policy", label: "정책 발표", base: -1.5 },
    { id: "debate", label: "TV 토론 승리", base: -2.0 },
    { id: "scandal", label: "스캔들/실수", base: 2.5 },
    { id: "endorsement", label: "지지선언", base: -0.5 },
    { id: "visit", label: "지역 방문", base: -0.3 },
    { id: "gaffe", label: "실언", base: 1.5 },
  ];
  const SEVERITY = [
    { id: "minor", label: "소형", mult: 0.5 },
    { id: "standard", label: "표준", mult: 1.0 },
    { id: "major", label: "대형", mult: 1.5 },
    { id: "critical", label: "초대형", mult: 2.0 },
  ];
  const selectedEvent = EVENT_TYPES.find(e => e.id === simEvent);
  const selectedSev = SEVERITY.find(s => s.id === simSeverity);
  const simImpact = (selectedEvent?.base || 0) * (selectedSev?.mult || 1);

  return (
    <div className="space-y-1.5 pb-12 max-w-6xl mx-auto">
      {/* Header */}
      <div className="wr-card border-t-2 border-t-red-600">
        <div className="px-4 py-3 flex items-center justify-between">
          <div>
            <h2 className="text-[14px] font-bold text-red-300">👤 상대 분석 — 박완수</h2>
            <p className="text-[10px] text-gray-500 mt-0.5">Pre-Trigger 경고 + 상대 행보 모니터링 + 이벤트 임팩트 시뮬레이션</p>
          </div>
          <button onClick={runPreTrigger} disabled={loading}
            className="bg-red-600 hover:bg-red-500 text-white px-3 py-1.5 rounded text-[10px] font-bold transition disabled:opacity-30">
            {loading ? "스캔 중..." : "Pre-Trigger 스캔"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-1.5">
        {/* Pre-Trigger 경고 (8/12) */}
        <div className="col-span-8 wr-card">
          <div className="wr-card-header flex justify-between">
            <span className="text-red-400">Pre-Trigger 경고</span>
            <span className="text-[8px] text-gray-600">도청 보도자료 + 상대 SNS + 기자 시그널 + 정책 선점</span>
          </div>
          {pretrigger ? (
            <div className="divide-y divide-[#0e1825] max-h-[400px] overflow-y-auto feed-scroll">
              {pretrigger.signals && pretrigger.signals.length > 0 ? (
                pretrigger.signals.map((s: any, i: number) => (
                  <div key={i} className={`px-3 py-2 ${s.severity === "critical" ? "bg-red-950/20" : ""}`}>
                    <div className="flex items-center gap-2">
                      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                        s.severity === "critical" ? "bg-red-500" : s.severity === "warning" ? "bg-amber-500" : "bg-gray-600"
                      }`} />
                      <span className="text-[11px] text-gray-200 font-bold flex-1">{s.title}</span>
                      <span className={`text-[8px] px-1.5 py-0.5 rounded ${
                        s.severity === "critical" ? "bg-red-950/50 text-red-400" : "bg-amber-950/50 text-amber-400"
                      }`}>{s.severity}</span>
                    </div>
                    <div className="text-[9px] text-gray-500 mt-0.5 ml-4">{s.detail}</div>
                    {s.recommended_action && (
                      <div className="text-[9px] text-cyan-400 mt-0.5 ml-4">→ {s.recommended_action}</div>
                    )}
                  </div>
                ))
              ) : (
                <div className="p-4 text-center text-gray-700 text-xs">현재 감지된 위협 없음</div>
              )}
              {pretrigger.summary && (
                <div className="px-3 py-2 bg-[#080d16]">
                  <div className="text-[9px] text-gray-400">
                    감지: {pretrigger.summary.total}건 (위험 {pretrigger.summary.critical}건) | {pretrigger.summary.scan_time}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-6 text-center text-gray-700 text-xs">
              "Pre-Trigger 스캔" 버튼을 눌러 상대 동향을 감지하세요
            </div>
          )}
        </div>

        {/* 상대 현황 요약 (4/12) */}
        <div className="col-span-4 space-y-1.5">
          <div className="wr-card">
            <div className="wr-card-header text-red-400">상대 현황</div>
            <div className="divide-y divide-[#0e1825]">
              <div className="flex items-center justify-between px-3 py-2 text-[10px]">
                <span className="text-gray-500">후보</span>
                <span className="text-gray-200 font-bold">박완수 (국민의힘)</span>
              </div>
              <div className="flex items-center justify-between px-3 py-2 text-[10px]">
                <span className="text-gray-500">공천</span>
                <span className="text-amber-400 font-bold">단수공천 확정</span>
              </div>
              <div className="flex items-center justify-between px-3 py-2 text-[10px]">
                <span className="text-gray-500">현직 프리미엄</span>
                <span className="text-red-400">도지사 재임 중</span>
              </div>
              <div className="flex items-center justify-between px-3 py-2 text-[10px]">
                <span className="text-gray-500">국힘 지지율</span>
                <span className="text-gray-300">{oppPoll?.party_opposition || 27}%</span>
              </div>
              <div className="flex items-center justify-between px-3 py-2 text-[10px]">
                <span className="text-gray-500">투표율 구조</span>
                <span className="text-red-400 font-bold">60+ 고투표율 유리</span>
              </div>
            </div>
          </div>

          {/* 위협 요약 */}
          <div className="wr-card">
            <div className="wr-card-header text-amber-400">주요 위협</div>
            <div className="px-3 py-2 space-y-1.5">
              {[
                { risk: "사법리스크 프레임", level: "high", detail: "7건 모니터링 중" },
                { risk: "민생지원금 선점", level: "medium", detail: "도청 발표 감지 실패" },
                { risk: "현직 행정력", level: "medium", detail: "예산/조직 동원력 우위" },
                { risk: "60대 고투표율", level: "high", detail: "구조적 +15만표 우위" },
              ].map((t, i) => (
                <div key={i} className="flex items-center gap-2 text-[10px]">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    t.level === "high" ? "bg-red-500" : "bg-amber-500"
                  }`} />
                  <span className="text-gray-300 flex-1">{t.risk}</span>
                  <span className="text-gray-600 text-[8px]">{t.detail}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 이벤트 임팩트 시뮬레이션 */}
      <div className="wr-card">
        <div className="wr-card-header flex justify-between">
          <span className="text-amber-400">상대 이벤트 임팩트 시뮬레이션</span>
          <span className="text-[8px] text-gray-600">"상대가 이걸 하면 우리에게 몇 %p 영향?"</span>
        </div>
        <div className="px-4 py-3">
          <div className="flex gap-4 mb-3">
            <div>
              <div className="text-[8px] text-gray-600 mb-1">상대 행동</div>
              <div className="flex rounded border border-[#1a2844] overflow-hidden">
                {EVENT_TYPES.map(e => (
                  <button key={e.id} onClick={() => setSimEvent(e.id)}
                    className={`px-2 py-1 text-[9px] font-bold transition ${
                      simEvent === e.id ? "bg-red-600/30 text-red-400" : "text-gray-600 hover:text-gray-400"
                    }`}>{e.label}</button>
                ))}
              </div>
            </div>
            <div>
              <div className="text-[8px] text-gray-600 mb-1">규모</div>
              <div className="flex rounded border border-[#1a2844] overflow-hidden">
                {SEVERITY.map(s => (
                  <button key={s.id} onClick={() => setSimSeverity(s.id)}
                    className={`px-2 py-1 text-[9px] font-bold transition ${
                      simSeverity === s.id ? "bg-amber-600/30 text-amber-400" : "text-gray-600 hover:text-gray-400"
                    }`}>{s.label} x{s.mult}</button>
                ))}
              </div>
            </div>
          </div>
          <div className="bg-[#080d16] rounded-lg p-3 flex items-center justify-between">
            <div>
              <span className="text-[10px] text-gray-400">상대가 </span>
              <span className="text-[11px] text-red-300 font-bold">{selectedEvent?.label}</span>
              <span className="text-[10px] text-gray-400">을 하면 ({selectedSev?.label})</span>
            </div>
            <div className="text-center">
              <div className={`text-2xl font-black ${simImpact >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {simImpact > 0 ? "+" : ""}{simImpact.toFixed(1)}<span className="text-[12px] text-gray-600">%p</span>
              </div>
              <div className="text-[8px] text-gray-600">우리 지지율 변화</div>
            </div>
            <div className="text-[9px] text-gray-500 max-w-[200px]">
              {simImpact >= 1 ? "우리에게 유리 — 상대 실수/스캔들 활용" :
               simImpact <= -1 ? "우리에게 불리 — 즉시 대응 메시지 필요" :
               "영향 미미 — 모니터링 유지"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
