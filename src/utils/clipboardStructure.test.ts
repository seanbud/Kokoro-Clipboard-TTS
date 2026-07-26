// @vitest-environment jsdom

import { describe, expect, it } from "vitest";
import { structuredClipboardText } from "./clipboardStructure";
import { planTextForTTS } from "./speechPlanner";

describe("structured clipboard recovery", () => {
  it("recovers headings and paragraph boundaries from matching HTML", () => {
    const result = structuredClipboardText({
      text: "Why this matters\nThe listener needs a moment.\nThen the next thought begins.",
      html: "<h2>Why this matters</h2><p>The listener needs a moment.</p><p>Then the next thought begins.</p>",
    });

    expect(result).toBe([
      "## Why this matters",
      "",
      "The listener needs a moment.",
      "",
      "Then the next thought begins.",
    ].join("\n"));
    expect(planTextForTTS(result).map(({ kind, pauseAfterMs }) => ({
      kind,
      pauseAfterMs,
    }))).toEqual([
      { kind: "heading", pauseAfterMs: 550 },
      { kind: "paragraph", pauseAfterMs: 420 },
      { kind: "paragraph", pauseAfterMs: 420 },
    ]);
  });

  it("turns explicit HTML line breaks into pause-worthy boundaries", () => {
    expect(structuredClipboardText({
      text: "First thought\nSecond thought",
      html: "First thought<br>Second thought",
    })).toBe("First thought\n\nSecond thought");
  });

  it("falls back to plain text when rich and plain clipboard content disagree", () => {
    expect(structuredClipboardText({
      text: "The text the user selected.",
      html: "<h1>Unrelated clipboard content</h1>",
    })).toBe("The text the user selected.");
  });

  it("ignores executable and styling elements", () => {
    expect(structuredClipboardText({
      text: "Safe text",
      html: "<style>hidden</style><script>bad()</script><p>Safe text</p>",
    })).toBe("Safe text");
  });
});
