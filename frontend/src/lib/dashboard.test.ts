import { describe, expect, it } from "vitest";
import { lessonDuration, studentInitials } from "./dashboard";

describe("teacher dashboard helpers", () => {
  it("formats real lesson duration and student initials", () => {
    expect(lessonDuration("2026-10-20T09:00:00Z", "2026-10-20T10:20:00Z")).toBe("1 ч 20 мин");
    expect(lessonDuration("2026-10-20T09:00:00Z", "2026-10-20T09:45:00Z")).toBe("45 мин");
    expect(studentInitials("Иванов Иван")).toBe("ИИ");
  });
});
