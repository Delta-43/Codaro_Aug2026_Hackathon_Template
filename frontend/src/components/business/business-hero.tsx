// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * The business profile header — the banner, the verified logo overlapping it,
 * the name/tagline and the rating · city · vertical meta row. It lives here
 * rather than in the Profile tab because Settings shows the *same* header: the
 * owner edits the banner and logo on exactly the view a customer sees, instead
 * of on a shrunken stand-in that renders differently from the real thing.
 *
 * `BusinessHero` is purely presentational; the overlay slots take whatever the
 * surface puts on top (Profile's settings cog, Settings' upload controls).
 * `EditableBusinessHero` fills those slots with the upload/remove affordances.
 */
import { useRef, useState, type ReactNode } from "react";
import { Camera, MapPin, Star, Trash2 } from "lucide-react";
import { isApiError } from "@/api";
import { BusinessArt } from "@/components/business/business-art";
import { BusinessBadge } from "@/components/business/verified-badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Provider } from "@/types/domain";

export function BusinessHero({
  provider: p,
  scene,
  vocabLabel,
  action,
  avatarAction,
  titleAs: Title = "h1",
}: {
  provider: Provider;
  scene: string;
  vocabLabel: string;
  /** The name's element. Settings already owns the page's <h1>, so it passes
   *  "p" — same type, same styling, no second top-level heading. */
  titleAs?: "h1" | "p";
  /** Overlaid on the banner's top-right corner (cog, upload buttons…). */
  action?: ReactNode;
  /** Overlaid on the logo (upload buttons…). */
  avatarAction?: ReactNode;
}) {
  return (
    <div className="overflow-hidden rounded-3xl border border-border bg-card">
      <div className="relative h-36 w-full sm:h-44">
        {/* The banner the owner uploaded in Settings, falling back to the
            generated on-brand scene while they haven't set one. Plain <img>:
            a Supabase Storage URL on a host next/image isn't configured for. */}
        {p.coverUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={p.coverUrl} alt="" className="size-full object-cover" />
        ) : (
          <BusinessArt scene={scene} />
        )}
        {action ? <div className="absolute right-3 top-3 flex gap-1.5">{action}</div> : null}
        <div className="absolute -bottom-8 left-4">
          <div className="relative">
            <BusinessBadge avatarUrl={p.avatarUrl} scene={scene} size="lg" />
            {avatarAction}
          </div>
        </div>
      </div>
      <div className="px-4 pb-4 pt-10">
        <Title className="truncate text-xl font-semibold tracking-tight">{p.name}</Title>
        {p.tagline ? <p className="text-sm text-muted-foreground">{p.tagline}</p> : null}
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Star className="size-3.5 fill-amber-400 text-amber-400" aria-hidden />
            <span className="font-medium text-foreground">{p.rating.toFixed(1)}</span>
            ({p.reviewCount})
          </span>
          {p.location.city ? (
            <span className="inline-flex items-center gap-1">
              <MapPin className="size-3.5" aria-hidden /> {p.location.city}
            </span>
          ) : null}
          <span className="rounded bg-muted px-1.5 py-0.5">{vocabLabel}</span>
        </div>
      </div>
    </div>
  );
}

const ACCEPTED = "image/jpeg,image/png,image/webp";

/** Round white icon button, the same affordance the avatar control uses. */
function IconAction({
  label,
  busy,
  onPress,
  children,
  className,
}: {
  label: string;
  busy: boolean;
  onPress: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Button
      variant="outline"
      size="icon-sm"
      isDisabled={busy}
      onPress={onPress}
      aria-label={label}
      className={cn(
        "size-8 rounded-full border-2 border-background bg-background p-0 shadow-sm dark:bg-background",
        className,
      )}
    >
      {children}
    </Button>
  );
}

/** The profile header as Settings shows it: identical layout, with the banner
 *  and logo swappable in place. Camera always opens the picker (upload or
 *  one-tap replace); trash appears only once there's an image to clear. */
export function EditableBusinessHero({
  provider,
  scene,
  vocabLabel,
  onUploadCover,
  onRemoveCover,
  onUploadAvatar,
  onRemoveAvatar,
}: {
  provider: Provider;
  scene: string;
  vocabLabel: string;
  onUploadCover: (file: File) => Promise<void>;
  onRemoveCover: () => Promise<void>;
  onUploadAvatar: (file: File) => Promise<void>;
  onRemoveAvatar: () => Promise<void>;
}) {
  const coverInput = useRef<HTMLInputElement>(null);
  const avatarInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(fn: () => Promise<void>, failure: string) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(isApiError(e) ? e.message : failure);
    } finally {
      setBusy(false);
    }
  }

  function pick(input: HTMLInputElement | null) {
    input?.click();
  }

  return (
    <div className="flex flex-col gap-1">
      <BusinessHero
        provider={provider}
        scene={scene}
        vocabLabel={vocabLabel}
        titleAs="p"
        action={
          <>
            <IconAction
              label={provider.coverUrl ? "Change banner image" : "Upload banner image"}
              busy={busy}
              onPress={() => pick(coverInput.current)}
            >
              <Camera className="size-3.5" />
            </IconAction>
            {provider.coverUrl ? (
              <IconAction
                label="Remove banner image"
                busy={busy}
                onPress={() => void run(onRemoveCover, "Couldn't remove your banner.")}
              >
                <Trash2 className="size-3.5 text-destructive" />
              </IconAction>
            ) : null}
          </>
        }
        avatarAction={
          // The verified tick owns the logo's bottom-right corner, so the two
          // controls sit along its top edge instead of stacking on top of it.
          <>
            <IconAction
              label={provider.avatarUrl ? "Change profile photo" : "Upload profile photo"}
              busy={busy}
              className="absolute -right-1 -top-1"
              onPress={() => pick(avatarInput.current)}
            >
              <Camera className="size-3.5" />
            </IconAction>
            {provider.avatarUrl ? (
              <IconAction
                label="Remove profile photo"
                busy={busy}
                className="absolute -left-1 -top-1"
                onPress={() => void run(onRemoveAvatar, "Couldn't remove your photo.")}
              >
                <Trash2 className="size-3.5 text-destructive" />
              </IconAction>
            ) : null}
          </>
        }
      />

      <input
        ref={coverInput}
        type="file"
        accept={ACCEPTED}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) void run(() => onUploadCover(file), "Couldn't upload your banner.");
        }}
      />
      <input
        ref={avatarInput}
        type="file"
        accept={ACCEPTED}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) void run(() => onUploadAvatar(file), "Couldn't upload your photo.");
        }}
      />
      {error ? <span className="text-xs text-destructive">{error}</span> : null}
    </div>
  );
}
