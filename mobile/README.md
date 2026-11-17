# PreparationPalAI for iOS and Android

One Expo (SDK 58) app for both stores. It uses the same account, API and credit balance as the web app.

| Tab | What it does | API |
| --- | --- | --- |
| Study | Ask about your notes, a tutor, or coding help; streamed answers with Markdown and maths; add a PDF or photo to your notes | `/api/chat/stream`, `/api/agent/stream`, `/api/code-chat/stream`, `/api/kb/jobs/upload` |
| Quiz | Multiple-choice quiz on a topic, scored as you go | `/api/quiz/generate` |
| Cards | Flashcard decks, generated from notes; saved on the phone for offline study | `/api/flashcards` |
| Coach | Recap, exam or interview practice with feedback and a summary | `/api/coach/sessions` |
| Account | Balance, history, buy credits (Apple / Google via RevenueCat), sign out, delete account | `/api/billing/*`, `/api/account` |

Drawing answers are web-only for now.

## How it works

- **Sign-in**: OIDC authorization code with PKCE through the system browser (`expo-auth-session`), against
  Logto. Tokens are stored only in the device keychain (`expo-secure-store`) and refreshed automatically.
  The server publishes the native client id and API resource at `/api/auth/status` (`native`).
- **API**: `src/utils/api.ts` attaches the token to every call; a 401 returns to sign-in. Answers stream
  with `expo/fetch`; a dropped connection keeps the partial answer and says so.
- **Purchases**: `src/utils/purchases.ts` configures RevenueCat with the learner's account id as the
  customer, so store purchases credit the same balance as the web. RevenueCat notifies billing at
  `/webhooks/revenuecat`.
- **Markdown and maths**: `src/components/markdown.tsx` is an Expo DOM component running the same
  react-markdown + KaTeX renderer as the web app.
- **Offline**: flashcard decks are cached with AsyncStorage and cleared on sign-out.

## Develop

```bash
npm install
npm test                 # Jest + React Native Testing Library
npm run typecheck
npx expo-doctor
npx expo run:ios         # a development build (RevenueCat needs native code, so Expo Go is not enough)
```

Environment (per build profile in `eas.json`; all are public by design):

| Variable | Meaning |
| --- | --- |
| `EXPO_PUBLIC_API_URL` | The PreparationPalAI server, for example `https://app.example.com` |
| `EXPO_PUBLIC_REVENUECAT_IOS_KEY` / `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY` | RevenueCat public SDK keys. Without them the Account tab points to the website for top-ups |

Store setup, review notes and release steps: `engineering/runbooks/mobile.md`.
