"use client";

/**
 * Profile picture control — the avatar plus a single white circular badge
 * overlaid on its bottom-right corner. The badge toggles by state: camera
 * icon + tap-to-upload when no photo is set, trash icon + tap-to-delete once
 * one is. Always visible (not hover-gated) so it works on touch.
 */
import { useRef, useState } from "react";
import { Camera, Trash2 } from "lucide-react";
import { isApiError } from "@/api";
import { AvatarImg } from "@/components/avatar-img";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const ACCEPTED = "image/jpeg,image/png,image/webp";

export function AvatarUpload({
  avatarUrl,
  name,
  className,
  onUpload,
  onRemove,
}: {
  avatarUrl: string;
  name: string;
  className?: string;
  /** Persist the chosen file (e.g. POST the avatar) and apply the new state. */
  onUpload: (file: File) => Promise<void>;
  /** Clear the avatar (e.g. DELETE it) and apply the new state. */
  onRemove: () => Promise<void>;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasPhoto = Boolean(avatarUrl);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      await onUpload(file);
    } catch (e) {
      setError(isApiError(e) ? e.message : "Couldn't upload your photo.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove() {
    setBusy(true);
    setError(null);
    try {
      await onRemove();
    } catch (e) {
      setError(isApiError(e) ? e.message : "Couldn't remove your photo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <div className={cn("relative", className)}>
        <AvatarImg src={avatarUrl} name={name} alt="" className="size-full" />
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) void handleFile(file);
          }}
        />
        {/* Camera always opens the picker (upload or one-tap replace); the
            trash badge appears only when there's a photo to remove. */}
        <Button
          variant="outline"
          size="icon-sm"
          isDisabled={busy}
          onPress={() => inputRef.current?.click()}
          aria-label={hasPhoto ? "Change profile photo" : "Upload profile photo"}
          className="absolute -right-1 -bottom-1 size-8 rounded-full border-2 border-background bg-background p-0 shadow-sm dark:bg-background"
        >
          <Camera className="size-3.5" />
        </Button>
        {hasPhoto ? (
          <Button
            variant="outline"
            size="icon-sm"
            isDisabled={busy}
            onPress={() => void handleRemove()}
            aria-label="Remove profile photo"
            className="absolute -right-1 -top-1 size-8 rounded-full border-2 border-background bg-background p-0 shadow-sm dark:bg-background"
          >
            <Trash2 className="size-3.5 text-destructive" />
          </Button>
        ) : null}
      </div>
      {error ? <span className="text-xs text-destructive">{error}</span> : null}
    </div>
  );
}
