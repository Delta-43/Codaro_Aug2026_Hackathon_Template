// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Showcase-only mode: the frontend published on its own, with no backend behind
 * it, as a portfolio piece.
 *
 * Arbor's hosted demo is gone, but `/` and `/showcase` are worth keeping
 * visitable. Both are presentational, so with this flag set the build serves
 * them and nothing else: `/showcase` reads its catalogue from the generated
 * snapshot instead of the API, the sign-in CTAs point at the source repository,
 * and `middleware.ts` sends the gated routes back to `/` rather than letting a
 * visitor walk into an app whose every request would fail.
 *
 * Unset (the default), none of that applies and the app behaves normally. This
 * is a deployment mode, not a feature flag to build on.
 */
export const SHOWCASE_ONLY = process.env.NEXT_PUBLIC_SHOWCASE_ONLY === "1";

/** Where the sign-in CTAs go when there is no app to sign in to. */
export const SOURCE_URL = "https://github.com/kaveOO/Arbor";

/** Routes that render without a backend. Everything else redirects to `/`. */
export const PUBLIC_ROUTES = ["/", "/showcase", "/privacy"];
