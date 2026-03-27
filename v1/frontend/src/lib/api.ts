const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const f = async <T>(path: string, timeout = 180000): Promise<T> => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(`${API_BASE}${path}`, { signal: controller.signal });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return res.json();
  } finally {
    clearTimeout(timer);
  }
};

export const getPolls = () => f<any>("/api/polls");
export const getPollLatest = () => f<any>("/api/polls/latest");
export const getPrediction = () => f<any>("/api/prediction");
export const getIndicesCurrent = () => f<any>("/api/indices/current");
export const getIndicesHistory = () => f<any>("/api/indices/history");
export const getNewsClusters = () => f<any>("/api/enrichment/news-clusters");
export const getIssueRadar = () => f<any>("/api/enrichment/issue-radar");
export const getReactionRadar = () => f<any>("/api/enrichment/reaction-radar");
export const getDailyBriefing = async (force = false): Promise<any> => {
  const maxRetries = 30;  // 최대 30회 × 3초 = 90초
  for (let i = 0; i < maxRetries; i++) {
    const data = await f<any>(`/api/strategy/daily-briefing${force ? "?force=true" : ""}`);
    if (data.status !== "generating") return data;
    await new Promise(r => setTimeout(r, 3000));  // 3초 대기 후 재시도
  }
  return { error: "생성 시간 초과" };
};
export const getWeeklyBriefing = (force = false) => f<any>(`/api/strategy/weekly-briefing${force ? "?force=true" : ""}`);
export const getTrainingData = () => f<any>("/api/strategy/training-data");
export const getDailyReports = () => f<any>("/api/strategy/daily-reports");
