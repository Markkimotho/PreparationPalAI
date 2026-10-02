import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { ModelPicker } from '../components/ModelPicker';
const mocks = vi.hoisted(() => ({ refresh: vi.fn(), stream: vi.fn() }));
vi.mock('../context/ModelContext', () => ({ useModelContext: () => ({
  supported: ['glm4:9b'], installed: [], selected: 'glm4:9b', setSelected: vi.fn(),
  refresh: mocks.refresh, online: true, catalogue: [],
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
