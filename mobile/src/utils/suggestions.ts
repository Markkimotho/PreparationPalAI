/**
 * Suggestions made for the learner: built from their subjects, goal and exam, so two people opening
 * the same screen see different starting points. Pure, so it is tested directly.
 */
import type { Profile } from '@/hooks/use-profile';

type Mode = 'notes' | 'tutor' | 'code';

const GENERIC: Record<Mode, string[]> = {
  notes: ['Summarise my notes in five points', 'What are the key terms I should know?', 'Explain the hardest idea simply'],
  tutor: ['Quiz me on photosynthesis', 'Teach me derivatives step by step', 'Check my understanding of supply and demand'],
  code: ['When should I use a hash map?', 'Explain Big O with examples', 'Review my approach to a REST API'],
};

export function studyIdeas(mode: Mode, p: Pick<Profile, 'subjects' | 'goal' | 'exam_context'>): string[] {
  const [first, second] = p.subjects;
  if (!first || mode === 'code') return GENERIC[mode];
  const other = second ?? first;
  if (mode === 'notes') {
    return [`Summarise my ${first} notes in five points`, `What are the key terms in ${first}?`,
      second ? `What links ${first} and ${second}?` : GENERIC.notes[2]];
  }
  const exam = p.exam_context.trim();
  return {
    exam: [`Quiz me on ${first}${exam ? ` for ${exam}` : ''}, exam style`, `What do examiners look for in ${other} answers?`, `Make me a one-week ${first} revision plan`],
    interview: [`Ask me an interview question on ${first}`, `How would I explain ${other} to an interviewer?`, `What follow-up questions come up on ${first}?`],
    understand: [`Explain the core idea of ${first} simply`, `Why does ${other} work the way it does?`, `Give me an intuition for the hardest part of ${first}`],
  }[p.goal];
}

/** Topics to offer as one-tap starting points (the learner's subjects, in their order). */
export function topicChips(p: Pick<Profile, 'subjects'>): string[] {
  return p.subjects.slice(0, 6);
}

/** The coach mode that matches the learner's goal. */
export function coachModeFor(goal: Profile['goal']): 'recap' | 'exam' | 'interview' {
  return goal === 'exam' ? 'exam' : goal === 'interview' ? 'interview' : 'recap';
}
