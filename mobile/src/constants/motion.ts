/**
 * Motion tokens. Values come from the animate-expo skill's tables (Emil Kowalski's curves and
 * Apple's spring parameters); nothing here is eyeballed. Never use ease-in on UI.
 */
import { Easing } from 'react-native-reanimated';

export const EASE_OUT = Easing.bezier(0.23, 1, 0.32, 1);        // entering, press feedback
export const EASE_IN_OUT = Easing.bezier(0.77, 0, 0.175, 1);    // moving on screen (card flip, indicator)
export const EASE_OUT_CSS = 'cubic-bezier(0.23, 1, 0.32, 1)';

export const SPRING_SETTLE = { duration: 400, dampingRatio: 1 } as const;     // no overshoot
export const SPRING_RELEASE = { duration: 400, dampingRatio: 0.8 } as const;  // after a drag; add velocity

export const PRESS_MS = 120;
export const SMALL_STATE_MS = 180;
export const FLIP_MS = 420;
