/**
 * A unique avatar for every learner, generated from a seed (their account id plus a shuffle seed).
 * Pure and deterministic: the same seed draws the same avatar on every device. Same algorithm as
 * mobile/src/utils/avatar.ts; both are checked against contracts/avatar-vectors.json.
 */
export interface AvatarSpec { colors: [string, string]; motif: 'diamond' | 'orbit' | 'petal' | 'stack'; angle: number; ink: string }

// Gradients from the brand family (blue, amber, green, coral, the logo's deep green and mint), brightened.
const GRADIENTS: [string, string][] = [
  ['#5c9bff', '#1d4f9f'], ['#ffc34d', '#e07a05'], ['#3fd29a', '#156b4d'], ['#ff8a72', '#c63c2b'],
  ['#c9e6bc', '#1fa774'], ['#8fb8ff', '#2f6fe4'], ['#ffb648', '#f8624d'], ['#6ee7c5', '#1d4f9f'],
];
const MOTIFS: AvatarSpec['motif'][] = ['diamond', 'orbit', 'petal', 'stack'];

/** 32-bit FNV-1a: small, fast, and well spread for short strings. */
export function hash(text: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

export function avatarSpec(seed: string): AvatarSpec {
  const h = hash(seed || 'preparationpal');
  const colors = GRADIENTS[h % GRADIENTS.length];
  return { colors, motif: MOTIFS[(h >>> 8) % MOTIFS.length], angle: ((h >>> 16) % 8) * 45, ink: '#ffffff' };
}

/** The letter shown on the avatar: the first letter of their name, or none. */
export function initialOf(name: string): string {
  const letter = [...name.trim()][0];
  return letter ? letter.toLocaleUpperCase() : '';
}

/** A new shuffle seed (letters and digits, matches the server's allowed pattern). */
export function newSeed(random: () => number = Math.random): string {
  return Array.from({ length: 8 }, () => 'abcdefghijkmnpqrstuvwxyz23456789'[Math.floor(random() * 31)]).join('');
}
