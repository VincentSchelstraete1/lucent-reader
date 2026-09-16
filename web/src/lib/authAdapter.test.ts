import { afterEach, describe, expect, it, vi } from "vitest"

import { getCsrfToken, setCsrfToken } from "../api/client"
import { authAdapter } from "./authAdapter"

afterEach(() => {
  setCsrfToken(null)
  vi.unstubAllGlobals()
})

describe("authAdapter account mutations", () => {
  it("uses the CSRF token returned by the authenticated session for logout", async () => {
    setCsrfToken("session-csrf")
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal("fetch", fetchMock)

    await authAdapter.logout()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/logout"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": "session-csrf" },
      }),
    )
  })

  it("refreshes a rotated CSRF token once before deleting the account", async () => {
    setCsrfToken("stale-csrf")
    const session = {
      user: { id: "user-1", email: "reader@example.com", email_verified: true, display_name: "Reader", avatar_url: null },
      csrf_token: "fresh-csrf",
    }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 403 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(session), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal("fetch", fetchMock)

    await authAdapter.deleteAccount()

    expect(fetchMock).toHaveBeenNthCalledWith(2, expect.stringContaining("/auth/me"), { credentials: "include" })
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      expect.stringContaining("/auth/account"),
      expect.objectContaining({ method: "DELETE", headers: { "X-CSRF-Token": "fresh-csrf" } }),
    )
    expect(getCsrfToken()).toBe("fresh-csrf")
  })
})
