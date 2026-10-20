export function isNavigationActive(pathname: string, href: string): boolean {
  const isDashboard = href === "/student" || href === "/teacher";
  return pathname === href || (!isDashboard && pathname.startsWith(`${href}/`));
}
