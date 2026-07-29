import { describe, expect, it } from "vitest";
import {
  DEFAULT_SHORTCUT_MAC,
  DEFAULT_SHORTCUT_WIN,
  getPlatformDefaultShortcut,
} from "./shortcuts";

describe("platform shortcut defaults", () => {
  it("uses Control+Option+R on macOS", () => {
    expect(getPlatformDefaultShortcut("Mozilla/5.0 (Macintosh; Intel Mac OS X)"))
      .toBe("Control+Option+R");
    expect(DEFAULT_SHORTCUT_MAC).toBe("Control+Option+R");
  });

  it("keeps the Windows default distinct", () => {
    expect(getPlatformDefaultShortcut("Mozilla/5.0 (Windows NT 10.0; Win64; x64)"))
      .toBe("Super+Shift+Q");
    expect(DEFAULT_SHORTCUT_WIN).toBe("Super+Shift+Q");
  });
});
