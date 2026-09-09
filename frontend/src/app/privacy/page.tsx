// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

/**
 * Public data-handling & privacy policy, ungated (sits outside the `(app)`
 * group like `login/`), linked from the sign-up consent checkbox. Plain server
 * component; vertical-neutral copy. Summarises what we store, the lawful basis,
 * and the GDPR right to erasure (Settings → Delete my data).
 */
export const metadata = {
  title: "Data handling & privacy",
};

export default function PrivacyPage() {
  return (
    <main className="mx-auto min-h-dvh max-w-2xl px-5 py-12">
      <Link
        href="/login"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden /> Back
      </Link>

      <h1 className="mt-6 text-2xl font-semibold tracking-tight">Data handling &amp; privacy</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        How we handle your personal data, in line with the GDPR.
      </p>

      <div className="mt-8 space-y-8 text-sm leading-relaxed text-foreground">
        <section>
          <h2 className="text-base font-semibold">What we store</h2>
          <p className="mt-2 text-muted-foreground">
            When you create an account we store your email address, the profile
            details you choose to add (display name, avatar, timezone), and the
            records you generate by using the service, your bookings, the
            businesses you follow, and reviews you leave or receive. Your password
            is handled by our authentication provider and is never visible to us.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold">Lawful basis &amp; consent</h2>
          <p className="mt-2 text-muted-foreground">
            We process this data to provide the booking service you signed up for.
            At sign-up you explicitly agree to this handling; we record the time
            you gave that consent. We do not sell your personal data, and we only
            share the minimum needed to complete a booking (for example, a business
            you request a booking with can see the contact details needed to serve
            you).
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold">Your privacy from other users</h2>
          <p className="mt-2 text-muted-foreground">
            Your account settings and private details remain yours. Other users
            cannot open your profile and read your private information, public
            surfaces show only what is meant to be public (such as a self-chosen
            display name on a review), never your email address or account
            settings.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold">Your right to erasure</h2>
          <p className="mt-2 text-muted-foreground">
            You can delete your account and all associated data at any time from{" "}
            <span className="font-medium text-foreground">Settings → Delete my data</span>.
            This permanently removes your account, bookings, follows, and reviews.
            The action is immediate and cannot be undone.
          </p>
        </section>
      </div>
    </main>
  );
}
