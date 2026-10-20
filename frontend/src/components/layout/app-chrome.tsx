"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";
import { LogoutButton } from "@/components/auth/logout-button";
import { isNavigationActive } from "@/lib/navigation";

type Theme = "system" | "light" | "dark";
type NavigationItem = { label: string; shortLabel: string; href: string };

const studentLinks: NavigationItem[] = [
  { label: "Главная", shortLabel: "Г", href: "/student" },
  { label: "Расписание", shortLabel: "Р", href: "/student/schedule" },
  { label: "Занятия", shortLabel: "З", href: "/student/lessons" },
  { label: "Финансы", shortLabel: "₽", href: "/student/billing" },
  { label: "Уведомления", shortLabel: "У", href: "/student/notifications" },
  { label: "Профиль", shortLabel: "П", href: "/student/profile" },
];

const teacherLinks: NavigationItem[] = [
  { label: "Главная", shortLabel: "Г", href: "/teacher" },
  { label: "Расписание", shortLabel: "Р", href: "/teacher/schedule" },
  { label: "Ученики", shortLabel: "У", href: "/teacher/students" },
  { label: "Финансы", shortLabel: "₽", href: "/teacher/finances" },
  { label: "Уведомления", shortLabel: "О", href: "/teacher/notifications" },
  { label: "Пробные заявки", shortLabel: "П", href: "/teacher/trials" },
  { label: "Настройки", shortLabel: "Н", href: "/teacher/settings" },
  { label: "Система", shortLabel: "С", href: "/teacher/system" },
];

function ThemePicker({ theme, onChange }: { theme: Theme; onChange: (theme: Theme) => void }) {
  return <label className="theme-picker"><span>Тема</span><select aria-label="Цветовая тема" value={theme} onChange={(event) => onChange(event.target.value as Theme)}><option value="system">Системная</option><option value="light">Светлая</option><option value="dark">Тёмная</option></select></label>;
}

export function AppChrome({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [theme, setTheme] = useState<Theme>("system");
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const storedTheme = localStorage.getItem("tutorcrm-theme");
    if (storedTheme === "light" || storedTheme === "dark" || storedTheme === "system") setTheme(storedTheme);
    setCollapsed(localStorage.getItem("tutorcrm-sidebar-collapsed") === "true");
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("tutorcrm-theme", theme);
  }, [theme]);

  useEffect(() => {
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");
  }, []);

  const role = pathname.startsWith("/student") ? "student" : pathname.startsWith("/teacher") ? "teacher" : null;
  const links = role === "student" ? studentLinks : role === "teacher" ? teacherLinks : null;

  const toggleSidebar = () => {
    setCollapsed((current) => {
      localStorage.setItem("tutorcrm-sidebar-collapsed", String(!current));
      return !current;
    });
  };

  return <>
    <a className="skip-link" href="#main-content">Перейти к содержимому</a>
    {links ? <div className={`app-shell${collapsed ? " app-shell-collapsed" : ""}`}>
      <aside className="app-sidebar">
        <Link className="app-brand" href={role === "teacher" ? "/teacher" : "/student"} title="Tutor CRM"><span aria-hidden="true">T</span><strong>Tutor CRM</strong></Link>
        <nav className="desktop-navigation" aria-label="Основная навигация">{links.map((item) => {
          const active = isNavigationActive(pathname, item.href);
          return <Link aria-current={active ? "page" : undefined} className={active ? "active" : ""} href={item.href} key={item.href} title={collapsed ? item.label : undefined}><span className="nav-glyph" aria-hidden="true">{item.shortLabel}</span><span className="nav-label">{item.label}</span></Link>;
        })}</nav>
        <button className="sidebar-toggle" type="button" onClick={toggleSidebar} aria-label={collapsed ? "Развернуть меню" : "Свернуть меню"} aria-expanded={!collapsed}><span aria-hidden="true">{collapsed ? "→" : "←"}</span><span className="nav-label">Свернуть</span></button>
      </aside>
      <div className="app-workspace">
        <header className="app-topbar"><p>{role === "teacher" ? "Кабинет преподавателя" : "Кабинет ученика"}</p><div className="topbar-actions"><ThemePicker theme={theme} onChange={setTheme} /><LogoutButton className="secondary-button topbar-logout" /></div></header>
        <div className="app-content" id="main-content" tabIndex={-1}>{children}</div>
      </div>
      <nav className="mobile-navigation" aria-label="Основная навигация">{links.slice(0, 5).map((item) => <Link aria-current={isNavigationActive(pathname, item.href) ? "page" : undefined} className={isNavigationActive(pathname, item.href) ? "active" : ""} href={item.href} key={item.href}><span className="nav-glyph" aria-hidden="true">{item.shortLabel}</span><span>{item.label}</span></Link>)}</nav>
    </div> : <><ThemePicker theme={theme} onChange={setTheme} /><div id="main-content" tabIndex={-1}>{children}</div></>}
  </>;
}
