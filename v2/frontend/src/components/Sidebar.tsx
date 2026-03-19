"use client";
import { useState } from "react";

const NAV_ITEMS = [
  { icon: "🖥", label: "상황실", id: "warroom", group: "share" },
  { icon: "📋", label: "공약", id: "pledges", group: "share" },
  { icon: "🗺", label: "지역", id: "regions", group: "share" },
  { icon: "📰", label: "이슈", id: "issues", group: "share" },
  { icon: "📱", label: "소셜", id: "social", group: "share" },
  { icon: "📈", label: "여론", id: "polling", group: "share" },
  { icon: "📊", label: "전략", id: "strategy", group: "admin" },
  { icon: "🎤", label: "메세지", id: "debate", group: "admin" },
  { icon: "📅", label: "일정", id: "schedule", group: "admin" },
];

export function Sidebar() {
  const [active, setActive] = useState("warroom");

  return (
    <nav className="w-16 bg-[#0d1117] border-r border-border flex flex-col py-2 shrink-0">
      <div className="text-[7px] text-gray-600 text-center py-1 uppercase tracking-wider">공유</div>
      {NAV_ITEMS.filter(n => n.group === "share").map(item => (
        <button
          key={item.id}
          onClick={() => setActive(item.id)}
          className={`py-3 text-center transition-all border-l-[3px] ${
            active === item.id
              ? "text-blue-400 border-blue-400 bg-blue-400/10"
              : "text-gray-500 border-transparent hover:text-blue-200 hover:bg-white/5"
          }`}
        >
          <span className="text-xl block">{item.icon}</span>
          <span className="text-[9px] block">{item.label}</span>
        </button>
      ))}
      <div className="h-px bg-border mx-2 my-1" />
      <div className="text-[7px] text-gray-600 text-center py-1 uppercase tracking-wider">어드민</div>
      {NAV_ITEMS.filter(n => n.group === "admin").map(item => (
        <button
          key={item.id}
          onClick={() => setActive(item.id)}
          className={`py-3 text-center transition-all border-l-[3px] ${
            active === item.id
              ? "text-blue-300 border-gray-500 bg-white/5"
              : "text-gray-600 border-transparent hover:text-gray-400 hover:bg-white/[0.03]"
          }`}
        >
          <span className="text-xl block">{item.icon}</span>
          <span className="text-[9px] block">{item.label}</span>
        </button>
      ))}
    </nav>
  );
}
