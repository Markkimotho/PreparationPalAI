/**
 * Paddle's overlay checkout. Paddle.js must be loaded from Paddle's CDN (it is the merchant of record);
 * the client-side token is designed to be public. Billing created the transaction, so the browser
 * never chooses an amount or an account.
 */
import type { Checkout } from '../api/billing';

const PADDLE_JS = 'https://cdn.paddle.com/paddle/v2/paddle.js';

interface PaddleEvent { name: string }
interface PaddleGlobal {
  Environment: { set(environment: string): void };
  Initialize(options: { token: string; eventCallback: (event: PaddleEvent) => void }): void;
  Checkout: { open(options: { transactionId: string }): void };
}

let loading: Promise<PaddleGlobal> | null = null;
let initialisedWith = '';
let onCompleted: (() => void) | null = null;

export function resetPaddleForTests() { loading = null; initialisedWith = ''; onCompleted = null; }

function load(): Promise<PaddleGlobal> {
  loading ??= new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = PADDLE_JS;
    script.async = true;
    script.onload = () => resolve((window as unknown as { Paddle: PaddleGlobal }).Paddle);
    script.onerror = () => { loading = null; reject(new Error('Could not load the payment page. Check your connection and retry.')); };
    document.head.appendChild(script);
  });
  return loading;
}

export async function openCheckout(checkout: Checkout, onComplete: () => void): Promise<void> {
  const paddle = await load();
  onCompleted = onComplete;
  if (initialisedWith !== checkout.client_token) {
    if (checkout.environment === 'sandbox') paddle.Environment.set('sandbox');
    paddle.Initialize({ token: checkout.client_token, eventCallback: event => { if (event.name === 'checkout.completed') onCompleted?.(); } });
    initialisedWith = checkout.client_token;
  }
  paddle.Checkout.open({ transactionId: checkout.transaction_id });
}
