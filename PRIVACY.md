# Privacy Policy — Accessibility Reader

_Last updated: 2026-08-12_

Accessibility Reader ("the extension") is a Chrome extension that helps
people simplify text on webpages to match a reading level they choose.
This page explains exactly what data the extension collects, what it
sends off your device, and what stays local.

## Data sent off your device

**Paragraph text.** When you click "Simplify," highlight text, or use
"Simplify Entire Page," the text of that paragraph is sent to our backend
server, which forwards it to Anthropic's API (the Claude model) to be
rewritten at your chosen reading level. Anthropic processes this text
under its own privacy policy. We do not store this text after the
request completes — our server does not log or save paragraph content to
a database or file.

**Reading level and length preference.** Your selected target grade
level (e.g. "Simple," "Comfortable") and text length preference (e.g.
"Shorter," "More Detail") are sent along with the paragraph text, since
they determine how the text is rewritten.

**Install ID.** The extension generates a random, anonymous identifier
(a UUID, not tied to your name, email, or Google account) the first time
it runs, and stores it in the extension's local storage. This ID is sent
with each simplify request solely to enforce a daily usage limit per
install. Usage counts are kept in server memory only (not written to
disk) and reset whenever the server restarts.

No account, sign-in, or personal information (name, email, IP-based
identity, etc.) is collected or required to use the extension.

## Data that stays on your device

**Mouse movement, scroll activity, and reading behavior.** The extension
tracks signals like mouse movement, scroll position/speed, and how long
you dwell on a paragraph, in order to detect when you might be struggling
with a passage and offer to simplify it. These events are held only in
the current page's memory and are cleared when you navigate away or
reload the page. They are never sent to our server or anywhere else
automatically.

A hidden, developer-only "Export Session Log" option (off by default,
and not shown in the normal extension menu) lets someone manually
download these events as a JSON file to their own computer for testing
purposes. This does not transmit anything — it only saves a local file.

**Preferences.** Your target reading level, text length preference, and
install ID are stored using Chrome's local extension storage
(`chrome.storage.local`) on your own device. This data is not synced to
Google or any third party by the extension.

## Third parties

Paragraph text you choose to simplify is sent to our backend server and
then to Anthropic's API to generate the simplified rewrite. This is the
only third-party sharing the extension performs. We do not use
analytics services, advertising networks, or tracking pixels.

## Where the extension runs

The extension activates on webpages you visit, so it can detect
paragraph text and offer to simplify it wherever you're reading. It does
not run on Chrome's own internal pages (e.g. `chrome://` pages) or other
browser extensions.

## Your choices and control over your data

Because the extension doesn't use accounts or collect personal
identifiers, there's no persistent personal profile to request or
delete. Specifically:

- **Preferences and install ID** can be cleared at any time by removing
  the extension, or by clearing its storage through Chrome's own
  extension settings.
- **In-page behavioral signals** (mouse, scroll, dwell) are already
  temporary by design — they clear automatically on page reload or
  navigation, and are never transmitted unless you personally use the
  hidden developer export option described above.
- **Paragraph text sent for simplification** is not retained by our
  server after the request completes, so there is nothing stored there
  to request deletion of.

If you have questions about your data or want more detail on how a
specific feature works, contact us using the information below.

## Children's privacy

The extension is not directed at children under 13, and we do not
knowingly collect personal information from children. Since the
extension does not collect names, emails, or other personal identifiers
from any user, this applies equally regardless of age.

## Changes to this policy

If what the extension collects or sends ever changes, this page will be
updated to reflect that, and the "Last updated" date at the top will
change accordingly. We recommend checking back periodically if you want
to stay current.

## Contact

Email: vincent.sch2006@gmail.com