"use client";
import { useAppStore } from "@/lib/store";

const GROUPS = [
  {
    label: "COCKPIT",
    items: [
      { icon: "⚔", label: "상황실", id: "warroom" },
    ],
  },
  {
    label: "STRATEGY",
    items: [
      { icon: "🎯", label: "전략실행", id: "strategy" },
      { icon: "📄", label: "리포트", id: "report" },
      { icon: "📢", label: "메시지", id: "debate" },
      { icon: "🗺", label: "지역작전", id: "regions" },
    ],
  },
  {
    label: "INTEL",
    items: [
      { icon: "📊", label: "여론추세", id: "polling" },
      { icon: "📰", label: "여론분석", id: "issues" },
      { icon: "👤", label: "상대분석", id: "opponent" },
    ],
  },
  {
    label: "SYSTEM",
    items: [
      { icon: "📈", label: "인덱스", id: "indices" },
      { icon: "🔬", label: "리서치", id: "research" },
      { icon: "📚", label: "학습", id: "learning" },
      { icon: "🔑", label: "키워드", id: "keywords" },
      { icon: "⚙", label: "시스템", id: "system" },
    ],
  },
];

export function Sidebar() {
  const active = useAppStore((s) => s.activePage);
  const setActive = useAppStore((s) => s.setActivePage);

  return (
    <nav className="w-[58px] bg-navy-900 border-r border-border-dim flex flex-col shrink-0 select-none overflow-y-auto">
      {GROUPS.map((g, gi) => (
        <div key={g.label}>
          {gi > 0 && <div className="h-px bg-border-dim mx-2 my-0.5" />}
          <div className="text-[7px] text-blue-400/40 text-center py-1.5 font-bold tracking-[0.15em]">{g.label}</div>
          {g.items.map((item) => {
            const isActive = active === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActive(item.id)}
                className={`w-full py-2.5 text-center transition-all border-l-2 ${
                  isActive
                    ? "text-blue-400 border-blue-500 bg-blue-500/10"
                    : "text-gray-400 border-transparent hover:text-gray-400 hover:bg-white/[0.02]"
                }`}
              >
                <span className="text-base block leading-none">{item.icon}</span>
                <span className="text-[8px] block mt-0.5 leading-none">{item.label}</span>
              </button>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
