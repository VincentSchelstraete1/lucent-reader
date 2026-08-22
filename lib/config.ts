// Single place the backend's base URL is defined. Swapping local dev for
// a deployed backend later is a one-line change here instead of a hunt
// through every content script that calls fetch().
export const BACKEND_URL = "http://127.0.0.1:8000"
