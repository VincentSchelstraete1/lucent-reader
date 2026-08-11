import { logEvent } from "../lib/session-log"

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

document.addEventListener("scroll", handleScroll)