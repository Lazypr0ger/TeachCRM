import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tutor CRM",
  description: "Локальная CRM преподавателя и учеников",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ru" data-theme="dark">
      <body>{children}</body>
    </html>
  );
}

