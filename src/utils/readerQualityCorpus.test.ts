import { describe, expect, it } from "vitest";
import corpus from "../../tests/fixtures/reader_quality_v1.json";
import { MAX_SPEECH_SEGMENT_CHARS, planTextForTTS } from "./speechPlanner";

describe("reader quality corpus", () => {
  it("is versioned and has unique, non-empty cases", () => {
    expect(corpus.schemaVersion).toBe(1);
    expect(corpus.cases.length).toBeGreaterThanOrEqual(20);

    const ids = corpus.cases.map((testCase) => testCase.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const testCase of corpus.cases) {
      expect(testCase.input.trim()).not.toBe("");
      expect(testCase.concerns.length).toBeGreaterThan(0);
    }
  });

  it("covers every v0.7 speech-planning risk category", () => {
    const categories = new Set(corpus.cases.map((testCase) => testCase.category));
    for (const required of [
      "structure",
      "chat",
      "acronyms",
      "numbers",
      "technical",
      "code",
      "punctuation",
      "long-form",
      "privacy",
    ]) {
      expect(categories.has(required)).toBe(true);
    }
  });

  it("contains critical fixtures for the reported product problems", () => {
    const criticalConcerns = new Set(
      corpus.cases
        .filter((testCase) => testCase.priority === "critical")
        .flatMap((testCase) => testCase.concerns),
    );

    for (const required of [
      "paragraph-boundary",
      "plain-text-heading-inference",
      "list-boundary",
      "shorthand",
      "currency",
      "code-policy",
      "thought-digestion",
      "first-audio-latency",
      "release-log-redaction",
    ]) {
      expect(criticalConcerns.has(required)).toBe(true);
    }
  });

  it("plans every fixture into bounded, source-mapped inference segments", () => {
    for (const testCase of corpus.cases) {
      const segments = planTextForTTS(testCase.input);
      expect(segments.length, testCase.id).toBeGreaterThan(0);
      expect(new Set(segments.map((segment) => segment.id)).size, testCase.id)
        .toBe(segments.length);

      for (const segment of segments) {
        expect(
          testCase.input.slice(segment.sourceStart, segment.sourceEnd),
          `${testCase.id}/${segment.id}`,
        ).toBe(segment.sourceText);
        if (segment.spokenText) {
          expect(segment.spokenText.length, `${testCase.id}/${segment.id}`)
            .toBeLessThanOrEqual(MAX_SPEECH_SEGMENT_CHARS);
        }
      }
    }
  });

  it("locks approved spoken forms into regression fixtures", () => {
    for (const testCase of corpus.cases) {
      if (!("expectedSpokenSegments" in testCase)) continue;
      const actual = planTextForTTS(testCase.input)
        .filter((segment) => segment.spokenText)
        .map((segment) => segment.spokenText);
      expect(actual, testCase.id).toEqual(testCase.expectedSpokenSegments);
    }
  });
});
