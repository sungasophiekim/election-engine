const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const f = async <T>(path: string): Promise<T> => {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
};

export const getPolls = () => f<any>("/api/polls");
export const getPollLatest = () => f<any>("/api/polls/latest");
export const getPrediction = () => f<any>("/api/prediction");
export const getIndicesCurrent = () => f<any>("/api/indices/current");
export const getIndicesHistory = () => f<any>("/api/indices/history");
export const getNewsClusters = () => f<any>("/api/enrichment/news-clusters");
export const getIssueRadar = () => f<any>("/api/enrichment/issue-radar");
export const getReactionRadar = () => f<any>("/api/enrichment/reaction-radar");
export const getDailyBriefing = (force = false) => f<any>(`/api/strategy/daily-briefing${force ? "?force=true" : ""}`);
export const getWeeklyBriefing = (force = false) => f<any>(`/api/strategy/weekly-briefing${force ? "?force=true" : ""}`);
