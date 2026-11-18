-- One free starter allowance per mailbox. Only a one-way key is stored, never the address.
CREATE TABLE billing.grant_emails (
    email_key  TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES billing.accounts(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
