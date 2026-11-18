"""Environment-driven settings. Secrets are read from the environment only."""
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.environ.get('BILLING_DATABASE_URL', ''), repr=False)
    service_token: str = field(default_factory=lambda: os.environ.get('BILLING_SERVICE_TOKEN', ''), repr=False)
    starter_grants_per_day: int = field(default_factory=lambda: int(os.environ.get('STARTER_GRANTS_PER_DAY', '200')))
    gateway_base_url: str = field(default_factory=lambda: os.environ.get('GATEWAY_BASE_URL', 'http://litellm:4000'))
    gateway_admin_key: str = field(default_factory=lambda: os.environ.get('GATEWAY_ADMIN_KEY', ''), repr=False)
    gateway_key_alias: str = field(default_factory=lambda: os.environ.get('GATEWAY_KEY_ALIAS', 'tayarishe-prod'))
    require_verified_email: bool = field(default_factory=lambda: os.environ.get('BILLING_REQUIRE_VERIFIED_EMAIL', 'true').lower() != 'false')
    paddle_api_key: str = field(default_factory=lambda: os.environ.get('PADDLE_API_KEY', ''), repr=False)
    paddle_environment: str = field(default_factory=lambda: 'live' if os.environ.get('PADDLE_ENVIRONMENT') == 'live' else 'sandbox')
    paddle_webhook_secret: str = field(default_factory=lambda: os.environ.get('PADDLE_WEBHOOK_SECRET', ''), repr=False)
    paddle_client_token: str = field(default_factory=lambda: os.environ.get('PADDLE_CLIENT_TOKEN', ''))
    paddle_api_base: str = field(default_factory=lambda: os.environ.get('PADDLE_API_BASE', ''))   # tests only; empty = Paddle's own
    paddle_webhook_tolerance: float = field(default_factory=lambda: float(os.environ.get('PADDLE_WEBHOOK_TOLERANCE', '300')))
    pool_max: int = field(default_factory=lambda: int(os.environ.get('BILLING_POOL_MAX', '20')))


def get_settings() -> Settings:
    return Settings()
