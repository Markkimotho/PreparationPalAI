import json, sys, time
sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__file__), '..', '..'))
from tests.support.fake_issuer import FakeIssuer
i = FakeIssuer()
now = int(time.time())
def tok(sub, **kw): return i.sign(i.claims(sub=sub, exp=now + 7200, **kw))
out = dict(issuer=i.issuer, audience=i.audience, jwks=i.jwks_url,
           alice=tok('alice', email='alice@example.com'), bob=tok('bob', email='bob@example.com'),
           mallory=tok('mallory', email='mallory@example.com', email_verified=False))
open(sys.argv[1], 'w').write(json.dumps(out)); print('issuer ready', i.issuer, flush=True)
time.sleep(7200)
