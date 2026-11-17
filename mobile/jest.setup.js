jest.mock('@react-native-async-storage/async-storage', () => require('@react-native-async-storage/async-storage/jest/async-storage-mock'));
jest.mock('expo/fetch', () => ({ fetch: (...args) => global.fetch(...args) }));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);
// Reanimated runs its web implementation under Jest via its resolver (package.json "jest.resolver").
jest.mock('expo-haptics', () => ({
  selectionAsync: jest.fn(async () => undefined), impactAsync: jest.fn(async () => undefined), notificationAsync: jest.fn(async () => undefined),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium' }, NotificationFeedbackType: { Success: 'success', Error: 'error' },
}));
