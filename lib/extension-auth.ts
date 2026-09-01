import { BACKEND_URL } from "./config"

const ACCESS_KEY = "lucentAccessToken"
const DB_NAME = "lucent-auth"

function refreshStore<T>(mode: IDBTransactionMode, operation: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open(DB_NAME, 1)
    open.onupgradeneeded = () => open.result.createObjectStore("credentials")
    open.onerror = () => reject(open.error)
    open.onsuccess = () => {
      const transaction = open.result.transaction("credentials", mode)
      const request = operation(transaction.objectStore("credentials"))
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
      transaction.oncomplete = () => open.result.close()
    }
  })
}

function randomToken(bytes = 32): string {
  const data = crypto.getRandomValues(new Uint8Array(bytes))
  return btoa(String.fromCharCode(...data)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "")
}

async function challenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))
  return btoa(String.fromCharCode(...new Uint8Array(digest))).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "")
}

async function tokens(): Promise<{ access?: string; refresh?: string }> {
  const [session, refresh] = await Promise.all([chrome.storage.session.get(ACCESS_KEY), refreshStore("readonly", (store) => store.get("refresh"))])
  return { access: session[ACCESS_KEY], refresh: typeof refresh === "string" ? refresh : undefined }
}

async function saveTokens(access: string, refresh: string): Promise<void> {
  await Promise.all([chrome.storage.session.set({ [ACCESS_KEY]: access }), refreshStore("readwrite", (store) => store.put(refresh, "refresh"))])
}

async function exchange(path: string, body: unknown): Promise<{ access_token: string; refresh_token: string }> {
  const response = await fetch(`${BACKEND_URL}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
  if (!response.ok) throw new Error(response.status === 401 ? "Lucent sign-in expired" : "Lucent sign-in failed")
  return response.json()
}

export async function login(): Promise<void> {
  const state = randomToken(), verifier = randomToken(48)
  const redirectUri = chrome.identity.getRedirectURL("lucent-auth")
  const url = `${BACKEND_URL}/auth/extension/start?${new URLSearchParams({ state, code_challenge: await challenge(verifier), redirect_uri: redirectUri })}`
  const resultUrl = await chrome.identity.launchWebAuthFlow({ url, interactive: true })
  if (!resultUrl) throw new Error("Lucent sign-in was cancelled")
  const result = new URL(resultUrl)
  if (result.searchParams.get("state") !== state) throw new Error("Lucent sign-in state mismatch")
  const code = result.searchParams.get("code")
  if (!code) throw new Error("Lucent sign-in did not return a code")
  const issued = await exchange("/auth/extension/token", { code, code_verifier: verifier, redirect_uri: redirectUri })
  await saveTokens(issued.access_token, issued.refresh_token)
}

async function refreshAccess(): Promise<string | null> {
  const current = await tokens()
  if (!current.refresh) return null
  try {
    const issued = await exchange("/auth/extension/refresh", { refresh_token: current.refresh })
    await saveTokens(issued.access_token, issued.refresh_token)
    return issued.access_token
  } catch {
    await clearTokens()
    return null
  }
}

export async function authenticatedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  let { access } = await tokens()
  if (!access) access = await refreshAccess() ?? undefined
  if (!access) return new Response(JSON.stringify({ detail: "Sign in to Lucent" }), { status: 401, headers: { "Content-Type": "application/json" } })
  const request = () => fetch(`${BACKEND_URL}${path}`, { ...init, headers: { ...init.headers, Authorization: `Bearer ${access}` } })
  let response = await request()
  if (response.status === 401) {
    access = await refreshAccess() ?? undefined
    if (access) response = await request()
  }
  return response
}

export async function authStatus(): Promise<{ authenticated: boolean; displayName?: string }> {
  const response = await authenticatedFetch("/auth/extension/me")
  if (!response.ok) return { authenticated: false }
  const user = await response.json()
  return { authenticated: true, displayName: user.display_name ?? user.email ?? "Lucent user" }
}

export async function clearTokens(): Promise<void> {
  await Promise.all([chrome.storage.session.remove(ACCESS_KEY), refreshStore("readwrite", (store) => store.delete("refresh"))])
}

export async function logout(): Promise<void> {
  await authenticatedFetch("/auth/extension/logout", { method: "POST" })
  await clearTokens()
}
