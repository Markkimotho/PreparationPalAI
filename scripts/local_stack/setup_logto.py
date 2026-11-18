"""Register the phone app and the API in the local Logto (docker-compose.logto.yml). Idempotent.

Fresh Logto has no admin account and no management credentials, so this writes the two records
straight into Logto's database, in the same shape Logto's own API stores them:
  * a Native application whose redirect is preparationpal://auth/callback (what Expo produces for
    the app's scheme), a single-page application for the web app at http://localhost:18000, and
  * the API resource the server checks as the token audience,
and turns off the breached-password lookup, which needs internet access from the container.
Prints the settings start_app.sh needs. Local trial only; production uses the admin console
(engineering/runbooks/mobile.md).

    python3 scripts/local_stack/setup_logto.py
"""
import json
import secrets
import subprocess
import sys
from pathlib import Path

COMPOSE = Path(__file__).with_name('docker-compose.logto.yml')
TENANT = 'default'
NATIVE_ID = 'ppal-native-local'
WEB_ID = 'ppal-web-local'
WEB_REDIRECTS = {'redirectUris': ['http://localhost:18000/auth/callback'], 'postLogoutRedirectUris': ['http://localhost:18000/']}
RESOURCE_ID = 'ppal-api-local'
AUDIENCE = 'https://api.preparationpal.local'
REDIRECTS = {'redirectUris': ['preparationpal://auth/callback'], 'postLogoutRedirectUris': ['preparationpal://']}


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql(statement: str) -> str:
    result = subprocess.run(['docker', 'compose', '-f', str(COMPOSE), 'exec', '-T', 'logto-db',
                             'psql', '-U', 'logto', '-d', 'logto', '-At', '-v', 'ON_ERROR_STOP=1', '-c', statement],
                            capture_output=True, text=True)
    if result.returncode:
        sys.exit(f'Logto database refused: {result.stderr.strip()}')
    return result.stdout.strip()


def main() -> None:
    sql(f"""INSERT INTO applications (tenant_id, id, name, secret, description, type, oidc_client_metadata, custom_client_metadata)
            VALUES ({literal(TENANT)}, {literal(NATIVE_ID)}, 'PreparationPalAI phone app (local)', {literal(secrets.token_hex(16))},
                    'Local trial; created by scripts/local_stack/setup_logto.py', 'Native', {literal(json.dumps(REDIRECTS))}::jsonb, '{{}}'::jsonb)
            ON CONFLICT (id) DO UPDATE SET oidc_client_metadata = EXCLUDED.oidc_client_metadata""")
    sql(f"""INSERT INTO applications (tenant_id, id, name, secret, description, type, oidc_client_metadata, custom_client_metadata)
            VALUES ({literal(TENANT)}, {literal(WEB_ID)}, 'PreparationPalAI web app (local)', {literal(secrets.token_hex(16))},
                    'Local trial; created by scripts/local_stack/setup_logto.py', 'SPA', {literal(json.dumps(WEB_REDIRECTS))}::jsonb, '{{}}'::jsonb)
            ON CONFLICT (id) DO UPDATE SET oidc_client_metadata = EXCLUDED.oidc_client_metadata""")
    sql(f"""INSERT INTO resources (tenant_id, id, name, indicator, is_default, access_token_ttl)
            VALUES ({literal(TENANT)}, {literal(RESOURCE_ID)}, 'PreparationPalAI API (local)', {literal(AUDIENCE)}, false, 3600)
            ON CONFLICT (id) DO NOTHING""")
    # Logto checks new passwords against api.pwnedpasswords.com; the container often has no outside DNS, and a
    # failed lookup fails sign-up with a 500. Keep every other password rule. Production keeps the check on.
    sql(f"""UPDATE sign_in_experiences SET password_policy = password_policy || '{{"rejects": {{"pwned": false, "repetitionAndSequence": true, "userInfo": true, "words": []}}}}'::jsonb
            WHERE tenant_id = {literal(TENANT)}""")
    app = sql(f"SELECT type || ' ' || oidc_client_metadata::text FROM applications WHERE id = {literal(NATIVE_ID)}")
    api = sql(f"SELECT indicator FROM resources WHERE id = {literal(RESOURCE_ID)}")
    signup = sql(f"SELECT sign_up::text FROM sign_in_experiences WHERE tenant_id = {literal(TENANT)}")
    policy = sql(f"SELECT password_policy::text FROM sign_in_experiences WHERE tenant_id = {literal(TENANT)}")
    print(f'native app: {app}\napi resource: {api}\nsign-up: {signup}\npassword policy: {policy}')
    print(f'\nexport OIDC_NATIVE_CLIENT_ID={NATIVE_ID} OIDC_WEB_CLIENT_ID={WEB_ID}')


if __name__ == '__main__':
    main()
