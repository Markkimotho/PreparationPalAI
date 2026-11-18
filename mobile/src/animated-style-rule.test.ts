/**
 * Gate: every useAnimatedStyle reads its shared values directly (`.get()` in its own body).
 *
 * Reanimated re-runs an animated style only when a shared value read inside that style's own
 * function changes. Reading one inside a helper worklet is not tracked, so the style is computed
 * once and then freezes. That shipped once: the welcome carousel's titles for slides 3 and 4 never
 * appeared, because their styles called `text(0.15)` and the helper read the scroll offset.
 */
import { readdirSync, readFileSync, statSync } from 'fs';
import { join, relative } from 'path';

const ROOT = join(__dirname);

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap(name => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

/** The text of each useAnimatedStyle(...) argument, found by balancing parentheses. */
export function animatedStyleBodies(code: string): string[] {
  const bodies: string[] = [];
  let at = code.indexOf('useAnimatedStyle(');
  while (at !== -1) {
    let depth = 0;
    let i = at + 'useAnimatedStyle'.length;
    for (; i < code.length; i++) {
      if (code[i] === '(') depth++;
      else if (code[i] === ')' && --depth === 0) break;
    }
    bodies.push(code.slice(at, i + 1));
    at = code.indexOf('useAnimatedStyle(', i);
  }
  return bodies;
}

test('the rule catches the bug it exists for', () => {
  expect(animatedStyleBodies("const t = useAnimatedStyle(() => text(0.15));")[0]).not.toContain('.get()');
  expect(animatedStyleBodies("const t = useAnimatedStyle(() => text(x.get(), 0.15));")[0]).toContain('.get()');
});

test('every animated style in the app reads a shared value directly', () => {
  const offenders = sources(ROOT).flatMap(file =>
    animatedStyleBodies(readFileSync(file, 'utf8')).filter(body => !body.includes('.get()')).map(body => `${relative(ROOT, file)}: ${body.slice(0, 80)}`));
  expect(offenders).toEqual([]);
});
