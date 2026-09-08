// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Owner-facing pitch — the closing call to action, and the one sign-in entry
 * point down here (the mid-page login buttons were removed).
 *
 * Two symmetric paths, the way SaaS landing pages usually split "start now" from
 * "talk to us": a self-serve card for owners who'll configure Arbor themselves
 * (routes to the business sign-in) and a concierge card for owners who'd rather
 * the founders set it up (a contact window with a prefilled email). The two cards
 * are identical in shape — same icon badge, one line of copy, one action button —
 * and the hierarchy is carried by the button weight (primary vs. outline), not by
 * colour: the whole plate stays on the pink-and-neutral palette, no accent hues.
 * A single shared "how config works" link sits under both, so neither card grows
 * taller than the other. Everything the windows need is same-origin — the sign-in
 * page, the /docs guide, and a mailto.
 */
import { useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Building2,
  Check,
  Copy,
  HeartHandshake,
  Mail,
  Wrench,
} from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";
import { Modal } from "@/components/modal";
import { GlassPanel, useScrollMotion } from "@/components/landing/scroll-reveal";

// Demo contact address for the concierge path. Arbor has no live mailbox yet,
// so this is a placeholder the founders swap for a real one at launch.
const FOUNDERS_EMAIL = "founders@arbor.build";
const MAIL_SUBJECT = "Set up my business on Arbor";
const MAIL_BODY = `Hi Arbor founders,

I'd like help setting up my business on Arbor. A bit about us:

• Business type:
• What we offer (services / resources):
• Our rules (pricing, party size, cancellation window):
• Rough booking volume:
• Target launch date:

Thanks!`;
const MAILTO = `mailto:${FOUNDERS_EMAIL}?subject=${encodeURIComponent(MAIL_SUBJECT)}&body=${encodeURIComponent(MAIL_BODY)}`;

// Icon badge for each card — reacts to the card's hover (the card carries
// `group`) so the icons read as interactive, filling primary like the plate
// indicators elsewhere. `buttonFx`-consistent feel, kept inline because it keys
// off the parent card's hover, not its own.
const CARD_ICON =
  "flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm transition-all duration-200 ease-out group-hover:scale-110 group-hover:bg-primary group-hover:text-primary-foreground";
const CARD =
  "group flex flex-col rounded-2xl border border-border/60 bg-card/70 p-6 shadow-sm backdrop-blur-md transition-colors hover:border-primary/40";

export function BusinessCta() {
  const { ref, style } = useScrollMotion<HTMLDivElement>();
  const [contact, setContact] = useState(false);

  return (
    <section className="flex min-h-[92vh] snap-start snap-always items-center px-4 py-20">
      <div ref={ref} style={style} className="mx-auto w-full max-w-4xl">
        <GlassPanel className="flex flex-col items-center gap-8 px-6 py-14 text-center sm:px-10">
          <span className="flex size-12 origin-center cursor-pointer items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm transition-all duration-200 ease-out hover:scale-[1.4] hover:-translate-y-1 hover:bg-primary hover:text-primary-foreground hover:shadow-xl">
            <Building2 className="size-6" aria-hidden />
          </span>
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              Run a business? Bring it to Arbor.
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-foreground/80">
              Arbor is one config file that sets your vocabulary, rules, pricing and look, so a whole
              booking business runs without a rewrite. Set it up yourself, or let us build it with
              you.
            </p>
          </div>

          {/* Two symmetric paths, side by side. */}
          <div className="grid w-full items-stretch gap-4 text-left sm:grid-cols-2">
            {/* Concierge — let the founders configure it for you. */}
            <div className={CARD}>
              <span className={CARD_ICON}>
                <HeartHandshake className="size-5" aria-hidden />
              </span>
              <h3 className="mt-4 text-lg font-semibold text-foreground">Have us set it up</h3>
              <p className="mt-1.5 flex-1 text-sm leading-relaxed text-foreground/80">
                Prefer a hand? Tell the founders about your business and we&apos;ll configure, seed
                and launch it with you, no config file to touch.
              </p>
              <Button
                variant="outline"
                size="lg"
                className={cn(buttonFx.pill, "mt-5 w-full gap-1.5 px-6")}
                onPress={() => setContact(true)}
              >
                <Mail className="size-4" aria-hidden />
                Talk to the founders
              </Button>
            </div>

            {/* Self-serve — configure it yourself, primary action. */}
            <div className={CARD}>
              <span className={CARD_ICON}>
                <Wrench className="size-5" aria-hidden />
              </span>
              <h3 className="mt-4 text-lg font-semibold text-foreground">Set it up yourself</h3>
              <p className="mt-1.5 flex-1 text-sm leading-relaxed text-foreground/80">
                Create your business account and shape that one config file: your vocabulary, rules,
                pricing and look. No code, no rewrite.
              </p>
              <Link
                href="/login/business"
                className={cn(buttonVariants({ size: "lg" }), buttonFx.pill, "mt-5 w-full gap-1.5 px-6")}
              >
                Start your business
                <ArrowRight className="size-4" aria-hidden />
              </Link>
            </div>
          </div>
        </GlassPanel>
      </div>

      <ContactWindow open={contact} onClose={() => setContact(false)} />
    </section>
  );
}

/** Concierge contact: the founders' address, a prefilled email, and what to send. */
function ContactWindow({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  async function copyEmail() {
    try {
      await navigator.clipboard.writeText(FOUNDERS_EMAIL);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard blocked — the address is visible to copy by hand */
    }
  }

  const INCLUDE = [
    "The kind of business you run",
    "What you offer: your services and resources",
    "Your rules: pricing, party size, cancellation window",
    "Rough booking volume, and when you'd like to launch",
  ];

  return (
    <Modal open={open} onClose={onClose} title="Let's build your Arbor together" className="md:max-w-lg">
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <HeartHandshake className="size-5" aria-hidden />
          </span>
          <div>
            <p className="text-sm font-semibold text-foreground">Set up by the founders</p>
            <p className="text-xs text-muted-foreground">We usually reply within 2 business days.</p>
          </div>
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">
          While Arbor is young we set new businesses up by hand, from configuration to seed data to
          go-live, so you can start taking bookings without touching the config file.
        </p>

        {/* Email + copy */}
        <div className="flex items-center justify-between gap-2 rounded-xl border border-border bg-muted/40 px-3 py-2.5">
          <span className="min-w-0 truncate font-mono text-sm text-foreground">{FOUNDERS_EMAIL}</span>
          <button
            type="button"
            onClick={copyEmail}
            aria-label="Copy email address"
            className={cn(
              "flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-muted-foreground transition-all hover:bg-muted hover:text-foreground",
              buttonFx.press,
            )}
          >
            {copied ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <p className="-mt-2 text-[11px] text-muted-foreground">
          Demo address for now. The founders swap this for a live mailbox at launch.
        </p>

        {/* What to include */}
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-foreground/60">
            What to tell us
          </p>
          <ul className="mt-2 space-y-2">
            {INCLUDE.map((item) => (
              <li key={item} className="flex gap-2.5">
                <Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                <span className="text-sm text-muted-foreground">{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <a
          href={MAILTO}
          className={cn(buttonVariants({ size: "lg" }), "w-full gap-1.5")}
        >
          <Mail className="size-4" aria-hidden />
          Email the founders
        </a>
      </div>
    </Modal>
  );
}
