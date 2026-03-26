let isAuthenticated = false;

async function ensureAuth() {
  if (isAuthenticated) return;
  // Try a test call — if it fails with 401/403, login automatically
  const test = await fetch("/api/executive-summary", { credentials: "include" });
  if (test.ok) { isAuthenticated = true; return; }
  // Auto-login
  const resp = await fetch("/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: "password=election2026",
    credentials: "include",
    redirect: "manual",
  });
  // The login endpoint returns a redirect with set-cookie
  isAuthenticated = true;
}

async function f<T>(path: string, opts?: RequestInit): Promise<T> {
  await ensureAuth();
  const res = await fetch(path, { ...opts, credentials: "include" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export const getExecutiveSummary = () => f<any>("/api/executive-summary");
export const getAlerts = () => f<any>("/api/alerts");
export const getCalendar = () => f<any>("/api/calendar");
export const getIssueResponses = () => f<any>("/api/issue-responses");
export const getKeywordAnalysis = (kw: string) => f<any>(`/api/keyword-analysis/${encodeURIComponent(kw)}`);
export const getPollingHistory = () => f<any>("/api/polling-history");
export const getSocialBuzz = () => f<any>("/api/social-buzz");
export const getCommunity = () => f<any>("/api/community");
export const runStrategy = () => f<any>("/api/run-strategy", { method: "POST" });
export const getPledges = () => f<any>("/api/pledges");
export const aiAnalyze = (kw: string) => f<any>("/api/ai-agent/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ keyword: kw }) });
export const getAiHistory = () => f<any>("/api/ai-agent/history");
export const getScores = () => f<any>("/api/scores");
export const syncNesdcPolls = () => f<any>("/api/polls/nesdc-sync", { method: "POST" });
export const getDailyBriefing = () => f<any>("/api/daily-briefing");

export const getSnsBattle = () => f<any>("/api/sns-battle");
export const getOrgScan = () => f<any>("/api/v2/org-scan");
export const getRegions = () => f<any>("/api/regions");
export const getPreTriggers = () => f<any>("/api/v2/pretrigger-scan");
export const getKeywordCompare = () => f<any>("/api/v2/keyword-compare");

// ─── V2 Engine Enrichment API ─────────────────────────────────
export const getV2Enrichment = () => f<any>("/api/v2/enrichment");
export const getV2Forecast = () => f<any>("/api/v2/forecast");
export const getV2LagHistory = () => f<any>("/api/v2/lag-history");
// index-trend는 인증 불필요 — ensureAuth 우회하여 직접 호출
export const getIndexTrend = async (days = 30) => {
  const res = await fetch(`/api/v2/index-trend?days=${days}`);
  if (!res.ok) return { trend: [] };
  return res.json();
};
export const getIndexDaily = (dt = "") => f<any>(`/api/v2/index-daily${dt ? `?date=${dt}` : ""}`);
export const getNewsComments = (keyword: string) => f<any>(`/api/v2/news-comments?keyword=${encodeURIComponent(keyword)}&max_articles=3`);
export const getRegionalMedia = (keyword: string) => f<any>(`/api/v2/regional-media?keyword=${encodeURIComponent(keyword)}`);
export const getAIBriefing = () => f<any>("/api/v2/ai-briefing");
export const getCandidateBuzz = async () => {
  const res = await fetch("/api/v2/candidate-buzz"); if (!res.ok) return { buzz: {} }; return res.json();
};
export const getApiStatus = async () => {
  const res = await fetch("/api/v2/api-status");
  if (!res.ok) return { apis: [] };
  return res.json();
};
export const getAutoPolls = async () => {
  const res = await fetch("/api/v2/auto-polls");
  if (!res.ok) return { polls: [] };
  return res.json();
};
export const getSystemHealth = async () => {
  const res = await fetch("/api/v2/system-health");
  if (!res.ok) return null;
  return res.json();
};

// ─── Strategic Report & News Clusters API ────────────────────
export const getStrategicReport = () => f<any>("/api/v2/strategic-report");
export const getNewsClusters = () => f<any>("/api/v2/news-clusters");

// ─── V3 Strategy OS API ───────────────────────────────────────
export const getV3StatusBar = () => f<any>("/api/v3/dashboard/status-bar");
export const getV3CommandBox = () => f<any>("/api/v3/dashboard/command-box");
export const getV3Signals = (type?: string) => f<any>(`/api/v3/signals${type ? `?signal_type=${type}` : ""}`);
export const getV3Proposals = (status?: string) => f<any>(`/api/v3/proposals${status ? `?status=${status}` : ""}`);
export const approveV3Proposal = (id: string, body?: any) =>
  f<any>(`/api/v3/proposals/${id}/approve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
export const rejectV3Proposal = (id: string, reason: string) =>
  f<any>(`/api/v3/proposals/${id}/reject`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rejection_reason: reason }) });
export const editV3Proposal = (id: string, humanVersion: string, owner?: string) =>
  f<any>(`/api/v3/proposals/${id}/edit`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ human_version: humanVersion, assigned_owner: owner }) });
export const getV3Overrides = () => f<any>("/api/v3/overrides");
export const getV3Narratives = () => f<any>("/api/v3/narratives");
export const getV3BlockedTerms = () => f<any>("/api/v3/blocked-terms");
export const getV3Memory = () => f<any>("/api/v3/memory");
export const getV3DecisionPatterns = () => f<any>("/api/v3/decisions/patterns");

// ─── V5 Learning Loop API ────────────────────────────────────
export const getLearningPending = () => f<any>("/api/v3/learning/decisions/pending");
export const getLearningDecisionsByType = (dtype: string) => f<any>(`/api/v3/learning/decisions/by-type/${encodeURIComponent(dtype)}`);
export const getLearningAwaiting = () => f<any>("/api/v3/learning/outcomes/awaiting");
export const getLearningAccuracy = () => f<any>("/api/v3/learning/accuracy");
export const getLearningOverrideStats = () => f<any>("/api/v3/learning/override-stats");
export const getLearningSummary = () => f<any>("/api/v3/learning/summary");
export const postLearningOverride = (id: string, value: string, reason?: string) =>
  f<any>(`/api/v3/learning/decisions/${id}/override`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ new_value: value, reason: reason || "" }) });
export const postLearningExecuted = (id: string) =>
  f<any>(`/api/v3/learning/decisions/${id}/executed`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
export const postLearningManualOutcome = (id: string, grade: string, notes?: string) =>
  f<any>(`/api/v3/learning/outcomes/${id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ outcome_grade: grade, evaluator_note: notes || "" }) });
export const postLearningAutoEvaluate = () =>
  f<any>("/api/v3/learning/outcomes/auto-evaluate", { method: "POST" });
