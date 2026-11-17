-- All money is integer micro-dollars (1 credit = 1000 micros). No floats.
CREATE TABLE billing.accounts (
    id          TEXT PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Append-only. amount_micros changes TOTAL funds (available + reserved): grants and top-ups
-- are positive, settles are negative. Reserve and release rows move money between available
-- and reserved, so their amount is 0 and the size of the hold is in hold_micros.
CREATE TABLE billing.ledger (
    id            BIGSERIAL PRIMARY KEY,
    account_id    TEXT NOT NULL REFERENCES billing.accounts(id),
    amount_micros BIGINT NOT NULL,
    hold_micros   BIGINT NOT NULL DEFAULT 0,
    kind          TEXT NOT NULL CHECK (kind IN ('grant', 'topup', 'reserve', 'settle', 'release', 'refund', 'adjust')),
    ref           TEXT NOT NULL,
    price_version INT,
    expires_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (kind, ref)
);
CREATE INDEX ledger_account_idx ON billing.ledger (account_id, id DESC);

CREATE FUNCTION billing.ledger_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'billing.ledger is append-only';
END $$;
CREATE TRIGGER ledger_no_update BEFORE UPDATE OR DELETE ON billing.ledger
    FOR EACH ROW EXECUTE FUNCTION billing.ledger_append_only();

CREATE TABLE billing.balances (
    account_id       TEXT PRIMARY KEY REFERENCES billing.accounts(id),
    available_micros BIGINT NOT NULL DEFAULT 0 CHECK (available_micros >= 0),
    reserved_micros  BIGINT NOT NULL DEFAULT 0 CHECK (reserved_micros >= 0),
    starter_micros   BIGINT NOT NULL DEFAULT 0 CHECK (starter_micros >= 0 AND starter_micros <= available_micros)
);

CREATE TABLE billing.reservations (
    request_id    TEXT PRIMARY KEY,
    account_id    TEXT NOT NULL REFERENCES billing.accounts(id),
    amount_micros BIGINT NOT NULL CHECK (amount_micros >= 0),
    action        TEXT NOT NULL,
    alias         TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'settled', 'released')),
    charged_micros BIGINT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX reservations_open_idx ON billing.reservations (created_at) WHERE status = 'open';

CREATE TABLE billing.prices (
    version          INT NOT NULL,
    alias            TEXT NOT NULL,
    tier             TEXT NOT NULL CHECK (tier IN ('open', 'premium')),
    input_per_m      NUMERIC(14, 6) NOT NULL,
    output_per_m     NUMERIC(14, 6) NOT NULL,
    cache_read_per_m NUMERIC(14, 6) NOT NULL DEFAULT 0,
    multiplier       NUMERIC(6, 3) NOT NULL CHECK (multiplier >= 1),
    effective_from   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (version, alias)
);

CREATE TABLE billing.payments (
    id             BIGSERIAL PRIMARY KEY,
    provider       TEXT NOT NULL,
    provider_ref   TEXT NOT NULL,
    account_id     TEXT NOT NULL REFERENCES billing.accounts(id),
    gross_minor    BIGINT NOT NULL,
    currency       TEXT NOT NULL,
    credits_micros BIGINT NOT NULL,
    status         TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_ref)
);

CREATE TABLE billing.grant_days (
    day   DATE PRIMARY KEY,
    count INT NOT NULL DEFAULT 0
);
