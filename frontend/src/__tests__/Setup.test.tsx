import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { DEFAULT_PROFILE } from '../api/profile';

const ctx = vi.hoisted(() => ({ save: vi.fn(), onboarded: false }));
vi.mock('../profile/ProfileContext', () => ({
  useProfile: () => ({ profile: { ...DEFAULT_PROFILE, onboarded: ctx.onboarded }, status: 'ready', workspace: 'u-x', save: ctx.save }),
}));
import { Setup } from '../sections/Setup/Setup';

function Where() { return <p data-testid="where">{useLocation().pathname}</p>; }
const renderAt = (url: string) => render(<MemoryRouter initialEntries={[url]}><Routes>
  <Route path="/setup" element={<Setup />} /><Route path="*" element={<Where />} />
</Routes></MemoryRouter>);

beforeEach(() => { vi.clearAllMocks(); ctx.onboarded = false; ctx.save.mockResolvedValue(undefined); });

it('a new learner makes the web app theirs, keyboard only, and exactly that is saved', async () => {
  const user = userEvent.setup();
  renderAt('/setup');
  expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
  await user.type(screen.getByLabelText('Your name'), 'Amani{Enter}');
  expect(screen.getByRole('heading', { name: 'What are you working toward, Amani?' })).toHaveFocus();
  await user.click(screen.getByRole('radio', { name: /Ace an exam/ }));
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Chemistry' }));
  await user.type(screen.getByLabelText('Add your own subject'), 'Statistics{Enter}');
  await user.click(screen.getByRole('radio', { name: 'Advanced' }));
  await user.type(screen.getByLabelText('Which exam, and when?'), 'KCSE 2027');
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  await user.click(screen.getByRole('radio', { name: 'Focused, 20 a day' }));
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  await user.click(screen.getByRole('radio', { name: 'coral colour' }));
  expect(screen.getByRole('img', { name: 'Your avatar, Amani' })).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Start learning' }));
  const saved = ctx.save.mock.calls[0][0];
  expect(saved).toMatchObject({ display_name: 'Amani', goal: 'exam', subjects: ['Chemistry', 'Statistics'], level: 'advanced',
    exam_context: 'KCSE 2027', daily_goal: 20, accent: 'coral', onboarded: true });
  expect(saved.avatar_seed).toMatch(/^[a-z0-9]{8}$/);
});

it('Back keeps the answer; Skip saves the defaults', async () => {
  const user = userEvent.setup();
  renderAt('/setup');
  await user.type(screen.getByLabelText('Your name'), 'Kofi{Enter}');
  await user.click(screen.getByRole('button', { name: '‹ Back' }));
  expect(screen.getByLabelText('Your name')).toHaveValue('Kofi');
  await user.click(screen.getByRole('button', { name: 'Skip for now' }));
  expect(ctx.save).toHaveBeenCalledWith(expect.objectContaining({ onboarded: true, display_name: '' }));
});

it('once the profile is set up, first-time setup hands over to the app', () => {
  ctx.onboarded = true;
  renderAt('/setup');
  expect(screen.getByTestId('where')).toHaveTextContent('/prepare');
});

it('editing saves and returns to Account; a refused save is explained and stays put', async () => {
  const user = userEvent.setup();
  ctx.onboarded = true;
  ctx.save.mockRejectedValueOnce(new Error('Could not save your profile. Please retry.'));
  renderAt('/setup?edit=1');
  expect(screen.queryByRole('button', { name: 'Skip for now' })).toBeNull();
  await user.type(screen.getByLabelText('Your name'), 'Amani{Enter}');
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  await user.click(screen.getByRole('button', { name: 'Biology' }));
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  await user.click(screen.getByRole('button', { name: 'Save changes' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not save your profile. Please retry.');
  await user.click(screen.getByRole('button', { name: 'Save changes' }));
  expect(screen.getByTestId('where')).toHaveTextContent('/account');
});
