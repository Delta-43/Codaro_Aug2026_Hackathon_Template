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

create or replace view slot_occupancy as
select
  s.id as slot_id,
  s.resource_id,
  s.starts_at,
  s.ends_at,
  s.capacity,
  count(b.id) filter (where b.status = 'confirmed') as booked_count,
  s.capacity - count(b.id) filter (where b.status = 'confirmed') as available_count
from slots s
left join bookings b on b.slot_id = s.id
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
