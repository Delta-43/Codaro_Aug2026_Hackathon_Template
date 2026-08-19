-- Neutral booking-engine schema. Idempotent by design (IF NOT EXISTS / OR
-- REPLACE, never DROP/ALTER) so a backend restart can safely re-run this
-- without touching existing data. Treat as frozen once the pivot happens —
-- new domain fields go in `metadata jsonb`, not new columns.

create table if not exists resources (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists slots (
  id uuid primary key default gen_random_uuid(),
  resource_id uuid not null references resources(id) on delete cascade,
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  capacity int not null default 1,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists bookings (
  id uuid primary key default gen_random_uuid(),
  slot_id uuid not null references slots(id) on delete cascade,
  -- no passwords: users are identified by email/userid only
  client_email text not null,
  client_id text,
  status text not null default 'confirmed', -- confirmed | cancelled | rescheduled
  history jsonb not null default '[]'::jsonb, -- append-only status history
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_slots_resource_id on slots(resource_id);
-- Every availability / month-density / calendar read filters slots by a
-- starts_at time window (slot_occupancy is grouped on it too); without this the
-- window can't be selectively scanned.
create index if not exists idx_slots_starts_at on slots(starts_at);
create index if not exists idx_bookings_slot_id on bookings(slot_id);
create index if not exists idx_bookings_client_email on bookings(client_email);
-- Owner-side client screening (owner.py _client_profile) filters bookings by
-- client_id; only client_email was indexed.
create index if not exists idx_bookings_client_id on bookings(client_id);

-- ===========================================================================
-- Extended entities: providers, services, multi-slot bookings, reviews, follows
-- (added for the frontend wiring). NEW tables only, idempotent like everything
-- else — the three base tables above stay frozen; their new domain fields live
-- in `metadata` (resources: service_id/capacity/active/attributes/image_url;
-- slots: service_id; bookings: party_size/reference/price_minor_units/currency/
-- provider_id/service_id/resource_id/change_history/slot_ids).
-- ===========================================================================

-- A provider is the business/tenant (labelled via terms.admin). Presentational
-- fields (avatar/cover/tagline/bio/location/links) live in metadata; `rating`
-- and `reviewCount` are DERIVED from `reviews`, never stored.
create table if not exists providers (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid references auth.users(id) on delete set null,
  name text not null,
  public_code text unique,          -- looked up by code entry / QR
  category_id text,                 -- vertical category (engine-neutral string)
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- A service is a bookable offering under a provider. The rules the frontend
-- models PER SERVICE live here as columns (duration/min-max/cutoff/price);
-- domain.config.json now holds only global defaults + vocabulary.
create table if not exists services (
  id uuid primary key default gen_random_uuid(),
  provider_id uuid not null references providers(id) on delete cascade,
  name text not null,
  description text,
  booking_model text not null default 'one_to_one', -- unit_selection | one_to_one | shared_capacity
  slot_duration_minutes int not null default 30,
  min_slots_per_booking int not null default 1,
  max_slots_per_booking int not null default 1,
  price_minor_units int not null default 0,
  currency text not null default 'EUR',
  cancellation_cutoff_hours int not null default 24,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- Multi-slot bookings: a booking links to one-or-more slots. `bookings.slot_id`
-- stays populated (the first slot) for compatibility; this join table is the
-- full set and the basis for occupancy.
create table if not exists booking_slots (
  booking_id uuid not null references bookings(id) on delete cascade,
  slot_id uuid not null references slots(id) on delete cascade,
  primary key (booking_id, slot_id)
);

-- One review per completed booking; provider rating/reviewCount are computed
-- from these rows.
create table if not exists reviews (
  id uuid primary key default gen_random_uuid(),
  booking_id uuid not null references bookings(id) on delete cascade,
  provider_id uuid not null references providers(id) on delete cascade,
  rating int not null,
  text text,
  created_at timestamptz not null default now()
);

-- A user follows a provider. user_id is auth.users(id).
create table if not exists follows (
  user_id uuid not null references auth.users(id) on delete cascade,
  provider_id uuid not null references providers(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, provider_id)
);

-- Client reputation: a provider rates a customer after a completed booking.
-- One review per booking; feeds the customer's public reputation and the
-- owner-side request screening. client_id is auth.users(id) as text (mirrors
-- bookings.client_id).
create table if not exists client_reviews (
  id uuid primary key default gen_random_uuid(),
  booking_id uuid not null references bookings(id) on delete cascade,
  client_id text not null,
  provider_id uuid references providers(id) on delete cascade,
  rating int not null check (rating between 1 and 5),
  text text not null default '',
  created_at timestamptz not null default now()
);
create unique index if not exists uq_client_reviews_booking on client_reviews(booking_id);
create index if not exists idx_client_reviews_client on client_reviews(client_id);

create index if not exists idx_services_provider_id on services(provider_id);
create index if not exists idx_booking_slots_slot_id on booking_slots(slot_id);
create index if not exists idx_booking_slots_booking_id on booking_slots(booking_id);
create index if not exists idx_reviews_provider_id on reviews(provider_id);
create index if not exists idx_reviews_booking_id on reviews(booking_id);
create index if not exists idx_follows_user_id on follows(user_id);

-- Occupancy sums PARTY SIZE across confirmed bookings that include each slot
-- (via booking_slots), so shared-capacity party sizes and multi-slot bookings
-- both count correctly. Only 'confirmed' holds capacity (cancelled/rescheduled
-- release it). party_size defaults to 1 when absent from metadata.
create or replace view slot_occupancy as
select
  s.id as slot_id,
  s.resource_id,
  s.starts_at,
  s.ends_at,
  s.capacity,
  coalesce(sum(coalesce((b.metadata->>'party_size')::int, 1))
           filter (where b.status = 'confirmed'), 0) as booked_count,
  s.capacity - coalesce(sum(coalesce((b.metadata->>'party_size')::int, 1))
           filter (where b.status = 'confirmed'), 0) as available_count
from slots s
left join booking_slots bs on bs.slot_id = s.id
left join bookings b on b.id = bs.booking_id
group by s.id, s.resource_id, s.starts_at, s.ends_at, s.capacity;

-- ===========================================================================
-- Auth: profiles + Row Level Security (branch 16-auth-system)
-- ===========================================================================
-- Supabase owns auth.users + password hashing; `profiles` holds the per-user
-- app data (the engine role) keyed 1:1 to auth.users. Roles are engine-neutral
-- strings ('owner' | 'client') — the UI labels them via terms.admin/terms.client
-- and the backend uses the same tokens for `actor`. Idempotent like everything
-- above: only create-if-not-exists / or-replace, and `drop policy if exists`
-- before each policy (policies are exempt from the no-DROP rule).
--
-- IMPORTANT: the backend talks to Postgres with the Supabase SERVICE key, which
-- BYPASSES RLS. These policies therefore only constrain requests made with a
-- *user's* JWT. They are the database-level isolation layer for when per-user
-- reads carry the token; until then the backend enforces the same rules in the
-- router (defense in depth). See supabase/CLAUDE.md and backend/CLAUDE.md.

create table if not exists profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  role text not null default 'client', -- engine role: owner | client
  created_at timestamptz not null default now()
);

-- Trusted role check used by the policies below. SECURITY DEFINER so it can read
-- profiles regardless of the caller's own RLS (and to avoid policy recursion).
create or replace function public.is_owner()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.role = 'owner'
  );
$$;

-- Auto-provision a profile on sign-up, copying the role the user registered
-- with (the frontend puts it in user_metadata → raw_user_meta_data). An admin
-- can later UPDATE profiles.role to promote/revoke — that becomes the trusted
-- source of truth for is_owner().
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, role)
  values (
    new.id,
    new.email,
    case when new.raw_user_meta_data->>'role' = 'owner' then 'owner' else 'client' end
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

-- The trigger lives on auth.users; creating it needs privileges the direct DB
-- role may not have. Guard it so a fresh DB still gets its public tables and
-- policies (the whole file runs as one transaction — an uncaught error here
-- would roll all of that back). If skipped, populate profiles via an admin.
do $$
begin
  drop trigger if exists on_auth_user_created on auth.users;
  create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();
exception
  when insufficient_privilege or undefined_table then
    raise notice 'Skipping auth.users trigger (no privilege); populate profiles manually.';
end $$;

alter table profiles  enable row level security;
alter table resources enable row level security;
alter table slots     enable row level security;
alter table bookings  enable row level security;

-- profiles: a user reads only their own row. No insert/update/delete policy for
-- the API, so a client can't self-promote to owner — only the trigger, the
-- service role, or an admin (all RLS-exempt) write profiles.
drop policy if exists profiles_select_own on profiles;
create policy profiles_select_own on profiles
  for select using (auth.uid() = id);

-- resources: public read (the landing page lists them for anon visitors); only
-- an owner creates, and only the owning owner modifies/deletes. Ownership is
-- recorded in metadata.owner_id (schema is frozen — no new column), stamped by
-- the backend's create_resource.
drop policy if exists resources_select_all on resources;
create policy resources_select_all on resources
  for select using (true);

drop policy if exists resources_insert_owner on resources;
create policy resources_insert_owner on resources
  for insert with check (public.is_owner());

drop policy if exists resources_modify_own on resources;
create policy resources_modify_own on resources
  for update using (public.is_owner() and metadata->>'owner_id' = auth.uid()::text)
  with check  (public.is_owner() and metadata->>'owner_id' = auth.uid()::text);

drop policy if exists resources_delete_own on resources;
create policy resources_delete_own on resources
  for delete using (public.is_owner() and metadata->>'owner_id' = auth.uid()::text);

-- slots: public read; write limited to the owner of the parent resource.
drop policy if exists slots_select_all on slots;
create policy slots_select_all on slots
  for select using (true);

drop policy if exists slots_write_owner on slots;
create policy slots_write_owner on slots
  for all
  using (
    public.is_owner() and exists (
      select 1 from resources r
      where r.id = slots.resource_id
        and r.metadata->>'owner_id' = auth.uid()::text
    )
  )
  with check (
    public.is_owner() and exists (
      select 1 from resources r
      where r.id = slots.resource_id
        and r.metadata->>'owner_id' = auth.uid()::text
    )
  );

-- bookings: a client sees/creates/modifies only their own (client_id holds the
-- auth user id, set from the token); an owner sees and manages all.
drop policy if exists bookings_select_own_or_owner on bookings;
create policy bookings_select_own_or_owner on bookings
  for select using (client_id = auth.uid()::text or public.is_owner());

drop policy if exists bookings_insert_own on bookings;
create policy bookings_insert_own on bookings
  for insert with check (client_id = auth.uid()::text);

drop policy if exists bookings_update_own_or_owner on bookings;
create policy bookings_update_own_or_owner on bookings
  for update using (client_id = auth.uid()::text or public.is_owner())
  with check  (client_id = auth.uid()::text or public.is_owner());

drop policy if exists bookings_delete_owner on bookings;
create policy bookings_delete_owner on bookings
  for delete using (public.is_owner());

-- ===========================================================================
-- RLS for the extended entities (same model: public read for discovery, owner
-- writes for provider/service, per-user writes for bookings' children/follows).
-- ===========================================================================
alter table providers     enable row level security;
alter table services      enable row level security;
alter table booking_slots enable row level security;
alter table reviews       enable row level security;
alter table follows       enable row level security;
alter table client_reviews enable row level security;

-- providers: public read (discovery/landing); an owner manages only their own.
drop policy if exists providers_select_all on providers;
create policy providers_select_all on providers for select using (true);

drop policy if exists providers_write_own on providers;
create policy providers_write_own on providers for all
  using (public.is_owner() and owner_id = auth.uid())
  with check (public.is_owner() and owner_id = auth.uid());

-- services: public read; write limited to the owner of the parent provider.
drop policy if exists services_select_all on services;
create policy services_select_all on services for select using (true);

drop policy if exists services_write_own on services;
create policy services_write_own on services for all
  using (public.is_owner() and exists (
    select 1 from providers p
    where p.id = services.provider_id and p.owner_id = auth.uid()))
  with check (public.is_owner() and exists (
    select 1 from providers p
    where p.id = services.provider_id and p.owner_id = auth.uid()));

-- booking_slots: visible/writable to the booking's owner (client) or any owner.
drop policy if exists booking_slots_select on booking_slots;
create policy booking_slots_select on booking_slots for select
  using (exists (select 1 from bookings b where b.id = booking_id
                 and (b.client_id = auth.uid()::text or public.is_owner())));

drop policy if exists booking_slots_write on booking_slots;
create policy booking_slots_write on booking_slots for all
  using (exists (select 1 from bookings b where b.id = booking_id
                 and (b.client_id = auth.uid()::text or public.is_owner())))
  with check (exists (select 1 from bookings b where b.id = booking_id
                 and (b.client_id = auth.uid()::text or public.is_owner())));

-- reviews: public read (feeds provider ratings); a client writes a review only
-- for their own booking.
drop policy if exists reviews_select_all on reviews;
create policy reviews_select_all on reviews for select using (true);

drop policy if exists reviews_insert_own on reviews;
create policy reviews_insert_own on reviews for insert
  with check (exists (select 1 from bookings b where b.id = booking_id
                      and b.client_id = auth.uid()::text));

-- client_reviews: public read (feeds a customer's reputation + owner screening);
-- only an owner writes one (the router further checks they own the booking's
-- provider). No update/delete policy — a re-review deletes+inserts via the
-- service key, like the provider-reviews flow.
drop policy if exists client_reviews_select_all on client_reviews;
create policy client_reviews_select_all on client_reviews for select using (true);

drop policy if exists client_reviews_insert_owner on client_reviews;
create policy client_reviews_insert_owner on client_reviews for insert
  with check (public.is_owner());

-- follows: a user sees and manages only their own follows.
drop policy if exists follows_select_own on follows;
create policy follows_select_own on follows for select using (user_id = auth.uid());

drop policy if exists follows_write_own on follows;
create policy follows_write_own on follows for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ===========================================================================
-- Messaging: 1:1 conversations between a client and a provider's owner
-- (branch 40-messaging). A NEW entity, so — per the pivot design — it's added
-- as new tables; the frozen base tables are untouched. Live delivery rides on
-- Supabase Realtime (postgres_changes) gated by the same RLS below.
-- ===========================================================================

-- One thread per (provider, client) pair. `owner_id` is the provider's owner,
-- denormalized so RLS / Realtime is a flat column compare (nullable — some
-- seeded providers carry no owner_id). last_message_* are stamped by the
-- trigger below so the inbox can list threads without scanning messages.
create table if not exists conversations (
  id uuid primary key default gen_random_uuid(),
  provider_id uuid not null references providers(id) on delete cascade,
  client_id uuid not null references auth.users(id) on delete cascade,
  owner_id uuid references auth.users(id) on delete set null,
  last_message_at timestamptz,
  last_message_preview text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (provider_id, client_id)
);

-- A message in a thread. Soft-deleted (deleted_at) rather than removed, so the
-- "Message deleted" placeholder and receipts survive. reply_to_id quotes another
-- message; delivered_at/read_at drive the iMessage-style receipts.
create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations(id) on delete cascade,
  sender_id uuid not null references auth.users(id) on delete cascade,
  body text not null,
  reply_to_id uuid references messages(id) on delete set null,
  delivered_at timestamptz,
  read_at timestamptz,
  deleted_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_messages_conversation on messages(conversation_id, created_at);
create index if not exists idx_conversations_client on conversations(client_id);
create index if not exists idx_conversations_owner on conversations(owner_id);
create index if not exists idx_conversations_provider on conversations(provider_id);

alter table conversations enable row level security;
alter table messages      enable row level security;

-- conversations: a participant (the client or the provider's owner) sees and
-- manages their own threads.
drop policy if exists conversations_select_participant on conversations;
create policy conversations_select_participant on conversations for select
  using (client_id = auth.uid() or owner_id = auth.uid());

drop policy if exists conversations_insert_participant on conversations;
create policy conversations_insert_participant on conversations for insert
  with check (client_id = auth.uid() or owner_id = auth.uid());

drop policy if exists conversations_update_participant on conversations;
create policy conversations_update_participant on conversations for update
  using (client_id = auth.uid() or owner_id = auth.uid())
  with check (client_id = auth.uid() or owner_id = auth.uid());

-- messages: visible/updatable to either participant of the parent conversation
-- (mirrors booking_slots' membership check); a message can only be inserted by
-- its own sender, and only into a conversation they participate in.
drop policy if exists messages_select_participant on messages;
create policy messages_select_participant on messages for select
  using (exists (select 1 from conversations c where c.id = conversation_id
                 and (c.client_id = auth.uid() or c.owner_id = auth.uid())));

drop policy if exists messages_insert_sender on messages;
create policy messages_insert_sender on messages for insert
  with check (sender_id = auth.uid() and exists (
    select 1 from conversations c where c.id = conversation_id
    and (c.client_id = auth.uid() or c.owner_id = auth.uid())));

drop policy if exists messages_update_participant on messages;
create policy messages_update_participant on messages for update
  using (exists (select 1 from conversations c where c.id = conversation_id
                 and (c.client_id = auth.uid() or c.owner_id = auth.uid())))
  with check (exists (select 1 from conversations c where c.id = conversation_id
                 and (c.client_id = auth.uid() or c.owner_id = auth.uid())));

-- Full replica identity so an UPDATE's Realtime payload carries the old + new
-- rows (read receipts and soft-deletes are UPDATEs the recipient must see live).
alter table messages replica identity full;

-- Bump the parent thread's preview/timestamp on every new message, so the inbox
-- reflects the latest line without a separate write path.
create or replace function public.touch_conversation()
returns trigger
language plpgsql
as $$
begin
  update public.conversations
     set last_message_at = new.created_at,
         last_message_preview = new.body
   where id = new.conversation_id;
  return new;
end;
$$;

drop trigger if exists on_message_insert on messages;
create trigger on_message_insert
  after insert on messages
  for each row execute function public.touch_conversation();

-- Publish the two tables to Supabase Realtime. Altering the managed
-- `supabase_realtime` publication can need privileges the direct DB role lacks
-- (same story as the auth.users trigger / storage bucket above), and re-adding a
-- table already in the publication raises duplicate_object — guard both so a
-- re-run is a no-op and a privilege gap degrades to HTTP-only (enable the tables
-- manually via Dashboard → Database → Replication).
do $$
begin
  alter publication supabase_realtime add table messages;
exception
  when duplicate_object then null;
  when insufficient_privilege or undefined_object then
    raise notice 'Skipping realtime publish for messages (no privilege / publication missing); enable it via the Supabase dashboard.';
end $$;

do $$
begin
  alter publication supabase_realtime add table conversations;
exception
  when duplicate_object then null;
  when insufficient_privilege or undefined_object then
    raise notice 'Skipping realtime publish for conversations (no privilege / publication missing); enable it via the Supabase dashboard.';
end $$;

-- ===========================================================================
-- Storage: avatar uploads (branch 35-profile-picture)
-- ===========================================================================
-- Public-read bucket for user avatars, matching the existing precedent that
-- provider avatar/cover images are already public. Objects are keyed
-- "{auth.uid()}/avatar" (no extension — Content-Type carries the format), so
-- there is exactly one possible object per user; the backend uploads/deletes
-- with the service key (ownership is enforced by deriving the key from the
-- verified JWT's user id server-side, never client input) — these policies are
-- defense-in-depth only, same model as the rest of this file.
--
-- Bucket/policy DDL can need privilege the direct DB role may not have (like
-- the auth.users trigger above); guard it the same way so a fresh DB still
-- gets everything else. If skipped, create the bucket/policies manually via
-- the Supabase dashboard.
do $$
begin
  insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
  values ('avatars', 'avatars', true, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
  on conflict (id) do nothing;

  -- No public "select" policy: a public bucket serves individual object reads
  -- via the /storage/v1/object/public/... endpoint, which bypasses RLS
  -- entirely, so a broad `select` policy here isn't needed for <img> to work
  -- and would instead let any authenticated client list/enumerate every
  -- object (i.e. every user id) in the bucket via storage.objects directly.
  drop policy if exists avatars_select_all on storage.objects;

  drop policy if exists avatars_select_own on storage.objects;
  create policy avatars_select_own on storage.objects for select
    using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);

  drop policy if exists avatars_write_own on storage.objects;
  create policy avatars_write_own on storage.objects for all
    using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text)
    with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);
exception
  when insufficient_privilege or undefined_table then
    raise notice 'Skipping avatars storage bucket/policies (no privilege); create manually via the Supabase dashboard.';
end $$;

-- ===========================================================================
-- Entitlements: what a customer has BOUGHT that changes what a booking costs
-- or whether it is allowed at all — a membership, a class pass, prepaid
-- credits. `domain.config.json` declares the PLANS (`entitlements.plans[]`);
-- this table records who holds one. A NEW entity, so per the pivot design it
-- is a new table and the frozen base tables are untouched.
--
-- `plan_key` is not a foreign key: plans live in the config file, not the DB,
-- so a plan can be renamed or retired without orphaning history. A row whose
-- plan_key no longer resolves is simply inert (see rules.resolve_entitlement).
--
-- `credits_total`/`credits_used` back the `pass` and `credits` kinds; a
-- `membership` leaves them null and rides on the plan's discountBps instead.
create table if not exists entitlements (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan_key text not null,
  -- Which business sold it. Null in single-tenant deployments, where there is
  -- only ever one.
  provider_id uuid references providers(id) on delete cascade,
  status text not null default 'active' check (status in ('active', 'expired', 'cancelled')),
  credits_total int,
  credits_used int not null default 0,
  starts_at timestamptz not null default now(),
  -- Null = open-ended (a rolling membership with no end date).
  ends_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_entitlements_user on entitlements(user_id, status);
create index if not exists idx_entitlements_plan on entitlements(plan_key);

alter table entitlements enable row level security;

-- A customer sees and manages only their own entitlements. Granting one to
-- someone else is a system/owner action and goes through the service key,
-- which bypasses RLS — exactly as bookings' owner-side writes already do.
drop policy if exists entitlements_select_own on entitlements;
create policy entitlements_select_own on entitlements for select using (user_id = auth.uid());

drop policy if exists entitlements_write_own on entitlements;
create policy entitlements_write_own on entitlements for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ===========================================================================
-- Waitlist: who wants a slot that is already full. `timing.waitlist` declares
-- whether the deployment offers one, how deep it goes (`maxPerSlot`) and
-- whether a freed seat is handed to the head of the queue automatically
-- (`autoPromote`). The whole block shipped in v2 and was enforced by nothing:
-- a config could advertise a 200-deep auto-promoting waitlist and the engine
-- had no way to record a single person on it.
--
-- A NEW entity, so per the pivot design it is a new table; the frozen base
-- tables are untouched.
--
-- `position` is assigned at join time and never renumbered — a queue that
-- resequences on every departure lets someone move backwards, which is the one
-- thing a queue must never do. Promotion reads the lowest position among
-- 'waiting' rows, so gaps are harmless.
create table if not exists waitlist_entries (
  id uuid primary key default gen_random_uuid(),
  slot_id uuid not null references slots(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  -- Denormalised so promotion can build a booking without re-reading the slot's
  -- service/resource; slots carry service_id only in metadata.
  service_id uuid references services(id) on delete cascade,
  resource_id uuid references resources(id) on delete cascade,
  party_size int not null default 1 check (party_size >= 1),
  position int not null,
  status text not null default 'waiting'
    check (status in ('waiting', 'promoted', 'cancelled', 'expired')),
  -- The booking created when this entry was promoted, for audit.
  booking_id uuid references bookings(id) on delete set null,
  created_at timestamptz not null default now()
);
-- One live entry per person per slot: joining twice would take two places in
-- the queue for one customer.
create unique index if not exists uq_waitlist_slot_user
  on waitlist_entries(slot_id, user_id) where status = 'waiting';
create index if not exists idx_waitlist_slot on waitlist_entries(slot_id, status, position);
create index if not exists idx_waitlist_user on waitlist_entries(user_id, status);

alter table waitlist_entries enable row level security;

-- A customer sees and manages only their own place in a queue. Promotion is a
-- system action and runs through the service key, which bypasses RLS.
drop policy if exists waitlist_select_own on waitlist_entries;
create policy waitlist_select_own on waitlist_entries for select using (user_id = auth.uid());

drop policy if exists waitlist_write_own on waitlist_entries;
create policy waitlist_write_own on waitlist_entries for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());
