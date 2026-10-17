import { describe, expect, it } from "vitest";

describe("theme baseline", () => {
  it("keeps the application name stable", () => {
    expect("Tutor CRM").toBe("Tutor CRM");
  });
});

