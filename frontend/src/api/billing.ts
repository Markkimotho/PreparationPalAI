/** Turn the server's 402 "not enough credits" body into one clear, actionable sentence. */
export interface CreditsBody {
  detail?: string;
  balance_credits?: number;
  required_credits?: number;
  top_up_url?: string;
}

export function creditsMessage(body: CreditsBody): string {
  const parts = [body.detail ?? "Not enough credits for this action."];
  if (typeof body.balance_credits === "number" && typeof body.required_credits === "number") {
    parts.push(`You have ${body.balance_credits} credits and this needs about ${body.required_credits}.`);
  }
  if (body.top_up_url) parts.push(`Top up: ${body.top_up_url}`);
  return parts.join(" ");
}

// ---- Account: balance, packs, history, checkout, deletion ----
import { apiFetch } from './access';

export interface Balance { available_credits: number; reserved_credits: number; starter_credits: number; top_up_url: string }
export interface Pack { id: string; price: string; credits: number; available: boolean }
export interface HistoryEntry { id: number; when: string; label: string; credits: number }
export interface Checkout { transaction_id: string; client_token: string; environment: 'sandbox' | 'live' }

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(path, init);
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail ?? detail; } catch { /* not JSON */ }
    throw Object.assign(new Error(detail), { status: response.status });
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export const getBalance = () => call<Balance>('/api/billing/balance');
export const getPacks = () => call<{ packs: Pack[] }>('/api/billing/packs');
export const getHistory = (beforeId?: number) =>
  call<{ entries: HistoryEntry[]; next_before_id: number | null }>(`/api/billing/history${beforeId ? `?before_id=${beforeId}` : ''}`);
export const startCheckout = (pack: string) =>
  call<Checkout>('/api/billing/checkout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pack }) });
export const deleteAccount = () => call<void>('/api/account', { method: 'DELETE' });
