import { renderToStaticMarkup } from "react-dom/server"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { SettingsPage } from "./SettingsPage"

vi.mock("../lib/AuthContext", () => ({
  useAuth: () => ({
    user: { display_name: "Vincent Schelstraete", email: "vincent@example.com" },
    deleteAccount: vi.fn(),
  }),
}))

describe("SettingsPage", () => {
  it("offers a clearly described account deletion action", () => {
    const html = renderToStaticMarkup(<MemoryRouter><SettingsPage /></MemoryRouter>)

    expect(html).toContain("Delete account")
    expect(html).toContain("Permanently remove your account")
    expect(html).toContain("saved materials")
    expect(html).toContain("learning progress")
  })
})
