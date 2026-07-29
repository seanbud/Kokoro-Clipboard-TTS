import { describe, expect, it } from "vitest";
import tauriConfig from "../../src-tauri/tauri.conf.json";

describe("floating widget native window", () => {
  it("keeps every control, including Close, inside the visible viewport", () => {
    const reader = tauriConfig.app.windows.find((window) => window.label === "reader");
    const controlWidths = [36, 28, 28, 72, 36, 28];
    const controlGaps = (controlWidths.length - 1) * 6;
    const containerPadding = 16;
    const shadowPadding = 80;
    const minimumWidth = controlWidths.reduce((sum, width) => sum + width, 0)
      + controlGaps
      + containerPadding
      + shadowPadding;

    expect(reader?.width).toBeGreaterThanOrEqual(minimumWidth);
    expect(reader?.shadow).toBe(true);
  });
});
