import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { Providers } from "./providers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Rob's Finance — Personal & Business Dashboard",
  description: "Personal and business finance dashboard — balances, debts, cash flow, and tax.",
  manifest: "/manifest.json",
  applicationName: "Rob's Finance",
  icons: {
    icon: [{ url: "/favicon.png", type: "image/png" }],
    apple: [{ url: "/icons/icon-180.png", sizes: "180x180", type: "image/png" }],
  },
  appleWebApp: {
    capable: true,
    title: "Rob's Finance",
    statusBarStyle: "black-translucent",
  },
};

export const viewport: Viewport = {
  themeColor: "#10b981",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-theme="dark"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <link rel="apple-touch-icon" href="/icons/icon-180.png" sizes="180x180" />
      </head>
      <body className="min-h-full flex flex-col">
        <div className="app-bg" aria-hidden="true">
          <span className="app-bg-orb app-bg-orb-1" />
          <span className="app-bg-orb app-bg-orb-2" />
          <span className="app-bg-orb app-bg-orb-3" />
        </div>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
