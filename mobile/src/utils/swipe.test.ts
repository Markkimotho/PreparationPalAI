import { project, swipeOutcome } from './swipe';

const WIDTH = 400;

test('projection follows Apple’s exponential decay: faster releases travel further', () => {
  expect(project(0)).toBe(0);
  expect(project(1000, 0.99)).toBeCloseTo(99, 0);
  expect(Math.abs(project(-2000, 0.99))).toBeGreaterThan(Math.abs(project(-1000, 0.99)));
});

test('a short, fast flick commits; the same distance released slowly springs home', () => {
  expect(swipeOutcome(-60, -1800, WIDTH)).toBe(-1);    // flick left: next card
  expect(swipeOutcome(-60, -50, WIDTH)).toBe(0);       // same distance, no momentum: stay
});

test('a slow drag past 40% of the width commits in its direction', () => {
  expect(swipeOutcome(-170, 0, WIDTH)).toBe(-1);
  expect(swipeOutcome(170, 0, WIDTH)).toBe(1);
  expect(swipeOutcome(150, 0, WIDTH)).toBe(0);
});

test('throwing back against the drag cancels it', () => {
  expect(swipeOutcome(-180, 1500, WIDTH)).toBe(0);
});
