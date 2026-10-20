"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

type Theme = "system" | "light" | "dark";

const studentLinks = [
  ["Главная", "/student"],
  ["Расписание", "/student/schedule"],
  ["Занятия", "/student/lessons"],
  ["Финансы", "/student/billing"],
  ["Ещё", "/student/profile"],
];

const teacherLinks = [
  ["Главная", "/teacher"],
  ["Расписание", "/teacher/schedule"],
  ["Ученики", "/teacher/students"],
  ["Финансы", "/teacher/finances"],
  ["Ещё", "/teacher/settings"],
];

export function AppChrome() {
  const pathname = usePathname();
  const [theme, setTheme] = useState<Theme>("system");

  useEffect(() => {
    const stored = localStorage.getItem("tutorcrm-theme");
    if (stored === "light" || stored === "dark" || stored === "system") setTheme(stored);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("tutorcrm-theme", theme);
  }, [theme]);

  useEffect(() => {
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");
  }, []);

  const links = pathname.startsWith("/student")
    ? studentLinks
    : pathname.startsWith("/teacher")
      ? teacherLinks
      : null;

  return <>
    <label className="theme-picker"><span>Тема</span><select value={theme} onChange={(event) => setTheme(event.target.value as Theme)}><option value="system">Системная</option><option value="light">Светлая</option><option value="dark">Тёмная</option></select></label>
    {links ? <nav className="mobile-navigation" aria-label="Основная навигация">{links.map(([label, href]) => <Link className={pathname === href ? "active" : ""} href={href} key={href}>{label}</Link>)}</nav> : null}
  </>;
}
