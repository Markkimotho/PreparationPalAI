import { fireEvent, render, screen } from '@testing-library/react-native';

const mockSignIn = jest.fn(async () => undefined);
let mockSession = { signIn: mockSignIn, notice: '', error: '' };
jest.mock('@/hooks/use-session', () => ({ useSession: () => mockSession }));
let mockParams: { slide?: string } = {};
jest.mock('expo-router', () => ({ useLocalSearchParams: () => mockParams }));
import * as Haptics from 'expo-haptics';
import { SLIDES, Welcome } from '.';

beforeEach(() => { jest.clearAllMocks(); mockParams = {}; mockSession = { signIn: mockSignIn, notice: '', error: '' }; });

test('every slide is described to screen readers, and the illustrations are not', async () => {
  await render(<Welcome />);
  for (const s of SLIDES) expect(screen.getByLabelText(`${s.title}. ${s.body}`)).toBeTruthy();
  expect(screen.queryByText('What makes ATP?')).toBeNull();     // flashcard art is decorative
});

test('Next walks the slides with one selection haptic per step, then offers Get started', async () => {
  await render(<Welcome />);
  for (let i = 0; i < SLIDES.length - 1; i++) await fireEvent.press(screen.getByRole('button', { name: 'Next' }));
  expect(Haptics.selectionAsync).toHaveBeenCalledTimes(SLIDES.length - 1);
  expect(screen.queryByRole('button', { name: 'Next' })).toBeNull();
  expect(screen.queryByRole('button', { name: 'Skip' })).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Get started' }));
  expect(mockSignIn).toHaveBeenCalledTimes(1);
});

test('Skip jumps to the last slide', async () => {
  await render(<Welcome />);
  await fireEvent.press(screen.getByRole('button', { name: 'Skip' }));
  expect(screen.getByRole('button', { name: 'Get started' })).toBeTruthy();
});

test('returning learners can sign in from the first slide', async () => {
  await render(<Welcome />);
  await fireEvent.press(screen.getByRole('button', { name: 'I already have an account' }));
  expect(mockSignIn).toHaveBeenCalledTimes(1);
});

test('a sign-in failure and an ended session are both explained', async () => {
  mockSession = { signIn: mockSignIn, notice: 'Your session ended. Sign in again to continue.', error: 'Could not reach the sign-in page. Please retry.' };
  await render(<Welcome />);
  expect(screen.getByRole('alert')).toHaveTextContent('Could not reach the sign-in page. Please retry.');
  expect(screen.getByText('Your session ended. Sign in again to continue.')).toBeTruthy();
});

test('a development deep link can open a given slide (and an invalid one falls back to the first)', async () => {
  mockParams = { slide: '3' };
  const view = await render(<Welcome />);
  expect(screen.getByRole('button', { name: 'Get started' })).toBeTruthy();
  await view.unmount();
  mockParams = { slide: 'nope' };
  await render(<Welcome />);
  expect(screen.getByRole('button', { name: 'Next' })).toBeTruthy();
});
