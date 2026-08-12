-- Schema for Reservations and Resource Scheduling
-- Mirrors docs/database.md

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE reservation_status AS ENUM ('pending', 'confirmed', 'cancelled');

CREATE TABLE resources (
    id                          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name                        TEXT        NOT NULL,
    category                    TEXT,
    capacity                    INT         NOT NULL DEFAULT 1 CHECK (capacity > 0),
    buffer_minutes              INT         NOT NULL DEFAULT 0 CHECK (buffer_minutes >= 0),
    cancellation_window_hours   INT         NOT NULL DEFAULT 0 CHECK (cancellation_window_hours >= 0),
    metadata                    JSONB       NOT NULL DEFAULT '{}'::JSONB
);

CREATE TABLE slots (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id   UUID        NOT NULL REFERENCES resources (id) ON DELETE CASCADE,
    start_time    TIMESTAMPTZ NOT NULL,
    end_time      TIMESTAMPTZ NOT NULL,
    is_recurring  BOOLEAN     NOT NULL DEFAULT FALSE,
    CHECK (end_time > start_time)
);

CREATE INDEX slots_resource_id_idx ON slots (resource_id);

-- swap for a view/alias over auth.users if Supabase auth is wired up instead
CREATE TABLE clients (
    id     UUID  PRIMARY KEY DEFAULT gen_random_uuid(),
    name   TEXT  NOT NULL,
    email  TEXT  NOT NULL UNIQUE
);

CREATE TABLE reservations (
    id          UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    slot_id     UUID                NOT NULL REFERENCES slots (id) ON DELETE CASCADE,
    client_id   UUID                NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    status      reservation_status  NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ         NOT NULL DEFAULT now()
);

CREATE INDEX reservations_slot_id_idx ON reservations (slot_id);
CREATE INDEX reservations_client_id_idx ON reservations (client_id);

-- one row per status transition; keeps a full audit trail independent of
-- the mutable `reservations.status` column
CREATE TABLE reservation_events (
    id               UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    reservation_id   UUID                NOT NULL REFERENCES reservations (id) ON DELETE CASCADE,
    action           TEXT                NOT NULL,
    old_status       reservation_status,
    new_status       reservation_status  NOT NULL,
    changed_at       TIMESTAMPTZ         NOT NULL DEFAULT now(),
    reason           TEXT
);

CREATE INDEX reservation_events_reservation_id_idx ON reservation_events (reservation_id);

-- capacity can exceed 1 (e.g. a shared resource), so a plain UNIQUE
-- constraint on slot_id can't express the rule; enforce it here instead
CREATE OR REPLACE FUNCTION check_slot_capacity()
RETURNS TRIGGER AS $$
DECLARE
    slot_capacity INT;
    active_count  INT;
BEGIN
    IF NEW.status NOT IN ('pending', 'confirmed') THEN
        RETURN NEW;
    END IF;

    WITH active_reservations AS (
        SELECT id
        FROM reservations
        WHERE slot_id = NEW.slot_id
          AND status IN ('pending', 'confirmed')
          AND id IS DISTINCT FROM NEW.id
    )
    SELECT r.capacity,
           (SELECT count(*) FROM active_reservations)
    INTO   slot_capacity,
           active_count
    FROM   resources r
    JOIN   slots s ON s.resource_id = r.id
    WHERE  s.id = NEW.slot_id;

    IF active_count >= slot_capacity THEN
        RAISE EXCEPTION 'slot % is already at capacity', NEW.slot_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER reservations_check_capacity
    BEFORE INSERT OR UPDATE ON reservations
    FOR EACH ROW
    EXECUTE FUNCTION check_slot_capacity();
