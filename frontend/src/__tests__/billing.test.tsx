import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { creditsMessage } from '../api/billing';
import { ErrorState } from '../components/ErrorState';
import { api, ApiError } from '../api/client';

it('explains how many credits are missing and where to top up', () => {
  expect(creditsMessage({ detail: 'Not enough credits for this action.', balance_credits: 3, required_credits: 14,
    top_up_url: 'https://pay.example/top-up' }))
    .toBe('Not enough credits for this action. You have 3 credits and this needs about 14. Top up: https://pay.example/top-up');
});

it('still produces a sentence when the body is sparse', () => {
  expect(creditsMessage({})).toBe('Not enough credits for this action.');
});

it('turns a top-up address in an error into a safe link', () => {
  render(<ErrorState message="Not enough credits. Top up: https://pay.example/top-up" />);
  const link = screen.getByRole('link', { name: 'https://pay.example/top-up' });
  expect(link).toHaveAttribute('href', 'https://pay.example/top-up');
  expect(link).toHaveAttribute('rel', 'noopener noreferrer');
});

it('does not link anything that is not http(s)', () => {
  render(<ErrorState message="Try javascript:alert(1) or ftp://x" />);
  expect(screen.queryByRole('link')).toBeNull();
});

it('surfaces a 402 from the API as an ApiError with the credit details', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'Not enough credits for this action.',
    balance_credits: 1, required_credits: 4, top_up_url: 'https://pay.example/top-up' }), { status: 402 })));
  const error = await api.models().catch((e) => e);
  expect(error).toBeInstanceOf(ApiError);
  expect(error.status).toBe(402);
  expect(error.message).toContain('You have 1 credits and this needs about 4.');
  vi.unstubAllGlobals();
});
