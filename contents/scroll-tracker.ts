export const config = {
  matches: ["https://en.wikipedia.org/*"]
}

let lastScrollY = window.scrollY
let lastScrollTime = Date.now()

function handleScroll() {
    const currentY = window.scrollY 
    const currentTime = Date.now()

    const scrollDistance = currentY-lastScrollY
    const scrollTime = currentTime-lastScrollTime
    const scrollSpeed = scrollDistance/scrollTime

    lastScrollY = currentY
    lastScrollTime = currentTime

    console.log(scrollSpeed)
}

document.addEventListener("scroll", handleScroll)