import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { ACCENT_COLOURS, DEFAULT_PROFILE } from '../api/profile';

const api = vi.hoisted(() => ({ getProfile: vi.fn(), putProfile: vi.fn(), getWorkspace: vi.fn() }));
vi.mock('../api/profile', async importOriginal => ({ ...(await importOriginal<object>()), ...api }));
import { ProfileProvider, useProfile } from '../profile/ProfileContext';
import { NeedsSetup } from '../App';

const SERVER = { ...DEFAULT_PROFILE, display_name: 'Amani', accent: 'green' as const, onboarded: true };
let exposed: ReturnType<typeof useProfile>;
function Probe() { exposed = useProfile(); return <p>{`${exposed.status}|${exposed.profile.display_name}|${exposed.profile.accent}`}</p>; }
beforeEach(() => { vi.clearAllMocks(); api.getWorkspace.mockResolvedValue('u-x'); });

it('loads the profile; saves are optimistic and roll back when refused', async () => {
  api.getProfile.mockResolvedValue(SERVER);
  render(<ProfileProvider><Probe /></ProfileProvider>);
  expect(await screen.findByText('ready|Amani|green')).toBeInTheDocument();
  api.putProfile.mockResolvedValueOnce({ ...SERVER, accent: 'coral' });
  await act(() => exposed.save({ accent: 'coral' }));
  expect(screen.getByText('ready|Amani|coral')).toBeInTheDocument();
  api.putProfile.mockRejectedValueOnce(new Error('Invalid'));
  await act(async () => { await expect(exposed.save({ accent: 'amber' })).rejects.toThrow('Invalid'); });
  expect(screen.getByText('ready|Amani|coral')).toBeInTheDocument();
});

it('an unreachable profile opens the app with defaults instead of blocking', async () => {
  api.getProfile.mockRejectedValue(new Error('offline'));
  render(<ProfileProvider><Probe /></ProfileProvider>);
  expect(await screen.findByText('unavailable||blue')).toBeInTheDocument();
});

function Where() { return <p data-testid="where">{useLocation().pathname}</p>; }
it('a learner who has not set up is sent to setup; a set-up learner is not', async () => {
  api.getProfile.mockResolvedValue(DEFAULT_PROFILE);
  const view = render(<ProfileProvider><MemoryRouter initialEntries={['/quiz']}><NeedsSetup /><Routes><Route path="*" element={<Where />} /></Routes></MemoryRouter></ProfileProvider>);
  await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/setup'));
  view.unmount();
  api.getProfile.mockResolvedValue(SERVER);
  render(<ProfileProvider><MemoryRouter initialEntries={['/quiz']}><NeedsSetup /><Routes><Route path="*" element={<Where />} /></Routes></MemoryRouter></ProfileProvider>);
  await waitFor(() => expect(api.getProfile).toHaveBeenCalled());
  expect(screen.getByTestId('where')).toHaveTextContent('/quiz');
});

/** WCAG relative luminance contrast. */
function contrast(a: string, b: string) {
  const lum = (hex: string) => {
    const [r, g, bl] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}
it('every learner colour is readable: as text on white, white text on it, and deep text on its soft tint', () => {
  for (const { main, soft, deep } of Object.values(ACCENT_COLOURS)) {
    expect(contrast(main, '#ffffff')).toBeGreaterThanOrEqual(4.5);
    expect(contrast(deep, soft)).toBeGreaterThanOrEqual(4.5);
  }
});
