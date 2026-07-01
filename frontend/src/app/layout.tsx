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
  title: "Rob's Solar — Inverter Control",
  description: "Secure monitoring and control for Sunsynk solar systems",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    title: "Rob's Solar",
    statusBarStyle: "black-translucent",
  },
};

export const viewport: Viewport = {
  themeColor: "#f59e0b",
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
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
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
