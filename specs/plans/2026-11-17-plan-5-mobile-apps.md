# Plan 5: iOS and Android apps with in-app purchases

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A native app for iOS and Android (one Expo codebase in `mobile/`) where a learner signs in, studies (chat, tutor, coding help, quizzes, flashcards that work offline, the preparation coach), buys credits with Apple or Google, sees their balance and history, and can delete their account, using the same account and balance as the web.

**Architecture:** The app talks only to the existing API with the same sign-in tokens as the web. Sign-in is standard OIDC with PKCE through `expo-auth-session` against Logto; tokens live in the device keychain (`expo-secure-store`). Purchases go through RevenueCat, which validates store receipts; RevenueCat notifies billing (`/webhooks/revenuecat`), and billing credits the same ledger as Paddle. Markdown and maths are rendered by an Expo DOM component that reuses the web's renderer.

**Tech Stack:** Expo SDK 58, Expo Router, TypeScript, `expo-auth-session`, `expo-secure-store`, `expo/fetch` (streaming), `react-native-purchases` 11.x, AsyncStorage, jest-expo + React Native Testing Library; billing in Python as before.

**Spec:** `specs/2026-11-17-hosted-product-design.md` (sections 7.7, 8.3, 9). **Builds on:** Plans 1 to 4 (PR #20). **Issues kept open:** #26 to #32.

**Decisions (2026-11-17):**
- `@logto/rn` 1.3.0 declares peer dependencies below Expo SDK 58, so sign-in uses `expo-auth-session` (provider-neutral OIDC + PKCE). Logto needs `resource` on the authorization and token requests; both are sent.
- RevenueCat facts confirmed from its docs: one-time purchases arrive as `NON_RENEWING_PURCHASE` with `app_user_id`, `product_id`, `transaction_id`, `price`, `currency`, `store`, `environment`, and an event `id` reused on retries; refunds arrive as `CANCELLATION`; requests carry a dashboard-configured Authorization value and, when enabled, `X-RevenueCat-Webhook-Signature: t=<unix>,v1=<hmac>` over `<t>.<raw body>`.
- Store packs (spec 8.3): `store-5` $4.99 = 5,000 credits; `store-10` $9.99 = 10,000; `store-20` $19.99 = 20,000; `store-50` $49.99 = 50,000.
- Sandbox purchases are free for any TestFlight tester, so they credit only accounts listed in `REVENUECAT_SANDBOX_ACCOUNTS` (the App Review demo account) or when `REVENUECAT_ACCEPT_SANDBOX=true` (staging).
- Drawing answers stay web-only in this plan; the app links to the web for them.
- Store submission needs the deferred selling entity and domain (#29); this plan ends at signed-ready builds, not submission.

## Global Constraints

- One account and one balance across web, iOS and Android. The app identifies the RevenueCat customer by the learner's workspace id.
- A store purchase is credited once per store transaction; a refund removes those credits once, never below zero.
- Credits come from billing's pack table, keyed by store product id, never from a price in a notification.
- Tokens are stored only in the platform keychain; nothing secret is bundled in the app (RevenueCat public SDK keys are public by design).
- Every screen meets 44-point touch targets and works with large text.
- Commit messages carry no Claude co-author line; push after every green task.

## Review Focus

1. A RevenueCat notification without the right Authorization value, or with a bad or stale signature, credits nothing. Test in Task 1.
2. The same purchase notified five times credits once; a refund after the credits were spent clamps at zero. Test in Task 1.
3. A sandbox purchase from an unknown TestFlight account is not credited; the review account is. Test in Task 1.
4. A stream cut off by a lost network connection shows a clear error and the partial answer, not a spinner forever. Test in Task 4.
5. A signed-out or expired session on the phone returns to sign-in on the next request, and tokens are cleared from the keychain. Test in Task 3.

---

### Task 1: Billing — store packs and RevenueCat notifications (DONE, 20 tests)

### Task 2: App API — store packs and the native sign-in client id (DONE, 3 tests; Caddy routes `/webhooks/revenuecat` to billing via a named matcher, validated)

### Task 3: Mobile foundation — project, sign-in, API client and streaming (DONE, 14 tests)

### Task 4: Study screens — chat, tutor, coding help, quizzes, flashcards (offline), coach, Markdown and maths (DONE, 11 tests)

### Task 5: Account screen — balance, history, buy credits with RevenueCat, delete account, sign out (DONE, 8 tests)

### Task 6: Build configuration, CI, docs and a native build check
