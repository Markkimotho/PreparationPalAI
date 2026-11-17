"""Internal billing API. Reachable only on the private network, always with the service token."""
import hmac
import json
import sys
from datetime import datetime, timezone

import yaml
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, ConfigDict, Field

from billing import db, grants, ledger, metrics, pricing
from billing.pricing import UnknownAlias, Usage
from billing.settings import get_settings

Name = Field(min_length=1, max_length=128)
Tokens = Field(ge=0, le=10_000_000)


def require_token(authorization: str = Header(default='')) -> None:
    expected = get_settings().service_token
    if not expected:
        raise HTTPException(503, 'Billing service token is not configured')   # fail closed
    scheme, _, supplied = authorization.partition(' ')
    if scheme != 'Bearer' or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(401, 'Invalid service token', headers={'WWW-Authenticate': 'Bearer'})


@asynccontextmanager
async def lifespan(_app):
    settings = get_settings()
    if settings.database_url:
        db.configure(settings.database_url, max_size=settings.pool_max)
    yield
    db.close()


app = FastAPI(title='PreparationPalAI billing', version='1.0.0', lifespan=lifespan)
router = APIRouter(dependencies=[Depends(require_token)])


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class BalanceOut(Strict):
    available_micros: int
    reserved_micros: int
    starter_micros: int


class GrantOut(Strict):
    granted: bool
    reason: str


class Line(Strict):
    alias: str = Name
    max_input_tokens: int = Tokens
    max_output_tokens: int = Tokens
    calls: int = Field(ge=1, le=100)


class ReserveIn(Strict):
    account_id: str = Name
    request_id: str = Name
    action: str = Name
    alias: str = Name                       # the learner's chosen model; decides the tier rule
    lines: list[Line] = Field(min_length=1, max_length=20)


class ReserveOut(Strict):
    request_id: str
    reserved_micros: int
    available_micros: int


class UsageIn(Strict):
    alias: str = Name
    input_tokens: int = Tokens
    output_tokens: int = Tokens
    cache_read_tokens: int = Field(default=0, ge=0, le=10_000_000)


class SettleIn(Strict):
    usage: list[UsageIn] = Field(max_length=200)


class SettleOut(Strict):
    charged_micros: int
    written_off_micros: int
    available_micros: int


class EstimateIn(Strict):
    alias: str = Name
    input_tokens: int = Tokens
    output_tokens: int = Tokens


class EstimateOut(Strict):
    micros: int


class PriceOut(Strict):
    alias: str
    tier: str
    input_per_m: str
    output_per_m: str
    cache_read_per_m: str
    multiplier: str


class PricesOut(Strict):
    version: int
    prices: list[PriceOut]


class TopupIn(Strict):
    provider: str = Name
    provider_ref: str = Name
    account_id: str = Name
    gross_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    credits_micros: int = Field(gt=0, le=10**12)


class RefundIn(Strict):
    provider: str = Name
    provider_ref: str = Name
    credits_micros: int = Field(gt=0, le=10**12)


class RefundOut(Strict):
    clawed_back_micros: int
    shortfall_micros: int
    available_micros: int


class HistoryEntry(Strict):
    id: int
    amount_micros: int
    hold_micros: int
    kind: str
    ref: str
    price_version: int | None
    created_at: datetime


class HistoryOut(Strict):
    entries: list[HistoryEntry]
    next_before_id: int | None


class InsufficientOut(Strict):
    detail: str
    balance_micros: int
    required_micros: int
    premium_requires_purchase: bool


@app.exception_handler(ledger.InsufficientCredits)
async def insufficient(_request, exc: ledger.InsufficientCredits):
    metrics.INSUFFICIENT.labels('premium_needs_purchase' if exc.premium_requires_purchase else 'balance').inc()
    return JSONResponse(status_code=402, content=InsufficientOut(
        detail='Not enough credits', balance_micros=exc.balance_micros, required_micros=exc.required_micros,
        premium_requires_purchase=exc.premium_requires_purchase).model_dump())


@app.exception_handler(UnknownAlias)
async def unknown_alias(_request, exc: UnknownAlias):
    metrics.UNKNOWN_ALIAS.inc()
    return JSONResponse(status_code=422, content={'detail': f'No price is published for alias {exc.args[0]!r}'})


def as_balance(b: ledger.Balance) -> BalanceOut:
    return BalanceOut(available_micros=b.available_micros, reserved_micros=b.reserved_micros, starter_micros=b.starter_micros)


@router.post('/v1/accounts/{account_id}', response_model=BalanceOut)
def ensure_account(account_id: str):
    with db.transaction() as conn:
        ledger.ensure_account(conn, account_id)
        return as_balance(ledger.balance(conn, account_id))


@router.post('/v1/accounts/{account_id}/grants/starter', response_model=GrantOut)
def starter_grant(account_id: str):
    with db.transaction() as conn:
        result = grants.grant_starter(conn, account_id, datetime.now(timezone.utc).date())
    metrics.STARTER_GRANTS.labels(result.reason).inc()
    return GrantOut(granted=result.granted, reason=result.reason)


@router.get('/v1/accounts/{account_id}/balance', response_model=BalanceOut)
def get_balance(account_id: str):
    with db.transaction() as conn:
        return as_balance(ledger.balance(conn, account_id))


