// A page is treated as sensitive - and nothing in this extension may
// activate on it - if it contains a password input field. This is a
// hard override: checked independently of, and with priority over, any
// other activation heuristic (e.g. isProbablyReaderable in
// contents/struggle-detector.ts). "Does this look like an article" and
// "is this safe to run on" are different questions - a bank homepage,
// login page, or checkout flow can have plenty of real prose text
// (marketing copy, security disclosures, footer legal text) while still
// being a page nothing here should ever touch.
//
// Known limitation, confirmed directly: this only catches a password
// field that's actually present in the DOM at the moment it's checked.
// A multi-step login flow that renders the password field only after
// an earlier step (username entry, an SSO redirect) won't have one yet
// on first load - this check can't protect a field that doesn't exist
// yet.
export function isSensitivePage(): boolean {
  return !!document.querySelector('input[type="password"]')
}
