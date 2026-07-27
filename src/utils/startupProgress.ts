export type StartupStage = "starting" | "loading-model" | "warming-engine" | "ready" | "error";

export function estimatedStartupProgress(stage: StartupStage, elapsedMs: number): number {
  switch (stage) {
    case "loading-model":
      return 82;
    case "warming-engine":
      return 92;
    case "ready":
    case "error":
      return 100;
    case "starting":
    default:
      // Extraction has no native progress signal. Move gradually toward a cap
      // and wait for real model milestones rather than promising a false ETA.
      return Math.min(72, 8 + Math.max(0, elapsedMs) / 1_000);
  }
}
