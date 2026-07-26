export const MAX_SPEECH_SEGMENT_CHARS = 140;

export type SpeechSegmentKind =
  | "heading"
  | "paragraph"
  | "sentence"
  | "list-item"
  | "quote"
  | "code";

export type SpeechSegment = {
  id: string;
  sourceText: string;
  spokenText: string;
  kind: SpeechSegmentKind;
  pauseAfterMs: number;
  sourceStart: number;
  sourceEnd: number;
};

export type SpeechPlannerOptions = {
  skipCodeBlocks?: boolean;
};

type SourceLine = {
  text: string;
  start: number;
  end: number;
};

type MappedText = {
  text: string;
  sourcePositions: number[];
};

type SpeechBlock = {
  kind: Exclude<SpeechSegmentKind, "sentence">;
  lines: SourceLine[];
  stripPrefix?: RegExp;
};

const FINAL_PAUSE_MS: Record<SpeechBlock["kind"], number> = {
  heading: 550,
  paragraph: 420,
  "list-item": 220,
  quote: 420,
  code: 420,
};

const SPOKEN_SHORTHAND: Record<string, string> = {
  idk: "I D K",
  imo: "I M O",
  lol: "L O L",
  tbh: "T B H",
};

function sourceLines(input: string): SourceLine[] {
  const lines: SourceLine[] = [];
  const pattern = /[^\r\n]*(?:\r\n|\n|\r|$)/g;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(input)) !== null) {
    if (match[0] === "") break;
    const newlineLength = match[0].endsWith("\r\n")
      ? 2
      : /[\r\n]$/.test(match[0])
        ? 1
        : 0;
    const text = newlineLength > 0 ? match[0].slice(0, -newlineLength) : match[0];
    lines.push({ text, start: match.index, end: match.index + text.length });
  }

  return lines;
}

function isHeading(line: SourceLine): boolean {
  return /^\s{0,3}#{1,6}\s+/.test(line.text);
}

function isListItem(line: SourceLine): boolean {
  return /^\s*(?:[-*+]|\d+[.)])\s+/.test(line.text);
}

function isQuote(line: SourceLine): boolean {
  return /^\s*>\s?/.test(line.text);
}

