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
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";
import { useApp } from "@/context/app-context";
import { AvatarImg } from "@/components/avatar-img";
import { Skeleton } from "@/components/skeleton";
import { getMyEntitlements, getMyReputation } from "@/api";
import type { ClientReputation } from "@/types/domain";
import { avatarDataUri } from "@/lib/business-demo";
import { formatMoney, whenLabel } from "@/lib/format";

const EMPTY_REP: ClientReputation = { score: 0, count: 0, reviews: [] };

/** What the customer holds under `entitlements`, and what is on offer.
 *
 *  Renders nothing at all when the deployment sells no plans — `entitlements`
 *  is off in most configs, and an empty "Membership" heading is worse than no
 *  section. The catalogue and the held rows arrive in one response, so this is
 *  a single request that can also say "become a Member" to someone who is not.
 */
function MembershipCard() {
  const [data, setData] = useState<Awaited<ReturnType<typeof getMyEntitlements>> | null>(null);
  useEffect(() => {
    let cancelled = false;
    getMyEntitlements()
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setData(null));
    return () => {
      cancelled = true;
    };
  }, []);

  if (!data?.enabled || !data.plans.length) return null;
  const held = data.held.filter((h) => h.status === "active");

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h2 className="text-sm font-semibold">Membership</h2>
      {held.length ? (
        <ul className="mt-2 space-y-1">
          {held.map((h) => (
            <li key={h.id} className="flex items-baseline justify-between text-sm">
              <span className="font-medium">{h.label}</span>
              <span className="text-muted-foreground">
                {h.creditsRemaining !== null
                  ? `${h.creditsRemaining} left`
                  : h.discountBps > 0
                    ? `${h.discountBps / 100}% off`
                    : "Active"}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <ul className="mt-2 space-y-1">
          {data.plans.map((p) => (
            <li key={p.key} className="flex items-baseline justify-between text-sm">
              <span className="text-muted-foreground">{p.label}</span>
              <span className="text-muted-foreground">
                {p.priceMinorUnits !== null ? formatMoney(p.priceMinorUnits, "EUR") : ""}
                {p.cycle !== "none" ? ` / ${p.cycle}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}


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
        <AvatarImg src={user?.avatarUrl} name={user?.displayName} alt="" className={cn("size-14", buttonFx.link)} />
        <div className="min-w-0 flex-1">
          <h1 className="flex items-center gap-1.5 truncate text-xl font-semibold tracking-tight">
            {user.displayName}
            {user.verified ? <BadgeCheck className="size-5 fill-primary text-card" aria-label="Verified" /> : null}
          </h1>
          <p className="truncate text-sm text-muted-foreground">{user.email}</p>
          <p className="mt-1 flex items-center gap-1 text-sm">
            <Star className={cn("size-3.5 fill-amber-400 text-amber-400", buttonFx.star)} aria-hidden />
            <span className="font-medium">{rep.score.toFixed(1)}</span>
            <span className="text-muted-foreground">· {rep.count} reviews from businesses</span>
          </p>
        </div>
        <Link
          href="/account/settings"
          aria-label="Settings"
          className={cn(
            "grid size-9 shrink-0 place-items-center rounded-full text-primary transition-all hover:bg-primary/10",
            buttonFx.press,
          )}
        >
          <Settings className="size-5" aria-hidden />
        </Link>
      </header>

      <MembershipCard />

      {/* Reputation */}
      <div className="rounded-2xl border border-border bg-card p-4">
        <div className="flex items-center gap-4">
          <div className="text-center">
            <div className="text-3xl font-semibold tracking-tight">{rep.score.toFixed(1)}</div>
            <div className="mt-0.5 flex justify-center">
              {[0, 1, 2, 3, 4].map((i) => (
                <Star
                  key={i}
                  className={cn(
                    "size-3.5",
                    buttonFx.star,
                    i < Math.round(rep.score) ? "fill-amber-400 text-amber-400" : "fill-muted text-muted",
                  )}
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
              <li key={i} className={cn("rounded-2xl border border-border bg-card p-3", buttonFx.surface)}>
                <div className="flex items-center gap-2">
                  <AvatarImg src={avatarDataUri(rv.author)} alt="" className={cn("size-8", buttonFx.link)} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">{rv.author}</span>
                      <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
                        <Star className={cn("size-3 fill-amber-400 text-amber-400", buttonFx.star)} aria-hidden />
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

    </section>
  );
}
