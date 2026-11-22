/**
 * Props for a field that holds an identifier, not prose (ticker, CUSIP, CIK, URL, API key,
 * a search query): no browser autofill, no autocorrect, no auto-capitalisation, no spell
 * check, so a phone keyboard never rewrites "nvda" or flags "CUSIP" as a typo.
 */
export const IDENTIFIER_INPUT = {
  autoComplete: "off",
  autoCorrect: "off",
  autoCapitalize: "none",
  spellCheck: false,
} as const;

/** A search box: the identifier props plus a "search" Enter key on phone keyboards. */
export const SEARCH_INPUT = { ...IDENTIFIER_INPUT, enterKeyHint: "search" } as const;