function isFence(line: SourceLine): boolean {
  return /^\s*```/.test(line.text);
}

function isLikelyPlainHeading(lines: SourceLine[], index: number): boolean {
  const line = lines[index];
  const text = line?.text.trim() ?? "";
  if (!text || text.length > 72 || /[.!?;:,]$/.test(text)) return false;

  const words = text.split(/\s+/);
  if (words.length > 9 || !/^\p{Lu}/u.test(text)) return false;
  if (index > 0 && lines[index - 1].text.trim()) return false;

  let nextIndex = index + 1;
  while (nextIndex < lines.length && !lines[nextIndex].text.trim()) nextIndex += 1;
  const nextText = lines[nextIndex]?.text.trim() ?? "";
  return (
    nextText.length >= Math.max(32, text.length + 12)
    && /^\p{Lu}/u.test(nextText)
    && /[.!?]["')\]]?$/.test(nextText)
  );
}

function beginsSpecialBlock(lines: SourceLine[], index: number): boolean {
  const line = lines[index];
  return (
    isHeading(line)
    || isLikelyPlainHeading(lines, index)
    || isListItem(line)
    || isQuote(line)
    || isFence(line)
  );
}

function parseBlocks(input: string): SpeechBlock[] {
  const lines = sourceLines(input);
  const blocks: SpeechBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.text.trim()) {
      index += 1;
      continue;
    }

    if (isFence(line)) {
      const codeLines = [line];
      index += 1;
      while (index < lines.length) {
        codeLines.push(lines[index]);
        const closing = isFence(lines[index]);
        index += 1;
        if (closing) break;
      }
      blocks.push({ kind: "code", lines: codeLines });
      continue;
    }

    if (isHeading(line) || isLikelyPlainHeading(lines, index)) {
      blocks.push({
        kind: "heading",
        lines: [line],
        stripPrefix: isHeading(line) ? /^\s{0,3}#{1,6}\s+/ : undefined,
      });
      index += 1;
      continue;
    }

    if (isListItem(line)) {
      blocks.push({
        kind: "list-item",
        lines: [line],
        stripPrefix: /^\s*(?:[-*+]|\d+[.)])\s+/,
      });
      index += 1;
      continue;
    }

    if (isQuote(line)) {
      const quoteLines = [];
      while (index < lines.length && isQuote(lines[index])) {
        quoteLines.push(lines[index]);
        index += 1;
      }
      blocks.push({ kind: "quote", lines: quoteLines, stripPrefix: /^\s*>\s?/ });
      continue;
    }

    const paragraphLines = [line];
    index += 1;
    while (
      index < lines.length
      && lines[index].text.trim()
      && !beginsSpecialBlock(lines, index)
    ) {
      paragraphLines.push(lines[index]);
      index += 1;
    }
    blocks.push({ kind: "paragraph", lines: paragraphLines });
  }

  return blocks;
}

function appendMappedText(
  mapped: MappedText,
  value: string,
  sourceStart: number,
): void {
  let pendingSpacePosition: number | null = null;
  for (let index = 0; index < value.length; index += 1) {
    const character = value[index];
    const sourcePosition = sourceStart + index;
    if (/\s/.test(character)) {
      if (mapped.text.length > 0) pendingSpacePosition = sourcePosition;
      continue;
    }
    if (pendingSpacePosition !== null && !mapped.text.endsWith(" ")) {
      mapped.text += " ";
      mapped.sourcePositions.push(pendingSpacePosition);
    }
    pendingSpacePosition = null;
    mapped.text += character;
    mapped.sourcePositions.push(sourcePosition);
  }
}

function mapBlock(block: SpeechBlock): MappedText {
  const mapped: MappedText = { text: "", sourcePositions: [] };
  for (const line of block.lines) {
    let content = line.text;
    let contentStart = line.start;
    if (block.stripPrefix) {
      const prefix = content.match(block.stripPrefix)?.[0] ?? "";
      content = content.slice(prefix.length);
      contentStart += prefix.length;
    }

    const leadingWhitespace = content.match(/^\s*/)?.[0].length ?? 0;
    content = content.trim();
    contentStart += leadingWhitespace;
    if (!content) continue;

    if (mapped.text.length > 0 && !mapped.text.endsWith(" ")) {
      mapped.text += " ";
      mapped.sourcePositions.push(Math.max(line.start - 1, 0));
    }
    appendMappedText(mapped, content, contentStart);
  }
  return mapped;
}

function trimRange(text: string, start: number, end: number): [number, number] | null {
  while (start < end && /\s/.test(text[start])) start += 1;
  while (end > start && /\s/.test(text[end - 1])) end -= 1;
  return start < end ? [start, end] : null;
}

function sentenceRanges(text: string): Array<[number, number]> {
  const ranges: Array<[number, number]> = [];
  let start = 0;
  let index = 0;

  while (index < text.length) {
    if (/[.!?]/.test(text[index])) {
      let end = index + 1;
      while (end < text.length && /[.!?]/.test(text[end])) end += 1;
      while (end < text.length && /["')\]]/.test(text[end])) end += 1;
      if (end === text.length || /\s/.test(text[end])) {
        const range = trimRange(text, start, end);
        if (range) ranges.push(range);
        start = end;
      }
      index = end;
      continue;
    }
    index += 1;
  }

  const finalRange = trimRange(text, start, text.length);
  if (finalRange) ranges.push(finalRange);
  return ranges;
}

function findSafeCut(text: string, start: number, maximumEnd: number): number {
  const minimumEnd = Math.min(start + 40, maximumEnd);
  for (let index = maximumEnd; index >= minimumEnd; index -= 1) {
    if (/[,;:—]/.test(text[index - 1])) return index;
  }
  for (let index = maximumEnd; index >= minimumEnd; index -= 1) {
    if (/\s/.test(text[index - 1])) return index - 1;
  }
  return maximumEnd;
}

function boundRange(
  text: string,
  start: number,
  end: number,
  maximumLength: number,
): Array<[number, number]> {
  const ranges: Array<[number, number]> = [];
  let cursor = start;
  while (end - cursor > maximumLength) {
    const cut = findSafeCut(text, cursor, cursor + maximumLength);
    const range = trimRange(text, cursor, cut);
    if (range) ranges.push(range);
    cursor = cut;
    while (cursor < end && /\s/.test(text[cursor])) cursor += 1;
  }
  const remainder = trimRange(text, cursor, end);
  if (remainder) ranges.push(remainder);
  return ranges;
}

function normalizeInlineMarkup(text: string): string {
  return text
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/(\*{1,3}|_{1,3})(.*?)\1/g, "$2")
    .replace(/~~(.*?)~~/g, "$1")
    .replace(/<[^>]*>/g, "")
    .replace(/\bok\b/gi, "Okay")
    .replace(/\b(?:idk|imo|lol|tbh)\b/gi, (match) => SPOKEN_SHORTHAND[match.toLowerCase()])
    .replace(/\s+/g, " ")
    .trim();
}

const CODE_INITIALISMS: Record<string, string> = {
  API: "A P I",
  CPU: "C P U",
  GPU: "G P U",
  HTML: "H T M L",
  HTTP: "H T T P",
  HTTPS: "H T T P S",
  ID: "I D",
  SQL: "S Q L",
  TTS: "T T S",
  UI: "U I",
  URL: "U R L",
};

function speakCodeIdentifier(identifier: string): string {
  if (CODE_INITIALISMS[identifier]) return CODE_INITIALISMS[identifier];
  return identifier
    .replace(/_/g, " ")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2");
}

export function normalizeCodeForSpeech(codeLine: string): string {
  let spoken = codeLine.trim();
  if (!spoken) return "";
  spoken = spoken
    .replace(/^\/\/\s*/, "Comment, ")
    .replace(/^#\s*/, "Comment, ")
    .replace(/[A-Za-z_$][\w$]*/g, speakCodeIdentifier)
    .replace(/!==/g, " does not strictly equal ")
    .replace(/===/g, " strictly equals ")
    .replace(/!=/g, " does not equal ")
    .replace(/==/g, " equals ")
    .replace(/=>/g, " maps to ")
    .replace(/>=/g, " greater than or equal to ")
    .replace(/<=/g, " less than or equal to ")
    .replace(/&&/g, " and ")
    .replace(/\|\|/g, " or ")
    .replace(/(?<=[A-Za-z_$])\.(?=[A-Za-z_$])/g, " dot ")
    .replace(/=/g, " equals ")
    .replace(/\+/g, " plus ")
    .replace(/\*/g, " times ")
    .replace(/\//g, " slash ")
    .replace(/[()[\]{};,:'"`]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return spoken;
}

