/** Register the service worker in production builds. Never blocks or breaks the app if it fails. */
export async function registerServiceWorker(nav: Navigator = navigator, production = import.meta.env.PROD): Promise<boolean> {
  if (!production || !('serviceWorker' in nav)) return false;
  try {
    await nav.serviceWorker.register('/sw.js', { scope: '/' });
    return true;
  } catch {
    return false;
  }
}
