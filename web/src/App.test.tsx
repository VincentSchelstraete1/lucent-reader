import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"
import { getUserInitials, SidebarAccount } from "./App"

describe("sidebar account", () => {
  it("exposes an explicit logout control for authenticated users", () => {
    const html = renderToStaticMarkup(
      <SidebarAccount user={{ display_name: "Development User", email: "dev@lucent.local" }} onLogout={vi.fn()} />,
    )

    expect(html).toContain("Development User")
    expect(html).toContain(">DU<")
    expect(html).toContain("Log out")
    expect(html).toContain("<button")
  })

  it("uses the first and last name initials", () => {
    expect(getUserInitials({ display_name: "Vincent Schelstraete", email: "vincent@example.com" })).toBe("VS")
    expect(getUserInitials({ display_name: "Prince", email: null })).toBe("P")
    expect(getUserInitials({ display_name: null, email: "alex.morgan@example.com" })).toBe("AM")
  })
})
