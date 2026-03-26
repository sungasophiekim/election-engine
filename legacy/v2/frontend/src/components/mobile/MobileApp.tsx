"use client";
import { useState } from "react";
import { MobileCommand } from "./MobileCommand";
import { MobileIssues } from "./MobileIssues";
import { MobileStrategy } from "./MobileStrategy";
import { MobileActions } from "./MobileActions";

const TABS = [
  { id: "command", label: "상황", icon: "⚔" },
  { id: "issues", label: "이슈", icon: "📰" },
  { id: "strategy", label: "전략", icon: "🎯" },
  { id: "actions", label: "실행", icon: "⚡" },
] as const;

type TabId = typeof TABS[number]["id"];

export function MobileApp() {
  const [tab, setTab] = useState<TabId>("command");

  return (
    <div className="flex flex-col h-screen bg-[#04070d]">
      {/* Content */}
      <main className="flex-1 overflow-y-auto">
        {tab === "command" && <MobileCommand />}
        {tab === "issues" && <MobileIssues />}
        {tab === "strategy" && <MobileStrategy />}
        {tab === "actions" && <MobileActions />}
      </main>

      {/* Bottom tab bar */}
      <nav className="shrink-0 bg-[#060a11] border-t border-[#1a2844] flex safe-area-bottom">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 py-2.5 text-center transition-colors ${
              tab === t.id
                ? "text-blue-400 bg-blue-500/10"
                : "text-gray-600 active:bg-white/5"
            }`}
          >
            <span className="text-lg block">{t.icon}</span>
            <span className="text-[9px] block mt-0.5 font-bold">{t.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
