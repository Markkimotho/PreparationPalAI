jest.mock('react-native-purchases', () => ({ __esModule: true, PRODUCT_CATEGORY: { NON_SUBSCRIPTION: 'NON_SUBSCRIPTION' },
  default: { configure: jest.fn(), logIn: jest.fn(async () => ({})), logOut: jest.fn(async () => ({})), getProducts: jest.fn(), purchaseStoreProduct: jest.fn() } }));
jest.mock('react-native', () => ({ Platform: { select: (o: Record<string, string>) => o.ios } }));

process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY = 'appl_public_key';
import { buy, endPurchases, resetPurchasesForTests, startPurchases, storePrices } from './purchases';

const mockPurchases = jest.requireMock('react-native-purchases').default;

beforeEach(() => { jest.clearAllMocks(); resetPurchasesForTests(); });

test('the customer is the learner account; switching accounts logs in instead of reconfiguring', async () => {
  await startPurchases('u-alice');
  expect(mockPurchases.configure).toHaveBeenCalledWith({ apiKey: 'appl_public_key', appUserID: 'u-alice' });
  await startPurchases('u-alice');
  await startPurchases('u-bob');
  expect(mockPurchases.configure).toHaveBeenCalledTimes(1);
  expect(mockPurchases.logIn).toHaveBeenCalledWith('u-bob');
  await endPurchases();
  expect(mockPurchases.logOut).toHaveBeenCalled();
});

test('local store prices are shown for the packs', async () => {
  await startPurchases('u-alice');
  mockPurchases.getProducts.mockResolvedValue([{ identifier: 'credits_5000', priceString: 'KES 650.00' }]);
  expect(await storePrices(['credits_5000'])).toEqual({ credits_5000: 'KES 650.00' });
});

test('buying: purchased, cancelled, or a readable failure', async () => {
  mockPurchases.getProducts.mockResolvedValue([{ identifier: 'credits_5000' }]);
  mockPurchases.purchaseStoreProduct.mockResolvedValueOnce({});
  expect(await buy('credits_5000')).toBe('purchased');
  mockPurchases.purchaseStoreProduct.mockRejectedValueOnce({ userCancelled: true });
  expect(await buy('credits_5000')).toBe('cancelled');
  mockPurchases.purchaseStoreProduct.mockRejectedValueOnce({ userCancelled: false, code: '2' });
  await expect(buy('credits_5000')).rejects.toThrow('You have not been charged');
  mockPurchases.getProducts.mockResolvedValue([]);
  await expect(buy('credits_missing')).rejects.toThrow('not available in your store');
});
