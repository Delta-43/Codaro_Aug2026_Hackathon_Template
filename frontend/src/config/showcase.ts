// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Showcase-only mode: the frontend published on its own, with no backend behind
 * it, as a portfolio piece.
 *
 * Arbor's hosted demo is gone, but the landing page is worth keeping visitable.
 * It is presentational, so with this flag set the build serves it and nothing
 * else: the sign-in CTAs point at the source repository, and `middleware.ts`
 * sends every other route back to `/` rather than letting a visitor walk into
 * an app whose every request would fail.

 *
 * Unset (the default), none of that applies and the app behaves normally. This
 * is a deployment mode, not a feature flag to build on.
 */
export const SHOWCASE_ONLY = process.env.NEXT_PUBLIC_SHOWCASE_ONLY === "1";

/** Where the sign-in CTAs go when there is no app to sign in to. */
export const SOURCE_URL = "https://github.com/kaveOO/Arbor";

/**
 * Routes that render without a backend. Everything else redirects to `/`.
 *
 * `/opengraph-image` is Next's generated social card, and it must be listed:
 * it has no file extension, so the middleware matcher does not treat it as a
 * static asset, and redirecting it means a scraper fetches the card, follows a
 * 307 to `/`, and shows no image at all.
 */
export const PUBLIC_ROUTES = ["/", "/privacy", "/opengraph-image"];
