/**
 * Haptics, used sparingly: one per meaningful event (a step, a snap, a right or wrong answer),
 * always alongside a visual change, never per frame. Silent where the device has none.
 */
import * as Haptics from 'expo-haptics';

const safely = (fire: () => Promise<void>) => { fire().catch(() => undefined); };

export const haptics = {
  select: () => safely(() => Haptics.selectionAsync()),
  snap: () => safely(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light)),
  success: () => safely(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success)),
  error: () => safely(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error)),
};
