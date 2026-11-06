import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { ModelPicker } from '../components/ModelPicker';
import type { ModelInfo } from '../api/types';
const mocks = vi.hoisted(() => ({ refresh: vi.fn(), stream: vi.fn(), catalogue: [] as ModelInfo[] }));
vi.mock('../context/ModelContext', () => ({ useModelContext: () => ({
  supported: ['glm4:9b'], installed: [], selected: 'glm4:9b', setSelected: vi.fn(),
  refresh: mocks.refresh, online: true, catalogue: mocks.catalogue,
}) }));
vi.mock('../api/stream', () => ({ streamPost: mocks.stream }));

it('shows a failed download and preserves the selected model for retry', async () => {
  mocks.stream.mockImplementation(async (_path, body, handlers) => {
    expect(body.model).toBe('glm4:9b');
    handlers.onEvent({ type: 'progress', status: 'Downloading', completed: 10, total: 20 });
    handlers.onEvent({ type: 'error', message: 'Download failed. Check the model tag.' });
  });
  render(<ModelPicker />);
  await userEvent.click(screen.getByRole('button', { name: 'Pull' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Download failed');
  expect(screen.getByRole('button', { name: 'Pull' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Model' })).toHaveTextContent('glm4:9b');
});

it('opens model details in a labelled dialog and closes without expanding the toolbar', async () => {
  mocks.catalogue = [{ id: 'glm4:9b', installed: false, availability: 'not installed', tools: null,
    structured_output: true, recommended_use: 'Technical explanations.', resources: 'Requires local memory.' }];
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
  render(<ModelPicker />);
  await userEvent.click(screen.getByRole('button', { name: 'Model info' }));
  expect(screen.getByRole('dialog', { name: 'glm4:9b' })).toBeInTheDocument();
  expect(screen.getByText('Not verified')).toBeInTheDocument();
  expect(screen.getByText('Technical explanations.')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Close model info' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
