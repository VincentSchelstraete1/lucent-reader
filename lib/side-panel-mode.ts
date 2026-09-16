// Browser-profile preference for the separate-window presentation. People can
// select it explicitly, and Lucent can also enable it after a browser such as
// Arc reports native-panel success without actually creating a side panel.
// The source marker lets us distinguish that automatic choice from a manual
// preference and safely discard values written by the older, overly eager
// Chrome detection.

export const USE_POPUP_FALLBACK_STORAGE_KEY = "usePopupFallback"
export const POPUP_FALLBACK_SOURCE_STORAGE_KEY = "popupFallbackSource"
export const DEFAULT_USE_POPUP_FALLBACK = false

export type PopupFallbackSource = "manual" | "detected"

export async function getUsePopupFallback(): Promise<boolean> {
  const stored = await chrome.storage.local.get([
    USE_POPUP_FALLBACK_STORAGE_KEY,
    POPUP_FALLBACK_SOURCE_STORAGE_KEY
  ])
  const enabled = stored[USE_POPUP_FALLBACK_STORAGE_KEY] ?? DEFAULT_USE_POPUP_FALLBACK
  const source = stored[POPUP_FALLBACK_SOURCE_STORAGE_KEY]

  // Earlier releases stored only a boolean. Chrome could receive `true` after
  // a false-negative context check, leaving every later click stuck in the
  // popup fallback. Reset that ambiguous legacy value once and detect again
  // with the reliable panel-open signal.
  if (enabled && source !== "manual" && source !== "detected") {
    await chrome.storage.local.set({
      [USE_POPUP_FALLBACK_STORAGE_KEY]: DEFAULT_USE_POPUP_FALLBACK,
      [POPUP_FALLBACK_SOURCE_STORAGE_KEY]: "manual"
    })
    return DEFAULT_USE_POPUP_FALLBACK
  }

  return enabled
}

export async function setUsePopupFallback(
  enabled: boolean,
  source: PopupFallbackSource = "manual"
): Promise<void> {
  await chrome.storage.local.set({
    [USE_POPUP_FALLBACK_STORAGE_KEY]: enabled,
    [POPUP_FALLBACK_SOURCE_STORAGE_KEY]: source
  })
}
