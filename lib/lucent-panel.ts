// Centralizes how Lucent's main interface (sidepanel.tsx / sidepanel.html)
// opens - the toolbar icon's chrome.action.onClicked handler and the
// on-page top-right toggle (via OPEN_SIDE_PANEL_MESSAGE_TYPE) both just
// call openLucent(windowId); everything else lives here instead of
// scattered across background.ts.
import {
  USE_POPUP_FALLBACK_STORAGE_KEY,
  DEFAULT_USE_POPUP_FALLBACK,
  getUsePopupFallback,
  setUsePopupFallback
} from "./side-panel-mode"

// Cached in memory rather than read fresh from chrome.storage.local on
// every click - chrome.sidePanel.open() has a hard requirement that it's
// called *synchronously* within the user-gesture handler that triggered
// it, and even a single `await chrome.storage.local.get(...)` beforehand
// is enough to make Chrome silently reject the call (confirmed directly:
// this is exactly what broke the real side panel in Chrome the first
// time this preference was read fresh, awaited, before calling it).
let cachedUsePopupFallback = DEFAULT_USE_POPUP_FALLBACK

// MV3 service workers cold-start on the very event that wakes them - if
// the toolbar icon is clicked after the worker's been idle and torn
// down, the click that restarts this script and the click delivered to
// chrome.action.onClicked are (from the extension's perspective) nearly
// the same moment, while chrome.storage.local.get() below is a real IPC
// round-trip. So this promise settling is not guaranteed to happen
// before the very first click after a cold start gets processed -
// openLucent()'s "correction" step below exists specifically for that
// window, rather than assuming this always wins the race.
let usePopupFallbackLoaded = false
const usePopupFallbackReady = getUsePopupFallback().then((v) => {
  cachedUsePopupFallback = v
  usePopupFallbackLoaded = true
  return v
})

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && USE_POPUP_FALLBACK_STORAGE_KEY in changes) {
    cachedUsePopupFallback = changes[USE_POPUP_FALLBACK_STORAGE_KEY].newValue ?? DEFAULT_USE_POPUP_FALLBACK
    usePopupFallbackLoaded = true
  }
})

// True feature detection - no browser-name checks, just "does this
// function exist at all." On its own this isn't sufficient (see below),
// but it's the part that's a legitimate capability check: it correctly
// excludes any browser with no side panel API surface whatsoever.
function hasSidePanelApi(): boolean {
  return typeof chrome.sidePanel?.open === "function"
}

// Named for what it actually decides, not "is the API present". Arc exposes
// chrome.sidePanel.open() and resolves it without actually creating a side
// panel. We therefore verify the resulting panel below instead of treating the
// resolved promise as proof that the UI opened.
export function shouldUseNativeSidePanel(): boolean {
  return hasSidePanelApi() && !cachedUsePopupFallback
}

type SidePanelOpenedInfo = {
  path: string
  windowId: number
}

type SidePanelOpenedEvent = {
  addListener: (callback: (info: SidePanelOpenedInfo) => void) => void
  removeListener: (callback: (info: SidePanelOpenedInfo) => void) => void
}

type SidePanelWithOpenedEvent = typeof chrome.sidePanel & {
  onOpened?: SidePanelOpenedEvent
}

type RuntimeContext = {
  contextType: string
  documentUrl?: string
  windowId: number
}

type RuntimeWithContexts = typeof chrome.runtime & {
  getContexts?: (filter: {
    contextTypes?: string[]
    documentUrls?: string[]
    windowIds?: number[]
  }) => Promise<RuntimeContext[]>
}

const NATIVE_PANEL_CHECK_ATTEMPTS = 5
const NATIVE_PANEL_CHECK_INTERVAL_MS = 100
const NATIVE_PANEL_OPEN_EVENT_TIMEOUT_MS = 500
const POPUP_FALLBACK_WIDTH = 220

const wait = (durationMs: number) => new Promise((resolve) => setTimeout(resolve, durationMs))

async function nativePanelContextAppeared(windowId: number): Promise<boolean> {
  const getContexts = (chrome.runtime as RuntimeWithContexts).getContexts
  if (typeof getContexts !== "function") return true

  const documentUrl = chrome.runtime.getURL("sidepanel.html")
  for (let attempt = 0; attempt < NATIVE_PANEL_CHECK_ATTEMPTS; attempt += 1) {
    const contexts = await getContexts.call(chrome.runtime, {
      contextTypes: ["SIDE_PANEL"]
    })
    if (contexts.some((context) =>
      context.contextType === "SIDE_PANEL" &&
      context.documentUrl === documentUrl &&
      (context.windowId === windowId || context.windowId === -1)
    )) return true
    if (attempt < NATIVE_PANEL_CHECK_ATTEMPTS - 1) await wait(NATIVE_PANEL_CHECK_INTERVAL_MS)
  }
  return false
}

type NativePanelOpenedWatcher = {
  result: Promise<boolean>
  cancel: () => void
}

