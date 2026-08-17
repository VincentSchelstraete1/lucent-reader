import { useEffect, useState } from "react"

import {
  DEFAULT_AUTO_ACTIVATE_ENABLED,
  DEFAULT_FONT_OVERRIDE_ENABLED,
  getAutoActivateEnabled,
  getFontOverrideEnabled,
  setAutoActivateEnabled,
  setFontOverrideEnabled
} from "~lib/extension-settings"
import {
  MANUAL_ACTIVATE_MESSAGE_TYPE,
  type ManualActivateResponse
} from "~lib/messages"

const tokens = {
  readingBg: "#F5F1E8",
  readingText: "#2C2C2A",
  accentTeal: "#1D9E75",
  captionText: "#5E5E5B"
}

type Tab = "home" | "settings"

function TabButton({
  label,
  active,
  onClick
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1,
        padding: "8px 0",
        border: "none",
        borderBottom: `2px solid ${active ? tokens.accentTeal : "transparent"}`,
        backgroundColor: "transparent",
        color: active ? tokens.readingText : tokens.captionText,
        fontWeight: active ? 600 : 400,
        fontSize: 13,
        cursor: "pointer"
      }}>
      {label}
    </button>
  )
}

function ToggleRow({
  label,
  description,
  enabled,
  onChange
}: {
  label: string
  description: string
  enabled: boolean
  onChange: (next: boolean) => void
}) {
  return (
    <div style={{ padding: "10px 2px" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12
        }}>
        <span style={{ fontSize: 14, color: tokens.readingText }}>{label}</span>
        <button
          onClick={() => onChange(!enabled)}
          style={{
            padding: "6px 12px",
            borderRadius: 20,
            border: "none",
            fontSize: 12,
            cursor: "pointer",
            backgroundColor: enabled ? tokens.accentTeal : tokens.captionText,
            color: "#FFFFFF"
          }}>
          {enabled ? "On" : "Off"}
        </button>
      </div>
      <p
        style={{
          fontSize: 12,
          color: tokens.captionText,
          margin: "4px 0 0",
          lineHeight: 1.4
        }}>
        {description}
      </p>
    </div>
  )
}

function IndexPopup() {
  const [tab, setTab] = useState<Tab>("home")
  const [fontOverrideEnabled, setFontOverrideEnabledState] = useState(
    DEFAULT_FONT_OVERRIDE_ENABLED
  )
  const [autoActivateEnabled, setAutoActivateEnabledState] = useState(
    DEFAULT_AUTO_ACTIVATE_ENABLED
  )
  const [activateStatus, setActivateStatus] = useState<string | null>(null)
  const [activating, setActivating] = useState(false)

  useEffect(() => {
    getFontOverrideEnabled().then(setFontOverrideEnabledState)
    getAutoActivateEnabled().then(setAutoActivateEnabledState)
  }, [])

  async function handleFontOverrideChange(next: boolean) {
    setFontOverrideEnabledState(next)
    await setFontOverrideEnabled(next)
  }

  async function handleAutoActivateChange(next: boolean) {
    setAutoActivateEnabledState(next)
    await setAutoActivateEnabled(next)
  }

  async function handleActivateClick() {
    setActivating(true)
    setActivateStatus(null)
    try {
      const [activeTab] = await chrome.tabs.query({
        active: true,
        currentWindow: true
      })
      if (!activeTab?.id) {
        setActivateStatus("Couldn't find the current tab.")
        return
      }

      const response = (await chrome.tabs.sendMessage(activeTab.id, {
        type: MANUAL_ACTIVATE_MESSAGE_TYPE
      })) as ManualActivateResponse

      if (response.ok) {
        setActivateStatus(
          response.alreadyActive
            ? "Already active on this page."
            : "Activated! Look for the Aa button on the page."
        )
      } else {
        setActivateStatus(
          "Lucent Reader never activates on pages with a sign-in or payment field, for your safety."
        )
      }
    } catch {
      // No content script listening - most often a page that hasn't
      // reloaded since install, or a page the extension can't run on
      // at all (chrome:// pages, the Chrome Web Store, etc.).
      setActivateStatus("Couldn't reach this page. Try reloading it first.")
    } finally {
      setActivating(false)
    }
  }

  return (
    <div
      style={{
        width: 280,
        backgroundColor: tokens.readingBg,
        fontFamily: "Inter, sans-serif"
      }}>
      <div style={{ padding: "16px 16px 0" }}>
        <h2 style={{ fontSize: 16, color: tokens.readingText, margin: "0 0 12px" }}>
          Lucent Reader
        </h2>
      </div>

      <div style={{ display: "flex", padding: "0 16px", gap: 8 }}>
        <TabButton label="Home" active={tab === "home"} onClick={() => setTab("home")} />
        <TabButton
          label="Settings"
          active={tab === "settings"}
          onClick={() => setTab("settings")}
        />
      </div>

      <div style={{ padding: 16 }}>
        {tab === "home" && (
          <div>
            <p
              style={{
                fontSize: 12,
                color: tokens.captionText,
                margin: "0 0 12px",
                lineHeight: 1.4
              }}>
              Lucent Reader activates automatically on pages it detects as
              readable. If it didn't on this page - or auto-activate is
              turned off in Settings - you can start it manually here.
            </p>
            <button
              onClick={handleActivateClick}
              disabled={activating}
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: 20,
                border: "none",
                backgroundColor: tokens.accentTeal,
                color: "#FFFFFF",
                fontSize: 14,
                cursor: activating ? "default" : "pointer",
                opacity: activating ? 0.7 : 1
              }}>
              {activating ? "Activating..." : "Activate on this page"}
            </button>
            {activateStatus && (
              <p
                style={{
                  fontSize: 12,
                  color: tokens.captionText,
                  marginTop: 10,
                  lineHeight: 1.4
                }}>
                {activateStatus}
              </p>
            )}
          </div>
        )}

        {tab === "settings" && (
          <div>
            <ToggleRow
              label="Dyslexia-friendly font"
              description="Applies the font chosen in the Aa menu (OpenDyslexic and others) to page text. Off by default - the Aa menu's font choice is remembered either way, it just won't render until this is on."
              enabled={fontOverrideEnabled}
              onChange={handleFontOverrideChange}
            />
            <ToggleRow
              label="Auto-activate on readable pages"
              description="When on, Lucent Reader turns itself on automatically on pages it detects as readable. When off, use the Activate on this page button in the Home tab instead."
              enabled={autoActivateEnabled}
              onChange={handleAutoActivateChange}
            />
          </div>
        )}
      </div>
    </div>
  )
}

export default IndexPopup
