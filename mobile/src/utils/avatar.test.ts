import { avatarSpec, hash, initialOf, newSeed } from './avatar';

test('the same seed always draws the same avatar', () => {
  expect(avatarSpec('u-abc:k3x9')).toEqual(avatarSpec('u-abc:k3x9'));
});

test('different learners get visibly different avatars', () => {
  const specs = Array.from({ length: 200 }, (_, i) => avatarSpec(`u-${i}:seed`));
  const distinct = new Set(specs.map(s => `${s.colors.join()}|${s.motif}|${s.angle}`));
  expect(distinct.size).toBeGreaterThan(100);                 // 8 gradients x 4 motifs x 8 angles = 256 looks
  expect(new Set(specs.map(s => s.colors[0])).size).toBe(8);   // every gradient is used
});

test('the hash is stable (avatars must not change between app versions)', () => {
  expect(hash('preparationpal')).toBe(hash('preparationpal'));
  expect(hash('a')).toBe(0xe40c292c);
});

test('the initial is the first letter, upper-cased, including non-Latin names', () => {
  expect(initialOf(' amani ')).toBe('A');
  expect(initialOf('Ólafur')).toBe('Ó');
  expect(initialOf('')).toBe('');
});

test('shuffle seeds match the server pattern and differ', () => {
  const seed = newSeed();
  expect(seed).toMatch(/^[A-Za-z0-9_-]{8}$/);
  expect(newSeed(() => 0)).not.toBe(newSeed(() => 0.99));
});
