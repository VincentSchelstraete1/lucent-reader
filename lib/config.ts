// Single place the backend's base URL is defined. Swapping local dev for
// a deployed backend later is a one-line change here instead of a hunt
// through every content script that calls fetch().
export const BACKEND_URL = "http://127.0.0.1:8000"

// The Library web app (web/) - the side panel's Notes tab just opens this
// in a new tab rather than reimplementing notes browsing in the panel.
export const WEB_APP_URL = "http://localhost:5173"
