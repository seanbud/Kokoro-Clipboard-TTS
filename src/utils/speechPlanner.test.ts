import { describe, expect, it } from "vitest";
import {
  MAX_SPEECH_SEGMENT_CHARS,
  normalizeCodeForSpeech,
  planTextForTTS,
  replayPlanFromSegment,
} from "./speechPlanner";

describe("speech planner", () => {
  it("preserves paragraph boundaries and source offsets", () => {
    const input = "The first thought ends here.\n\nThe second thought starts later.";

    const segments = planTextForTTS(input);

    expect(segments.map((segment) => segment.spokenText)).toEqual([
      "The first thought ends here.",
      "The second thought starts later.",
    ]);
    expect(segments.map((segment) => segment.kind)).toEqual(["paragraph", "paragraph"]);
    expect(segments.map((segment) => segment.pauseAfterMs)).toEqual([420, 420]);
    for (const segment of segments) {
      expect(input.slice(segment.sourceStart, segment.sourceEnd)).toBe(segment.sourceText);
    }
  });

  it("turns headings, list items, and quotes into semantic segments", () => {
    const input = [
      "## Priorities",
      "- exact pause",
      "2. faster audio",
      "> Preserve the listener's context.",
    ].join("\n");

    const segments = planTextForTTS(input);

    expect(segments.map(({ kind, spokenText, pauseAfterMs }) => ({
      kind,
      spokenText,
      pauseAfterMs,
    }))).toEqual([
      { kind: "heading", spokenText: "Priorities", pauseAfterMs: 550 },
      { kind: "list-item", spokenText: "exact pause", pauseAfterMs: 220 },
      { kind: "list-item", spokenText: "faster audio", pauseAfterMs: 220 },
      { kind: "quote", spokenText: "Preserve the listener's context.", pauseAfterMs: 420 },
    ]);
  });

  it("infers a high-confidence heading when plain clipboard text retains only a line break", () => {
    const segments = planTextForTTS(
      "Why this matters\nThe listener needs a brief pause before this explanation begins.",
    );

    expect(segments.map(({ kind, spokenText, pauseAfterMs }) => ({
      kind,
      spokenText,
      pauseAfterMs,
    }))).toEqual([
      { kind: "heading", spokenText: "Why this matters", pauseAfterMs: 550 },
      {
        kind: "paragraph",
        spokenText: "The listener needs a brief pause before this explanation begins.",
        pauseAfterMs: 420,
      },
    ]);
  });

  it("does not treat an ordinary hard-wrapped sentence as a heading", () => {
    const segments = planTextForTTS(
      "This thought wraps without punctuation\nand continues in lowercase on the next copied line.",
    );

    expect(segments).toHaveLength(1);
    expect(segments[0].kind).toBe("paragraph");
    expect(segments[0].spokenText).toBe(
      "This thought wraps without punctuation and continues in lowercase on the next copied line.",
    );
  });

  it("announces and intelligently reads fenced code by default", () => {
    const input = "Before.\n```ts\nstream.write(chunk);\n```\nAfter.";

    const segments = planTextForTTS(input);

    expect(segments.map((segment) => segment.spokenText)).toEqual([
      "Before.",
      "Code block.",
      "stream dot write chunk",
      "End code block.",
      "After.",
    ]);
    expect(segments.find((segment) => segment.spokenText.includes("stream"))?.sourceText)
      .toBe("stream.write(chunk);");
  });

  it("announces skipped code only when the setting is enabled", () => {
    const input = "Before.\n```ts\nstream.write(chunk);\n```\nAfter.";
    const segments = planTextForTTS(input, { skipCodeBlocks: true });

    expect(segments.map((segment) => segment.spokenText)).toEqual([
      "Before.",
      "Code block skipped.",
      "After.",
    ]);
  });

  it("normalizes identifiers and operators without spelling every delimiter", () => {
    expect(normalizeCodeForSpeech("if (activeSessionRef && request_id >= 2) {"))
      .toBe("if active Session Ref and request id greater than or equal to 2");
  });

  it("bounds long inference segments at a safe word or clause boundary", () => {
    const input = "Although generation can process a long sentence, the first audible sample should not wait for every supporting clause, and the playback controller should retain enough context to continue naturally without creating an oversized model input that fails on an experimental backend.";

    const segments = planTextForTTS(input);

    expect(segments.length).toBeGreaterThan(1);
    expect(segments.every((segment) => segment.spokenText.length <= MAX_SPEECH_SEGMENT_CHARS))
      .toBe(true);
    expect(segments.map((segment) => segment.spokenText).join(" "))
      .toBe(input);
  });

  it("keeps segments bounded after pronunciation expansions", () => {
    const segments = planTextForTTS(`${Array(36).fill("AI").join(" ")}.`);

    expect(segments.length).toBeGreaterThan(1);
    expect(segments.every((segment) => segment.spokenText.length <= MAX_SPEECH_SEGMENT_CHARS))
      .toBe(true);
  });

  it("uses sentence pauses internally and a paragraph pause at the block end", () => {
    const segments = planTextForTTS("First sentence. Second sentence? Third sentence!");

    expect(segments.map((segment) => segment.pauseAfterMs)).toEqual([120, 120, 420]);
    expect(segments.map((segment) => segment.kind)).toEqual([
      "sentence",
      "sentence",
      "paragraph",
    ]);
  });

  it("recognizes an ellipsis boundary without splitting semantic versions", () => {
    const segments = planTextForTTS("Ok.. Try v0.7.0 when it is ready.");

    expect(segments.map((segment) => segment.spokenText)).toEqual([
      "Okay..",
      "Try version 0 point 7 point 0 when it is ready.",
    ]);
    expect(segments[0].pauseAfterMs).toBe(320);
  });

  it("pronounces common chat shorthand as initialisms without changing meaning", () => {
    const segments = planTextForTTS(
      "idk, that looks wrong lol. TBH I expected more, but imo it helps.",
    );

    expect(segments.map((segment) => segment.spokenText)).toEqual([
      "I D K, that looks wrong L O L.",
      "T B H I expected more, but I M O it helps.",
    ]);
  });

  it("handles broader conversational shorthand and uppercase initialisms", () => {
    const segments = planTextForTTS(
      "FYI, the API is ready ASAP. btw, the US team shared a URL with us.",
    );

    expect(segments.map((segment) => segment.spokenText)).toEqual([
      "F Y I, the A P I is ready A S A P.",
      "B T W, the U S team shared a U R L with us.",
    ]);
  });

  it("reads common numeric formats as deliberate speech", () => {
    const segments = planTextForTTS(
      "On 2026-07-25 at 3:05 p.m., upgrade from v0.6.3 to v0.7.0. It costs $12.50 at 0.5x, or 59.9% less.",
    );

    expect(segments.map((segment) => segment.spokenText)).toEqual([
      "On July 25, 2026 at 3 oh 5 P M, upgrade from version 0 point 6 point 3 to version 0 point 7 point 0.",
      "It costs 12 dollars and 50 cents at 0 point 5 times, or 59 point 9 percent less.",
    ]);
  });

  it("makes links, email addresses, paths, and inline code concise but intelligible", () => {
    const segments = planTextForTTS(
      "Open https://example.com/docs, email support@example.com, inspect /Users/me/app.ts, then call `stream.start()`.",
    );

    expect(segments.map((segment) => segment.spokenText).join(" ")).toBe(
      "Open example dot com slash docs, email support at example dot com, inspect path Users slash me slash app dot T S, then call stream dot start.",
    );
  });

  it("adds a modest thought pause when a retained line break separates sentences", () => {
    const segments = planTextForTTS(
      "The first thought is complete.\nThe next thought begins on its own line.",
    );

    expect(segments.map((segment) => segment.pauseAfterMs)).toEqual([260, 420]);
  });

  it("removes inline markup while preserving meaningful text", () => {
    const segments = planTextForTTS(
      "Read **important** [documentation](https://example.com) and `request_id`.",
    );

    expect(segments[0].spokenText).toBe(
      "Read important documentation and request id.",
    );
  });

  it("returns no segments for empty input", () => {
    expect(planTextForTTS(" \n\n ")).toEqual([]);
  });
});

describe("sentence replay planning", () => {
  const plan = planTextForTTS("First sentence. Second sentence. Third sentence.");

  it("restarts at the active sentence and preserves everything after it", () => {
    expect(replayPlanFromSegment(plan, plan[1].id)).toEqual(plan.slice(1));
  });

  it("falls back to the full plan when no current sentence is known", () => {
    expect(replayPlanFromSegment(plan, null)).toBe(plan);
    expect(replayPlanFromSegment(plan, "stale-segment")).toBe(plan);
  });
});
