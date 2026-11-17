# Local stack for trying the phone app

Everything the iOS simulator build needs on this Mac: sign-in (Logto behind local HTTPS), the AI gateway
with a fake model provider, billing, and the server on http://localhost:18000. Answers are placeholder
text from the fake provider; sign-in, credits, flashcards and account all work for real.

```bash
docker compose -f scripts/local_stack/docker-compose.logto.yml up -d    # Logto at https://localhost:8443
python3 scripts/local_stack/setup_logto.py                              # register the phone app and API
OIDC_NATIVE_CLIENT_ID=ppal-native-local scripts/local_stack/start_app.sh
.venv/bin/python scripts/local_stack/check_signin.py --username demo --password 'PrepPal-Local-2026'
```

Trust the local HTTPS certificate in the simulator once (Expo's sign-in needs HTTPS):

```bash
docker cp "$(docker compose -f scripts/local_stack/docker-compose.logto.yml ps -q https)":/data/caddy/pki/authorities/local/root.crt scripts/local_stack/.state/local-root.crt
xcrun simctl keychain booted add-root-cert scripts/local_stack/.state/local-root.crt
```

`check_signin.py` registers (or signs in) an account through Logto exactly as the app does and passes only
if the server accepts the token. Stop with `scripts/local_stack/stop.sh` (add `--all` to stop sign-in too).
State, logs and keys live in `scripts/local_stack/.state/` (git-ignored).
