"use client";
export function WarRoom() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        {/* 여론조사 추이 */}
        <div className="bg-bg-card border border-border rounded-lg p-4 row-span-2">
          <h3 className="text-blue-400 text-sm font-semibold mb-3 pb-2 border-b border-border">
            📈 여론조사 추이
          </h3>
          <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
            차트 로딩 중...
          </div>
        </div>

        {/* 승률 */}
        <div className="bg-bg-card border border-border rounded-lg p-4 text-center">
          <h3 className="text-blue-400 text-sm font-semibold mb-2">승률</h3>
          <div className="text-4xl font-bold text-red-400">46.9%</div>
          <div className="text-sm text-gray-500 mt-1">격차 -0.2%p</div>
        </div>

        {/* D-Day + 일정 */}
        <div className="bg-bg-card border border-border rounded-lg p-4">
          <div className="text-center text-3xl font-bold text-blue-400 mb-2">D-76</div>
          <div className="text-xs text-gray-500 space-y-1">
            <div className="text-gray-600 line-through">✓ 02-03 예비후보 등록</div>
            <div className="text-gray-600 line-through">✓ 03-17 김경수 등록</div>
            <div className="text-blue-300">○ 05-04 후보 등록</div>
            <div className="text-blue-300">○ 05-20 TV 토론</div>
            <div className="text-orange-400">○ 06-03 투표일</div>
          </div>
        </div>
      </div>

      {/* 소셜 + 이슈 */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-bg-card border border-border rounded-lg p-4">
          <h3 className="text-blue-400 text-sm font-semibold mb-3 pb-2 border-b border-border">
            📱 소셜 통계
          </h3>
          <div className="text-sm text-gray-500">로딩 중...</div>
        </div>
        <div className="bg-bg-card border border-border rounded-lg p-4">
          <h3 className="text-blue-400 text-sm font-semibold mb-3 pb-2 border-b border-border">
            📰 이슈 현황
          </h3>
          <div className="text-sm text-gray-500">로딩 중...</div>
        </div>
      </div>

      {/* 핵심 메시지 */}
      <div className="bg-bg-card border border-accent-blue rounded-lg p-4">
        <h3 className="text-blue-400 text-sm font-semibold mb-3 pb-2 border-b border-border">
          💬 오늘의 핵심 메시지
        </h3>
        <div className="text-sm text-gray-500">전략 갱신 후 표시됩니다</div>
      </div>
    </div>
  );
}
