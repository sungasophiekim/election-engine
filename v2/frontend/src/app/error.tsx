"use client";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div style={{ padding: 40, color: "#fff", background: "#1a1a2e", minHeight: "100vh" }}>
      <h2>오류가 발생했습니다</h2>
      <p style={{ color: "#f87171" }}>{error.message}</p>
      <button
        onClick={reset}
        style={{ marginTop: 16, padding: "8px 16px", background: "#3b82f6", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}
      >
        다시 시도
      </button>
    </div>
  );
}
