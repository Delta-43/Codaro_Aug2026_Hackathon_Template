# Security policy

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Use GitHub's private reporting instead: the **Security** tab on this repository
→ **Report a vulnerability**. That opens a private advisory only the maintainers
can see, and it is the fastest route to a fix.

If you cannot use GitHub Security Advisories, email **founders@arbor.build** with
`SECURITY` in the subject line.

Please include: what you found, the steps to reproduce it, the impact you think
it has, and the commit or deployed URL you tested against. A proof of concept
helps, but a clear description is enough to get started.

## What to expect

| | |
|---|---|
| First response | within 5 working days |
| Assessment and a plan | within 10 working days |
| Fix and disclosure | coordinated with you before anything is made public |

We will credit you in the advisory unless you would rather stay anonymous.

## Supported versions

Arbor has not yet reached a stable release. Only the latest commit on `main`
receives security fixes; older tags and the `develop` branch do not.

| Version | Supported |
|---|---|
| `main` (latest) | yes |
| everything else | no |

## Scope

In scope: authentication and session handling, Supabase Row Level Security
policy gaps, booking/slot authorization (acting on another user's or another
provider's data), the config validator (`domain.config.json` handling), and
dependency vulnerabilities that are reachable from application code.

Out of scope: findings that only affect the seeded demo accounts, which are
public by design — `backend/seed.py` and `frontend/src/components/demo-logins.tsx`
ship their credentials deliberately so anyone can try the demo. Also out of
scope: missing rate limiting and missing security headers, both of which are
known and tracked publicly.

## A note on self-hosting

Arbor is AGPL-3.0 software you run yourself. A deployment's security depends on
how it is configured — in particular `CORS_ORIGINS` (which defaults to `*` for
local development), keeping `SUPABASE_SERVICE_KEY` server-side only, and having
RLS enabled on your Supabase project. See [DEPLOY.md](DEPLOY.md).
