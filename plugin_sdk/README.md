# Arbor booking widget

Add booking to any existing website with one `<script>` tag. No account
setup on the host site, no iframe wiring, no CSS to fight — the widget
injects a floating launcher button; clicking it opens a themed booking flow
in a modal.

This works because of how the platform is deployed: **one deployment = one
business** (`tenancy.mode: "single"` in `domain.config.json`). The widget
script's own `src` origin *is* the business — there's no provider code or
API key to configure.

## Quick start

```html
<script src="https://<your-deployment>/embed.js" async></script>
```

That's it. A "Book now" button appears in the bottom-right corner of the
page. Visitors can sign in with an email one-time code (no password) or an
existing account, then book — the same flow as the main app, just chromeless
and inside a modal.

See [`example.html`](example.html) for a complete, runnable page.

## Testing locally

`example.html` is a real, complete host page — no server needed to try it,
just a running deployment to point it at.

1. From the repo root, start the stack:
   ```bash
   make start
   ```
   Wait for it to come up, then confirm the backend is healthy:
   ```bash
   curl http://localhost:8000/health   # -> {"status":"ok"}
   ```
   The repo's own seeded demo config already runs `tenancy.mode: "single"`
   (the `VISTULA-4471` fleet vertical), so `/embed` and `/embed.js` work out
   of the box against `frontend/`'s deployment (`:3000`) — no config changes
   needed for this step. (`frontend/`'s own landing page (`/`) also loads
   `embed.js`, in buttonless mode, and its Login/Get Started/Sign in buttons
   call `window.Arbor.open()` — a live example on the project's real page,
   see [`CLAUDE.md`](CLAUDE.md).)
2. Open [`example.html`](example.html) and replace the placeholder in the
   `<script>` tag at the bottom of the file:
   ```diff
   - <script src="YOUR_DEPLOYMENT_URL/embed.js" data-label="Reserve a table" async></script>
   + <script src="http://localhost:3000/embed.js" data-label="Reserve a table" async></script>
   ```
   (Leave this edit uncommitted — the placeholder is what ships in the repo,
   since `example.html` is meant to demonstrate the pattern generically, not
   point at any one deployment.)
3. Open the file directly in a browser — no dev server needed:
   ```bash
   open plugin_sdk/example.html        # macOS
   xdg-open plugin_sdk/example.html    # Linux
   ```
   or just double-click it / drag it into a browser tab, or use your editor's
   "Open with Live Server" / "Preview" if it has one.
4. A "Reserve a table" button should appear bottom-right. Click it — a modal
   opens with the real `/embed` booking flow inside (sign in with an email
   code, or toggle to password sign-in with the seeded demo account:
   `demo@codaro.app` / `Codaro-Demo-2026`), and pick a vehicle class to see
   the full flow through to a real booking.

If the button never appears, open the browser console first — a blank host
page with no errors usually means the deployment isn't reachable at the URL
in the `<script src>` (check step 1's `curl` succeeded and the port in the
tag matches).

## Attributes

The script tag itself carries configuration — no separate init call, no
global JS object to wire up.

| Attribute | Default | What it does |
|---|---|---|
| `data-label` | `"Book now"` | The launcher button's text. |
| `data-mode` | (button mode) | `"buttonless"` skips the floating launcher entirely — use this when your own page has its own buttons and calls `window.Arbor.open()`/`close()` directly. |

That's the whole surface. Two things you might expect aren't here, on
purpose:

- **No provider/business code** — the script's `src` origin already
  identifies the business (one deployment per business), so a second
  identifier would be redundant.
- **No color/theme override** — branding comes from that deployment's own
  `domain.config.json` (`theme.primaryColor`, `theme.logoUrl`,
  `theme.fontFamily`), applied *inside* the iframe. Setting it once
  server-side, in the same place as every other pivot setting, means there's
  one source of truth instead of two that can drift. Change your brand color
  by editing `domain.config.json`, not the widget.

## What actually loads, and when

Nothing beyond the script itself (a few KB, no dependencies) loads until a
visitor clicks the button. The booking iframe (`/embed` on your deployment)
only loads at that point — so the widget has effectively zero cost on your
page's initial load.

Once opened, the iframe stays alive for the rest of the visit — closing the
modal hides it, it doesn't tear it down, so a visitor who signs in, closes
the modal to read more of your page, and reopens it later doesn't have to
sign in again.

## Auth inside the widget

Two ways in, both real accounts by the time a booking is created:

- **Email code (default, shown first)** — type an email, get a one-time
  code, no password. First-time visitors get an account created
  automatically on verification.
- **Password sign-in** — a "Already have an account? Sign in" toggle reveals
  the same sign-in/sign-up form as the main app's `/login` page, for a
  returning customer who set a password.

## Alternative: no widget, just the API

If an iframe/modal doesn't fit your site — say you want the booking flow
laid out inline in your own markup, styled with your own CSS — skip the
widget and call the REST API directly against your deployment:

```
GET  /config                      # vocabulary, pricing, theme — build your own UI from this
GET  /services?provider_id=...    # what's bookable
GET  /availability?service_id=... # open slots
POST /bookings                    # create a booking (needs a signed-in user's bearer token)
```

Auth is `Authorization: Bearer <supabase-jwt>`, not cookies, so this works
from any origin without a CORS/credentials dance. See `backend/CLAUDE.md`'s
"Domain API" section for the full endpoint reference and
`frontend/src/api/index.ts` for a working TypeScript client to copy patterns
from. This path needs more work on your end (build the UI yourself) but zero
constraints on how it looks or where it lives on the page.

## Requirements

- The deployment this script is loaded from must run `tenancy.mode: "single"`
  with a `tenancy.providerCode` set — `/embed` has no discovery UI, it always
  resolves to that one business. (This is already how every real adopter of
  the widget is expected to run — see `docs/PIVOT-SYSTEM.md`.)
- Nothing else. The widget works over plain HTTP(S), needs no build step on
  the consuming site, and doesn't require the host page to be built with any
  particular framework — it's four DOM elements and a `postMessage` listener.
