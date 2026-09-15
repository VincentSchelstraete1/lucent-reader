import assert from "node:assert/strict"
import test from "node:test"

import { DEFAULT_RELEASE_ORIGINS, resolveReleaseConfig } from "./extension-release-config.mjs"

const productionManifest = {
  host_permissions: [
    "https://api.lucentreader.com/*",
    "https://lucentreader.com/*"
  ]
}

test("release config uses the checked-in HTTPS production origins", () => {
  assert.deepEqual(resolveReleaseConfig({}, productionManifest), DEFAULT_RELEASE_ORIGINS)
})

test("release config accepts an allowlisted HTTPS origin override", () => {
  const manifest = { host_permissions: ["https://api.example.test/*", "https://app.example.test/*"] }
  assert.deepEqual(resolveReleaseConfig({
    PLASMO_PUBLIC_API_URL: "https://api.example.test/",
    PLASMO_PUBLIC_WEB_APP_URL: "https://app.example.test"
  }, manifest), {
    api: "https://api.example.test",
    website: "https://app.example.test"
  })
})

test("release config rejects HTTP and localhost addresses", () => {
  assert.throws(
    () => resolveReleaseConfig({ PLASMO_PUBLIC_API_URL: "http://127.0.0.1:8000" }, productionManifest),
    /must use HTTPS/
  )
})

test("release config rejects paths and origins absent from extension permissions", () => {
  assert.throws(
    () => resolveReleaseConfig({ PLASMO_PUBLIC_API_URL: "https://api.lucentreader.com/v1" }, productionManifest),
    /must not include a path/
  )
  assert.throws(
    () => resolveReleaseConfig({ PLASMO_PUBLIC_API_URL: "https://unapproved.example" }, productionManifest),
    /missing from manifest host_permissions/
  )
})
