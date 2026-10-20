import { describe, expect, it } from "vitest";
import { isNavigationActive } from "./navigation";

describe("application navigation", () => {
  it("marks nested sections without activating the dashboard for every route", () => {
    expect(isNavigationActive("/teacher/students/42", "/teacher/students")).toBe(true);
    expect(isNavigationActive("/teacher/students", "/teacher")).toBe(false);
    expect(isNavigationActive("/student", "/student")).toBe(true);
    expect(isNavigationActive("/student/billing", "/teacher/finances")).toBe(false);
  });
});
