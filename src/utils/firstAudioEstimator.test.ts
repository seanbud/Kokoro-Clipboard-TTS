import { describe, expect, it } from "vitest";
import {
  estimateFirstAudioMs,
  estimatedGenerationProgress,
  estimatedRemainingLabel,
  recordFirstAudioSample,
  type FirstAudioContext,
  type FirstAudioSample,
} from "./firstAudioEstimator";

const context: FirstAudioContext = {
  backend: "kokoro-pytorch-cpu",
  voice: "am_fenrir",
  firstSegmentChars: 30,
};

function sample(durationMs: number, overrides = {}): FirstAudioSample {
  return { ...context, durationMs, ...overrides };
}

describe("first audio estimator", () => {
  it("keeps only recent valid contextual samples", () => {
    let history: FirstAudioSample[] = [];
    history = recordFirstAudioSample(history, 800, context, 3);
    history = recordFirstAudioSample(history, Number.NaN, context, 3);
    history = recordFirstAudioSample(history, 900, context, 3);
    history = recordFirstAudioSample(history, 1000, context, 3);
    history = recordFirstAudioSample(history, 1100, context, 3);
    expect(history.map(({ durationMs }) => durationMs)).toEqual([900, 1000, 1100]);
  });

  it("uses a robust median after three comparable observations", () => {
    expect(estimateFirstAudioMs([sample(800), sample(900)], context)).toBeNull();
    expect(estimateFirstAudioMs([sample(800), sample(900), sample(12_000)], context)).toBe(900);
    expect(estimateFirstAudioMs(
      [sample(700), sample(800), sample(900), sample(1000)],
      context,
    )).toBe(850);
  });

  it("does not mix voices, backends, or segment-size buckets", () => {
    const history = [
      sample(700),
      sample(800),
      sample(900),
      sample(5000, { voice: "af_heart" }),
      sample(6000, { backend: "experimental-mps" }),
      sample(7000, { firstSegmentChars: 120 }),
    ];
    expect(estimateFirstAudioMs(history, context)).toBe(800);
    expect(estimateFirstAudioMs(history, { ...context, voice: "af_heart" })).toBeNull();
    expect(estimateFirstAudioMs(history, { ...context, firstSegmentChars: 120 })).toBeNull();
  });

  it("never predicts completion before the playback event", () => {
    expect(estimatedGenerationProgress(500, null)).toBeNull();
    expect(estimatedGenerationProgress(500, 1000)).toBe(0.45);
    expect(estimatedGenerationProgress(5000, 1000)).toBe(0.9);
  });

  it("shows a coarse remaining-time label", () => {
    expect(estimatedRemainingLabel(250, 1000)).toBe("~1.0s");
    expect(estimatedRemainingLabel(700, 1000)).toBe("~0.5s");
    expect(estimatedRemainingLabel(1200, 1000)).toBe("almost ready");
    expect(estimatedRemainingLabel(100, null)).toBeNull();
  });
});
