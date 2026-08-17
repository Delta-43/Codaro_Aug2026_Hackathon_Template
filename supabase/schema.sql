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
create index if not exists idx_bookings_slot_id on bookings(slot_id);
create index if not exists idx_bookings_client_email on bookings(client_email);

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
