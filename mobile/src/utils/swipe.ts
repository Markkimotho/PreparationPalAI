/** Swipe decisions for thrown cards. Pure worklets, so they run on the UI thread and in tests. */

/** Where a release at `velocity` (px/s) would come to rest: Apple's exponential-decay projection. */
export function project(velocity: number, decelerationRate = 0.998) {
  'worklet';
  return ((velocity / 1000) * decelerationRate) / (1 - decelerationRate);
}

/** The swipe decision, pure so it can be tested: -1 (next), +1 (previous) or 0 (stay). */
export function swipeOutcome(translation: number, velocity: number, width: number): -1 | 0 | 1 {
  'worklet';
  const landing = translation + project(velocity, 0.99);
  if (Math.abs(landing) < width * 0.4) return 0;
  return landing < 0 ? -1 : 1;
}
