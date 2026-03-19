import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Election Engine",
  description: "AI 선거 캠프 전략 플랫폼",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
