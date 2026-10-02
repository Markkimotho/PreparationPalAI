import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { Markdown } from '../components/Markdown';

it('does not fetch remote images embedded in untrusted model content', () => {
  const { container } = render(<Markdown>{'![reference](https://untrusted.example/secret.png)'}</Markdown>);
  expect(container.querySelector('img')).toBeNull();
  expect(screen.getByText('[Image omitted: reference]')).toBeInTheDocument();
});
