-- Rysia's schema — resources -> slots -> bookings
-- Built from scratch to learn the model. See DECISIONS.md for the "why" behind each choice.

create extension if not exists pgcrypto; -- gives us gen_random_uuid()

-- ============================================================
-- RESOURCES: the bookable thing (a room, a tutor, a car — anything)
-- ============================================================
create table resources (
    id                          uuid primary key default gen_random_uuid(),
    name                        text not null,
    category                    text,                          -- e.g. "meeting room" — for filtering/grouping
    capacity                    int  not null default 1 check (capacity > 0),      -- max concurrent bookings per slot
    buffer_minutes              int  not null default 0 check (buffer_minutes >= 0), -- required gap between slots
    cancellation_window_hours   int  not null default 0 check (cancellation_window_hours >= 0), -- how late you can still cancel
    created_at                  timestamptz not null default now()
);
-- Business rules live as COLUMNS here, not hardcoded numbers in code, on purpose:
-- when the pivot changes "a tutoring session needs 2h notice" to "a car needs 0",
-- that's a data update, not a code change.

-- ============================================================
-- SLOTS: fixed, bookable time windows belonging to one resource
-- ============================================================
create table slots (
    id            uuid primary key default gen_random_uuid(),
    resource_id   uuid not null references resources (id) on delete cascade,
    start_time    timestamptz not null,
    end_time      timestamptz not null,
    created_at    timestamptz not null default now(),
    check (end_time > start_time)
);

create index slots_resource_id_idx on slots (resource_id);

-- ============================================================
-- CLIENTS: who books. Simple table for now — can be swapped for
-- Supabase auth.users later without touching resources/slots/bookings.
-- ============================================================
create table clients (
    id     uuid primary key default gen_random_uuid(),
    name   text not null,
    email  text not null unique
);

-- ============================================================
-- BOOKINGS: the reservation itself
-- ============================================================
create type booking_status as enum ('pending', 'confirmed', 'cancelled');

create table bookings (
    id          uuid primary key default gen_random_uuid(),
    slot_id     uuid not null references slots (id) on delete cascade,
    client_id   uuid not null references clients (id) on delete cascade,
    status      booking_status not null default 'pending',
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create index bookings_slot_id_idx on bookings (slot_id);
create index bookings_client_id_idx on bookings (client_id);

-- ============================================================
-- RULE: max bookings per slot (resources.capacity)
-- Enforced here, in the database, not just in the API — so it can
-- never be bypassed by a bug or a second app hitting the same DB.
-- ============================================================
create or replace function check_slot_capacity()
returns trigger as $$
declare
    slot_capacity int;
    active_count  int;
begin
    if new.status = 'cancelled' then
        return new; -- cancelling never needs a capacity check
    end if;

    -- Lock the slot row FIRST, before counting. Without this line, two
    -- simultaneous booking requests for the same slot can both run the
    -- count below before either one commits, both see "capacity not
    -- reached yet", and both get inserted -> overbooking. Locking the
    -- slot row forces the second transaction to wait until the first
    -- one finishes, so it always counts against up-to-date data.
    perform 1 from slots where id = new.slot_id for update;

    select r.capacity into slot_capacity
      from resources r
      join slots s on s.resource_id = r.id
     where s.id = new.slot_id;

    select count(*) into active_count
      from bookings b
     where b.slot_id = new.slot_id
       and b.status in ('pending', 'confirmed')
       and b.id is distinct from new.id;

    if active_count >= slot_capacity then
        raise exception 'slot % is already at capacity', new.slot_id;
    end if;

    return new;
end;
$$ language plpgsql;

create trigger bookings_check_capacity
    before insert or update on bookings
    for each row
    execute function check_slot_capacity();

-- ============================================================
-- AVAILABILITY VIEW: what the frontend calendar queries directly
-- ============================================================
create view availability as
select
    r.id as resource_id,
    r.name as resource_name,
    s.id as slot_id,
    s.start_time,
    s.end_time,
    r.capacity,
    count(b.id) filter (where b.status in ('pending', 'confirmed')) as booked_count,
    (r.capacity - count(b.id) filter (where b.status in ('pending', 'confirmed'))) as spots_left
from resources r
join slots s on s.resource_id = r.id
left join bookings b on b.slot_id = s.id
group by r.id, r.name, s.id, s.start_time, s.end_time, r.capacity;

-- Buffer time (resources.buffer_minutes) and cancellation window
-- (resources.cancellation_window_hours) are intentionally NOT enforced
-- here — see DECISIONS.md for why they live in the FastAPI layer instead.
