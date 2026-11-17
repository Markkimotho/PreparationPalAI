from billing import ledger


def fund(conn, account='a1', micros=10_000, ref=None):
    return ledger.credit(conn, account, micros, 'topup', ref or f'fund-{account}-{micros}')


def state(conn, account='a1'):
    b = ledger.balance(conn, account)
    return b.available_micros, b.reserved_micros
