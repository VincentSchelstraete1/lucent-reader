import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"
import { SidebarAccount } from "./App"

describe("sidebar account", () => {
  it("exposes an explicit logout control for authenticated users", () => {
    const html = renderToStaticMarkup(
      <SidebarAccount user={{ display_name: "Development User", email: "dev@lucent.local" }} onLogout={vi.fn()} />,
    )

    expect(html).toContain("Development User")
    expect(html).toContain("Log out")
    expect(html).toContain("<button")
  })
})
