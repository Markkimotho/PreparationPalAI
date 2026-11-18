import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, Outlet } from 'react-router-dom';
import { expect, it, vi } from 'vitest';

vi.mock('../context/ModelContext', () => ({ ModelProvider: ({ children }: { children: ReactNode }) => children }));
vi.mock('../context/KnowledgeBaseContext', () => ({ KnowledgeBaseProvider: ({ children }: { children: ReactNode }) => children }));
vi.mock('../components/AppLayout', () => ({ AppLayout: () => <Outlet /> }));
vi.mock('../sections/Coach', () => ({ Coach: () => <p>coach page</p> }));
vi.mock('../sections/QuizPrep', () => ({ QuizPrep: () => <p>quiz page</p> }));
import { App } from '../App';

// Regression: after sign-in the router still held /auth/callback, matched only the catch-all,
// and learners landed on Quiz instead of the coach.
it('returning from sign-in lands on the coach', () => {
  render(<MemoryRouter initialEntries={['/auth/callback?code=x&state=y']}><App /></MemoryRouter>);
  expect(screen.getByText('coach page')).toBeInTheDocument();
});

it('unknown pages still fall back to Quiz', () => {
  render(<MemoryRouter initialEntries={['/nowhere']}><App /></MemoryRouter>);
  expect(screen.getByText('quiz page')).toBeInTheDocument();
});
