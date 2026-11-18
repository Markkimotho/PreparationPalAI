import { fireEvent, render, screen } from '@testing-library/react-native';

const mockSave = jest.fn(async (_changes: Record<string, unknown>) => undefined);
const mockBack = jest.fn();
const mockReplace = jest.fn();
jest.mock('expo-router', () => ({ router: { back: () => mockBack(), replace: (to: string) => mockReplace(to) } }));
let mockOnboarded = false;
jest.mock('@/hooks/use-profile', () => {
  const actual = jest.requireActual('@/hooks/use-profile');
  return { ...actual, useProfile: () => ({ profile: { ...actual.DEFAULT_PROFILE, onboarded: mockOnboarded }, workspace: 'u-x', status: 'ready', save: mockSave }) };
});
import { Setup } from './setup';

beforeEach(() => { jest.clearAllMocks(); mockOnboarded = false; });
const next = () => fireEvent.press(screen.getByRole('button', { name: 'Continue' }));

test('a new learner makes the app theirs in five steps, and exactly that is saved', async () => {
  await render(<Setup />);
  expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();           // a name first
  await fireEvent.changeText(screen.getByLabelText('Your name'), 'Amani');
  await next();
  expect(screen.getByText('What are you working toward, Amani?')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Ace an exam. Recall, exam-style questions and timing.' }));
  await next();
  expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();           // at least one subject
  await fireEvent.press(screen.getByRole('button', { name: 'Chemistry' }));
  await fireEvent.changeText(screen.getByLabelText('Add your own subject'), 'Statistics');
  await fireEvent.press(screen.getByRole('button', { name: 'Add subject' }));
  await fireEvent.press(screen.getByRole('tab', { name: 'Advanced' }));
  await fireEvent.changeText(screen.getByLabelText('Which exam, and when?'), 'KCSE, November 2027');
  await next();
  await fireEvent.press(screen.getByRole('button', { name: 'Focused, 20 a day' }));
  await next();
  await fireEvent.press(screen.getByRole('button', { name: 'coral colour' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Start learning' }));
  expect(mockSave).toHaveBeenCalledTimes(1);
  const saved = mockSave.mock.calls[0][0];
  expect(saved).toMatchObject({ display_name: 'Amani', goal: 'exam', subjects: ['Chemistry', 'Statistics'], level: 'advanced',
    exam_context: 'KCSE, November 2027', daily_goal: 20, accent: 'coral', onboarded: true });
  expect(saved.avatar_seed).toMatch(/^[a-z0-9]{8}$/);
  expect(mockBack).not.toHaveBeenCalled();
});

test('first-time setup hands over to the app once the profile is set up (here, or already on another device)', async () => {
  mockOnboarded = true;
  await render(<Setup />);
  expect(mockReplace).toHaveBeenCalledWith('/');
});

test('the editor does not jump away just because the profile is set up', async () => {
  mockOnboarded = true;
  await render(<Setup editing />);
  expect(mockReplace).not.toHaveBeenCalled();
});

test('Back returns to the previous step with the answer kept', async () => {
  await render(<Setup />);
  await fireEvent.changeText(screen.getByLabelText('Your name'), 'Kofi');
  await next();
  await fireEvent.press(screen.getByRole('button', { name: 'Back' }));
  expect(screen.getByLabelText('Your name').props.value).toBe('Kofi');
});

test('Skip finishes setup with the defaults, so it is not asked again', async () => {
  await render(<Setup />);
  await fireEvent.press(screen.getByRole('button', { name: 'Skip for now' }));
  expect(mockSave).toHaveBeenCalledWith(expect.objectContaining({ onboarded: true, display_name: '' }));
});

test('editing an existing profile saves and closes', async () => {
  await render(<Setup editing />);
  expect(screen.queryByRole('button', { name: 'Skip for now' })).toBeNull();
  await fireEvent.changeText(screen.getByLabelText('Your name'), 'Amani');
  for (let i = 0; i < 4; i++) {
    if (i === 2) await fireEvent.press(screen.getByRole('button', { name: 'Biology' }));
    await next();
  }
  await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));
  expect(mockSave).toHaveBeenCalledTimes(1);
  expect(mockBack).toHaveBeenCalledTimes(1);
});

test('a refused save is explained and nothing closes', async () => {
  mockSave.mockRejectedValueOnce(new Error('Could not reach the server. Please retry.'));
  await render(<Setup editing />);
  await fireEvent.changeText(screen.getByLabelText('Your name'), 'Amani');
  for (let i = 0; i < 4; i++) {
    if (i === 2) await fireEvent.press(screen.getByRole('button', { name: 'Biology' }));
    await next();
  }
  await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server. Please retry.');
  expect(mockBack).not.toHaveBeenCalled();
});

// Regression: the daily-goal tiles took a percentage width on the pressable's inner view, which
// resolved against an unsized wrapper and squeezed each tile's text to one letter per line.
test('daily-goal tiles sit in half-width slots, two per row', async () => {
  const { StyleSheet } = require('react-native');
  await render(<Setup />);
  await fireEvent.changeText(screen.getByLabelText('Your name'), 'Amani');
  await next();
  await next();
  await fireEvent.press(screen.getByRole('button', { name: 'Biology' }));
  await next();
  const tile = screen.getByRole('button', { name: 'Steady, 10 a day' });
  let slot = tile.parent;
  while (slot && StyleSheet.flatten(slot.props.style)?.width === undefined) slot = slot.parent;
  expect(StyleSheet.flatten(slot!.props.style).width).toBe('50%');
});
