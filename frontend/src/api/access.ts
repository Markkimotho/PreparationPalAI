// Memory-only: server credentials never enter local/session storage.
let accessKey = '';
export function setAccessKey(key: string) { accessKey = key; }
export function apiFetch(path: string, init: RequestInit = {}) {
  if (!accessKey) return fetch(path, Object.keys(init).length ? init : undefined);
  const headers = new Headers(init.headers);
  if (accessKey) headers.set('Authorization', `Bearer ${accessKey}`);
  return fetch(path, { ...init, headers });
}
