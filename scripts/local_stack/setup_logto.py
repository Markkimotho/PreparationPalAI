"""Register the phone app and the API in the local Logto (docker-compose.logto.yml). Idempotent.

Fresh Logto has no admin account and no management credentials, so this writes the two records
straight into Logto's database, in the same shape Logto's own API stores them:
  * a Native application whose redirect is tayarishe://auth/callback (what Expo produces for
    the app's scheme), a single-page application for the web app at http://localhost:18000, and
  * the API resource the server checks as the token audience,
turns off the breached-password lookup (it needs internet access from the container), and brands the
sign-in page as Tayarishe (logo, colour, the apps' look, no "Powered by Logto").
Prints the settings start_app.sh needs. Local trial only; production uses the admin console
(engineering/runbooks/mobile.md).

    python3 scripts/local_stack/setup_logto.py
"""
import base64
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
AUDIENCE = 'https://api.tayarishe.local'
REDIRECTS = {'redirectUris': ['tayarishe://auth/callback'], 'postLogoutRedirectUris': ['tayarishe://']}


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql(statement: str) -> str:
    result = subprocess.run(['docker', 'compose', '-f', str(COMPOSE), 'exec', '-T', 'logto-db',
                             'psql', '-U', 'logto', '-d', 'logto', '-At', '-v', 'ON_ERROR_STOP=1', '-c', statement],
                            capture_output=True, text=True)
    if result.returncode:
        sys.exit(f'Logto database refused: {result.stderr.strip()}')
    return result.stdout.strip()


ROOT = Path(__file__).resolve().parents[2]
APP_URL = 'http://localhost:18000'


def data_uri(path: Path, mime: str) -> str:
    """Embed a file: the sign-in page is HTTPS, so assets from the local http:// app would be
    blocked as mixed content. In production, point these at your HTTPS domain instead."""
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode()


def branding_css() -> str:
    """The phone app's look for the sign-in page. Targets Logto's stable class names and plain
    elements only (its other class names are generated and change between versions)."""
    fonts = ROOT / 'frontend/public/fonts'
    manrope = data_uri(fonts / 'manrope-latin-variable.woff2', 'font/woff2')
    source = data_uri(fonts / 'source-sans-3-latin-variable.woff2', 'font/woff2')
    return f"""
@font-face {{ font-family: "Manrope"; src: url({manrope}) format("woff2"); font-weight: 200 800; }}
@font-face {{ font-family: "Source Sans 3"; src: url({source}) format("woff2"); font-weight: 200 900; }}
body {{ font-family: "Source Sans 3", -apple-system, sans-serif !important; background: #fbfaf6 !important; }}
/* Logto paints the page on this container, so the colour fields live here. */
.logto_page-container {{ background: radial-gradient(circle at 92% 6%, #e3edff 0 260px, transparent 261px),
    radial-gradient(circle at 4% 96%, #dbf4e8 0 220px, transparent 221px), #fbfaf6 !important; }}
/* Self-hosted Logto ignores hide_logto_branding (a Cloud feature); hiding it is allowed by its licence. */
/* High specificity and several properties: Logto's own !important rule keeps it visible otherwise. */
html body .logto_main-content div.logto_signature.logto_signature {{ display: none !important; visibility: hidden !important;
  height: 0 !important; overflow: hidden !important; margin: 0 !important; padding: 0 !important; }}
.logto_main-content {{ background: #fff !important; border: 1px solid #ebe8df; border-radius: 28px !important;
  box-shadow: 0 24px 60px rgba(31, 38, 43, .12) !important; }}
.logto_branding-header img {{ height: 44px; width: auto; }}
.logto_main-content h1, .logto_main-content h2, .logto_main-content [class*="title"] {{
  font-family: "Manrope", sans-serif !important; font-weight: 800 !important; letter-spacing: -0.02em; }}
.logto_main-content input {{ border-radius: 14px !important; }}
.logto_main-content button {{ border-radius: 14px !important; font-family: "Manrope", sans-serif !important; font-weight: 700 !important;
  transition: transform 120ms cubic-bezier(.23, 1, .32, 1); }}
.logto_main-content button:active {{ transform: scale(.97); }}
.logto_main-content button[type="submit"] {{ background: linear-gradient(135deg, #2f6fe4, #1d4f9f) !important; border: none !important;
  box-shadow: 0 10px 22px rgba(29, 79, 159, .28); min-height: 52px; }}
@media (prefers-reduced-motion: reduce) {{ .logto_main-content button:active {{ transform: none; }} }}
"""


