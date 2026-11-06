import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { StudyExport } from '../components/StudyExport';

vi.mock('../context/ModelContext', () => ({ useModelContext: () => ({ selected: 'qwen2.5:7b' }) }));
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('downloads a checked pack using the selected model and format', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(['%PDF']) });
  vi.stubGlobal('fetch', fetchMock);
  URL.createObjectURL = vi.fn().mockReturnValue('blob:study');
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  render(<StudyExport questions={[{ question: 'Define force.' }]} />);
  await userEvent.click(screen.getByRole('button', { name: 'Study pack' }));
  await userEvent.click(screen.getByRole('option', { name: 'Revision checklist' }));
  await userEvent.click(screen.getByRole('button', { name: 'Download' }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ kind: 'checklist', format: 'pdf', model: 'qwen2.5:7b' });
});

it('shows actionable errors and does not expose unfinished session answer keys', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: 'Safety checking is unavailable. Please retry.' }) }));
  render(<StudyExport sessionId="session" learner="ada" answersAvailable={false} />);
  await userEvent.click(screen.getByRole('button', { name: 'Study pack' }));
  expect(screen.queryByRole('option', { name: 'Separate answer key' })).not.toBeInTheDocument();
  await userEvent.keyboard('{Escape}');
  await userEvent.click(screen.getByRole('button', { name: 'Download' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Safety checking is unavailable');
});
