-- A hold remembers how much of it came from starter credits and which tier it is for,
-- so release and settle can return the right kind of credit.
ALTER TABLE billing.reservations
    ADD COLUMN starter_hold_micros BIGINT NOT NULL DEFAULT 0 CHECK (starter_hold_micros >= 0),
    ADD COLUMN tier TEXT NOT NULL DEFAULT 'open' CHECK (tier IN ('open', 'premium'));
