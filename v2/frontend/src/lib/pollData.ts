// 여론조사 데이터 — 모든 페이지에서 공유
// 새 여론조사 추가 시 여기만 수정하면 전체 반영

export const POLL_DATA = [
  { label: "6기 지선", date: "2014", kim: 36.0, park: 59.4, type: "election" as const },
  { label: "7기 지선", date: "2018", kim: 52.8, park: 43.5, type: "election" as const },
  { label: "8기 지선", date: "2022", kim: 30.0, park: 65.7, type: "election" as const },
  { label: "MBC경남(KSOI)", date: "25.09", kim: 39.5, park: 44.0, type: "poll" as const },
  { label: "경남신문(한국갤럽)", date: "25.10", kim: 31.0, park: 39.0, type: "poll" as const },
  { label: "MBC경남(KSOI)", date: "25.11", kim: 36.0, park: 35.5, type: "poll" as const },
  { label: "경남매일(모노커뮤)", date: "25.12", kim: 35.0, park: 45.0, type: "poll" as const },
  { label: "경남신문(한국갤럽)", date: "25.12", kim: 43.0, park: 45.0, type: "poll" as const },
  { label: "부산일보(KSOI)", date: "26.01", kim: 38.5, park: 38.5, type: "poll" as const },
  { label: "경남일보(리얼미터)", date: "26.01", kim: 41.0, park: 42.0, type: "poll" as const },
  { label: "KBS(케이스텟)", date: "26.02", kim: 29.5, park: 29.5, type: "poll" as const },
  { label: "KNN(서던포스트)", date: "26.03", kim: 36.0, park: 34.0, type: "poll" as const },
  { label: "경남일보(리얼미터)", date: "26.03", kim: 38.1, park: 38.3, type: "poll" as const },
  { label: "세계일보(한국갤럽)", date: "26.04", kim: 44.0, park: 40.0, type: "poll" as const },
  { label: "KBS창원(한국리서치)", date: "26.04", kim: 37.0, park: 27.0, type: "poll" as const },
  { label: "MBC경남(KSOI)", date: "26.04", kim: 46.9, park: 35.7, type: "poll" as const },
];

export type PollEntry = typeof POLL_DATA[0];

// 자동 감지 여론조사를 POLL_DATA에 병합
export function mergeAutoPolls(autoPolls: any[]): PollEntry[] {
  const autoEntries: PollEntry[] = autoPolls
    .filter((p: any) => p.kim > 0 && p.park > 0)
    .map((p: any) => ({
      label: p.org || "자동감지",
      date: p.date?.slice(2, 7) || "auto",
      kim: p.kim,
      park: p.park,
      type: "poll" as const,
    }))
    .filter((p) => !POLL_DATA.some(d => d.kim === p.kim && d.park === p.park));

  return [...POLL_DATA, ...autoEntries];
}

// 최신 여론조사 (자동 감지 포함)
export function getLatestPoll(autoPolls: any[] = []): PollEntry {
  const merged = mergeAutoPolls(autoPolls);
  return merged[merged.length - 1];
}
