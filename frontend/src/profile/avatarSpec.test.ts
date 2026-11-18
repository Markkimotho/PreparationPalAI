import { expect, it } from 'vitest';
import contract from '../../../contracts/avatar-vectors.json';
import { avatarSpec, initialOf, newSeed } from './avatarSpec';

it('draws exactly the avatars in the shared contract (same as the phone)', () => {
  for (const { seed, spec } of contract.avatars) expect(avatarSpec(seed)).toEqual(spec);
  for (const { name, initial } of contract.initials) expect(initialOf(name)).toBe(initial);
});

it('shuffle seeds match the server pattern', () => {
  expect(newSeed()).toMatch(/^[A-Za-z0-9_-]{8}$/);
});
