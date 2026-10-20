import { describe, expect, it } from "vitest";
import { FILE_MAX_BYTES, validateFileSelection } from "./files";

describe("homework file selection", () => {
  it("accepts supported multiple files within the shared limits", () => {
    expect(validateFileSelection([
      { name: "answer.PDF", size: 1024 },
      { name: "photo.jpeg", size: 2048 },
    ], 2)).toBeNull();
  });

  it("rejects unsupported, empty, oversized and excessive selections", () => {
    expect(validateFileSelection([{ name: "script.html", size: 10 }], 0)).toContain("неподдерживаемый");
    expect(validateFileSelection([{ name: "empty.png", size: 0 }], 0)).toContain("1 байта");
    expect(validateFileSelection([{ name: "huge.pdf", size: FILE_MAX_BYTES + 1 }], 0)).toContain("15 МБ");
    expect(validateFileSelection([{ name: "extra.webp", size: 1 }], 10)).toContain("не больше 10");
  });
});
