import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { AccessGate } from '../components/AccessGate';
import { apiFetch, setAccessKey } from '../api/access';

afterEach(() => { setAccessKey(''); vi.unstubAllGlobals(); });
it('requires a key before mounting protected views and keeps it out of storage', async () => {
  const mocked = vi.fn(async (path: string) => ({ ok: true, json: async () => path.endsWith('status') ? { enabled: true } : { workspace: 'alice' } }));
  vi.stubGlobal('fetch', mocked);
  render(<AccessGate><div>Private study</div></AccessGate>);
  expect(screen.queryByText('Private study')).not.toBeInTheDocument();
  await userEvent.type(await screen.findByLabelText('Workspace access key'), 'secret-key');
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  expect(await screen.findByText('Private study')).toBeInTheDocument();
  await apiFetch('/api/kb/count');
  const calls = mocked.mock.calls as unknown as [string, RequestInit][];
  expect(new Headers(calls[calls.length - 1][1].headers).get('Authorization')).toBe('Bearer secret-key');
  expect(JSON.stringify(localStorage)).not.toContain('secret-key');
  expect(JSON.stringify(sessionStorage)).not.toContain('secret-key');
});
