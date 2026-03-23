import { describe, it, expect } from "vitest";
import { cleanTextForTTS } from "./textCleaner";

describe("cleanTextForTTS", () => {
  it("returns empty string for empty input", () => {
    expect(cleanTextForTTS("")).toBe("");
  });

  it("returns empty string for null-ish input", () => {
    expect(cleanTextForTTS(undefined as unknown as string)).toBe("");
  });

  it("passes through clean text unchanged", () => {
    const text = "Hello world, this is a normal sentence.";
    expect(cleanTextForTTS(text)).toBe(text);
  });

  // ── Headings ──────────────────────────────────────────────────────────────
  it("strips markdown headings", () => {
    expect(cleanTextForTTS("# Title")).toBe("Title");
    expect(cleanTextForTTS("## Subtitle")).toBe("Subtitle");
    expect(cleanTextForTTS("### Deep heading")).toBe("Deep heading");
  });

  // ── Bold / Italic ─────────────────────────────────────────────────────────
  it("strips bold markers", () => {
    expect(cleanTextForTTS("This is **bold** text")).toBe("This is bold text");
  });

  it("strips italic markers", () => {
    expect(cleanTextForTTS("This is *italic* text")).toBe("This is italic text");
  });

  it("strips underscore bold/italic", () => {
    expect(cleanTextForTTS("__bold__ and _italic_")).toBe("bold and italic");
  });

  // ── Code ──────────────────────────────────────────────────────────────────
  it("strips inline code backticks", () => {
    expect(cleanTextForTTS("Use `console.log` to debug")).toBe(
      "Use console.log to debug"
    );
  });

  it("strips code fences", () => {
    const input = "Before\n```js\nconst x = 1;\n```\nAfter";
    expect(cleanTextForTTS(input)).toBe("Before After");
  });

  // ── Blockquotes ───────────────────────────────────────────────────────────
  it("strips blockquotes", () => {
    expect(cleanTextForTTS("> This is a quote")).toBe("This is a quote");
  });

  it("strips nested blockquotes", () => {
    expect(cleanTextForTTS("> > nested quote")).toBe("> nested quote");
  });

  // ── Lists ─────────────────────────────────────────────────────────────────
  it("strips unordered list bullets", () => {
    const input = "- Item one\n- Item two\n* Item three";
    expect(cleanTextForTTS(input)).toBe("Item one Item two Item three");
  });

  it("strips ordered list numbers", () => {
    const input = "1. First\n2. Second\n3. Third";
    expect(cleanTextForTTS(input)).toBe("First Second Third");
  });

  // ── Links and Images ──────────────────────────────────────────────────────
  it("keeps link text, strips URL", () => {
    expect(cleanTextForTTS("[Click here](https://example.com)")).toBe(
      "Click here"
    );
  });

  it("keeps image alt text, strips URL", () => {
    expect(cleanTextForTTS("![A photo](https://example.com/img.jpg)")).toBe(
      "A photo"
    );
  });

  // ── Horizontal Rules ──────────────────────────────────────────────────────
  it("strips horizontal rules", () => {
    expect(cleanTextForTTS("Above\n---\nBelow")).toBe("Above Below");
  });

  // ── Strikethrough ─────────────────────────────────────────────────────────
  it("strips strikethrough markers", () => {
    expect(cleanTextForTTS("This is ~~deleted~~ text")).toBe(
      "This is deleted text"
    );
  });

  // ── HTML ──────────────────────────────────────────────────────────────────
  it("strips HTML tags", () => {
    expect(cleanTextForTTS("<b>Bold</b> and <i>italic</i>")).toBe(
      "Bold and italic"
    );
  });

  // ── Whitespace Normalization ──────────────────────────────────────────────
  it("collapses multiple spaces", () => {
    expect(cleanTextForTTS("Hello    world")).toBe("Hello world");
  });

  it("collapses multiple newlines", () => {
    expect(cleanTextForTTS("Line one\n\n\n\nLine two")).toBe(
      "Line one Line two"
    );
  });

  // ── Mixed Content ─────────────────────────────────────────────────────────
  it("handles complex mixed markdown", () => {
    const input = `# Welcome

This is **bold** and *italic* text with \`code\`.

> A blockquote

- List item one
- List item two

Visit [our site](https://example.com) for more.

\`\`\`python
print("hello")
\`\`\`

That's all!`;

    const result = cleanTextForTTS(input);
    expect(result).toBe(
      "Welcome This is bold and italic text with code. A blockquote List item one List item two Visit our site for more. That's all!"
    );
  });
});
