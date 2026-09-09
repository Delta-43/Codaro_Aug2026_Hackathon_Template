// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { PUBLIC_ROUTES, SHOWCASE_ONLY } from "@/config/showcase";

/**
 * Keeps a showcase-only deployment to the pages that work without a backend.
 *
 * `/` and `/showcase` are presentational; everything else (`/login`, `/search`,
 * `/bookings`, `/owner/*`) needs an API that a showcase build has not got. Left
 * reachable they would load, fire requests at nothing and sit there failing,
 * which reads as a broken app rather than a deliberately static one. So they
 * redirect to `/` instead.
 *
 * When `SHOWCASE_ONLY` is unset this returns immediately and every route
 * behaves normally, so a full deployment is unaffected.
 */
export function middleware(request: NextRequest) {
  if (!SHOWCASE_ONLY) return NextResponse.next();

  const { pathname } = request.nextUrl;
  if (PUBLIC_ROUTES.includes(pathname)) return NextResponse.next();

  return NextResponse.redirect(new URL("/", request.url));
}

export const config = {
  // Everything except Next's own assets and static files, which must keep
  // serving or the pages we do allow would render unstyled.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|media|.*\\..*).*)"],
};
