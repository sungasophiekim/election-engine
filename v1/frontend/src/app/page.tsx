"use client";
import { useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import { useAuth } from "@/lib/auth";
import { fmtTs } from "@/lib/format";
import PollChart, { NationalTrendChart } from "@/components/PollChart";
import PredictionBars from "@/components/PredictionBars";
import IndicesPanel from "@/components/IndicesPanel";
import NewsTop from "@/components/NewsTop";
import ReactionSidebar from "@/components/ReactionSidebar";
import SystemPanel from "@/components/SystemPanel";
import ReportPanel from "@/components/ReportPanel";
import LoginPage from "@/components/LoginPage";

export default function WarRoom() {
  const { fetchAll, loading, lastUpdated, newPollAlert, dismissAlert, collectionStatus } = useStore();
  const { token, tier, username, label, logout, checkSession } = useAuth();
  const [systemOpen, setSystemOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    checkSession().finally(() => setAuthChecked(true));
  }, [checkSession]);

  useEffect(() => {
    if (!token) return;
    fetchAll();
    const interval = setInterval(fetchAll, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchAll, token]);

  if (!authChecked) return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-cyan-400 text-sm animate-pulse">인증 확인 중...</div>
    </div>
  );

  if (!token) return <LoginPage />;

  if (loading) return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-center">
        <div className="text-cyan-400 text-sm animate-pulse mb-2">Election Engine v1</div>
        <div className="text-gray-600 text-xs">War Room 로딩 중...</div>
      </div>
    </div>
  );

  return (
    <div className="max-w-[1920px] mx-auto px-4 py-3">
      <SystemPanel open={systemOpen} onClose={() => setSystemOpen(false)} />
      <ReportPanel open={reportOpen} onClose={() => setReportOpen(false)} />

      {/* 새 여론조사 Alert */}
      {newPollAlert && (
        <div className="mb-2 px-4 py-2 rounded-lg bg-amber-500/15 border border-amber-500/40 flex items-center justify-between anim-in">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400 live-dot" />
            <span className="text-[11px] font-bold text-amber-300">NEW POLL</span>
            <span className="text-[11px] text-gray-300">
              새로운 여론조사 감지 — {newPollAlert.label} ({newPollAlert.date})
            </span>
          </div>
          <button onClick={dismissAlert} className="text-[10px] text-gray-500 hover:text-gray-300 transition-colors">
            ✕ 닫기
          </button>
        </div>
      )}

      {/* 헤더 */}
      <div className="flex items-center justify-between mb-3 anim-in">
        <div className="flex items-center gap-3">
          <h1 className="text-[15px] font-black text-blue-300 uppercase tracking-wider">War Room</h1>
          <span className="w-2 h-2 rounded-full bg-emerald-500 live-dot" />
          <span className="text-[9px] text-emerald-500 font-bold">LIVE</span>
        </div>
        <div className="flex items-center gap-3">
          {tier !== null && tier >= 1 && (
            <>
              <button
                onClick={() => setReportOpen(true)}
                className="text-[10px] font-bold text-gray-400 hover:text-cyan-300 border border-[#1a2844] hover:border-cyan-800/50 px-2.5 py-1 rounded transition-colors"
              >
                전략모드
              </button>
              <button
                onClick={() => setSystemOpen(true)}
                className="text-[10px] font-bold text-gray-400 hover:text-cyan-300 border border-[#1a2844] hover:border-cyan-800/50 px-2.5 py-1 rounded transition-colors"
              >
                시스템
              </button>
            </>
          )}
          <span className="text-[9px] text-gray-600">{fmtTs(lastUpdated)}</span>
          {collectionStatus?.today && (() => {
            const t = collectionStatus.today;
            const icon = t.status === "ok" ? "text-emerald-500" : t.status === "warning" ? "text-amber-400" : "text-rose-500";
            const dot = t.status === "ok" ? "bg-emerald-500" : t.status === "warning" ? "bg-amber-400" : "bg-rose-500";
            return (
              <span className={`text-[9px] ${icon} flex items-center gap-1`}>
                <span className={`w-1.5 h-1.5 rounded-full ${dot} ${t.status !== "ok" ? "animate-pulse" : ""}`} />
                {t.count}/{t.expected}건
              </span>
            );
          })()}
          <span className="text-[10px] text-gray-500">경남도지사 선거 · Election Engine v1</span>
          <span className="text-[9px] text-gray-600 border-l border-[#1a2844] pl-3">
            {username} <span className="text-gray-700">({label})</span>
          </span>
          <button
            onClick={logout}
            className="text-[9px] text-gray-600 hover:text-rose-400 transition-colors"
          >
            로그아웃
          </button>
        </div>
      </div>

      {/* 2열: 왼쪽 메인(8) + 오른쪽 사이드(4) */}
      <div className="grid grid-cols-12 gap-3">
        {/* 왼쪽 메인 */}
        <div className="col-span-9 space-y-3">
          <PollChart />
          <NationalTrendChart />
          <PredictionBars />
          <IndicesPanel />
</div>

        {/* 오른쪽 사이드 */}
        <div className="col-span-3 grid grid-rows-2 gap-3" style={{ height: "fit-content" }}>
          <NewsTop />
          <ReactionSidebar />
        </div>
      </div>
    </div>
  );
}
