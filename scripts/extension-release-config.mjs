export const DEFAULT_RELEASE_ORIGINS = Object.freeze({
  api: "https://api.lucentreader.com",
  website: "https://lucentreader.com"
})

function releaseOrigin(name, value) {
  let parsed
  try {
    parsed = new URL(value)
  } catch {
    throw new Error(`${name} must be a valid absolute URL`)
  }

  if (parsed.protocol !== "https:") {
    throw new Error(`${name} must use HTTPS for a release build`)
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash || !parsed.hostname) {
    throw new Error(`${name} must be a plain HTTPS origin without credentials, query, or fragment`)
  }
  if (parsed.pathname !== "/") {
    throw new Error(`${name} must not include a path`)
  }
  return parsed.origin
}

export function resolveReleaseConfig(environment = process.env, manifest = {}) {
  const api = releaseOrigin(
    "PLASMO_PUBLIC_API_URL",
    environment.PLASMO_PUBLIC_API_URL?.trim() || DEFAULT_RELEASE_ORIGINS.api
  )
  const website = releaseOrigin(
    "PLASMO_PUBLIC_WEB_APP_URL",
    environment.PLASMO_PUBLIC_WEB_APP_URL?.trim() || DEFAULT_RELEASE_ORIGINS.website
  )
  const permissions = new Set(manifest.host_permissions || [])

  for (const origin of [api, website]) {
    if (!permissions.has(`${origin}/*`)) {
      throw new Error(`Release origin ${origin} is missing from manifest host_permissions`)
    }
  }

  return { api, website }
}
