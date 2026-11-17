import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  getBalance: vi.fn(), getPacks: vi.fn(), getHistory: vi.fn(), startCheckout: vi.fn(), deleteAccount: vi.fn(),
}));
const pay = vi.hoisted(() => ({ openCheckout: vi.fn() }));
const auth = vi.hoisted(() => ({ signOut: vi.fn() }));
vi.mock('../api/billing', () => api);
vi.mock('../payments/paddle', () => pay);
vi.mock('../auth/session', () => ({ session: auth }));

import { Account } from '../sections/Account/Account';

const balance = { available_credits: 1234, reserved_credits: 0, starter_credits: 200, top_up_url: '' };
beforeEach(() => {
  vi.clearAllMocks();
  api.getBalance.mockResolvedValue(balance);
  api.getPacks.mockResolvedValue({ packs: [{ id: 'web-5', price: '$5', credits: 5000, available: true },
                                           { id: 'web-10', price: '$10', credits: 10500, available: false }] });
  api.getHistory.mockResolvedValue({ entries: [{ id: 2, when: '2026-11-17T10:00:00Z', label: 'Credits purchased', credits: 5000 },
                                               { id: 1, when: '2026-11-16T10:00:00Z', label: 'Study activity', credits: -1.5 }], next_before_id: null });
});

it('shows the balance, the free part of it, and readable history', async () => {
  render(<Account />);
  expect(await screen.findByText('1,234')).toBeInTheDocument();
  expect(screen.getByText(/200 of these are free starter credits/)).toBeInTheDocument();
  expect(screen.getByText('Credits purchased')).toBeInTheDocument();
  expect(screen.getByText('+5,000')).toBeInTheDocument();
  expect(screen.getByText('-1.5')).toBeInTheDocument();
});

it('buys a pack through checkout and refreshes the balance when payment completes', async () => {
  api.startCheckout.mockResolvedValue({ transaction_id: 'txn_1', client_token: 'live_tok', environment: 'live' });
  pay.openCheckout.mockImplementation(async (_checkout: unknown, onComplete: () => void) => { onComplete(); });
  render(<Account />);
  await userEvent.click(await screen.findByRole('button', { name: 'Buy 5,000 credits for $5' }));
  expect(api.startCheckout).toHaveBeenCalledWith('web-5');
  expect(pay.openCheckout).toHaveBeenCalledWith({ transaction_id: 'txn_1', client_token: 'live_tok', environment: 'live' }, expect.any(Function));
  expect(await screen.findByRole('status')).toHaveTextContent('Payment received');
  await waitFor(() => expect(api.getBalance.mock.calls.length).toBeGreaterThan(1));
})

it('does not offer packs that are not on sale', async () => {
  render(<Account />);
  expect(await screen.findByRole('button', { name: 'Buy 10,500 credits for $10' })).toBeDisabled();
});

it('explains a checkout that could not start', async () => {
  api.startCheckout.mockRejectedValue(new Error('The payment provider could not start a checkout. Please retry.'));
  render(<Account />);
  await userEvent.click(await screen.findByRole('button', { name: 'Buy 5,000 credits for $5' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('could not start a checkout');
  expect(pay.openCheckout).not.toHaveBeenCalled();
});

it('requires typing DELETE, warns about the remaining balance, then deletes and signs out', async () => {
  api.deleteAccount.mockResolvedValue(undefined);
  render(<Account />);
  await userEvent.click(await screen.findByRole('button', { name: 'Delete my account' }));
  expect(screen.getByText(/1,234 remaining credits will be lost/)).toBeInTheDocument();
  const confirm = screen.getByRole('button', { name: 'Permanently delete my account' });
  expect(confirm).toBeDisabled();
  await userEvent.type(screen.getByLabelText('Type DELETE to confirm'), 'DELETE');
  await userEvent.click(confirm);
  expect(api.deleteAccount).toHaveBeenCalled();
  await waitFor(() => expect(auth.signOut).toHaveBeenCalled());
});

it('keeps the learner signed in and explains when deletion fails', async () => {
  api.deleteAccount.mockRejectedValue(new Error('Billing is temporarily unavailable. Nothing was deleted; please retry.'));
  render(<Account />);
  await userEvent.click(await screen.findByRole('button', { name: 'Delete my account' }));
  await userEvent.type(screen.getByLabelText('Type DELETE to confirm'), 'DELETE');
  await userEvent.click(screen.getByRole('button', { name: 'Permanently delete my account' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Nothing was deleted');
  expect(auth.signOut).not.toHaveBeenCalled();
});

it('explains that credits are a hosted feature when billing is off', async () => {
  api.getBalance.mockRejectedValue(Object.assign(new Error('Billing is not enabled.'), { status: 404 }));
  render(<Account />);
  expect(await screen.findByText(/Credits and account settings are available on hosted PreparationPalAI/)).toBeInTheDocument();
});
