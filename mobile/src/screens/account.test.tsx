import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';

const mockSignOut = jest.fn(async () => undefined);
jest.mock('@/hooks/use-session', () => ({ useSession: () => ({ signOut: mockSignOut }) }));
jest.mock('@/utils/api', () => ({ getJson: jest.fn(), deleteRequest: jest.fn() }));
jest.mock('@/utils/purchases', () => ({
  purchasesAvailable: jest.fn(() => true), startPurchases: jest.fn(async () => true),
  storePrices: jest.fn(async () => ({ credits_5000: 'KES 650.00' })), buy: jest.fn(),
}));
import { deleteRequest, getJson } from '@/utils/api';
import { buy, purchasesAvailable, startPurchases } from '@/utils/purchases';
import { Account } from './account';

const api = getJson as jest.Mock;
beforeEach(() => {
  jest.clearAllMocks();
  api.mockImplementation(async (path: string) => ({
    '/api/billing/balance': { available_credits: 1234, reserved_credits: 0, starter_credits: 200 },
    '/api/billing/history': { entries: [{ id: 1, when: '2026-11-17', label: 'Credits purchased', credits: 5000 }] },
    '/api/billing/packs?channel=store': { packs: [{ id: 'store-5', price: '$4.99', credits: 5000, available: true, product_id: 'credits_5000' },
                                                  { id: 'store-10', price: '$9.99', credits: 10000, available: false, product_id: null }] },
    '/api/auth/me': { workspace: 'u-abc' },
  } as Record<string, unknown>)[path]);
});

test('shows the balance, history and store packs in the local price, tied to this account', async () => {
  await render(<Account />);
  expect(await screen.findByText('1,234')).toBeTruthy();
  expect(screen.getByText('+5,000')).toBeTruthy();
  expect(await screen.findByRole('button', { name: '5,000 credits for KES 650.00' })).toBeTruthy();
  expect(screen.getByRole('button', { name: '10,000 credits for $9.99' })).toBeDisabled();
  expect(startPurchases).toHaveBeenCalledWith('u-abc');
});

test('a completed purchase refreshes the balance; a cancelled one changes nothing', async () => {
  (buy as jest.Mock).mockResolvedValueOnce('purchased').mockResolvedValueOnce('cancelled');
  await render(<Account />);
  await fireEvent.press(await screen.findByRole('button', { name: '5,000 credits for KES 650.00' }));
  expect(await screen.findByText(/Purchase complete/)).toBeTruthy();
  expect(buy).toHaveBeenCalledWith('credits_5000');
  await waitFor(() => expect(api.mock.calls.filter(c => c[0] === '/api/billing/balance').length).toBeGreaterThan(1));
  await fireEvent.press(screen.getByRole('button', { name: '5,000 credits for KES 650.00' }));
  await waitFor(() => expect(buy).toHaveBeenCalledTimes(2));
  expect(screen.queryByRole('alert')).toBeNull();
});

test('without store keys the app points to the website instead of failing', async () => {
  (purchasesAvailable as jest.Mock).mockReturnValue(false);
  await render(<Account />);
  expect(await screen.findByText(/top up on the website/)).toBeTruthy();
});

test('deleting needs DELETE typed, warns about remaining credits, then signs out', async () => {
  (deleteRequest as jest.Mock).mockResolvedValue(undefined);
  await render(<Account />);
  await screen.findByText('1,234');
  await fireEvent.press(screen.getByRole('button', { name: 'Delete my account' }));
  expect(screen.getByText(/1,234 remaining credits will be lost/)).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Permanently delete my account' })).toBeDisabled();
  await fireEvent.changeText(screen.getByLabelText('Type DELETE to confirm'), 'DELETE');
  await fireEvent.press(screen.getByRole('button', { name: 'Permanently delete my account' }));
  await waitFor(() => expect(mockSignOut).toHaveBeenCalled());
  expect(deleteRequest).toHaveBeenCalledWith('/api/account');
});

test('a failed deletion keeps the learner signed in and explains why', async () => {
  (deleteRequest as jest.Mock).mockRejectedValue(new Error('Billing is temporarily unavailable. Nothing was deleted; please retry.'));
  await render(<Account />);
  await screen.findByText('1,234');
  await fireEvent.press(screen.getByRole('button', { name: 'Delete my account' }));
  await fireEvent.changeText(screen.getByLabelText('Type DELETE to confirm'), 'DELETE');
  await fireEvent.press(screen.getByRole('button', { name: 'Permanently delete my account' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/Nothing was deleted/);
  expect(mockSignOut).not.toHaveBeenCalled();
});
