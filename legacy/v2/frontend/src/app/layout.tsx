import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Election Engine",
  description: "AI 선거 캠프 전략 플랫폼",
  viewport: "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no",
  themeColor: "#060a11",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Election Engine" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
      </head>
      <body>{children}</body>
    </html>
  );
}
