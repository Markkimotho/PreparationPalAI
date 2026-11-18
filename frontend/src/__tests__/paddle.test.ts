import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { openCheckout, resetPaddleForTests } from '../payments/paddle';

type PaddleEvent = { name: string };
const fake = { initialize: vi.fn(), open: vi.fn(), environment: vi.fn(), callback: null as null | ((e: PaddleEvent) => void) };

beforeEach(() => {
  resetPaddleForTests();
  vi.clearAllMocks();
  document.head.innerHTML = '';
  const originalAppend = document.head.appendChild.bind(document.head);
  vi.spyOn(document.head, 'appendChild').mockImplementation(<T extends Node>(node: T): T => {
    const result = originalAppend(node);
    (window as unknown as { Paddle: unknown }).Paddle = {
      Environment: { set: fake.environment },
      Initialize: (options: { token: string; eventCallback: (e: PaddleEvent) => void }) => { fake.initialize(options.token); fake.callback = options.eventCallback; },
      Checkout: { open: fake.open },
    };
    setTimeout(() => (node as unknown as HTMLScriptElement).onload?.(new Event('load')), 0);
    return result;
  });
});
afterEach(() => { vi.restoreAllMocks(); delete (window as unknown as { Paddle?: unknown }).Paddle; });

it('loads Paddle.js once from Paddle, in the right environment, and opens the transaction', async () => {
  await openCheckout({ transaction_id: 'txn_1', client_token: 'test_tok', environment: 'sandbox' }, () => {});
  await openCheckout({ transaction_id: 'txn_2', client_token: 'test_tok', environment: 'sandbox' }, () => {});
  const scripts = document.head.querySelectorAll('script');
  expect(scripts).toHaveLength(1);
  expect(scripts[0].src).toBe('https://cdn.paddle.com/paddle/v2/paddle.js');
  expect(fake.environment).toHaveBeenCalledWith('sandbox');
  expect(fake.initialize).toHaveBeenCalledTimes(1);
  expect(fake.open).toHaveBeenLastCalledWith({ transactionId: 'txn_2' });
});

it('calls back once the payment completes, and not for other checkout events', async () => {
  const done = vi.fn();
  await openCheckout({ transaction_id: 'txn_1', client_token: 'live_tok', environment: 'live' }, done);
  fake.callback?.({ name: 'checkout.loaded' });
  expect(done).not.toHaveBeenCalled();
  fake.callback?.({ name: 'checkout.completed' });
  expect(done).toHaveBeenCalledTimes(1);
  expect(fake.environment).not.toHaveBeenCalled();                // live is Paddle's default
});
