import json, sys, time, httpx, pymupdf as fitz
E = sys.argv[1]
tok = json.load(open(f'{E}/issuer.json'))
H = lambda who: {'Authorization': f'Bearer {tok[who]}'}
app = httpx.Client(base_url='http://localhost:18000', timeout=60)
def chat(who, q='hello'):
    r = app.post('/api/chat/stream', json={'question': q, 'session_id': 's1'}, headers=H(who))
    return r.status_code, (r.json() if r.headers.get('content-type','').startswith('application/json') else r.text)
def bal(who): return app.get('/api/billing/balance', headers=H(who)).json()
def show(title, value): print(f'\n== {title}\n{value}')

show('0. nobody signed in', app.get('/api/flashcards').status_code)
show('1. alice (verified email) chats; starter allowance granted', (chat('alice')[0], bal('alice')))
code, body = chat('mallory')
show('2. mallory (UNVERIFIED email) gets no free credits', (code, body))
show('3. bob (verified) has his own separate balance', (chat('bob')[0], bal('bob')))
show('4. alice creates a deck', app.post('/api/flashcards', json={'name': 'Alice private deck'}, headers=H('alice')).status_code)
show('   bob lists decks (must be empty)', app.get('/api/flashcards', headers=H('bob')).json())
show('   alice lists decks', [d['name'] for d in app.get('/api/flashcards', headers=H('alice')).json()['decks']])

pdf = fitz.open(); page = pdf.new_page(); page.insert_text((72, 100), "Newton's second law: force equals mass times acceleration. Alice private physics notes.")
data = pdf.tobytes()
up = app.post('/api/kb/jobs/upload', files=[('files', ('alice-notes.pdf', data, 'application/pdf'))], headers=H('alice'))
show('5. alice uploads a PDF (queued for the worker)', (up.status_code, up.json()))
job = up.json()['jobs'][0]['id']
for _ in range(40):
    state = app.get(f'/api/kb/jobs/{job}', headers=H('alice')).json()
    if state['state'] in ('completed', 'failed'): break
    time.sleep(1)
show('   worker result', state)
show('   alice sees her document', app.get('/api/kb/sources', headers=H('alice')).json())
show('   bob sees no documents', app.get('/api/kb/sources', headers=H('bob')).json())
show('   alice balance after the upload was metered', bal('alice'))

show('6. bob deletes his account', app.delete('/api/account', headers=H('bob')).status_code)
show('   bob tries to use the service again', chat('bob'))
show('   alice is untouched', (app.get('/api/flashcards', headers=H('alice')).json()['decks'].__len__(), app.get('/api/kb/sources', headers=H('alice')).json()))
