---
description: Configure, build and release the iOS and Android apps, and set up in-app purchases with RevenueCat.
---
# Phone apps

`mobile/` is one Expo (SDK 58) app for the App Store and Google Play. It uses the same accounts, API and
credit balance as the web app. See `mobile/README.md` for the screens and local development.

## What the server needs

| Setting | Purpose |
| --- | --- |
| `OIDC_NATIVE_CLIENT_ID` | The Logto **native** application id. Published at `/api/auth/status` (`native`). |
| `REVENUECAT_WEBHOOK_AUTH` | The exact Authorization value configured for the RevenueCat webhook. |
| `REVENUECAT_SIGNING_SECRET` | Optional HMAC signing secret; when set, unsigned or stale notifications are refused. |
| `REVENUECAT_PRODUCTS` | Store product id to pack, for example `{"credits_5000":"store-5", …}`. |
| `REVENUECAT_SANDBOX_ACCOUNTS` | Workspace ids allowed to buy in sandbox: the App Review demo account. |

Caddy routes `/webhooks/revenuecat` (and `/webhooks/paddle`) to billing; nothing else of billing is public.

## Logto

Create a **Native** application. Redirect URI: `preparationpal://auth/callback`. Post sign-out redirect:
`preparationpal://`. Enable the API resource (`OIDC_AUDIENCE`) and the same access-token claims as the web
(see [Accounts and storage](accounts.md)). Turn on refresh tokens; the app asks for `offline_access`.
Apple sign-in is required on iOS because other social sign-ins are offered.

## Store products and RevenueCat

1. In App Store Connect and Google Play Console, create **consumable** products:
   `credits_5000` ($4.99), `credits_10000` ($9.99), `credits_20000` ($19.99), `credits_50000` ($49.99).
2. In RevenueCat, add both apps and the products. Put the public SDK keys in the build profile as
   `EXPO_PUBLIC_REVENUECAT_IOS_KEY` and `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY` (public by design).
3. Add a webhook to `https://<PUBLIC_HOST>/webhooks/revenuecat` with an Authorization value; set
   `REVENUECAT_WEBHOOK_AUTH` to exactly that value. Enable signing if available and set the secret.
4. The app identifies the RevenueCat customer by the learner's workspace id, so a purchase on the phone
   credits the same balance as the web.

Billing credits a `NON_RENEWING_PURCHASE` once per store transaction, using the pack table (never the
price in the notification), and applies a `CANCELLATION` (refund) once, never below zero.

### Sandbox purchases

Store sandbox purchases cost nothing, and every TestFlight tester buys in sandbox. Billing therefore
credits sandbox purchases only for accounts in `REVENUECAT_SANDBOX_ACCOUNTS`. Put the App Review demo
account there, and nothing else, in production. Staging may set `REVENUECAT_ACCEPT_SANDBOX=true`.

## Build and release

```bash
cd mobile
npx eas-cli@latest login               # the package is eas-cli; `npx eas` does not exist
npx eas-cli@latest init                # links the project (adds extra.eas.projectId)
npx eas-cli@latest build --profile preview --platform all
npx eas-cli@latest build --profile production --platform all
npx eas-cli@latest submit --platform ios   # and android
```

Set `EXPO_PUBLIC_API_URL` per profile in `eas.json`. Bundle id and package are
`app.preparationpal.mobile` until the domain is chosen (issue #29). Store submission needs the selling
entity (Apple organisation account, D-U-N-S) and the domain (issue #29).

## App Review notes

- Give reviewers the demo account (email one-time code works without a phone) and list it in
  `REVENUECAT_SANDBOX_ACCOUNTS` so their test purchase credits.
- Account deletion is in the app: Account > Delete account (App Store guideline 5.1.1(v)).
- Purchases are consumable credits sold through in-app purchase only; the app does not link to web checkout.

## Checks before a release

`npm test`, `npm run typecheck`, `npx expo-doctor`, and `npx expo export --platform ios --platform android`
all run in CI (`.github/workflows/quality.yml`, job `mobile`). Build a Release app on a simulator before
submitting: `npx expo run:ios --configuration Release`.
