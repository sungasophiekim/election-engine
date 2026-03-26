/**ISO 타임스탬프 → "마지막업데이트: ~분 전" 형식*/
export function fmtTs(ts: string | undefined): string {
  if (!ts) return "—";
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return ts.slice(0, 16).replace("T", " ");
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);

    if (diffMin < 1) return "마지막업데이트: 방금 전";
    if (diffMin < 60) return `마지막업데이트: ${diffMin}분 전`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `마지막업데이트: ${diffHr}시간 전`;
    const diffDay = Math.floor(diffHr / 24);
    return `마지막업데이트: ${diffDay}일 전`;
  } catch {
    return ts.slice(0, 16);
  }
}

/**ISO 타임스탬프 → "마지막업데이트: YY.MM.DD" 고정 날짜 형식 (여론조사 기반 업데이트용)*/
export function fmtDate(ts: string | undefined): string {
  if (!ts) return "—";
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return ts.slice(0, 10);
    const yy = String(d.getFullYear()).slice(2);
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `마지막업데이트: ${yy}.${mm}.${dd}`;
  } catch {
    return ts.slice(0, 10);
  }
}
