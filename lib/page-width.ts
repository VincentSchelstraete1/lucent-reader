// Reading Mode's content column width - same chrome.storage.local
// pattern as text-spacing.ts, three discrete widths rather than a
// continuous slider.

export const PAGE_WIDTH_OPTIONS = [
  { value: "narrow", label: "Narrow", maxWidth: "560px" },
  { value: "medium", label: "Medium", maxWidth: "680px" },
  { value: "wide", label: "Wide", maxWidth: "860px" }
] as const

export type PageWidth = (typeof PAGE_WIDTH_OPTIONS)[number]["value"]

export const DEFAULT_PAGE_WIDTH: PageWidth = "medium"

export const PAGE_WIDTH_STORAGE_KEY = "pageWidth"

export async function getPageWidth(): Promise<PageWidth> {
  const stored = await chrome.storage.local.get(PAGE_WIDTH_STORAGE_KEY)
  return stored[PAGE_WIDTH_STORAGE_KEY] ?? DEFAULT_PAGE_WIDTH
}

export async function setPageWidth(width: PageWidth): Promise<void> {
  await chrome.storage.local.set({ [PAGE_WIDTH_STORAGE_KEY]: width })
}
