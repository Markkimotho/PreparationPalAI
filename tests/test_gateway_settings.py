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
