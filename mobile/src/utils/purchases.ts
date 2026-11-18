/**
 * In-app purchases through RevenueCat (it validates Apple and Google receipts and notifies billing).
 * The RevenueCat customer is the learner's account id, so a purchase on the phone credits the same
 * balance as the web. The public SDK keys are designed to ship inside apps.
 */
import { Platform } from 'react-native';
import Purchases, { PRODUCT_CATEGORY, type PurchasesStoreProduct } from 'react-native-purchases';

const apiKey = () => Platform.select({ ios: process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY, android: process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_KEY }) ?? '';
let configuredFor: string | null = null;

export function purchasesAvailable(): boolean { return !!apiKey(); }

export async function startPurchases(accountId: string): Promise<boolean> {
  const key = apiKey();
  if (!key) return false;
  if (configuredFor === null) Purchases.configure({ apiKey: key, appUserID: accountId });
  else if (configuredFor !== accountId) await Purchases.logIn(accountId);
  configuredFor = accountId;
  return true;
}

export async function endPurchases(): Promise<void> {
  if (configuredFor === null) return;
  try { await Purchases.logOut(); } catch { /* already anonymous */ }
  configuredFor = null;
}

export function resetPurchasesForTests() { configuredFor = null; }

export async function storePrices(productIds: string[]): Promise<Record<string, string>> {
  if (!configuredFor || productIds.length === 0) return {};
  const products = await Purchases.getProducts(productIds, PRODUCT_CATEGORY.NON_SUBSCRIPTION);
  return Object.fromEntries(products.map((p: PurchasesStoreProduct) => [p.identifier, p.priceString]));
}

/** Buy one credit pack. Resolves 'purchased' or 'cancelled'; other failures throw a readable error. */
export async function buy(productId: string): Promise<'purchased' | 'cancelled'> {
  const [product] = await Purchases.getProducts([productId], PRODUCT_CATEGORY.NON_SUBSCRIPTION);
  if (!product) throw new Error('This credit pack is not available in your store yet.');
  try {
    await Purchases.purchaseStoreProduct(product);
    return 'purchased';
  } catch (error) {
    if ((error as { userCancelled?: boolean | null }).userCancelled) return 'cancelled';
    throw new Error('The store could not complete the purchase. You have not been charged; please retry.');
  }
}
