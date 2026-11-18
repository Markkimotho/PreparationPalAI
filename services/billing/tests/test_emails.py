from datetime import date

import pytest

from billing import ledger
from billing.emails import email_key, is_disposable
from billing.grants import GrantResult, grant_starter

DAY = date(2026, 11, 17)


@pytest.fixture(autouse=True)
def require_verified_email(monkeypatch):
    monkeypatch.setenv('BILLING_REQUIRE_VERIFIED_EMAIL', 'true')


def grant(conn, account, email, verified=True, cap=None):
    return grant_starter(conn, account, DAY, email=email, email_verified=verified, cap=cap)


@pytest.mark.parametrize('variants', [
    ['a.b.c@gmail.com', 'abc@gmail.com', 'ABC@GMAIL.COM', 'a.b.c+promo@gmail.com', 'abc@googlemail.com', '  abc+x+y@Gmail.com '],
    ['Jo@Example.com', 'jo+tag@example.com', 'JO@example.COM'],
])
def test_variants_of_one_mailbox_share_a_key(variants):
    assert len({email_key(v) for v in variants}) == 1


def test_different_people_get_different_keys():
    keys = {email_key(e) for e in ['abc@gmail.com', 'abd@gmail.com', 'abc@example.com', 'a.bc@example.com', 'abc@outlook.com']}
    assert len(keys) == 5          # dots are ignored only at Gmail; elsewhere they identify a different mailbox


@pytest.mark.parametrize('email,expected', [
    ('x@mailinator.com', True), ('x@sub.mailinator.com', True), ('x@YOPMAIL.com', True),
    ('x@gmail.com', False), ('x@notmailinator.com', False), ('x@university.edu', False),
])
def test_disposable_domains(email, expected):
    assert is_disposable(email) is expected


@pytest.mark.parametrize('email', ['', 'nobody', 'a@', '@b.com', 'a@@b.com', 'a b@c.com'])
def test_malformed_emails_are_never_trusted(conn, email):
    assert grant(conn, 'a1', email).reason == 'email_unverified'


def test_an_unverified_or_missing_email_gets_nothing(conn):
    assert grant(conn, 'a1', 'a@example.com', verified=False) == GrantResult(False, 'email_unverified')
    assert grant_starter(conn, 'a2', DAY) == GrantResult(False, 'email_unverified')
    assert ledger.balance(conn, 'a1') == ledger.Balance(0, 0, 0)


def test_disposable_addresses_get_nothing(conn):
    assert grant(conn, 'a1', 'x@mailinator.com') == GrantResult(False, 'disposable_email')


def test_the_same_mailbox_cannot_claim_twice(conn):
    assert grant(conn, 'a1', 'a.b@gmail.com').granted
    assert grant(conn, 'a2', 'ab+second@googlemail.com') == GrantResult(False, 'email_in_use')
    assert ledger.balance(conn, 'a2').available_micros == 0
    assert grant(conn, 'a1', 'a.b@gmail.com') == GrantResult(False, 'already_granted')


def test_a_refused_attempt_does_not_use_up_the_daily_cap(conn):
    assert grant(conn, 'a1', 'a@example.com', verified=False, cap=1).reason == 'email_unverified'
    assert grant(conn, 'a2', 'x@mailinator.com', cap=1).reason == 'disposable_email'
    assert grant(conn, 'a3', 'c@example.com', cap=1).granted        # the cap of 1 is still free
    assert conn.execute('SELECT count FROM billing.grant_days').fetchone()['count'] == 1


def test_hitting_the_cap_does_not_burn_the_email_for_tomorrow(conn):
    assert grant(conn, 'a1', 'a@example.com', cap=1).granted
    assert grant(conn, 'a2', 'b@example.com', cap=1) == GrantResult(False, 'daily_cap')
    assert grant_starter(conn, 'a2', date(2026, 11, 18), email='b@example.com', email_verified=True, cap=1).granted


def test_the_grant_records_the_mailbox_key_only(conn):
    grant(conn, 'a1', 'Someone.Private@gmail.com')
    stored = conn.execute('SELECT email_key, account_id FROM billing.grant_emails').fetchone()
    assert stored['account_id'] == 'a1' and 'private' not in stored['email_key'] and len(stored['email_key']) == 64


def test_the_requirement_can_be_switched_off_for_deployments_without_accounts(conn, monkeypatch):
    monkeypatch.setenv('BILLING_REQUIRE_VERIFIED_EMAIL', 'false')
    assert grant_starter(conn, 'a1', DAY).granted
