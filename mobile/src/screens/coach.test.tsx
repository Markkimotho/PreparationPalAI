import { fireEvent, render, screen } from '@testing-library/react-native';

jest.mock('@/utils/api', () => ({ postJson: jest.fn() }));
import { postJson } from '@/utils/api';
import { Coach } from './coach';

const question = (q: string, options?: Record<string, string>) => ({ type: options ? 'mcq' : 'short_answer', question: q, options });

test('practise: start, answer, read feedback, finish with a summary', async () => {
  const mock = postJson as jest.Mock;
  mock.mockResolvedValueOnce({ id: 's1', index: 0, total: 2, done: false, question: question('Big-O of binary search?', { A: 'O(n)', B: 'O(log n)' }), answers: [], summary: null })
    .mockResolvedValueOnce({ id: 's1', index: 1, total: 2, done: false, question: question('Explain a hash collision.'),
      answers: [{ result: { score: 100, feedback: 'Exactly right.' } }], summary: null })
    .mockResolvedValueOnce({ id: 's1', index: 2, total: 2, done: true, question: null,
      answers: [{ result: { score: 100, feedback: 'Exactly right.' } }, { result: { score: 60, feedback: 'Mention chaining.', hint: 'Compare open addressing.' } }],
      summary: { score: 80, next_actions: ['Review hashing, then practise again.'] } });
  await render(<Coach />);
  await fireEvent.changeText(screen.getByLabelText('What are you preparing for?'), 'Algorithms');
  await fireEvent.press(screen.getByRole('tab', { name: 'Interview' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Start practice' }));
  expect(mock).toHaveBeenLastCalledWith('/api/coach/sessions', { learner: 'me', topic: 'Algorithms', mode: 'interview', n: 5 });
  await fireEvent.press(await screen.findByRole('button', { name: 'B. O(log n)' }));
  expect(mock).toHaveBeenLastCalledWith('/api/coach/sessions/s1/answers', { learner: 'me', answer: 'B', index: 0, confidence: 3 });
  expect(await screen.findByText('Exactly right.')).toBeTruthy();
  await fireEvent.changeText(screen.getByLabelText('Your answer'), 'Two keys hash to the same slot.');
  await fireEvent.press(screen.getByRole('button', { name: 'Submit answer' }));
  expect(await screen.findByText('Overall 80/100')).toBeTruthy();
  expect(screen.getByText('• Review hashing, then practise again.')).toBeTruthy();
  expect(screen.getByText('Compare open addressing.')).toBeTruthy();
});