def apply_branding() -> None:
    brand = ROOT / 'frontend/public/brand'
    branding = {'logoUrl': data_uri(brand / 'logo.png', 'image/png'), 'darkLogoUrl': data_uri(brand / 'logo-dark.png', 'image/png'),
                'favicon': data_uri(brand / 'mark.png', 'image/png')}
    colour = {'primaryColor': '#2F6FE4', 'darkPrimaryColor': '#5C9BFF', 'isDarkModeEnabled': False}
    sql(f"""UPDATE sign_in_experiences SET color = {literal(json.dumps(colour))}::jsonb, branding = {literal(json.dumps(branding))}::jsonb,
            hide_logto_branding = true, custom_css = {literal(branding_css())},
            unknown_session_redirect_url = {literal(APP_URL + '/prepare')}
            WHERE tenant_id = {literal(TENANT)}""")
    # Headings in the app's name instead of Logto's generic wording (English; add other languages likewise).
    phrases = {'description': {'sign_in_to_your_account': 'Sign in to Tayarishe',
                               'create_your_account': 'Create your Tayarishe account'}}
    sql(f"DELETE FROM custom_phrases WHERE tenant_id = {literal(TENANT)} AND language_tag = 'en'")
    sql(f"""INSERT INTO custom_phrases (tenant_id, id, language_tag, translation)
            VALUES ({literal(TENANT)}, 'ppal-phrases-en', 'en', {literal(json.dumps(phrases))}::jsonb)""")
    sql(f"""UPDATE applications SET name = 'Tayarishe' WHERE tenant_id = {literal(TENANT)} AND id IN ({literal(NATIVE_ID)}, {literal(WEB_ID)})""")


def main() -> None:
    sql(f"""INSERT INTO applications (tenant_id, id, name, secret, description, type, oidc_client_metadata, custom_client_metadata)
            VALUES ({literal(TENANT)}, {literal(NATIVE_ID)}, 'Tayarishe phone app (local)', {literal(secrets.token_hex(16))},
                    'Local trial; created by scripts/local_stack/setup_logto.py', 'Native', {literal(json.dumps(REDIRECTS))}::jsonb, '{{}}'::jsonb)
            ON CONFLICT (id) DO UPDATE SET oidc_client_metadata = EXCLUDED.oidc_client_metadata""")
    sql(f"""INSERT INTO applications (tenant_id, id, name, secret, description, type, oidc_client_metadata, custom_client_metadata)
            VALUES ({literal(TENANT)}, {literal(WEB_ID)}, 'Tayarishe web app (local)', {literal(secrets.token_hex(16))},
                    'Local trial; created by scripts/local_stack/setup_logto.py', 'SPA', {literal(json.dumps(WEB_REDIRECTS))}::jsonb, '{{}}'::jsonb)
            ON CONFLICT (id) DO UPDATE SET oidc_client_metadata = EXCLUDED.oidc_client_metadata""")
    sql(f"""INSERT INTO resources (tenant_id, id, name, indicator, is_default, access_token_ttl)
            VALUES ({literal(TENANT)}, {literal(RESOURCE_ID)}, 'Tayarishe API (local)', {literal(AUDIENCE)}, false, 3600)
            ON CONFLICT (id) DO UPDATE SET indicator = EXCLUDED.indicator, name = EXCLUDED.name""")
    # Logto checks new passwords against api.pwnedpasswords.com; the container often has no outside DNS, and a
    # failed lookup fails sign-up with a 500. Keep every other password rule. Production keeps the check on.
    sql(f"""UPDATE sign_in_experiences SET password_policy = password_policy || '{{"rejects": {{"pwned": false, "repetitionAndSequence": true, "userInfo": true, "words": []}}}}'::jsonb
            WHERE tenant_id = {literal(TENANT)}""")
    apply_branding()
    app = sql(f"SELECT type || ' ' || oidc_client_metadata::text FROM applications WHERE id = {literal(NATIVE_ID)}")
    api = sql(f"SELECT indicator FROM resources WHERE id = {literal(RESOURCE_ID)}")
    signup = sql(f"SELECT sign_up::text FROM sign_in_experiences WHERE tenant_id = {literal(TENANT)}")
    policy = sql(f"SELECT password_policy::text FROM sign_in_experiences WHERE tenant_id = {literal(TENANT)}")
    print(f'native app: {app}\napi resource: {api}\nsign-up: {signup}\npassword policy: {policy}')
    print(f'\nexport OIDC_NATIVE_CLIENT_ID={NATIVE_ID} OIDC_WEB_CLIENT_ID={WEB_ID}')


if __name__ == '__main__':
    main()
