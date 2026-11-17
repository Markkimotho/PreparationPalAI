import pytest
from pydantic import ValidationError

from app.config import Settings


def make(**kw):
    return Settings(_env_file=None, **kw)


def test_defaults_keep_self_hosting():
    s = make()
    assert s.inference_backend == 'ollama' and s.ollama_model == 'qwen2.5:7b'


def test_gateway_requires_url_and_key():
    with pytest.raises(ValidationError, match='GATEWAY_BASE_URL'):
        make(inference_backend='gateway', gateway_api_key='k')
    with pytest.raises(ValidationError, match='GATEWAY_API_KEY'):
        make(inference_backend='gateway', gateway_base_url='http://litellm:4000')


def test_gateway_url_rejects_credentials_and_bad_scheme():
    for url in ('ftp://x', 'http://user:pw@litellm:4000', 'litellm:4000'):
        with pytest.raises(ValidationError):
            make(inference_backend='gateway', gateway_base_url=url, gateway_api_key='k')


def test_gateway_switches_default_model_alias():
    s = make(inference_backend='gateway', gateway_base_url='http://litellm:4000', gateway_api_key='k')
    assert s.ollama_model == 'open-default'


def test_explicit_model_is_kept_in_gateway_mode():
    s = make(inference_backend='gateway', gateway_base_url='http://litellm:4000', gateway_api_key='k', ollama_model='open-fast')
    assert s.ollama_model == 'open-fast'


def test_gateway_key_never_in_repr():
    s = make(inference_backend='gateway', gateway_base_url='http://litellm:4000', gateway_api_key='sk-secret')
    assert 'sk-secret' not in repr(s) and 'sk-secret' not in str(s)


GATEWAY = dict(inference_backend='gateway', gateway_base_url='http://litellm:4000', gateway_api_key='k')


def test_billing_requires_the_gateway_backend():
    with pytest.raises(ValidationError, match='INFERENCE_BACKEND=gateway'):
        make(billing_enabled=True, billing_base_url='http://billing:8100', billing_service_token='t')


def test_billing_requires_url_and_token():
    with pytest.raises(ValidationError, match='BILLING_BASE_URL'):
        make(**GATEWAY, billing_enabled=True, billing_service_token='t')
    with pytest.raises(ValidationError, match='BILLING_SERVICE_TOKEN'):
        make(**GATEWAY, billing_enabled=True, billing_base_url='http://billing:8100')


def test_billing_token_never_in_repr():
    s = make(**GATEWAY, billing_enabled=True, billing_base_url='http://billing:8100', billing_service_token='tok-secret')
    assert 'tok-secret' not in repr(s) and s.billing_enabled
