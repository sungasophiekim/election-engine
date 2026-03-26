"use client";
import { useState, useEffect, useCallback } from "react";

interface Keyword {
  keyword: string;
  category: string;
  priority: string;
  type: "candidate" | "issue";
}

interface CandidateBuzz {
  mention_count: number;
  velocity: number;
  negative_ratio: number;
  media_tier: number;
  candidate_linked: boolean;
  portal_trending: boolean;
  tv_reported: boolean;
  ai_sentiment?: {
    net_sentiment: number;
    sentiment_6way: Record<string, number>;
    dominant_tone: string;
    summary: string;
    strength_topics: { topic: string; count: number; sample: string }[];
    weakness_topics: { topic: string; count: number; sample: string }[];
    about_us: { positive: number; negative: number };
    about_opponent: { positive: number; negative: number };
    positive_ratio: number;
    negative_ratio: number;
  } | null;
}

const CATEGORIES = [
  "후보", "선거", "정당", "공약", "이슈", "산업", "생활",
  "세대", "지역", "상대감시", "미디어", "동원", "기타",
];

const PRIORITY_COLORS: Record<string, string> = {
  high: "bg-rose-500/20 text-rose-300 border-rose-500/30",
  medium: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  low: "bg-gray-500/20 text-gray-400 border-gray-500/30",
};

const CATEGORY_COLORS: Record<string, string> = {
  후보: "bg-blue-500/20 text-blue-300",
  선거: "bg-purple-500/20 text-purple-300",
  정당: "bg-indigo-500/20 text-indigo-300",
  공약: "bg-cyan-500/20 text-cyan-300",
  이슈: "bg-rose-500/20 text-rose-300",
  산업: "bg-emerald-500/20 text-emerald-300",
  생활: "bg-amber-500/20 text-amber-300",
  세대: "bg-pink-500/20 text-pink-300",
  지역: "bg-teal-500/20 text-teal-300",
  상대감시: "bg-red-500/20 text-red-300",
  미디어: "bg-sky-500/20 text-sky-300",
  동원: "bg-orange-500/20 text-orange-300",
  기타: "bg-gray-500/20 text-gray-400",
};

