import { coachModeFor, studyIdeas, topicChips } from './suggestions';

const amani = { subjects: ['Organic chemistry', 'Statistics'], goal: 'exam' as const, exam_context: 'KCSE 2027' };

test('suggestions are built from the learner’s own subjects, goal and exam', () => {
  expect(studyIdeas('tutor', amani)[0]).toBe('Quiz me on Organic chemistry for KCSE 2027, exam style');
  expect(studyIdeas('tutor', { ...amani, goal: 'interview' })[0]).toBe('Ask me an interview question on Organic chemistry');
  expect(studyIdeas('notes', amani)).toContain('What links Organic chemistry and Statistics?');
});

test('two learners see different suggestions on the same screen', () => {
  const kofi = { subjects: ['History'], goal: 'understand' as const, exam_context: '' };
  expect(studyIdeas('tutor', amani)).not.toEqual(studyIdeas('tutor', kofi));
});

test('a learner with no subjects yet, or code mode, gets sensible general ideas', () => {
  expect(studyIdeas('tutor', { subjects: [], goal: 'exam', exam_context: '' })).toHaveLength(3);
  expect(studyIdeas('code', amani)[0]).toBe('When should I use a hash map?');
  expect(studyIdeas('notes', { subjects: ['Law'], goal: 'understand', exam_context: '' })).toHaveLength(3);
});

test('topic chips and the coach mode follow the profile', () => {
  expect(topicChips(amani)).toEqual(['Organic chemistry', 'Statistics']);
  expect([coachModeFor('exam'), coachModeFor('interview'), coachModeFor('understand')]).toEqual(['exam', 'interview', 'recap']);
});
