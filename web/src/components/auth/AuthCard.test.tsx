import { renderToStaticMarkup } from "react-dom/server"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"
import { AuthCard } from "./AuthCard"

describe("AuthCard", () => {
  it("keeps the public sign-in surface focused on Google OAuth", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <AuthCard mode="login" />
      </MemoryRouter>,
    )

    expect(html).toContain("Continue with Google")
    expect(html).toContain("Welcome back.")
    expect(html).not.toContain("development user")
    expect(html).not.toContain("learner card")
  })
})
