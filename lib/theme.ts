// Reading-mode color theme (light/dark) - same chrome.storage.local
// pattern as reading-font.ts/text-spacing.ts. Only affects Reading Mode's
// overlay and the bottom Reading Controls bar, not the rest of the page.

export const READING_THEME_OPTIONS = [
  {
    value: "light",
    label: "Light",
    bg: "#F5F1E8",
    text: "#2C2C2A",
    surface: "#FFFFFF",
    caption: "#5E5E5B",
    codeBg: "#EAE6D9"
  },
  {
    value: "dark",
    label: "Dark",
    bg: "#1E1F1C",
    text: "#ECE8DE",
    surface: "#2A2B27",
    caption: "#A8A59C",
    codeBg: "#33342F"
  }
] as const

export type ReadingTheme = (typeof READING_THEME_OPTIONS)[number]["value"]

export const DEFAULT_READING_THEME: ReadingTheme = "light"

export const READING_THEME_STORAGE_KEY = "readingTheme"

export async function getReadingTheme(): Promise<ReadingTheme> {
  const stored = await chrome.storage.local.get(READING_THEME_STORAGE_KEY)
  return stored[READING_THEME_STORAGE_KEY] ?? DEFAULT_READING_THEME
}

export async function setReadingTheme(theme: ReadingTheme): Promise<void> {
  await chrome.storage.local.set({ [READING_THEME_STORAGE_KEY]: theme })
}

export function getThemeTokens(theme: ReadingTheme) {
  return READING_THEME_OPTIONS.find((o) => o.value === theme) ?? READING_THEME_OPTIONS[0]
}
