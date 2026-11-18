import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';

jest.mock('@/components/markdown', () => { const { Text } = require('react-native'); return ({ text }: { text: string }) => <Text>{text}</Text>; });
jest.mock('@/utils/upload', () => ({ pickAndUpload: jest.fn(async () => 1) }));
jest.mock('@/utils/api', () => ({ stream: jest.fn() }));
import { stream } from '@/utils/api';
import { Study } from './study';

const mockStream = stream as jest.Mock;
beforeEach(() => jest.clearAllMocks());

test('an answer streams in, with its sources', async () => {
  mockStream.mockImplementation(async (_p: string, _b: unknown, onEvent: (e: unknown) => void) => {
    onEvent({ type: 'token', text: 'Force equals ' }); onEvent({ type: 'token', text: 'mass times acceleration.' });
    onEvent({ type: 'sources', sources: [{ source: 'physics.pdf' }] }); onEvent({ type: 'done' });
  });
  await render(<Study />);
  await fireEvent.changeText(screen.getByLabelText('Your question'), "What is Newton's second law?");
  await fireEvent.press(screen.getByRole('button', { name: 'Send' }));
  expect(await screen.findByText('Force equals mass times acceleration.')).toBeTruthy();
  expect(screen.getByText('Sources: physics.pdf')).toBeTruthy();
  expect(mockStream).toHaveBeenCalledWith('/api/chat/stream', expect.objectContaining({ question: "What is Newton's second law?" }), expect.any(Function), expect.anything());
});

test('the tutor and code modes use their own endpoints', async () => {
  mockStream.mockResolvedValue(undefined);
  await render(<Study />);
  await fireEvent.press(screen.getByRole('tab', { name: 'Tutor' }));
  await fireEvent.changeText(screen.getByLabelText('Your question'), 'Quiz me');
  await fireEvent.press(screen.getByRole('button', { name: 'Send' }));
  await waitFor(() => expect(mockStream).toHaveBeenCalledWith('/api/agent/stream', expect.objectContaining({ message: 'Quiz me' }), expect.any(Function), expect.anything()));
});

test('a dropped connection keeps the partial answer and explains what happened', async () => {
  mockStream.mockImplementation(async (_p: string, _b: unknown, onEvent: (e: unknown) => void) => {
    onEvent({ type: 'token', text: 'Partial answer' });
    throw new Error('The connection dropped before the answer finished. Check your connection and try again.');
  });
  await render(<Study />);
  await fireEvent.changeText(screen.getByLabelText('Your question'), 'q');
  await fireEvent.press(screen.getByRole('button', { name: 'Send' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/connection dropped/);
  expect(screen.getByText('Partial answer')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Send' })).toBeTruthy();         // not stuck on a spinner
});

test('a credit shortfall is shown, not swallowed', async () => {
  mockStream.mockRejectedValue(new Error('Not enough credits for this action. You have 2 credits and this needs about 13.'));
  await render(<Study />);
  await fireEvent.changeText(screen.getByLabelText('Your question'), 'q');
  await fireEvent.press(screen.getByRole('button', { name: 'Send' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/needs about 13/);
});

test('adding notes uploads a file and says what happens next', async () => {
  await render(<Study />);
  await fireEvent.press(screen.getByRole('button', { name: 'Add notes (PDF or photo)' }));
  expect(await screen.findByText(/being read/)).toBeTruthy();
});
