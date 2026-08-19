"use client";

/**
 * First-run business creation for the owner console.
 *
 * An owner with no provider previously saw a dead end — "No business yet" with
 * nothing to act on — because `createProvider` had no client and the console
 * could only create services. Seeds were the only route to a business, which
 * made the owner side undemonstrable on a fresh deployment.
 *
 * Every label comes from the vertical vocabulary, so a pivot that calls its
 * providers "Studios" or "Depots" says so here too.
 */
import { useState } from "react";
import { ApiError, createProvider } from "@/api";
import { useOwner } from "@/context/owner-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function CreateBusiness() {
  const { vocab, refreshProviders } = useOwner();
  const noun = vocab.providerNoun.toLowerCase();
  const [name, setName] = useState("");
  const [tagline, setTagline] = useState("");
  const [city, setCity] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await createProvider({
        name: name.trim(),
        tagline: tagline.trim() || undefined,
        // Only sent when given: a blank code would claim the empty string, and
        // single-tenant deployments resolve their sole business by this.
        publicCode: code.trim() || undefined,
        location: city.trim()
          ? { city: city.trim(), country: "", lat: 0, lng: 0 }
          : undefined,
      });
      await refreshProviders();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Couldn't create your ${noun}.`);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-md space-y-4 py-10">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Set up your {noun}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          This is the {noun} customers will find. You can edit it later in Profile.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="biz-name">Name</Label>
        <Input id="biz-name" value={name} required onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="biz-tagline">Tagline</Label>
        <Input id="biz-tagline" value={tagline} onChange={(e) => setTagline(e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="biz-city">City</Label>
        <Input id="biz-city" value={city} onChange={(e) => setCity(e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="biz-code">Public code</Label>
        <Input
          id="biz-code"
          value={code}
          placeholder="e.g. VISTULA-4471"
          onChange={(e) => setCode(e.target.value.toUpperCase())}
        />
        <p className="text-xs text-muted-foreground">
          How customers reach you directly. Optional.
        </p>
      </div>

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <Button type="submit" className="w-full" isDisabled={busy || !name.trim()}>
        {busy ? "Creating…" : `Create ${noun}`}
      </Button>
    </form>
  );
}
