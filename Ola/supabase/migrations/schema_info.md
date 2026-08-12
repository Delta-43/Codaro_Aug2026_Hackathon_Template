# `EXTENSION`
Line: `CREATE EXTENSION IF NOT EXISTS pgcrypto;`

A Postgres **extension** is an optional add-on package of extra functionality that isn't part of the database by default. `pgcrypto` adds cryptography-related functions — including `gen_random_uuid()` from point 1. `IF NOT EXISTS` just means "don't throw an error if this extension is already installed" — it makes the script safe to run more than once.


# `TYPE`
Line: `CREATE TYPE reservation_status AS ENUM ('pending', 'confirmed', 'cancelled');`

This creates a custom **type** called `reservation_status`, specifically an **ENUM** (short for "enumeration"). An ENUM is a type that can only ever hold one of a fixed, predefined list of values — here, only `'pending'`, `'confirmed'`, or `'cancelled'`. Think of it like a multiple-choice dropdown instead of a free-text box: if you try to insert `'maybe'`, the database will reject it. This `reservation_status` type is then used as the type of the `status` column on the `reservations` table.


# `UUID`
Line: `id  UUID  PRIMARY KEY DEFAULT gen_random_uuid(),`

`UUID` ("Universally Unique Identifier") is a **data type** for IDs. Instead of simple counting numbers (1, 2, 3…), a UUID looks like `f47ac10b-58cc-4372-a567-0e02b2c3d479` — a long, effectively-random string. Why use it instead of a plain number?
- It doesn't reveal how many rows exist (a number like `id = 42` leaks that info; a UUID doesn't).
- The chance of two UUIDs ever colliding is astronomically small, even across different tables or databases.
- It can be generated before the row is even inserted, if needed.

Every table in this schema uses `UUID` as its primary key type for these reasons.


# `gen_random_uuid()`
Line: `id  UUID  PRIMARY KEY DEFAULT gen_random_uuid(),`

`gen_random_uuid()` is a **function** — it generates a random unique ID every time it's called. `DEFAULT gen_random_uuid()` means: "if nobody supplies a value for `id` when a new row is inserted, run this function and use whatever it returns." So every new resource, slot, client, etc. automatically gets a unique ID — you never have to invent one yourself. This function comes from the `pgcrypto` extension (see point 3 below).

# `JSONB`
Line: `metadata  JSONB  NOT NULL DEFAULT '{}'::JSONB`

