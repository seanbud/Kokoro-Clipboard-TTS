export const DEFAULT_SHORTCUT_MAC = "Control+Option+R";
export const DEFAULT_SHORTCUT_WIN = "Super+Shift+Q";

export function getPlatformDefaultShortcut(
  userAgent: string = navigator.userAgent,
): string {
  return userAgent.includes("Mac")
    ? DEFAULT_SHORTCUT_MAC
    : DEFAULT_SHORTCUT_WIN;
}
