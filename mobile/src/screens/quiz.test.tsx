import { fireEvent, render, screen } from '@testing-library/react-native';

jest.mock('@/utils/api', () => ({ postJson: jest.fn() }));
import { postJson } from '@/utils/api';
import { Quiz } from './quiz';

test('make a quiz, answer it, see the score', async () => {
  (postJson as jest.Mock).mockResolvedValue([
    { question: 'Unit of force?', options: { A: 'Newton', B: 'Joule' }, correct: 'A', explanation: 'F = ma, in newtons.' },
    { question: 'Unit of energy?', options: { A: 'Watt', B: 'Joule' }, correct: 'B', explanation: 'Energy is in joules.' },
  ]);
  await render(<Quiz />);
  await fireEvent.changeText(screen.getByLabelText('Topic'), 'Mechanics');
  await fireEvent.press(screen.getByRole('button', { name: 'Make a quiz' }));
  expect(postJson).toHaveBeenCalledWith('/api/quiz/generate', { topic: 'Mechanics', n: 5, question_type: 'mcq' });
  await fireEvent.press(await screen.findByRole('button', { name: 'A. Newton' }));
  expect(screen.getByText(/Correct\./)).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'A. Watt' }));
  expect(screen.getByText(/Not quite: the answer is B/)).toBeTruthy();
  expect(screen.getByText('You scored 1 of 2.')).toBeTruthy();
});
