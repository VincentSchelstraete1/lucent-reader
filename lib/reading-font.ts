// Shared source of truth for the page-content reading font control.
// Same chrome.storage.local pattern as text-spacing.ts.
//
// Each option has a loading "strategy", since the three kinds of fonts
// here need genuinely different delivery mechanisms:
//  - "system": already installed on virtually every OS - just a
//    font-family value, nothing to load at all.
//  - "google": loaded on demand via a Google Fonts stylesheet <link>,
//    the same mechanism loadReadingFont() already uses in
//    contents/struggle-detector.ts for the Reading Mode overlay's font.
//  - "bundled": self-hosted inside the extension itself
//    (assets/fonts/) - used for OpenDyslexic specifically, since it
//    isn't available on Google Fonts. Referenced via data-base64:
//    imports in struggle-detector.ts so the font ships inline with the
//    extension bundle - no runtime network request, works offline, and
//    isn't subject to a page's Content-Security-Policy the way an
//    external stylesheet link can be.
//
// Font choices: OpenDyslexic was explicitly requested. The rest were
// picked for having a real, specific reason to help reading -
// Atkinson Hyperlegible (designed by the Braille Institute to maximize
// letterform distinction for low vision) and Lexend (Google-backed
// research showing measurable reading-speed/comprehension gains) are
// the two purpose-built-for-reading Google Fonts; Verdana, Tahoma, and
// Arial are the wide-letterform system fonts most commonly recommended
// in dyslexia style guides (e.g. the British Dyslexia Association's);
// Comic Neue is an open, less-cartoonish alternative to Comic Sans,
// whose irregular letterforms are frequently cited as easier for some
// dyslexic readers to tell apart (b/d/p/q) than a geometric sans.

export const FONT_OPTIONS = [
  {
    value: "default",
    label: "Default",
    cssFontFamily: "",
    strategy: "system"
  },
  {
    value: "opendyslexic",
    label: "OpenDyslexic",
    cssFontFamily: "'OpenDyslexic', sans-serif",
    strategy: "bundled"
  },
  {
    value: "atkinson",
    label: "Atkinson Hyperlegible",
    cssFontFamily: "'Atkinson Hyperlegible', sans-serif",
    strategy: "google",
    googleFontParam: "Atkinson+Hyperlegible"
  },
  {
    value: "lexend",
    label: "Lexend",
    cssFontFamily: "'Lexend', sans-serif",
    strategy: "google",
    googleFontParam: "Lexend"
  },
  {
    value: "comic-neue",
    label: "Comic Neue",
    cssFontFamily: "'Comic Neue', sans-serif",
    strategy: "google",
    googleFontParam: "Comic+Neue"
  },
  {
    value: "verdana",
    label: "Verdana",
    cssFontFamily: "Verdana, Geneva, sans-serif",
    strategy: "system"
  },
  {
    value: "tahoma",
    label: "Tahoma",
    cssFontFamily: "Tahoma, Geneva, sans-serif",
    strategy: "system"
  },
  {
    value: "arial",
    label: "Arial",
    cssFontFamily: "Arial, Helvetica, sans-serif",
    strategy: "system"
  }
] as const

export type ReadingFont = (typeof FONT_OPTIONS)[number]["value"]

export const DEFAULT_READING_FONT: ReadingFont = "default"

export const READING_FONT_STORAGE_KEY = "readingFont"

export async function getReadingFont(): Promise<ReadingFont> {
  const stored = await chrome.storage.local.get(READING_FONT_STORAGE_KEY)
  return stored[READING_FONT_STORAGE_KEY] ?? DEFAULT_READING_FONT
}

export async function setReadingFont(font: ReadingFont): Promise<void> {
  await chrome.storage.local.set({ [READING_FONT_STORAGE_KEY]: font })
}