`JSONB` is a data type for storing JSON documents (think: nested key/value data like `{"color": "blue", "seats": 4}`) directly in a column, but in a pre-parsed *binary* form (that's what the "B" stands for) rather than as plain text. That means Postgres can search and index inside the JSON efficiently, unlike a plain `JSON`/`TEXT` column where it would have to re-read the whole string every time. It's used here for `metadata` because different resources may need different extra fields (a room might need "projector: true", a doctor might need "specialty: cardiology") — rather than adding a new column for every possible field, this one flexible column can hold whatever shape of data each resource type needs. `DEFAULT '{}'::JSONB` means: if nothing is provided, start with an empty JSON object `{}` (the `::JSONB` part is a **cast**, telling Postgres to treat that text as JSONB rather than a plain string).

# `TIMESTAMPTZ`
Line: `start_time  TIMESTAMPTZ NOT NULL,`

`TIMESTAMPTZ` = "timestamp with time zone." It's a data type that stores a specific point in time (date + time) along with time zone awareness. Internally Postgres stores it as UTC and converts it for display based on whoever's asking. This matters for a booking app because clients could be in different time zones — using `TIMESTAMPTZ` (instead of a plain `TIMESTAMP` with no zone info) avoids ambiguity about *whose* "9am" a slot starts at.


# `explanation`
`is_recurring  BOOLEAN  NOT NULL DEFAULT FALSE,`

This defines a column named `is_recurring`:
- `BOOLEAN` — the type; it can only be `true` or `false`.
- `NOT NULL` — this field can never be left empty; it must always have a value.
- `DEFAULT FALSE` — if you don't specify a value when inserting a row, Postgres assumes `false`.

In plain terms: it's a yes/no flag marking whether this particular slot was auto-generated from a recurring schedule (e.g. "every Monday at 9am") rather than being a one-off slot someone created manually.

# `explanation`
`CHECK (end_time > start_time)`

A `CHECK` constraint is a rule the database enforces on every row, on top of the column's basic type. Here, it says: whatever value ends up in `end_time` must be later than whatever value is in `start_time` for that same row. If you try to insert or update a slot where the end time is before (or equal to) the start time — e.g. a slot that supposedly ends before it begins — Postgres rejects the write with an error. It's a way of encoding a business rule ("a time window must actually make sense") directly into the schema, so no buggy app code can ever sneak in a nonsensical slot.

# `explanation`
`CREATE INDEX slots_resource_id_idx ON slots (resource_id);`

An **index** is like the index at the back of a book — it lets the database jump straight to the relevant rows instead of scanning the entire `slots` table every time. This particular index is built on the `resource_id` column, which makes sense because `resource_id` is a foreign key that's frequently used to look up "all the slots belonging to this resource" (and to join with the `resources` table). Trade-off: an index costs a small amount of extra disk space and slightly slows down writes (inserts/updates), but massively speeds up reads/lookups on that column — usually a great trade for columns you query often.


# `explanation`
`-- swap for a view/alias over auth.users if Supabase auth is wired up instead`

Anything after `--` in SQL is a **comment** — plain text notes for humans that Postgres completely ignores when running the script. This particular comment is a note-to-future-developer: right now, `clients` is its own table. But if this project later adds Supabase's built-in login/authentication system, Supabase already provides a table called `auth.users` for logged-in users. At that point, instead of keeping two separate, possibly-out-of-sync tables of people, you could replace this `clients` table with a **view** (a saved, reusable query that looks like a table) pointing at `auth.users`, so client info and login info stay in one place.


# `REFERENCES`
Line: `slot_id  UUID  NOT NULL REFERENCES slots (id) ON DELETE CASCADE,`

`REFERENCES` creates a **foreign key**. It means: "the value in this `slot_id` column must match the `id` of some existing row in the `slots` table." This is how Postgres links related tables together and protects data integrity — you can't create a reservation that points to a slot that doesn't exist. If you try, the database will reject the insert.


# `ON DELETE CASCADE`
Line: `slot_id  UUID  NOT NULL REFERENCES slots (id) ON DELETE CASCADE,`

This controls what happens to a row when the row it references gets deleted. `ON DELETE CASCADE` means: "if the referenced `slot` is deleted, automatically delete every `reservation` that pointed to it too." This keeps the database clean — you never end up with "orphan" reservations pointing at a slot that no longer exists. (The alternative, not used here, would be something like `ON DELETE RESTRICT`, which would instead *block* you from deleting a slot while reservations still reference it.)

# `explanation`
The `check_slot_capacity` function and trigger

This whole block enforces a business rule — "a slot can't have more active reservations than its resource's capacity" — directly inside the database, so it can never be bypassed by a bug in the app code. Here's what each piece does:

- **`CREATE OR REPLACE FUNCTION check_slot_capacity() RETURNS TRIGGER AS $$ ... $$ LANGUAGE plpgsql;`** — defines a small stored program (a "function") written in `plpgsql`, Postgres's procedural scripting language. `RETURNS TRIGGER` marks it as a special kind of function meant to be run automatically by a trigger, not called directly.
- **`DECLARE slot_capacity INT; active_count INT;`** — declares two local variables to temporarily hold numbers while the function runs.
- **`NEW`** — inside a trigger function, `NEW` refers to the row that's currently being inserted or updated. So `NEW.status` and `NEW.slot_id` are the values from the reservation row that's about to be saved.
- **`IF NEW.status NOT IN ('pending', 'confirmed') THEN RETURN NEW; END IF;`** — if the incoming row's status is something other than pending/confirmed (i.e., it's being cancelled), skip the capacity check entirely and let it through — cancelling never needs a capacity check.
- **`WITH active_reservations AS (...)`** — this is a CTE (Common Table Expression), basically a temporary, named mini-query you can reuse below. It finds all *other* active reservations (`pending`/`confirmed`) for the same slot, excluding the row currently being saved (`id IS DISTINCT FROM NEW.id` is a null-safe way of saying "not the same row").
- **`SELECT r.capacity, (SELECT count(*) FROM active_reservations) INTO slot_capacity, active_count FROM resources r JOIN slots s ON ... WHERE s.id = NEW.slot_id;`** — looks up the resource's total `capacity` and counts how many active reservations already exist for this slot, storing both numbers into the variables declared earlier.
- **`IF active_count >= slot_capacity THEN RAISE EXCEPTION '...';`** — if the slot is already full, stop everything and throw an error, which cancels the insert/update. `%` in the message gets filled in with `NEW.slot_id`.
- **`RETURN NEW;`** — otherwise, allow the row to be saved as normal.
- **`CREATE TRIGGER reservations_check_capacity BEFORE INSERT OR UPDATE ON reservations FOR EACH ROW EXECUTE FUNCTION check_slot_capacity();`** — this is what actually wires the function up. It tells Postgres: "before every single insert or update on the `reservations` table, run `check_slot_capacity()` first, for each row being changed." Without this line, the function above would just sit there unused — the trigger is what makes it fire automatically.