import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Election Engine v1 — War Room",
  description: "경남도지사 선거 전략 대시보드",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