// Chrome 141+ provides an explicit event when the side panel is visible. Start
// listening before sidePanel.open() so a fast open cannot race past us. This is
// materially more reliable than querying runtime contexts immediately after
// the open promise resolves (the old query could lag and open both UIs).
function watchForNativePanelOpened(windowId: number): NativePanelOpenedWatcher | null {
  const onOpened = (chrome.sidePanel as SidePanelWithOpenedEvent).onOpened
  if (!onOpened || typeof onOpened.addListener !== "function") return null

  let finish: (opened: boolean) => void = () => {}
  let timer: ReturnType<typeof setTimeout> | undefined
  const result = new Promise<boolean>((resolve) => {
    let settled = false
    const listener = (info: SidePanelOpenedInfo) => {
      if (info.windowId !== windowId || !info.path.endsWith("sidepanel.html")) return
      finish(true)
    }
    finish = (opened) => {
      if (settled) return
      settled = true
      if (timer !== undefined) clearTimeout(timer)
      onOpened.removeListener(listener)
      resolve(opened)
    }
    onOpened.addListener(listener)
    timer = setTimeout(() => finish(false), NATIVE_PANEL_OPEN_EVENT_TIMEOUT_MS)
  })

  return { result, cancel: () => finish(false) }
}

async function rememberPopupFallback(): Promise<void> {
  cachedUsePopupFallback = true
  usePopupFallbackLoaded = true
  await setUsePopupFallback(true, "detected")
}

// Reuses sidepanel.html as-is (it has no dependency on actually being a
// side panel) rendered in a small popup window instead. Anchored to the
// calling window's own right edge, matching its height, so it looks
// like a docked panel rather than an arbitrary window - plain
// width/height alone weren't enough in Arc (it opened full-size instead
// of the requested dimensions without an explicit left/top).
async function openPopupFallback(windowId: number) {
  try {
    console.log("[Lucent] opening popup window fallback")
    const createOptions: chrome.windows.CreateData = {
      url: chrome.runtime.getURL("sidepanel.html"),
      type: "popup",
      width: POPUP_FALLBACK_WIDTH,
      height: 640
    }

    try {
      const parentWindow = await chrome.windows.get(windowId)
      if (
        parentWindow.left !== undefined &&
        parentWindow.top !== undefined &&
        parentWindow.width !== undefined &&
        parentWindow.height !== undefined
      ) {
        createOptions.left = parentWindow.left + parentWindow.width - createOptions.width!
        createOptions.top = parentWindow.top
        createOptions.height = parentWindow.height
      }
    } catch (err) {
      console.error("[Lucent] couldn't read the parent window's bounds, using defaults", err)
    }

    const win = await chrome.windows.create(createOptions)
    console.log("[Lucent] chrome.windows.create resolved", win)
  } catch (err) {
    console.error("Lucent: popup window fallback failed, opening a tab instead", err)
    chrome.tabs.create({ url: chrome.runtime.getURL("sidepanel.html") }).then(
      (t) => console.log("[Lucent] chrome.tabs.create resolved", t),
      (e) => console.error("[Lucent] chrome.tabs.create ALSO failed", e)
    )
  }
}

// NOT async, and chrome.sidePanel.open() is called as the very first
// thing with nothing awaited before it - see the comment on
// cachedUsePopupFallback above for why that matters.
export function openLucent(windowId: number): void {
  const usedNative = shouldUseNativeSidePanel()
  console.log("[Lucent] openLucent called", { windowId, hasSidePanelApi: hasSidePanelApi(), usedNative })

  if (usedNative) {
    const openedWatcher = watchForNativePanelOpened(windowId)
    chrome.sidePanel.open({ windowId }).then(
      async () => {
        console.log("[Lucent] chrome.sidePanel.open() resolved; verifying the visible panel")
        try {
          const panelOpened = openedWatcher
            ? await openedWatcher.result
            : await nativePanelContextAppeared(windowId)
          if (!panelOpened) {
            console.warn("[Lucent] native side panel did not become visible; opening popup fallback")
            // Browsers without the explicit opened event use the runtime-context
            // fallback. Remember that result so Arc opens quickly next time. If
            // an event-capable browser merely reports late, fall back for this
            // click without permanently forcing Chrome into popup mode.
            if (!openedWatcher) await rememberPopupFallback()
            openPopupFallback(windowId)
          }
        } catch (err) {
          console.error("Lucent: couldn't verify the native side panel, falling back to a window", err)
          openPopupFallback(windowId)
        }
      },
      (err) => {
        openedWatcher?.cancel()
        console.error("Lucent: sidePanel.open() failed, falling back to a window", err)
        openPopupFallback(windowId)
      }
    )
  } else {
    openPopupFallback(windowId)
  }

  // Cold-start race correction (see usePopupFallbackLoaded above): if the
  // preference hadn't actually finished loading yet when the decision
  // above was made - so it ran on the default (native) - and it turns
  // out the user really had the fallback turned on, open the fallback
  // now too. A same-click extra window right after a cold start is a far
  // better outcome than a silent no-op in Arc.
  if (!usePopupFallbackLoaded) {
    usePopupFallbackReady.then((resolvedValue) => {
      if (resolvedValue && usedNative) {
        console.warn("[Lucent] usePopupFallback resolved true after a cold-start race - opening the fallback now")
        openPopupFallback(windowId)
      }
    })
  }
}
