---
description: Sell credits through Paddle, receive signed payment notifications, and handle refunds and chargebacks.
---
# Payments

Learners buy prepaid credits on the web through **Paddle**, the merchant of record: Paddle is the
legal seller, collects and files sales tax and VAT worldwide, and pays out. Store purchases (Apple and
Google) arrive in a later plan and post to the same ledger.

## How a purchase flows

1. The Account page lists packs from `GET /api/billing/packs` (billing's pack table; spec 8.3).
2. **Buy** calls `POST /api/billing/checkout`. The app forwards the signed-in learner's account id
   (never one from the request) to billing, which creates a Paddle transaction tagged with
   `custom_data.account_id` and the pack, and returns its id plus Paddle's client-side token.
3. The browser opens Paddle's overlay checkout for that transaction. The amount and the account were
   fixed by the server, so the browser cannot change either.
4. Paddle sends `transaction.completed` to `https://<PUBLIC_HOST>/webhooks/paddle`. Caddy routes this
   one path straight to billing. Billing verifies the signature and credits the pack's credits.

Credits come from the pack table, not the amount paid, so local-currency pricing and discounts cannot
change them. Each Paddle transaction is credited once, however often Paddle retries.

| Pack | Price | Credits |
| --- | --- | --- |
| `web-5` | $5 | 5,000 |
| `web-10` | $10 | 10,500 |
| `web-20` | $20 | 21,500 |
| `web-50` | $50 | 55,000 |

## Set up Paddle

1. Create products and one price per pack (USD, one-time). Put their ids in `PADDLE_PRICE_IDS` as JSON.
   A pack without a price id is shown as unavailable.
2. Create an API key with `transaction.write`; set `PADDLE_API_KEY` (server only).
3. Create a client-side token; set `PADDLE_CLIENT_TOKEN` (public by design; Paddle.js uses it).
4. Add a notification destination for `https://<PUBLIC_HOST>/webhooks/paddle` with the events
   `transaction.completed`, `adjustment.created` and `adjustment.updated`; set `PADDLE_WEBHOOK_SECRET`
   to its secret key.
5. Keep `PADDLE_ENVIRONMENT=sandbox` until a full sandbox purchase, refund and chargeback test passes.
   Only the exact value `live` switches to real money; anything else stays in sandbox.
6. Approve the default payment link domain (`PUBLIC_HOST`) in Paddle.

## Signature checks

Every notification carries `Paddle-Signature: ts=…;h1=…`. Billing computes HMAC-SHA256 over
`<ts>:<raw body>` with the destination secret and accepts the request if any `h1` matches (Paddle sends
more than one while a secret is rotated). The timestamp must be within `PADDLE_WEBHOOK_TOLERANCE`
seconds (default 300) so a captured request cannot be replayed later. A bad, stale or missing
signature returns 401 and changes nothing. If no secret is configured the endpoint returns 503.

## Refunds and chargebacks

Paddle reports refunds and chargebacks as adjustments. Billing applies an adjustment once, when its
status is `approved`, and claws back credits in proportion to the amount refunded
(`credits × adjustment total ÷ amount paid`). It never takes a balance below zero and never touches
free starter credits; any shortfall is recorded. Credit adjustments (money returned to the business)
are ignored.

## Events that cannot be used

A paid transaction with an unknown price id or without an account id is acknowledged with 200 (so
Paddle stops retrying), not credited, logged, and counted in
`billing_payment_events_total{outcome="ignored"}`. Investigate it in Paddle and credit manually with a
ledger adjustment if it was genuine. A payment for an account that was already deleted is credited to
the closed account and logged: refund it in Paddle.

## Monitoring

`billing_payment_events_total{provider="paddle",outcome}` counts `credited`, `duplicate`, `refunded`,
`ignored` and `bad_signature`. A rise in `bad_signature` means a wrong secret or someone probing the endpoint.
