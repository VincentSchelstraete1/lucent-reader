import { useEffect, useState } from "react"

import { WEB_APP_URL } from "~lib/config"
import {
  DEFAULT_AUTO_ACTIVATE_ENABLED,
  DEFAULT_FONT_OVERRIDE_ENABLED,
  getAutoActivateEnabled,
  getFontOverrideEnabled,
  setAutoActivateEnabled,
  setFontOverrideEnabled
} from "~lib/extension-settings"
import { getInstallId } from "~lib/install-id"
import {
  MANUAL_ACTIVATE_MESSAGE_TYPE,
  type ManualActivateResponse,
  GET_SELECTION_MESSAGE_TYPE,
  type GetSelectionMessage,
  type GetSelectionResponse,
  REPLACE_SELECTION_MESSAGE_TYPE,
  type ReplaceSelectionMessage,
  type ReplaceSelectionResponse,
  SIMPLIFY_MESSAGE_TYPE,
  type SimplifyMessage,
  type SimplifyResponse,
  EXPLAIN_MESSAGE_TYPE,
  type ExplainMessage,
  type ExplainResponse,
  SUMMARIZE_MESSAGE_TYPE,
  type SummarizeMessage,
  type SummarizeResponse,
  ENSURE_DOCUMENT_MESSAGE_TYPE,
  type EnsureDocumentMessage,
  type EnsureDocumentResponse,
  SAVE_NOTE_MESSAGE_TYPE,
  AUTH_STATUS_MESSAGE_TYPE,
  AUTH_LOGIN_MESSAGE_TYPE,
  AUTH_LOGOUT_MESSAGE_TYPE,
  type AuthStatusResponse,
  type SaveNoteMessage,
  type SaveNoteResponse
} from "~lib/messages"
import {
  VALID_GRADE_LEVELS,
  DEFAULT_GRADE_LEVEL,
  getTargetGradeLevel,
  setTargetGradeLevel,
  getTierLabel
} from "~lib/reading-level"
import { DEFAULT_TEXT_LENGTH, getTargetLength, setTargetLength, type TextLength } from "~lib/text-length"

const tokens = {
  readingBg: "#F5F1E8",
  readingText: "#2C2C2A",
  accentTeal: "#1D9E75",
  badgeDoneBg: "#EEEDFE",
  badgeDoneText: "#26215C",
  captionText: "#5E5E5B",
  errorBg: "#FBEAEA",
  errorText: "#8A2E2E"
}

type Tab = "assist" | "notes" | "settings"

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
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
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
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
      <p style={{ fontSize: 12, color: tokens.captionText, margin: "4px 0 0", lineHeight: 1.4 }}>
        {description}
      </p>
    </div>
  )
}

async function getActiveTab(): Promise<chrome.tabs.Tab | null> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  return tab ?? null
}

async function getSelectionFromPage(): Promise<GetSelectionResponse | null> {
  const tab = await getActiveTab()
  if (!tab?.id) return null
  try {
    const message: GetSelectionMessage = { type: GET_SELECTION_MESSAGE_TYPE }
    return (await chrome.tabs.sendMessage(tab.id, message)) as GetSelectionResponse
  } catch {
    return null
  }
}

type QuickAction = "simplify" | "explain" | "summarize"
type SelectionSnapshot = {
  text: string
  context: string
  pageTitle: string
  url: string
}

const QUICK_ACTION_LABELS: Record<QuickAction, string> = {
  simplify: "Simplify",
  explain: "Explain this",
  summarize: "Summarize this section"
}

