export type ClipboardPayload = {
  text?: string | null;
  html?: string | null;
};

const IGNORED_HTML_TAGS = new Set([
  "script",
  "style",
  "noscript",
  "svg",
  "canvas",
  "template",
]);

function renderChildren(element: Element): string {
  return Array.from(element.childNodes).map(renderNode).join("");
}

function renderNode(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return node.nodeValue ?? "";
  if (node.nodeType !== Node.ELEMENT_NODE) return "";

  const element = node as Element;
  const tag = element.tagName.toLowerCase();
  if (IGNORED_HTML_TAGS.has(tag)) return "";

  const content = renderChildren(element);
  if (/^h[1-6]$/.test(tag)) {
    return `\n\n${"#".repeat(Number(tag[1]))} ${content}\n\n`;
  }
  if (tag === "p" || tag === "section" || tag === "article") {
    return `\n\n${content}\n\n`;
  }
  if (tag === "blockquote") return `\n\n> ${element.textContent ?? ""}\n\n`;
  if (tag === "br") return "\n\n";
  if (tag === "div") return `\n${content}\n`;
  if (tag === "li") {
    const parent = element.parentElement;
    const ordered = parent?.tagName.toLowerCase() === "ol";
    const siblings = parent
      ? Array.from(parent.children).filter((child) => child.tagName.toLowerCase() === "li")
      : [];
    const marker = ordered ? `${siblings.indexOf(element) + 1}.` : "-";
    return `\n${marker} ${content}\n`;
  }
  if (tag === "ul" || tag === "ol") return `\n${content}\n`;
  if (tag === "pre") return `\n\n\`\`\`\n${element.textContent ?? ""}\n\`\`\`\n\n`;
  if (tag === "tr") return `\n${content}\n`;
  if (tag === "td" || tag === "th") return `${content} `;
  return content;
}

function normalizeStructuredText(value: string): string {
  return value
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n[ \t]+/g, "\n")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function canonicalWords(value: string): string {
  return value
    .normalize("NFC")
    .replace(/^\s*```[^\n]*$/gm, " ")
    .replace(/^\s*(?:#{1,6}\s+|[-+*•]\s+|\d+[.)]\s+|>\s*)/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Prefer semantic HTML boundaries only when its visible words agree with the
 * plain-text clipboard representation. This keeps rich clipboard recovery a
 * structural hint, never a content-rewriting step.
 */
export function structuredClipboardText(payload: ClipboardPayload): string {
  const plainText = normalizeStructuredText(payload.text ?? "");
  if (!payload.html?.trim() || typeof DOMParser === "undefined") return plainText;

  const document = new DOMParser().parseFromString(payload.html, "text/html");
  const structured = normalizeStructuredText(renderChildren(document.body));
  if (!structured) return plainText;
  if (!plainText) return structured;
  if (canonicalWords(structured) !== canonicalWords(plainText)) return plainText;

  const carriesStructure = /\n|^\s*(?:#{1,6}|[-+*]|\d+[.)]|>)/m.test(structured);
  return carriesStructure ? structured : plainText;
}
