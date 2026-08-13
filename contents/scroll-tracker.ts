import { logEvent } from "../lib/session-log"
import { isSensitivePage } from "../lib/sensitive-page"

export const config = {
  matches: ["<all_urls>"]
}

let lastScrollY = window.scrollY
let lastScrollTime = Date.now()

function handleScroll() {
    const currentY = window.scrollY 
    const currentTime = Date.now()

    const scrollDistance = currentY - lastScrollY
    const scrollTime = currentTime - lastScrollTime
    const scrollSpeed = scrollDistance / scrollTime

    lastScrollY = currentY
    lastScrollTime = currentTime

    logEvent("scroll", { y: currentY, speed: scrollSpeed })
}

// Unlike struggle-detector.ts, this ran on <all_urls> with no
// readability gate at all - so it was tracking scroll position/speed on
// every site, sensitive pages included, before this check existed.
if (!isSensitivePage()) {
  document.addEventListener("scroll", handleScroll)
}