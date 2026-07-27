import { describe, expect, it } from "vitest";
import { estimatedStartupProgress } from "./startupProgress";

describe("startup progress", () => {
  it("advances gradually while the frozen engine is preparing", () => {
    expect(estimatedStartupProgress("starting", 0)).toBe(8);
    expect(estimatedStartupProgress("starting", 30_000)).toBe(38);
    expect(estimatedStartupProgress("starting", 120_000)).toBe(72);
  });

  it("uses real engine milestones for the final steps", () => {
    expect(estimatedStartupProgress("loading-model", 1)).toBe(82);
    expect(estimatedStartupProgress("warming-engine", 1)).toBe(92);
    expect(estimatedStartupProgress("ready", 1)).toBe(100);
    expect(estimatedStartupProgress("error", 1)).toBe(100);
  });
});