export function KeywordMonitorPage() {
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [updatedAt, setUpdatedAt] = useState("");
  const [loading, setLoading] = useState(true);
  const [newKeyword, setNewKeyword] = useState("");
  const [newCategory, setNewCategory] = useState("이슈");
  const [newPriority, setNewPriority] = useState("medium");
  const [newType, setNewType] = useState<"candidate" | "issue">("issue");
  const [filterCategory, setFilterCategory] = useState("전체");
  const [filterPriority, setFilterPriority] = useState("전체");
  const [filterType, setFilterType] = useState("전체");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [buzzData, setBuzzData] = useState<Record<string, CandidateBuzz>>({});

  const fetchKeywords = useCallback(async () => {
    try {
      const res = await fetch("/api/v2/keywords");
      const data = await res.json();
      setKeywords(data.keywords || []);
      setUpdatedAt(data.updated_at || "");
    } catch {
      setError("키워드 로드 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchBuzz = useCallback(async () => {
    try {
      const res = await fetch("/api/v2/candidate-buzz");
      const data = await res.json();
      setBuzzData(data.buzz || {});
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchKeywords(); fetchBuzz(); }, [fetchKeywords, fetchBuzz]);

  // 카테고리 변경 시 type 자동 설정
  const handleCategoryChange = (cat: string) => {
    setNewCategory(cat);
    if (cat === "후보" || cat === "정당") {
      setNewType("candidate");
    } else {
      setNewType("issue");
    }
  };

  const addKeyword = async () => {
    if (!newKeyword.trim()) return;
    setError(""); setSuccess("");
    try {
      const res = await fetch("/api/v2/keywords", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          keyword: newKeyword.trim(),
          category: newCategory,
          priority: newPriority,
          type: newType,
        }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "추가 실패"); return; }
      setSuccess(`"${newKeyword.trim()}" 추가 완료 (총 ${data.total}개)`);
      setNewKeyword("");
      fetchKeywords();
    } catch { setError("네트워크 오류"); }
  };

  const deleteKeyword = async (kw: string) => {
    if (!confirm(`"${kw}" 키워드를 삭제하시겠습니까?`)) return;
    setError(""); setSuccess("");
    try {
      const res = await fetch("/api/v2/keywords", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: kw }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "삭제 실패"); return; }
      setSuccess(`"${kw}" 삭제 완료 (총 ${data.total}개)`);
      fetchKeywords();
    } catch { setError("네트워크 오류"); }
  };

  // Filter
  const filtered = keywords.filter((k) => {
    if (filterCategory !== "전체" && k.category !== filterCategory) return false;
    if (filterPriority !== "전체" && k.priority !== filterPriority) return false;
    if (filterType !== "전체" && k.type !== filterType) return false;
    return true;
  });

  // Stats
  const catStats: Record<string, number> = {};
  keywords.forEach((k) => { catStats[k.category] = (catStats[k.category] || 0) + 1; });

  const typeStats = { candidate: 0, issue: 0 };
  keywords.forEach((k) => { typeStats[k.type] = (typeStats[k.type] || 0) + 1; });

  const priStats = { high: 0, medium: 0, low: 0 };
  keywords.forEach((k) => { priStats[k.priority as keyof typeof priStats] = (priStats[k.priority as keyof typeof priStats] || 0) + 1; });

  if (loading) return <div className="text-gray-400 p-4">로딩 중...</div>;

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-gray-100">키워드 모니터</h2>
          <p className="text-xs text-gray-500">총 {keywords.length}개 키워드 | 마지막 업데이트: {updatedAt}</p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="px-2 py-1 rounded bg-blue-500/10 text-blue-300">후보추적 {typeStats.candidate}</span>
          <span className="px-2 py-1 rounded bg-cyan-500/10 text-cyan-300">이슈추적 {typeStats.issue}</span>
          <span className="mx-1 text-gray-600">|</span>
          <span className="px-2 py-1 rounded bg-rose-500/10 text-rose-300">HIGH {priStats.high}</span>
          <span className="px-2 py-1 rounded bg-amber-500/10 text-amber-300">MED {priStats.medium}</span>
          <span className="px-2 py-1 rounded bg-gray-500/10 text-gray-400">LOW {priStats.low}</span>
        </div>
      </div>

      {/* Type Explanation */}
      <div className="bg-navy-800 border border-border-dim rounded-lg px-3 py-2 text-[11px] text-gray-400">
        <span className="text-blue-400 font-bold">후보추적</span> = 후보 인지도/버즈 모니터링 (이슈 스코어링 제외, CRISIS 판정 안됨) &nbsp;|&nbsp;
        <span className="text-cyan-400 font-bold">이슈추적</span> = 이슈 레이더 대상 (스코어링 → CRISIS/ALERT 판정)
      </div>

      {/* Messages */}
      {error && <div className="bg-red-500/10 border border-red-500/30 text-red-300 px-3 py-2 rounded text-sm">{error}</div>}
      {success && <div className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 px-3 py-2 rounded text-sm">{success}</div>}

      {/* Candidate Buzz Summary */}
      {Object.keys(buzzData).length > 0 && (
        <div className="bg-navy-800 border border-blue-500/20 rounded-lg p-3">
          <div className="text-xs text-blue-300 font-bold mb-2">후보 버즈 현황 <span className="text-gray-500 font-normal">(AI 6분류 감성분석 포함 · 6시간 캐시)</span></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {Object.entries(buzzData).map(([kw, buzz]) => {
              const ai = buzz.ai_sentiment;
              const s6 = ai?.sentiment_6way || {};
              const s6Total = Object.values(s6).reduce((a: number, b: number) => a + (b as number), 0) as number;
              return (
                <div key={kw} className="bg-navy-900 rounded px-3 py-2">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs text-gray-200 font-medium">{kw}</span>
                    <div className="flex items-center gap-2 text-[10px]">
                      <span className="text-white font-bold">{buzz.mention_count}건</span>
                      <span className={`${buzz.velocity > 2 ? "text-emerald-400" : "text-gray-500"}`}>
                        v{buzz.velocity.toFixed(1)}
                      </span>
                      {buzz.tv_reported && <span className="text-amber-400">TV</span>}
                    </div>
                  </div>

                  {/* AI 6분류 바 */}
                  {ai && s6Total > 0 && (
                    <div className="mb-1.5">
                      <div className="flex h-2 rounded overflow-hidden">
                        {(s6["지지"] || 0) > 0 && <div className="bg-blue-500" style={{ width: `${((s6["지지"] || 0) / s6Total) * 100}%` }} title={`지지 ${s6["지지"]}`} />}
                        {(s6["스윙"] || 0) > 0 && <div className="bg-amber-400" style={{ width: `${((s6["스윙"] || 0) / s6Total) * 100}%` }} title={`스윙 ${s6["스윙"]}`} />}
                        {(s6["부정"] || 0) > 0 && <div className="bg-rose-500" style={{ width: `${((s6["부정"] || 0) / s6Total) * 100}%` }} title={`부정 ${s6["부정"]}`} />}
                        {(s6["정체성"] || 0) > 0 && <div className="bg-red-700" style={{ width: `${((s6["정체성"] || 0) / s6Total) * 100}%` }} title={`정체성 ${s6["정체성"]}`} />}
                        {(s6["정책"] || 0) > 0 && <div className="bg-orange-500" style={{ width: `${((s6["정책"] || 0) / s6Total) * 100}%` }} title={`정책 ${s6["정책"]}`} />}
                        {(s6["중립"] || 0) > 0 && <div className="bg-gray-600" style={{ width: `${((s6["중립"] || 0) / s6Total) * 100}%` }} title={`중립 ${s6["중립"]}`} />}
                      </div>
                      <div className="flex gap-2 mt-1 text-[9px] text-gray-500 flex-wrap">
                        {(s6["지지"] || 0) > 0 && <span><span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-500 mr-0.5" />지지 {s6["지지"]}</span>}
                        {(s6["스윙"] || 0) > 0 && <span><span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-400 mr-0.5" />스윙 {s6["스윙"]}</span>}
                        {(s6["부정"] || 0) > 0 && <span><span className="inline-block w-1.5 h-1.5 rounded-full bg-rose-500 mr-0.5" />부정 {s6["부정"]}</span>}
                        {(s6["정체성"] || 0) > 0 && <span><span className="inline-block w-1.5 h-1.5 rounded-full bg-red-700 mr-0.5" />정체성 {s6["정체성"]}</span>}
                        {(s6["정책"] || 0) > 0 && <span><span className="inline-block w-1.5 h-1.5 rounded-full bg-orange-500 mr-0.5" />정책 {s6["정책"]}</span>}
                        {(s6["중립"] || 0) > 0 && <span><span className="inline-block w-1.5 h-1.5 rounded-full bg-gray-600 mr-0.5" />중립 {s6["중립"]}</span>}
                      </div>
                    </div>
                  )}

                  {/* 감성 요약 + 강점/약점 */}
                  {ai && (
                    <div className="text-[10px] space-y-0.5">
                      {ai.dominant_tone && (
                        <div className="text-gray-400">
                          톤: <span className="text-gray-200 font-medium">{ai.dominant_tone}</span>
                          {ai.net_sentiment !== 0 && (
                            <span className={`ml-2 ${ai.net_sentiment > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                              감성 {ai.net_sentiment > 0 ? "+" : ""}{(ai.net_sentiment * 100).toFixed(0)}
                            </span>
                          )}
                        </div>
                      )}
                      {ai.summary && <div className="text-gray-400 truncate" title={ai.summary}>{ai.summary}</div>}
                      <div className="flex gap-3">
                        {ai.strength_topics?.slice(0, 2).map((t, i) => (
                          <span key={i} className="text-emerald-400">+{t.topic}</span>
                        ))}
                        {ai.weakness_topics?.slice(0, 2).map((t, i) => (
                          <span key={i} className="text-rose-400">-{t.topic}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* AI 미적용 시 기본 정보 */}
                  {!ai && (
                    <div className="text-[10px] text-gray-500">
                      부정 {(buzz.negative_ratio * 100).toFixed(0)}% (기본 사전분석)
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Add Form */}
      <div className="bg-navy-800 border border-border-dim rounded-lg p-3">
        <div className="text-xs text-blue-300 font-bold mb-2">키워드 추가</div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addKeyword()}
            placeholder="새 키워드 입력..."
            className="flex-1 bg-navy-900 border border-border-dim rounded px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
          />
          <select
            value={newCategory}
            onChange={(e) => handleCategoryChange(e.target.value)}
            className="bg-navy-900 border border-border-dim rounded px-2 py-1.5 text-sm text-gray-300"
          >
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select
            value={newType}
            onChange={(e) => setNewType(e.target.value as "candidate" | "issue")}
            className="bg-navy-900 border border-border-dim rounded px-2 py-1.5 text-sm text-gray-300"
          >
            <option value="issue">이슈추적</option>
            <option value="candidate">후보추적</option>
          </select>
          <select
            value={newPriority}
            onChange={(e) => setNewPriority(e.target.value)}
            className="bg-navy-900 border border-border-dim rounded px-2 py-1.5 text-sm text-gray-300"
          >
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <button
            onClick={addKeyword}
            className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-1.5 rounded text-sm font-medium transition-colors"
          >
            추가
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 text-xs">
        <span className="text-gray-500">필터:</span>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="bg-navy-900 border border-border-dim rounded px-2 py-1 text-gray-300 text-xs"
        >
          <option value="전체">유형 전체</option>
          <option value="candidate">후보추적 ({typeStats.candidate})</option>
          <option value="issue">이슈추적 ({typeStats.issue})</option>
        </select>
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="bg-navy-900 border border-border-dim rounded px-2 py-1 text-gray-300 text-xs"
        >
          <option value="전체">카테고리 전체</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c} ({catStats[c] || 0})</option>)}
        </select>
        <select
          value={filterPriority}
          onChange={(e) => setFilterPriority(e.target.value)}
          className="bg-navy-900 border border-border-dim rounded px-2 py-1 text-gray-300 text-xs"
        >
          <option value="전체">우선순위 전체</option>
          <option value="high">High ({priStats.high})</option>
          <option value="medium">Medium ({priStats.medium})</option>
          <option value="low">Low ({priStats.low})</option>
        </select>
        <span className="text-gray-500 ml-auto">{filtered.length}개 표시</span>
      </div>

      {/* Category Overview */}
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(catStats).sort((a, b) => b[1] - a[1]).map(([cat, count]) => (
          <button
            key={cat}
            onClick={() => setFilterCategory(filterCategory === cat ? "전체" : cat)}
            className={`px-2 py-0.5 rounded text-xs transition-colors ${
              filterCategory === cat ? "ring-1 ring-blue-400 " : ""
            }${CATEGORY_COLORS[cat] || CATEGORY_COLORS["기타"]}`}
          >
            {cat} {count}
          </button>
        ))}
      </div>

      {/* Keyword Table */}
      <div className="bg-navy-800 border border-border-dim rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-dim text-gray-500 text-xs">
              <th className="text-left px-3 py-2 font-medium">#</th>
              <th className="text-left px-3 py-2 font-medium">키워드</th>
              <th className="text-left px-3 py-2 font-medium">유형</th>
              <th className="text-left px-3 py-2 font-medium">카테고리</th>
              <th className="text-left px-3 py-2 font-medium">우선순위</th>
              <th className="text-right px-3 py-2 font-medium">삭제</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((k, i) => (
              <tr key={k.keyword} className="border-b border-border-dim/50 hover:bg-white/[0.02] transition-colors">
                <td className="px-3 py-1.5 text-gray-600 text-xs">{i + 1}</td>
                <td className="px-3 py-1.5 text-gray-200 font-medium">{k.keyword}</td>
                <td className="px-3 py-1.5">
                  <span className={`px-1.5 py-0.5 rounded text-xs ${
                    k.type === "candidate"
                      ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                      : "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                  }`}>
                    {k.type === "candidate" ? "후보추적" : "이슈추적"}
                  </span>
                </td>
                <td className="px-3 py-1.5">
                  <span className={`px-1.5 py-0.5 rounded text-xs ${CATEGORY_COLORS[k.category] || CATEGORY_COLORS["기타"]}`}>
                    {k.category}
                  </span>
                </td>
                <td className="px-3 py-1.5">
                  <span className={`px-1.5 py-0.5 rounded text-xs border ${PRIORITY_COLORS[k.priority] || PRIORITY_COLORS.medium}`}>
                    {k.priority}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-right">
                  <button
                    onClick={() => deleteKeyword(k.keyword)}
                    className="text-gray-600 hover:text-red-400 transition-colors text-xs px-1"
                    title="삭제"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="text-center py-8 text-gray-600 text-sm">해당 조건의 키워드가 없습니다</div>
        )}
      </div>
    </div>
  );
}
