"use client";
import { useEffect, useState } from "react";
import { getPledges } from "@/lib/api";
import { useAppStore } from "@/lib/store";

const PLEDGE_ICONS = ["🏗", "🌉", "💰", "⚓", "👩‍🎓"];
const PLEDGE_COLORS = ["border-blue-500", "border-green-500", "border-orange-500", "border-red-500", "border-purple-500"];

export function PledgesPage() {
  const [data, setData] = useState<any>(null);
  const candidate = useAppStore((s) => s.candidate) || "김경수";

  useEffect(() => {
    getPledges().then(setData).catch(() => {});
  }, []);

  if (!data) return <div className="text-center py-8 text-gray-500">로딩...</div>;

  const ours = data.our_pledges || [];
  const opponents = data.opponent_pledges || {};

  return (
    <div className="space-y-4">
      <h2 className="text-blue-400 font-bold text-lg">{candidate} 핵심 공약</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {ours.map((p: any, i: number) => (
          <div key={i} className={`bg-bg-card border-l-4 ${PLEDGE_COLORS[i % 5]} rounded-lg p-4`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-2xl">{PLEDGE_ICONS[i % 5]}</span>
              <h3 className="text-white font-bold">{p.name}</h3>
            </div>
            {p.numbers && <div className="text-blue-300 text-sm font-bold mb-1">{p.numbers}</div>}
            <p className="text-gray-400 text-sm">{p.description}</p>
            {p.deadline && <div className="mt-2 text-xs bg-blue-900/30 text-blue-300 px-2 py-1 rounded inline-block">{p.deadline}</div>}
          </div>
        ))}
      </div>

      {Object.entries(opponents).map(([name, info]: [string, any]) => (
        <div key={name} className="mt-6">
          <h2 className="text-red-400 font-bold text-lg mb-3">상대 공약 — {name} ({info.party})</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {(info.pledges || []).map((p: any, i: number) => (
              <div key={i} className="bg-bg-card border-l-4 border-red-800 rounded-lg p-4">
                <h3 className="text-red-300 font-bold mb-1">{p.name}</h3>
                {p.numbers && <div className="text-red-400 text-sm font-bold mb-1">{p.numbers}</div>}
                <p className="text-gray-400 text-sm">{p.description}</p>
                {p.weakness && <div className="mt-2 text-xs text-orange-400">⚠ {p.weakness}</div>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
