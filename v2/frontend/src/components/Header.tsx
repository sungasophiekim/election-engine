"use client";
export function Header() {
  return (
    <header className="bg-gradient-to-r from-[#0d1117] to-[#1a237e] px-6 py-3 flex justify-between items-center border-b-2 border-border">
      <div>
        <h1 className="text-white text-lg font-bold">Election Engine</h1>
        <p className="text-blue-300 text-xs">AI 선거 캠프 전략 플랫폼</p>
      </div>
      <div className="flex items-center gap-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-green-400">46.9%</div>
          <div className="text-[10px] text-gray-500">승률</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-blue-400">D-76</div>
        </div>
        <button className="bg-accent-blue text-white px-4 py-2 rounded-md text-sm font-semibold hover:bg-blue-700 transition">
          전략 갱신
        </button>
      </div>
    </header>
  );
}
