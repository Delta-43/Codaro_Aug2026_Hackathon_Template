// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import path from "node:path";

/**
 * The card a shared link renders as, on LinkedIn and anywhere else that reads
 * Open Graph. Generated rather than checked in as a PNG so it cannot drift from
 * the page's own wording, and so there is no binary to re-export by hand.
 *
 * Node runtime, not edge: the leaf mark is read off disk and inlined as a data
 * URI. `ImageResponse` will not fetch a relative URL, and an absolute one would
 * have to know the deployment's own hostname before it has finished deploying.
 */
export const runtime = "nodejs";
export const alt = "Arbor: one engine, any booking business";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  // Inlined so the card renders identically on every host, with no second
  // request that a scraper might not follow.
  const mark = await readFile(path.join(process.cwd(), "public", "arbor-mark-7d.png"));
  const markSrc = `data:image/png;base64,${mark.toString("base64")}`;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#000",
          color: "#fff",
          padding: "72px 80px",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={markSrc} width={52} height={52} alt="" />
          <span style={{ fontSize: 40, fontWeight: 700, letterSpacing: "-0.02em" }}>Arbor</span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <span style={{ fontSize: 68, fontWeight: 700, letterSpacing: "-0.03em", lineHeight: 1.05 }}>
            One engine.
            <br />
            Any booking business.
          </span>
          <span style={{ fontSize: 30, color: "rgba(255,255,255,0.72)", lineHeight: 1.35 }}>
            Provider, service, resource, slot, booking, user. Edit one JSON file
            and the same deployment becomes a different business.
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 20, fontSize: 24 }}>
          <span
            style={{
              padding: "10px 20px",
              borderRadius: 999,
              background: "rgba(255,255,255,0.12)",
              color: "#fff",
            }}
          >
            1st place, Track B
          </span>
          <span style={{ color: "rgba(255,255,255,0.55)" }}>
            Next.js · FastAPI · Supabase · AGPL-3.0
          </span>
        </div>
      </div>
    ),
    size,
  );
}
