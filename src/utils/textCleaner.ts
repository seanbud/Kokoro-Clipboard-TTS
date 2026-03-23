/**
 * Text cleaner utility for TTS preprocessing.
 *
 * Strips markdown formatting and normalizes whitespace so the
 * Kokoro TTS engine reads clean, natural-sounding text.
 */

/**
 * Strip markdown syntax and normalize whitespace for TTS consumption.
 */
export function cleanTextForTTS(input: string): string {
  if (!input) return "";

  let text = input;

  // Remove code fences (``` ... ```) — multiline
  text = text.replace(/```[\s\S]*?```/g, " ");

  // Remove inline code (` ... `)
  text = text.replace(/`([^`]*)`/g, "$1");

  // Remove markdown headings (# ## ### etc.)
  text = text.replace(/^#{1,6}\s+/gm, "");

  // Remove bold/italic markers (**, __, *, _)
  text = text.replace(/(\*{1,3}|_{1,3})(.*?)\1/g, "$2");

  // Remove strikethrough (~~text~~)
  text = text.replace(/~~(.*?)~~/g, "$1");

  // Remove blockquotes (> )
  text = text.replace(/^\s*>\s?/gm, "");

  // Remove horizontal rules (---, ***, ___)
  text = text.replace(/^[\s]*([-*_]){3,}\s*$/gm, "");

  // Remove unordered list bullets (- , * , + )
  text = text.replace(/^\s*[-*+]\s+/gm, "");

  // Remove ordered list numbers (1. , 2. , etc.)
  text = text.replace(/^\s*\d+\.\s+/gm, "");

  // Remove markdown images ![alt](url) — MUST come before links
  text = text.replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1");

  // Remove markdown links [text](url) → keep text
  text = text.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");

  // Remove HTML tags
  text = text.replace(/<[^>]*>/g, "");

  // Normalize whitespace: collapse multiple spaces/newlines
  text = text.replace(/\s+/g, " ");

  return text.trim();
}
