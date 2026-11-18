"""Add a ready-made flashcard deck to a local account, for trying the phone app's flashcards.

The local stack's fake model provider cannot write real cards, so this adds them by hand through
the same API the app uses (sign-in as the account, then POST /api/flashcards and /cards).

    .venv/bin/python scripts/local_stack/seed_deck.py --username demo --password 'PrepPal-Local-2026'
"""
import argparse
import sys

import httpx

from check_signin import API, local_client, sign_in

CARDS = [
    ('What makes most of a cell’s ATP?', 'The mitochondria, through cellular respiration.'),
    ('What does the cell membrane do?', 'Controls what enters and leaves the cell; it is selectively permeable.'),
    ('Where is DNA kept in a eukaryotic cell?', 'In the nucleus (and a little in mitochondria).'),
    ('What do ribosomes make?', 'Proteins, by translating messenger RNA.'),
    ('What is the job of the Golgi apparatus?', 'It modifies, sorts and packages proteins for transport.'),
    ('Plant cells have what that animal cells lack?', 'A cell wall, chloroplasts and a large central vacuole.'),
    ('What happens in photosynthesis?', 'Light energy turns carbon dioxide and water into glucose and oxygen.'),
    ('What is osmosis?', 'Water moving across a membrane from low to high solute concentration.'),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--name', default='Cell biology basics')
    args = parser.parse_args()
    with local_client() as client:
        token = sign_in(client, args.username, args.password)['access_token']
    auth = {'Authorization': f'Bearer {token}'}
    deck = httpx.post(f'{API}/api/flashcards', json={'name': args.name}, headers=auth)
    deck.status_code == 200 or sys.exit(f'FAIL create deck -> {deck.status_code} {deck.text}')
    deck_id = deck.json()['id']
    for front, back in CARDS:
        r = httpx.post(f'{API}/api/flashcards/{deck_id}/cards', json={'front': front, 'back': back}, headers=auth)
        r.status_code == 200 or sys.exit(f'FAIL add card -> {r.status_code} {r.text}')
    print(f'PASS  deck {args.name!r} ({deck_id}) with {len(CARDS)} cards')


if __name__ == '__main__':
    main()
