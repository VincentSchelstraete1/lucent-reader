import { spawnSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

import { resolveReleaseConfig } from "./extension-release-config.mjs"

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const action = process.argv[2]

if (!new Set(["build", "package"]).has(action)) {
  console.error("Usage: node scripts/extension-release.mjs <build|package>")
  process.exit(2)
}

const packageJson = JSON.parse(readFileSync(resolve(projectRoot, "package.json"), "utf8"))
let config
try {
  config = resolveReleaseConfig(process.env, packageJson.manifest)
} catch (error) {
  console.error(`Unsafe extension release configuration: ${error.message}`)
  process.exit(2)
}

const result = spawnSync(
  process.execPath,
  [resolve(projectRoot, "node_modules/plasmo/bin/index.mjs"), action],
  {
    cwd: projectRoot,
    env: {
      ...process.env,
      PLASMO_PUBLIC_API_URL: config.api,
      PLASMO_PUBLIC_WEB_APP_URL: config.website,
      PLASMO_PUBLIC_RELEASE: "true"
    },
    stdio: "inherit"
  }
)

if (result.error) {
  console.error(`Unable to run the extension ${action}: ${result.error.message}`)
  process.exit(1)
}
process.exit(result.status ?? 1)
