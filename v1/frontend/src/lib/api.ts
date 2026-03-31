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
export const getReactionRadar = () => f<any>("/api/enrichment/reaction-radar");
export const getCollectionStatus = () => f<any>("/api/indices/collection-status");
export const getRegionalReaction = () => f<any>("/api/indices/regional");
export const getDailyBriefing = () => f<any>("/api/strategy/daily-briefing");
export const generateDailyBriefing = async (): Promise<any> => {
  // 생성 트리거
  const triggerRes = await fetch(`${API_BASE}/api/strategy/daily-briefing/generate`, { method: "POST" });
  const triggerData = await triggerRes.json();
  // 1일 1회 제한: 이미 생성된 경우 기존 리포트 반환
  if (triggerData.status === "already_generated") {
    alert(triggerData.message);
    return f<any>("/api/strategy/daily-briefing");
  }
  // 폴링: 완료될 때까지 대기
  const maxRetries = 40;  // 최대 40회 × 3초 = 120초
  for (let i = 0; i < maxRetries; i++) {
    await new Promise(r => setTimeout(r, 3000));
    const data = await f<any>("/api/strategy/daily-briefing");
    if (data.status !== "generating") return data;
  }
  return { error: "생성 시간 초과 (2분)" };
};
export const getWeeklyBriefing = (force = false) => f<any>(`/api/strategy/weekly-briefing${force ? "?force=true" : ""}`);
export const getTrainingData = () => f<any>("/api/strategy/training-data");
export const getDailyReports = () => f<any>("/api/strategy/daily-reports");
export const getFeedback = (date: string) => f<any>(`/api/strategy/feedback/${date}`);
export const addFeedback = async (date: string, category: string, text: string): Promise<any> => {
  const res = await fetch(`${API_BASE}/api/strategy/feedback?date=${date}&category=${encodeURIComponent(category)}&text=${encodeURIComponent(text)}`, { method: "POST" });
  return res.json();
};
