import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { QuestionCard } from '../sections/QuizPrep/QuestionCard';
import { StudyMode } from '../sections/Flashcards/StudyMode';

it('can select and submit a quiz answer with the keyboard', async () => {
  const onSubmit = vi.fn();
  render(<QuestionCard question={{ type: 'mcq', question: 'Energy unit?', options: { A: 'Joule', B: 'Watt' } }} idx={0} total={2} correctSoFar={0} submitting={false} onSubmit={onSubmit} />);
  await userEvent.tab();
  await userEvent.keyboard(' ');
  await userEvent.tab();
  await userEvent.keyboard('{Enter}');
  expect(onSubmit).toHaveBeenCalledWith('A');
});

it('does not let global flashcard shortcuts hijack the Exit button', async () => {
  const onExit = vi.fn();
  render(<StudyMode deckName="Physics" cards={[{ id: 'a', front: 'F?', back: 'ma', created_at: 0 }]} onExit={onExit} />);
  await userEvent.tab();
  await userEvent.keyboard('{Enter}');
  expect(onExit).toHaveBeenCalledOnce();
});
