import { describe, expect, it } from "vitest";
import { mondayFor, moscowDateKey, shiftDate, weekRange } from "./calendar";

describe("Moscow calendar helpers", () => {
  it("builds a Monday-to-Monday range across month boundaries", () => {
    expect(weekRange("2026-11-01")).toEqual({
      start: "2026-10-26",
      end: "2026-11-02",
      days: ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01"],
    });
  });

  it("uses Moscow date when UTC is still on the previous day", () => {
    expect(moscowDateKey("2026-10-20T21:30:00Z")).toBe("2026-10-21");
    expect(mondayFor("invalid")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(shiftDate("2026-12-31", 1)).toBe("2027-01-01");
  });
});