function SidePanel() {
  const [tab, setTab] = useState<Tab>("assist")
  const [auth, setAuth] = useState<{ loading: boolean; authenticated: boolean; displayName?: string; error?: string }>({ loading: true, authenticated: false })

  // Assist tab state
  const [level, setLevel] = useState(DEFAULT_GRADE_LEVEL)
  const [targetLength, setTargetLengthState] = useState<TextLength>(DEFAULT_TEXT_LENGTH)
  const [activeAction, setActiveAction] = useState<QuickAction>("simplify")
  const [resultText, setResultText] = useState("")
  const [resultSelection, setResultSelection] = useState<SelectionSnapshot | null>(null)
  const [resultError, setResultError] = useState<string | null>(null)
  const [working, setWorking] = useState(false)
  const [replaceStatus, setReplaceStatus] = useState<string | null>(null)
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle")
  const [saveError, setSaveError] = useState<string | null>(null)

  // Settings tab state
  const [fontOverrideEnabled, setFontOverrideEnabledState] = useState(DEFAULT_FONT_OVERRIDE_ENABLED)
  const [autoActivateEnabled, setAutoActivateEnabledState] = useState(DEFAULT_AUTO_ACTIVATE_ENABLED)
  const [activateStatus, setActivateStatus] = useState<string | null>(null)
  const [activating, setActivating] = useState(false)

  useEffect(() => {
    getTargetGradeLevel().then(setLevel)
    getTargetLength().then(setTargetLengthState)
    getFontOverrideEnabled().then(setFontOverrideEnabledState)
    getAutoActivateEnabled().then(setAutoActivateEnabledState)
    chrome.runtime.sendMessage({ type: AUTH_STATUS_MESSAGE_TYPE }).then((response: AuthStatusResponse) => {
      if (response.ok === false) setAuth({ loading: false, authenticated: false, error: response.error })
      else setAuth({ loading: false, authenticated: response.authenticated, displayName: response.displayName })
    })
  }, [])

  async function handleAuth() {
    setAuth((current) => ({ ...current, loading: true, error: undefined }))
    const response = await chrome.runtime.sendMessage({ type: auth.authenticated ? AUTH_LOGOUT_MESSAGE_TYPE : AUTH_LOGIN_MESSAGE_TYPE }) as AuthStatusResponse
    if (response.ok === false) setAuth({ loading: false, authenticated: false, error: response.error })
    else setAuth({ loading: false, authenticated: response.authenticated, displayName: response.displayName })
  }

  async function handleLevelChange(next: number) {
    setLevel(next)
    await setTargetGradeLevel(next)
  }

  async function runQuickAction(action: QuickAction) {
    setWorking(true)
    setActiveAction(action)
    setResultText("")
    setResultSelection(null)
    setResultError(null)
    setReplaceStatus(null)
    setSaveStatus("idle")
    setSaveError(null)

    const selection = await getSelectionFromPage()
    if (!selection || selection.ok === false) {
      setResultError("Highlight some text on the page first.")
      setWorking(false)
      return
    }
    const activeTab = await getActiveTab()
    if (!activeTab?.url) {
      setResultError("Lucent couldn't identify this page.")
      setWorking(false)
      return
    }

    try {
      const installId = await getInstallId()
      if (action === "simplify") {
        const message: SimplifyMessage = {
          type: SIMPLIFY_MESSAGE_TYPE,
          text: selection.text,
          targetGradeLevel: level,
          targetLength,
          installId
        }
        const response = (await chrome.runtime.sendMessage(message)) as SimplifyResponse
        if (response.ok === false) throw new Error(response.error)
        setResultText(response.simplified)
      } else if (action === "explain") {
        const message: ExplainMessage = {
          type: EXPLAIN_MESSAGE_TYPE,
          text: selection.text,
          context: selection.context,
          targetGradeLevel: level,
          targetLength,
          installId
        }
        const response = (await chrome.runtime.sendMessage(message)) as ExplainResponse
        if (response.ok === false) throw new Error(response.error)
        setResultText(response.explanation)
      } else {
        const message: SummarizeMessage = {
          type: SUMMARIZE_MESSAGE_TYPE,
          text: selection.context || selection.text,
          targetGradeLevel: level,
          targetLength,
          installId
        }
        const response = (await chrome.runtime.sendMessage(message)) as SummarizeResponse
        if (response.ok === false) throw new Error(response.error)
        setResultText(response.summary)
      }
      setResultSelection({ ...selection, url: activeTab.url })
    } catch (err) {
      setResultError(err instanceof Error ? err.message : "Something went wrong")
    } finally {
      setWorking(false)
    }
  }

  async function handleReplaceInPage() {
    const tab = await getActiveTab()
    if (!tab?.id || !resultText) return
    try {
      const message: ReplaceSelectionMessage = { type: REPLACE_SELECTION_MESSAGE_TYPE, text: resultText }
      const response = (await chrome.tabs.sendMessage(tab.id, message)) as ReplaceSelectionResponse
      setReplaceStatus(response.ok ? "Replaced in page." : "Nothing selected on the page anymore.")
    } catch {
      setReplaceStatus("Couldn't reach the page.")
    }
  }

  async function handleCopy() {
    if (!resultText) return
    await navigator.clipboard.writeText(resultText)
    setReplaceStatus("Copied.")
  }

  async function handleSaveToLucent() {
    setSaveStatus("saving")
    setSaveError(null)
    try {
      const currentTab = await getActiveTab()
      const currentSelection = await getSelectionFromPage()
      const selection = resultText && resultSelection
        ? resultSelection
        : currentTab?.url && currentSelection?.ok
          ? { ...currentSelection, url: currentTab.url }
          : null
      if (!selection) throw new Error("Highlight some text on the page first.")

      const ensureMessage: EnsureDocumentMessage = {
        type: ENSURE_DOCUMENT_MESSAGE_TYPE,
        url: selection.url,
        title: selection.pageTitle,
        content: selection.context
      }
      const ensureResponse = (await chrome.runtime.sendMessage(ensureMessage)) as EnsureDocumentResponse
      if (ensureResponse.ok === false) {
        throw new Error(ensureResponse.error)
      }

      const saveMessage: SaveNoteMessage = {
        type: SAVE_NOTE_MESSAGE_TYPE,
        title: selection.text.length > 80 ? `${selection.text.slice(0, 80)}…` : selection.text,
        content: resultText || selection.text,
        contentType: resultText
          ? activeAction === "explain" ? "explanation" : activeAction === "simplify" ? "simplification" : "summary"
          : "highlight",
        sourcePassage: resultText && activeAction !== "summarize" ? selection.text : undefined,
        sourceUrl: selection.url,
        documentId: ensureResponse.documentId
      }
      const saveResponse = (await chrome.runtime.sendMessage(saveMessage)) as SaveNoteResponse
      if (saveResponse.ok === false) throw new Error(saveResponse.error)
      setSaveStatus("saved")
    } catch (error) {
      setSaveStatus("error")
      setSaveError(error instanceof Error ? error.message : "Save failed. Try again.")
    }
  }

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
      const activeTab = await getActiveTab()
      if (!activeTab?.id) {
        setActivateStatus("Couldn't find the current tab.")
        return
      }

      const response = (await chrome.tabs.sendMessage(activeTab.id, {
        type: MANUAL_ACTIVATE_MESSAGE_TYPE
      })) as ManualActivateResponse

      if (response.ok) {
        setActivateStatus(
          response.alreadyActive ? "Already active on this page." : "Activated on this page."
        )
      } else {
        setActivateStatus(
          "Lucent never activates on pages with a sign-in or payment field, for your safety."
        )
      }
    } catch {
      setActivateStatus("Couldn't reach this page. Try reloading it first.")
    } finally {
      setActivating(false)
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: tokens.readingBg,
        fontFamily: "Inter, sans-serif"
      }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 16px 0"
        }}>
        <h2 style={{ fontSize: 16, color: tokens.readingText, margin: 0 }}>✦ Lucent</h2>
        {/* Native window controls aren't reliably reachable when this
            renders as a popup window instead of a real side panel (the
            popup-window fallback for browsers like Arc, where
            chrome.sidePanel exists but never actually shows anything) -
            confirmed directly that at the size that fallback uses, the
            OS window's own close control isn't reachable. window.close()
            is safe to call even when this genuinely is a side panel;
            it's just an unnecessary no-op button there. */}
        <button
          onClick={() => window.close()}
          title="Close"
          style={{
            border: "none",
            background: "transparent",
            color: tokens.captionText,
            fontSize: 16,
            cursor: "pointer",
            padding: "0 4px",
            lineHeight: 1
          }}>
          ✕
        </button>
      </div>

      <div style={{ margin: "10px 16px 0", padding: "8px 10px", border: `1px solid ${tokens.captionText}`, borderRadius: 8, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 12, color: tokens.captionText }}>{auth.authenticated ? auth.displayName || "Signed in" : "Sign in to use Lucent"}</span>
        <button onClick={handleAuth} disabled={auth.loading} style={{ ...secondaryButtonStyle, padding: "6px 10px" }}>{auth.loading ? "Checking…" : auth.authenticated ? "Sign out" : "Sign in"}</button>
      </div>
      {auth.error && <p role="alert" style={{ margin: "6px 16px 0", color: tokens.errorText, fontSize: 12 }}>{auth.error}</p>}

      <div style={{ display: "flex", padding: "12px 16px 0", gap: 8 }}>
        <TabButton label="Assist" active={tab === "assist"} onClick={() => setTab("assist")} />
        <TabButton label="Notes" active={tab === "notes"} onClick={() => setTab("notes")} />
        <TabButton label="Settings" active={tab === "settings"} onClick={() => setTab("settings")} />
      </div>

      <div style={{ padding: 16 }}>
        {tab === "assist" && (
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 12
              }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: tokens.readingText }}>
                ✦ {QUICK_ACTION_LABELS[activeAction]}
              </span>
              <select
                value={level}
                onChange={(e) => handleLevelChange(Number(e.target.value))}
                style={{
                  padding: "4px 8px",
                  borderRadius: 20,
                  border: `1px solid ${tokens.captionText}`,
                  fontSize: 12,
                  backgroundColor: "#FFFFFF",
                  color: tokens.readingText
                }}>
                {VALID_GRADE_LEVELS.map((l) => (
                  <option key={l} value={l}>
                    {getTierLabel(l)}
                  </option>
                ))}
              </select>
            </div>
            {saveError && <p style={{ fontSize: 12, color: tokens.errorText, margin: "-8px 0 12px" }}>{saveError}</p>}

            <div
              style={{
                minHeight: 120,
                maxHeight: 220,
                overflowY: "auto",
                backgroundColor: "#FFFFFF",
                border: `1px solid ${tokens.captionText}`,
                borderRadius: 10,
                padding: 12,
                fontSize: 13,
                lineHeight: 1.6,
                color: resultError ? tokens.errorText : tokens.readingText,
                marginBottom: 10,
                whiteSpace: "pre-wrap"
              }}>
              {working
                ? "Working..."
                : resultError || resultText || "Highlight text on the page, then pick an action below."}
            </div>

            <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
              <button
                onClick={handleReplaceInPage}
                disabled={!resultText || working}
                style={primaryButtonStyle(!resultText || working)}>
                Replace in page
              </button>
              <button onClick={handleCopy} disabled={!resultText} style={secondaryButtonStyle}>
                Copy
              </button>
            </div>
            {replaceStatus && (
              <p style={{ fontSize: 12, color: tokens.captionText, margin: "-8px 0 12px" }}>
                {replaceStatus}
              </p>
            )}

            <p style={{ fontSize: 12, fontWeight: 600, color: tokens.captionText, margin: "0 0 8px" }}>
              Quick actions
            </p>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 8,
                marginBottom: 16
              }}>
              <QuickActionButton
                label="Explain this"
                onClick={() => runQuickAction("explain")}
                disabled={working}
              />
              <QuickActionButton
                label="Summarize this section"
                onClick={() => runQuickAction("summarize")}
                disabled={working}
              />
              <QuickActionButton
                label={saveStatus === "saved" ? "Saved ✓" : saveStatus === "error" ? "Save failed" : resultText ? `Save ${activeAction}` : "Save highlight"}
                onClick={handleSaveToLucent}
                disabled={saveStatus === "saving"}
              />
              <QuickActionButton label="Create flashcards" onClick={() => {}} disabled title="Coming soon" />
            </div>

            <button
              onClick={() => runQuickAction("simplify")}
              disabled={working}
              style={{ ...primaryButtonStyle(working), width: "100%" }}>
              {working && activeAction === "simplify" ? "Simplifying..." : "Simplify selection"}
            </button>
          </div>
        )}

        {tab === "notes" && (
          <div>
            <p style={{ fontSize: 13, color: tokens.captionText, lineHeight: 1.5, marginBottom: 16 }}>
              Every highlight, explanation, simplification, and generated note you've saved lives in
              your Library.
            </p>
            <button
              onClick={() => chrome.tabs.create({ url: `${WEB_APP_URL}/app` })}
              style={{ ...primaryButtonStyle(false), width: "100%" }}>
              Open Library
            </button>
          </div>
        )}

        {tab === "settings" && (
          <div>
            <ToggleRow
              label="Apply chosen font"
              description="Applies the font you picked in Reading Preferences to the page's text. Off by default."
              enabled={fontOverrideEnabled}
              onChange={handleFontOverrideChange}
            />
            <ToggleRow
              label="Auto-activate on readable pages"
              description="When off, use Activate on this page below instead."
              enabled={autoActivateEnabled}
              onChange={handleAutoActivateChange}
            />

            <div style={{ marginTop: 16 }}>
              <button
                onClick={handleActivateClick}
                disabled={activating}
                style={{ ...primaryButtonStyle(activating), width: "100%" }}>
                {activating ? "Activating..." : "Activate on this page"}
              </button>
              {activateStatus && (
                <p style={{ fontSize: 12, color: tokens.captionText, marginTop: 10, lineHeight: 1.4 }}>
                  {activateStatus}
                </p>
              )}
            </div>

            <button
              onClick={() => chrome.runtime.openOptionsPage()}
              style={{ ...secondaryButtonStyle, width: "100%", marginTop: 12 }}>
              Reading level assessment
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function QuickActionButton({
  label,
  onClick,
  disabled,
  title
}: {
  label: string
  onClick: () => void
  disabled?: boolean
  title?: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={{
        padding: "10px 8px",
        borderRadius: 10,
        border: `1px solid ${tokens.captionText}`,
        backgroundColor: "#FFFFFF",
        color: disabled ? tokens.captionText : tokens.readingText,
        fontSize: 12,
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.6 : 1,
        textAlign: "left"
      }}>
      {label}
    </button>
  )
}

function primaryButtonStyle(disabled: boolean): React.CSSProperties {
  return {
    padding: "10px 14px",
    borderRadius: 20,
    border: "none",
    backgroundColor: tokens.accentTeal,
    color: "#FFFFFF",
    fontSize: 13,
    cursor: disabled ? "default" : "pointer",
    opacity: disabled ? 0.6 : 1
  }
}

const secondaryButtonStyle: React.CSSProperties = {
  padding: "10px 14px",
  borderRadius: 20,
  border: `1px solid ${tokens.captionText}`,
  backgroundColor: "#FFFFFF",
  color: tokens.readingText,
  fontSize: 13,
  cursor: "pointer"
}

export default SidePanel
