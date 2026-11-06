import { useEffect, useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { DrawingWorkspace, needsDrawing } from '../components/DrawingWorkspace';

vi.mock('../components/DrawingCanvas', () => ({ default: ({ onReady }: { onReady: (fn: () => Promise<unknown>) => void }) => {
  const [text, setText] = useState('');
  useEffect(() => { onReady(async () => ({ image: 'data:image/png;base64,test', scene: { elements: [{ type: 'arrow' }] } })); }, [onReady]);
  return <label>Canvas draft<input value={text} onChange={e => setText(e.target.value)} /></label>;
} }));
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });

it('recognizes explicit visual tasks without mistaking ordinary reasoning for drawing', () => {
  for (const question of ['Draw a labelled circuit diagram.', 'Plot the probability distribution.', 'Sketch a force diagram.', 'Draw a labelled cell.']) expect(needsDrawing(question)).toBe(true);
  expect(needsDrawing('Draw conclusions from this result.')).toBe(false);
});

it('opens for visual questions, preserves a hidden draft and submits the actual snapshot', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 'drawing1' }) });
  vi.stubGlobal('fetch', fetchMock);
  render(<MemoryRouter><DrawingWorkspace question="Draw a circuit diagram." model="qwen2.5:7b" /></MemoryRouter>);
  await userEvent.type(await screen.findByLabelText('Canvas draft'), 'Arrow + label');
  await userEvent.click(screen.getByRole('button', { name: 'Hide drawing workspace' }));
  await userEvent.click(screen.getByRole('button', { name: 'Open drawing workspace' }));
  expect(screen.getByLabelText('Canvas draft')).toHaveValue('Arrow + label');
  await userEvent.type(screen.getByLabelText('Explain your drawing'), 'Current direction is labelled.');
  await userEvent.click(screen.getByRole('button', { name: 'Submit drawing for review' }));
  expect(await screen.findByRole('link', { name: /Open drawing reviews/ })).toHaveAttribute('href', '/drawings');
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ question: 'Draw a circuit diagram.', explanation: 'Current direction is labelled.', image: 'data:image/png;base64,test' });
});

it('retains the drawing and explanation when submission fails', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: 'Safety checking is unavailable. Retry.' }) }));
  render(<MemoryRouter><DrawingWorkspace question="Explain Newton’s law." /></MemoryRouter>);
  expect(screen.queryByLabelText('Canvas draft')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Add a drawing' }));
  await userEvent.type(await screen.findByLabelText('Canvas draft'), 'Force arrow');
  await userEvent.type(screen.getByLabelText('Explain your drawing'), 'Gravity acts downward.');
  await userEvent.click(screen.getByRole('button', { name: 'Submit drawing for review' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Safety checking is unavailable'));
  expect(screen.getByLabelText('Canvas draft')).toHaveValue('Force arrow');
  expect(screen.getByLabelText('Explain your drawing')).toHaveValue('Gravity acts downward.');
});
