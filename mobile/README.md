# Tayarishe for iOS and Android

One Expo (SDK 58) app for both stores. It uses the same account, API and credit balance as the web app.

Signed out, learners see a four-slide welcome carousel (3D illustrations, swipe or Next), which ends in sign-in.

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

## Personal for every learner

- After the first sign-in, **Make it yours** (`src/screens/setup.tsx`) asks for a name, goal (exam, interviews,
  understanding), subjects and level (and the exam, if any), a daily goal, and a colour and avatar. It is
  saved to `GET/PUT /api/profile` (server: `app/profile.py`), so it follows the learner to every device
  and is editable from Account > Edit profile. Skip saves the defaults.
- The server tailors every AI request that sends no profile of its own to the learner's subjects, level,
  goal, exam and language: chat, tutor, code, quizzes, explanations, flashcards and coaching.
- Every account gets a unique avatar generated from its id and a shuffle seed (`src/utils/avatar.ts`).
- The learner's colour tints the tabs, Study and Account. Study greets them by name, shows a daily goal
  dial (`todayCount` in `src/utils/streak.ts`) and suggestions built from their subjects and goal
  (`src/utils/suggestions.ts`); Quiz, Cards and Coach offer their subjects as one-tap topics, and Coach
  starts on their goal.
- The profile is cached on the phone (`cache:profile`, cleared on sign-out); setup is only shown once the
  server confirms the profile is not set up.

## Design and motion

- **Palette** (`src/constants/theme.ts`): the web app and docs family brightened. Each area has its own
  accent: Study blue (the web's navy), Quiz amber (the docs' gold), Cards green (the logo), Coach coral.
  Fonts are the web's pair: Manrope for headings, Source Sans 3 for text.
- **Motion rules** follow the animate-expo, choreograph, gestures and apple-design skills in
  `.claude/skills/` (Emil Kowalski). Values live in `src/constants/motion.ts`; nothing is eyeballed.
  - Press feedback: scale 0.97 over 120ms (a Reanimated CSS transition). Tabs never animate.
  - Everything that moves runs on the UI thread with Reanimated; only transform and opacity animate,
    except childless absolute fills (progress bars).
  - The welcome carousel is a native paging scroll; one shared scroll value drives the 3D page turns,
    parallax, background colour and dots. Illustration loops run only on the visible slide.
  - Flashcards (`src/components/card-deck.tsx`) are a 3D deck: tap flips (with a slight lift), swipe right
    for Got it and left for Still learning. The card follows the finger 1:1, GOT IT / AGAIN stamps and
    the cards underneath are driven by the same drag, and release commits on Apple's momentum projection
    or 40% of the width (`src/utils/swipe.ts`). Answers are remembered per deck (`src/utils/mastery.ts`)
    and shown as mastery bars on the deck tiles; the end of a deck offers a review of what is left.
  - Haptics: one per meaningful event (`src/utils/haptics.ts`), always with a visual change.
  - Reduced motion: no loops, 3D, parallax or confetti; crossfades only.
- **Gate:** `src/animated-style-rule.test.ts` fails if a `useAnimatedStyle` does not read its shared values
  directly (a style that reads them through a helper never updates; this shipped once).
- **Streak:** `src/utils/streak.ts` counts consecutive local study days, shown on the Study tab, cleared on
  sign-out.

## Develop

```bash
npm install
npm test                 # Jest + React Native Testing Library
npm run typecheck
npx expo-doctor
npx expo run:ios         # a development build (RevenueCat needs native code, so Expo Go is not enough)
```

Without a local Xcode build, use a cloud development build and Metro:

```bash
npx eas-cli@latest build --profile development-simulator --platform ios   # install the .app on a simulator
EXPO_PUBLIC_API_URL=http://localhost:18000 npx expo start --dev-client
scripts/sim-shot.sh "sign-in?slide=2" /tmp/shots/slide3.png               # deep link + screenshot, no tapping
```

`?slide=N` on the sign-in route opens the carousel on a slide, and `deck/<id>?face=back` opens a deck
flipped, in development builds only. `scripts/local_stack/seed_deck.py` adds an 8-card sample deck to a
local account (the fake model provider cannot write real cards). Every tab is
reachable by link (`tayarishe://quiz`, `/cards`, `/coach`, `/account`). The local server stack is in
`scripts/local_stack/` at the repository root.

Environment (per build profile in `eas.json`; all are public by design):

| Variable | Meaning |
| --- | --- |
| `EXPO_PUBLIC_API_URL` | The Tayarishe server, for example `https://app.example.com` |
| `EXPO_PUBLIC_REVENUECAT_IOS_KEY` / `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY` | RevenueCat public SDK keys. Without them the Account tab points to the website for top-ups |

Store setup, review notes and release steps: `engineering/runbooks/mobile.md`.
