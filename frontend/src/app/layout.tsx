import type { Metadata } from "next";
import Script from "next/script";
import type { ReactNode } from "react";
import { AppChrome } from "@/components/layout/app-chrome";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tutor CRM",
  description: "Локальная CRM преподавателя и учеников",
  manifest: "/manifest.webmanifest",
};

const themeScript = `(function(){try{var t=localStorage.getItem('tutorcrm-theme')||'system';document.documentElement.dataset.theme=t}catch(e){}})()`;

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ru" data-theme="system" suppressHydrationWarning>
      <body><Script id="theme-initializer" strategy="beforeInteractive">{themeScript}</Script><AppChrome /><div id="main-content" tabIndex={-1}>{children}</div></body>
    </html>
  );
}

