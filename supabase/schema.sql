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
