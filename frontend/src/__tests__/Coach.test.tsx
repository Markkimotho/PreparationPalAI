import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { Coach } from '../sections/Coach';

vi.mock('../context/ModelContext', () => ({ useModelContext: () => ({ selected: 'deepseek-r1:7b' }) }));
const session = {
  id: 'session1', topic: 'Physics', mode: 'exam', model: 'deepseek-r1:7b', index: 0,
  total: 2, deadline: 0, done: false, grounding: 'model-general knowledge', sources: [], answers: [], summary: null,
  question: { type: 'mcq', question: 'Which unit measures energy?', topic: 'Units', options: { A: 'Joule', B: 'Watt' } },
};
const fetchMock = vi.fn();
beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockImplementation(async (_url: string, init?: RequestInit) => ({
    ok: true, json: async () => init ? session : { sessions: [], weak_topics: ['Thermodynamics'] },
  }));
});
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });
const setup = () => render(<MemoryRouter><Coach /></MemoryRouter>);

describe('Preparation coach', () => {
  it('starts a topic session with the exact selected model and format', async () => {
    setup();
    await userEvent.type(screen.getByLabelText('Topic, subject, or syllabus focus'), 'Physics');
    await userEvent.click(screen.getByRole('button', { name: 'Exam practice Mixed questions, with an optional timer.' }));
    await userEvent.selectOptions(screen.getByLabelText('Time limit'), '10');
    await userEvent.click(screen.getByRole('button', { name: 'Start preparation' }));
    expect(await screen.findByText('Which unit measures energy?')).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([_url, init]) => Boolean(init));
    expect(JSON.parse(call![1].body as string)).toMatchObject({ topic: 'Physics', mode: 'exam', minutes: 10, question_type: 'mixed', model: 'deepseek-r1:7b' });
    expect(screen.getByText(/General model knowledge/)).toBeInTheDocument();
  });

  it('shows actionable grading feedback and a revision plan', async () => {
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => ({
      ok: true, json: async () => url.endsWith('/answers') ? { ...session, done: true, index: 1, question: null,
        answers: [{ question: 'Q', reference: 'Joule', explanation: 'Energy units', result: { score: 50, feedback: 'Review energy units.', key_missed: ['Units'], hint: 'Compare work and power.' } }],
        summary: { score: 25, topics: [{ topic: 'Units', score: 50, missed: ['Units'] }], next_actions: ['Practise unit conversions.'] },
      } : init ? session : { sessions: [], weak_topics: [] },
    }));
    setup();
    await userEvent.type(screen.getByLabelText('Topic, subject, or syllabus focus'), 'Physics');
    await userEvent.click(screen.getByRole('button', { name: 'Start preparation' }));
    await userEvent.click(await screen.findByLabelText('A: Joule'));
    await userEvent.click(screen.getByRole('button', { name: 'Submit answer' }));
    expect(await screen.findByText('Review energy units.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'View results' }));
    expect(screen.getByText('Practise unit conversions.')).toBeInTheDocument();
  });

  it('surfaces missing-model recovery without losing topic input', async () => {
    fetchMock.mockImplementation(async (_url: string, init?: RequestInit) => ({
      ok: !init, json: async () => init ? { detail: 'Model missing. Choose Pull, then retry.' } : { sessions: [], weak_topics: [] },
    }));
    setup();
    await userEvent.type(screen.getByLabelText('Topic, subject, or syllabus focus'), 'Biology');
    await userEvent.click(screen.getByRole('button', { name: 'Start preparation' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Choose Pull');
    expect(screen.getByLabelText('Topic, subject, or syllabus focus')).toHaveValue('Biology');
  });
});
