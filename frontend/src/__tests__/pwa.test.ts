import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import { registerServiceWorker } from '../pwa/register';

const publicDir = resolve(__dirname, '../../public');
const scope: { swStrategy?: (url: string, method: string, mode: string, origin: string) => string } = {};
new Function('self', readFileSync(resolve(publicDir, 'sw-strategy.js'), 'utf8'))(scope);
const strategy = (path: string, { method = 'GET', mode = 'cors', origin = 'https://app.example' } = {}) =>
  scope.swStrategy!(path.startsWith('http') ? path : `https://app.example${path}`, method, mode, origin);

describe('what the service worker does with each request', () => {
  it.each(['/api/flashcards', '/api/chat/stream', '/auth/callback?code=1', '/webhooks/paddle', '/metrics', '/health/ready'])(
    'never caches %s', path => expect(strategy(path)).toBe('network'));

  it('never caches writes', () => expect(strategy('/assets/x.js', { method: 'POST' })).toBe('network'));

  it('never touches other sites (sign-in, payments)', () => {
    expect(strategy('https://auth.example/oidc/auth')).toBe('network');
    expect(strategy('https://cdn.paddle.com/paddle/v2/paddle.js')).toBe('network');
  });

  it('serves content-hashed assets from cache first', () => expect(strategy('/assets/index-abc123.js')).toBe('cache-first'));

  it('tries the network for pages and falls back to the cached shell offline', () =>
    expect(strategy('/account', { mode: 'navigate' })).toBe('page'));

  it('refreshes icons and fonts in the background', () => expect(strategy('/fonts/inter.woff2')).toBe('stale-while-revalidate'));
});

describe('the manifest', () => {
  const manifest = JSON.parse(readFileSync(resolve(publicDir, 'manifest.webmanifest'), 'utf8'));

  it('makes the app installable', () => {
    expect(manifest).toMatchObject({ name: 'PreparationPalAI', short_name: 'PrepPal', display: 'standalone', start_url: '/prepare', scope: '/' });
    expect(manifest.theme_color).toBe('#194f3c');
  });

  it('ships 192px, 512px and maskable icons that exist', () => {
    const sizes = manifest.icons.map((i: { sizes: string; purpose?: string }) => `${i.sizes}:${i.purpose ?? 'any'}`);
    expect(sizes).toEqual(expect.arrayContaining(['192x192:any', '512x512:any', '512x512:maskable']));
    for (const icon of manifest.icons) {
      const png = readFileSync(resolve(publicDir, icon.src.replace(/^\//, '')));
      expect(png.subarray(1, 4).toString()).toBe('PNG');
      expect(png.readUInt32BE(16)).toBe(Number(icon.sizes.split('x')[0]));            // the file really has the declared width
    }
  });
});

describe('registering the worker', () => {
  it('registers in production builds only', async () => {
    const register = vi.fn(async () => ({}));
    await registerServiceWorker({ serviceWorker: { register } } as unknown as Navigator, true);
    expect(register).toHaveBeenCalledWith('/sw.js', { scope: '/' });
    register.mockClear();
    await registerServiceWorker({ serviceWorker: { register } } as unknown as Navigator, false);
    expect(register).not.toHaveBeenCalled();
  });

  it('does nothing in browsers without service workers and survives a failed registration', async () => {
    await expect(registerServiceWorker({} as Navigator, true)).resolves.toBe(false);
    const register = vi.fn(async () => { throw new Error('insecure context'); });
    await expect(registerServiceWorker({ serviceWorker: { register } } as unknown as Navigator, true)).resolves.toBe(false);
  });
});

it('index.html links the manifest, theme colour and Apple icon', () => {
  const html = readFileSync(resolve(__dirname, '../../index.html'), 'utf8');
  expect(html).toContain('<link rel="manifest" href="/manifest.webmanifest" />');
  expect(html).toContain('<meta name="theme-color" content="#194f3c" />');
  expect(html).toContain('<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />');
});
