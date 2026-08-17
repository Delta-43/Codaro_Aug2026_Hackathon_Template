"use client";

/**
 * Customer tab 5 — Profile. The user's public profile: businesses screen a
 * customer before accepting a booking (rating, reviews left by businesses,
 * membership), so users are motivated to keep a good profile too. Mirrors the
 * business Profile: a cog (top-right) opens the User Settings Panel. Editable
 * account details + preferences now live there, not here.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { BadgeCheck, Settings, Star } from "lucide-react";
import { useApp } from "@/context/app-context";
import { useAuth } from "@/lib/auth";
import { AvatarImg } from "@/components/avatar-img";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/skeleton";
import { AvatarImg } from "@/components/avatar-img";
import { getMyReputation } from "@/api";
import type { ClientReputation } from "@/types/domain";
import { avatarDataUri } from "@/lib/business-demo";

function whenLabel(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(new Date(iso));
  } catch {
    return "";
  }
}

const EMPTY_REP: ClientReputation = { score: 0, count: 0, reviews: [] };

export default function ProfilePage() {
  const { ready, user } = useApp();
  const [rep, setRep] = useState<ClientReputation>(EMPTY_REP);

  useEffect(() => {
    let cancelled = false;
    getMyReputation()
      .then((r) => !cancelled && setRep(r))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!ready || !user) return <Skeleton className="h-96 w-full" />;

  return (
    <section className="space-y-8 py-6">
      <header className="flex items-center gap-3">
        <AvatarImg src={user?.avatarUrl} name={user?.displayName} alt="" className="size-14" />
        <div className="min-w-0 flex-1">
          <h1 className="flex items-center gap-1.5 truncate text-xl font-semibold tracking-tight">
            {user.displayName}
            {user.verified ? <BadgeCheck className="size-5 fill-primary text-card" aria-label="Verified" /> : null}
          </h1>
          <p className="truncate text-sm text-muted-foreground">{user.email}</p>
          <p className="mt-1 flex items-center gap-1 text-sm">
            <Star className="size-3.5 fill-amber-400 text-amber-400" aria-hidden />
            <span className="font-medium">{rep.score.toFixed(1)}</span>
            <span className="text-muted-foreground">· {rep.count} reviews from businesses</span>
          </p>
        </div>
        <Link
          href="/account/settings"
          aria-label="Settings"
          className="grid size-9 shrink-0 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Settings className="size-5" aria-hidden />
        </Link>
      </div>

      {/* Reputation */}
      <div className="rounded-2xl border border-border bg-card p-4">
        <div className="flex items-center gap-4">
          <div className="text-center">
            <div className="text-3xl font-semibold tracking-tight">{rep.score.toFixed(1)}</div>
            <div className="mt-0.5 flex justify-center">
              {[0, 1, 2, 3, 4].map((i) => (
                <Star
                  key={i}
                  className={`size-3.5 ${i < Math.round(rep.score) ? "fill-amber-400 text-amber-400" : "fill-muted text-muted"}`}
                  aria-hidden
                />
              ))}
            </div>
          </div>
          <p className="text-sm text-muted-foreground">
            Businesses rate you after each booking. A strong profile means faster approvals and a warmer welcome.
          </p>
        </div>
      </div>

      {/* Reviews */}
      <div>
        <h2 className="mb-2 text-sm font-semibold">Reviews from businesses</h2>
        {rep.reviews.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-border px-4 py-6 text-center text-xs text-muted-foreground">
            No reviews yet — businesses rate you after a completed booking.
          </p>
        ) : (
          <ul className="space-y-3">
            {rep.reviews.map((rv, i) => (
              <li key={i} className="rounded-2xl border border-border bg-card p-3">
                <div className="flex items-center gap-2">
                  <AvatarImg src={avatarDataUri(rv.author)} alt="" className="size-8" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">{rv.author}</span>
                      <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
                        <Star className="size-3 fill-amber-400 text-amber-400" aria-hidden />
                        {rv.rating.toFixed(1)}
                      </span>
                    </div>
                    <span className="text-[11px] text-muted-foreground">{whenLabel(rv.createdAtUtc)}</span>
                  </div>
                </div>
                {rv.text ? <p className="mt-2 text-sm text-muted-foreground">{rv.text}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="text-[11px] text-muted-foreground">
        Manage your account in{" "}
        <Link href="/account/settings" className="text-primary hover:underline">
          Settings
        </Link>
        .
      </p>
    </section>
  );
}
