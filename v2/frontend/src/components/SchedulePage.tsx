"use client";
import { useState } from "react";

export function SchedulePage() {
  const [mode, setMode] = useState<"daily" | "weekly">("daily");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const load = (d: string, m: "daily" | "weekly") => {
    setLoading(true);
    setData(null);
    const url = m === "daily" ? `/api/schedule/${d}` : `/api/schedule-week/${d}`;
    fetch(url).then(r => r.json()).then(setData).catch(() => {}).finally(() => setLoading(false));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex bg-bg-card rounded-lg overflow-hidden border border-border">
          <button onClick={() => setMode("daily")} className={`px-4 py-2 text-sm ${mode === "daily" ? "bg-blue-600 text-white" : "text-gray-400"}`}>일일</button>
          <button onClick={() => setMode("weekly")} className={`px-4 py-2 text-sm ${mode === "weekly" ? "bg-blue-600 text-white" : "text-gray-400"}`}>주간</button>
        </div>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
          className="bg-bg-card border border-border rounded px-3 py-2 text-sm text-white" />
        <button onClick={() => load(date, mode)}
          className="bg-accent-blue text-white px-4 py-2 rounded text-sm font-semibold hover:bg-blue-700 transition">
          조회
        </button>
      </div>

      {loading && <div className="text-center py-8 text-gray-500">로딩...</div>}

      {data && mode === "daily" && (
        <div className="bg-bg-card border border-border rounded-lg p-4">
          <h3 className="text-blue-400 text-sm font-semibold mb-3 pb-2 border-b border-border">📅 {date} 유세 일정</h3>
          {(data.events || data.schedule || []).length > 0 ? (
            <div className="space-y-2">
              {(data.events || data.schedule || []).map((ev: any, i: number) => (
                <div key={i} className="flex gap-3 p-2 bg-[#0d1117] rounded">
                  <div className="text-blue-400 font-mono text-sm w-16 shrink-0">{ev.time || ev.start_time}</div>
                  <div className="flex-1">
                    <div className="text-white font-bold text-sm">{ev.event || ev.title}</div>
                    {ev.region && <div className="text-gray-500 text-xs">📍 {ev.region}</div>}
                    {ev.talking_points && <div className="text-gray-400 text-xs mt-1">{Array.isArray(ev.talking_points) ? ev.talking_points.join(", ") : ev.talking_points}</div>}
                  </div>
                </div>
              ))}
            </div>
          ) : <div className="text-gray-600 text-sm">일정 없음</div>}
          {data.travel_time && <div className="text-gray-500 text-xs mt-3">🚗 총 이동시간: {data.travel_time}</div>}
        </div>
      )}

      {data && mode === "weekly" && (
        <div className="bg-bg-card border border-border rounded-lg p-4">
          <h3 className="text-blue-400 text-sm font-semibold mb-3 pb-2 border-b border-border">📅 주간 일정 ({date}~)</h3>
          {(data.days || data.week || []).map((day: any, i: number) => (
            <div key={i} className="mb-4">
              <div className="text-white font-bold text-sm mb-1">{day.date || day.day}</div>
              {(day.events || day.schedule || []).map((ev: any, j: number) => (
                <div key={j} className="flex gap-3 ml-4 p-1.5 text-sm">
                  <span className="text-blue-400 font-mono w-16 shrink-0">{ev.time || ev.start_time}</span>
                  <span className="text-gray-300">{ev.event || ev.title}</span>
                  {ev.region && <span className="text-gray-600">({ev.region})</span>}
                </div>
              ))}
            </div>
          ))}
          {data.region_coverage && (
            <div className="text-gray-500 text-xs mt-2 pt-2 border-t border-border">
              지역 커버리지: {typeof data.region_coverage === "object" ? Object.entries(data.region_coverage).map(([k, v]) => `${k}: ${v}회`).join(", ") : data.region_coverage}
            </div>
          )}
        </div>
      )}

      {!data && !loading && <div className="text-center py-12 text-gray-600">날짜를 선택하고 조회를 눌러주세요</div>}
    </div>
  );
}