function codeSegments(
  input: string,
  block: SpeechBlock,
  firstId: number,
  skipCodeBlocks: boolean,
): SpeechSegment[] {
  const sourceStart = block.lines[0].start;
  const sourceEnd = block.lines[block.lines.length - 1].end;
  if (skipCodeBlocks) {
    return [{
      id: `segment-${firstId}`,
      sourceText: input.slice(sourceStart, sourceEnd),
      spokenText: "Code block skipped.",
      kind: "code",
      pauseAfterMs: FINAL_PAUSE_MS.code,
      sourceStart,
      sourceEnd,
    }];
  }

  const hasClosingFence = block.lines.length > 1 && isFence(block.lines[block.lines.length - 1]);
  const bodyLines = block.lines.slice(1, hasClosingFence ? -1 : undefined);
  const segments: SpeechSegment[] = [{
    id: `segment-${firstId}`,
    sourceText: input.slice(block.lines[0].start, block.lines[0].end),
    spokenText: "Code block.",
    kind: "code",
    pauseAfterMs: 220,
    sourceStart: block.lines[0].start,
    sourceEnd: block.lines[0].end,
  }];

  for (const line of bodyLines) {
    const spokenLine = normalizeCodeForSpeech(line.text);
    if (!spokenLine) continue;
    const chunks = boundRange(spokenLine, 0, spokenLine.length, MAX_SPEECH_SEGMENT_CHARS);
    for (const [start, end] of chunks) {
      segments.push({
        id: `segment-${firstId + segments.length}`,
        sourceText: input.slice(line.start, line.end),
        spokenText: spokenLine.slice(start, end),
        kind: "code",
        pauseAfterMs: 180,
        sourceStart: line.start,
        sourceEnd: line.end,
      });
    }
  }

  const closingLine = hasClosingFence
    ? block.lines[block.lines.length - 1]
    : block.lines[block.lines.length - 1];
  segments.push({
    id: `segment-${firstId + segments.length}`,
    sourceText: input.slice(closingLine.start, closingLine.end),
    spokenText: "End code block.",
    kind: "code",
    pauseAfterMs: FINAL_PAUSE_MS.code,
    sourceStart: closingLine.start,
    sourceEnd: closingLine.end,
  });
  return segments;
}

function internalPauseMs(spokenText: string): number {
  // Informal fragments such as “Okay..” and “What if..” carry an explicit
  // thought break that should be longer than an ordinary sentence boundary.
  return /\.{2,}["')\]]?$/.test(spokenText) ? 320 : 120;
}

function segmentsForBlock(
  input: string,
  block: SpeechBlock,
  firstId: number,
  options: SpeechPlannerOptions,
): SpeechSegment[] {
  if (block.kind === "code") {
    return codeSegments(input, block, firstId, options.skipCodeBlocks ?? false);
  }

  const mapped = mapBlock(block);
  const ranges = sentenceRanges(mapped.text).flatMap(([start, end]) =>
    boundRange(mapped.text, start, end, MAX_SPEECH_SEGMENT_CHARS)
  );

  return ranges.flatMap(([start, end], index) => {
    const spokenText = normalizeInlineMarkup(mapped.text.slice(start, end));
    if (!spokenText) return [];
    const sourceStart = mapped.sourcePositions[start];
    const sourceEnd = mapped.sourcePositions[end - 1] + 1;
    const isLast = index === ranges.length - 1;
    return [{
      id: `segment-${firstId + index}`,
      sourceText: input.slice(sourceStart, sourceEnd),
      spokenText,
      kind: ranges.length > 1 && !isLast ? "sentence" : block.kind,
      pauseAfterMs: isLast ? FINAL_PAUSE_MS[block.kind] : internalPauseMs(spokenText),
      sourceStart,
      sourceEnd,
    } satisfies SpeechSegment];
  });
}

export function planTextForTTS(
  input: string,
  options: SpeechPlannerOptions = {},
): SpeechSegment[] {
  if (!input.trim()) return [];

  const segments: SpeechSegment[] = [];
  for (const block of parseBlocks(input)) {
    const planned = segmentsForBlock(input, block, segments.length, options);
    segments.push(...planned);
  }
  return segments.map((segment, index) => ({ ...segment, id: `segment-${index}` }));
}