@router.get('/v1/accounts/{account_id}/history', response_model=HistoryOut)
def get_history(account_id: str, limit: int = Query(50, ge=1, le=200), before_id: int | None = Query(None, ge=1)):
    with db.transaction() as conn:
        rows = ledger.history(conn, account_id, limit + 1, before_id)
    page = rows[:limit]
    return HistoryOut(entries=[HistoryEntry(**r.__dict__) for r in page],
                      next_before_id=page[-1].id if len(rows) > limit else None)


@router.post('/v1/reservations', status_code=201, response_model=ReserveOut,
          responses={402: {'model': InsufficientOut}})
def reserve(body: ReserveIn):
    with db.transaction() as conn:
        prices = pricing.current_prices(conn)
        pricing.price_for(prices, body.alias)
        amount = sum(line.calls * pricing.ceiling_micros(pricing.price_for(prices, line.alias),
                                                          line.max_input_tokens, line.max_output_tokens) for line in body.lines)
        available = ledger.reserve(conn, body.account_id, body.request_id, amount, body.action, body.alias)
    return ReserveOut(request_id=body.request_id, reserved_micros=amount, available_micros=available)


@router.post('/v1/reservations/{request_id}/settle', response_model=SettleOut)
def settle(request_id: str, body: SettleIn):
    usages = [Usage(u.alias, u.input_tokens, u.output_tokens, u.cache_read_tokens) for u in body.usage]
    with db.transaction() as conn:
        row = conn.execute('SELECT action FROM billing.reservations WHERE request_id = %s', (request_id,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Unknown reservation')
        prices = pricing.current_prices(conn)
        lines = [(u, pricing.price_for(prices, u.alias)) for u in usages]
        total = sum(pricing.charge_micros(u, p) for u, p in lines)
        version = next(iter(prices.values())).version
        result = ledger.settle(conn, request_id, total, version)
    if result.written_off_micros:
        metrics.WRITTEN_OFF.inc(result.written_off_micros)
    else:
        for usage, price in lines:
            charge = pricing.charge_micros(usage, price)
            metrics.CHARGED.labels(usage.alias, row['action']).inc(charge)
            metrics.MARGIN.labels(usage.alias).inc(charge - pricing.provider_cost_micros(usage, price))
    return SettleOut(charged_micros=result.charged_micros, written_off_micros=result.written_off_micros,
                     available_micros=result.balance_micros)


@router.post('/v1/reservations/{request_id}/release', status_code=204)
def release(request_id: str):
    with db.transaction() as conn:
        ledger.release(conn, request_id)
    return Response(status_code=204)


@router.post('/v1/estimate', response_model=EstimateOut)
def estimate(body: EstimateIn):
    with db.transaction() as conn:
        price = pricing.price_for(pricing.current_prices(conn), body.alias)
    return EstimateOut(micros=pricing.ceiling_micros(price, body.input_tokens, body.output_tokens))


@router.get('/v1/prices', response_model=PricesOut)
def prices():
    with db.transaction() as conn:
        current = pricing.current_prices(conn)
    return PricesOut(version=max((p.version for p in current.values()), default=0), prices=[
        PriceOut(alias=p.alias, tier=p.tier, input_per_m=str(p.input_per_m), output_per_m=str(p.output_per_m),
                 cache_read_per_m=str(p.cache_read_per_m), multiplier=str(p.multiplier)) for p in current.values()])


@router.post('/v1/payments/topup', response_model=BalanceOut)
def topup(body: TopupIn):
    with db.transaction() as conn:
        ledger.record_topup(conn, body.provider, body.provider_ref, body.account_id, body.gross_minor, body.currency.upper(), body.credits_micros)
        return as_balance(ledger.balance(conn, body.account_id))


@router.post('/v1/payments/refund', response_model=RefundOut)
def refund(body: RefundIn):
    with db.transaction() as conn:
        try:
            result = ledger.refund(conn, body.provider, body.provider_ref, body.credits_micros)
        except KeyError:
            raise HTTPException(404, 'Unknown payment') from None
    return RefundOut(clawed_back_micros=result.charged_micros, shortfall_micros=result.written_off_micros, available_micros=result.balance_micros)


app.include_router(router)


# Health and metrics carry no secrets and are only reachable on the private network.

@app.get('/healthz', include_in_schema=False)
def healthz():
    with db.transaction() as conn:
        conn.execute('SELECT 1')
    return {'ok': True}


@app.get('/metrics', include_in_schema=False)
def prometheus():
    with db.transaction() as conn:
        metrics.OPEN_RESERVATIONS.set(conn.execute("SELECT count(*) AS n FROM billing.reservations WHERE status = 'open'").fetchone()['n'])
        for run in conn.execute('SELECT DISTINCT ON (name) name, finished_at, problem, result FROM billing.job_runs '
                                'ORDER BY name, id DESC').fetchall():
            metrics.JOB_LAST_RUN.labels(run['name']).set(run['finished_at'].timestamp())
            metrics.JOB_PROBLEM.labels(run['name']).set(1 if run['problem'] else 0)
            if run['name'] == 'reconcile':
                metrics.RECONCILE_DRIFT.set(run['result'].get('drift_micros', 0))
            if run['name'] == 'check-prices':
                metrics.PRICE_DRIFT.set(len(run['result'].get('price_diffs', [])))
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == '__main__':
    if '--dump-openapi' in sys.argv:
        print(yaml.safe_dump(json.loads(json.dumps(app.openapi())), sort_keys=False), end='')
