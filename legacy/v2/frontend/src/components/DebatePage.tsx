"use client";
import { useEffect, useState } from "react";

export function DebatePage() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    fetch("/api/debate-prep").then(r => r.json()).then(setData).catch(() => {});
  }, []);

  if (!data) return <div className="text-center py-8 text-gray-500">로딩...</div>;

  const questions = data.questions || [];
  const attacks = data.attack_scripts || [];
  const defenses = data.defense_scripts || [];
  const redLines = data.red_lines || [];

  return (
    <div className="space-y-4">
      {/* 오프닝 / 클로징 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-bg-card border-l-4 border-green-600 rounded-lg p-4">
          <h3 className="text-green-400 text-sm font-semibold mb-2">오프닝</h3>
          <p className="text-gray-300 text-sm whitespace-pre-wrap">{data.opening}</p>
        </div>
        <div className="bg-bg-card border-l-4 border-orange-600 rounded-lg p-4">
          <h3 className="text-orange-400 text-sm font-semibold mb-2">클로징</h3>
          <p className="text-gray-300 text-sm whitespace-pre-wrap">{data.closing}</p>
        </div>
      </div>

      {/* 예상 질문 */}
      <div className="bg-bg-card border border-border rounded-lg p-4">
        <h3 className="text-blue-400 text-sm font-semibold mb-3 pb-2 border-b border-border">❓ 예상 질문 ({questions.length})</h3>
        <div className="space-y-3">
          {questions.map((q: any, i: number) => {
            const diffColor = q.difficulty === "hard" ? "bg-red-500" : q.difficulty === "medium" ? "bg-yellow-500" : "bg-green-500";
            return (
              <div key={i} className="p-3 bg-[#0d1117] rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`w-2 h-2 rounded-full ${diffColor}`} />
                  <span className="text-gray-500 text-xs">{q.source}</span>
                  <span className="text-white font-bold text-sm">{q.topic}</span>
                </div>
                <div className="text-blue-300 text-sm mb-1"><strong>Q:</strong> {q.question}</div>
                <div className="text-gray-300 text-sm mb-1"><strong>A:</strong> {q.answer}</div>
                {q.trap && <div className="text-orange-400 text-xs">⚠ 함정: {q.trap}</div>}
                {q.pivot && <div className="text-blue-400 text-xs">→ 피벗: {q.pivot}</div>}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 공격 스크립트 */}
        <div className="bg-bg-card border border-red-900 rounded-lg p-4">
          <h3 className="text-red-400 text-sm font-semibold mb-3 pb-2 border-b border-border">⚔ 공격 스크립트</h3>
          {attacks.map((a: any, i: number) => (
            <div key={i} className="mb-3 p-2 bg-[#0d1117] rounded border-l-2 border-red-800">
              <div className="text-red-300 font-bold text-sm mb-1">{a.topic}</div>
              <div className="text-gray-300 text-sm">{a.opening}</div>
              {a.killer_question && <div className="text-red-400 text-xs mt-1">💀 {a.killer_question}</div>}
            </div>
          ))}
        </div>

        {/* 방어 스크립트 */}
        <div className="bg-bg-card border border-green-900 rounded-lg p-4">
          <h3 className="text-green-400 text-sm font-semibold mb-3 pb-2 border-b border-border">🛡 방어 스크립트</h3>
          {defenses.map((d: any, i: number) => (
            <div key={i} className="mb-3 p-2 bg-[#0d1117] rounded border-l-2 border-green-800">
              <div className="text-orange-300 font-bold text-sm mb-1">{d.attack}</div>
              <div className="text-gray-300 text-sm">{d.response}</div>
              {d.pivot && <div className="text-blue-300 text-xs mt-1">→ {d.pivot}</div>}
            </div>
          ))}
        </div>
      </div>

      {/* 레드라인 */}
      {redLines.length > 0 && (
        <div className="bg-bg-card border border-red-800 rounded-lg p-4">
          <h3 className="text-red-400 text-sm font-semibold mb-3">⛔ 레드라인 — 절대 하지 말 것</h3>
          <div className="space-y-1">
            {redLines.map((r: string, i: number) => (
              <div key={i} className="text-red-300 text-sm">⛔ {r}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
