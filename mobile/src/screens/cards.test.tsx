import AsyncStorage from '@react-native-async-storage/async-storage';
import { fireEvent, render, screen } from '@testing-library/react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';

jest.mock('expo-router', () => ({ Link: ({ children }: { children: React.ReactNode }) => children }));
jest.mock('@/utils/api', () => ({ getJson: jest.fn(), postJson: jest.fn() }));
import { getJson } from '@/utils/api';
import { Cards } from './cards';
import { DeckStudy } from './deck';

const deck = { id: 'd1', name: 'Biology', cards: [{ id: 'c1', front: 'What makes ATP?', back: 'Mitochondria' }, { id: 'c2', front: 'Plant energy?', back: 'Photosynthesis' }] };
beforeEach(async () => { jest.clearAllMocks(); await AsyncStorage.clear(); });

test('decks load and are saved for offline use', async () => {
  (getJson as jest.Mock).mockResolvedValue({ decks: [{ id: 'd1', name: 'Biology', card_count: 2 }] });
  await render(<Cards />);
  expect(await screen.findByText('Biology')).toBeTruthy();
  expect(JSON.parse((await AsyncStorage.getItem('cache:decks'))!).decks[0].name).toBe('Biology');
});

test('offline, the saved decks are shown with a note and new decks cannot be made', async () => {
  await AsyncStorage.setItem('cache:decks', JSON.stringify({ decks: [{ id: 'd1', name: 'Biology', card_count: 2 }] }));
  (getJson as jest.Mock).mockRejectedValue(new TypeError('Network request failed'));
  await render(<Cards />);
  expect(await screen.findByText(/You're offline/)).toBeTruthy();
  expect(screen.getByText('Biology')).toBeTruthy();
  await fireEvent.changeText(screen.getByLabelText('Make a deck from your notes about…'), 'Cells');
  expect(screen.getByRole('button', { name: 'Make 10 cards' })).toBeDisabled();
});

test('a real error from the server is shown, not hidden behind the cache', async () => {
  await AsyncStorage.setItem('cache:decks', JSON.stringify({ decks: [] }));
  (getJson as jest.Mock).mockRejectedValue(Object.assign(new Error('Sign in to continue.'), { status: 401 }));
  await render(<Cards />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Sign in to continue.');
});

test('studying a deck flips and moves between cards, and works offline from the saved copy', async () => {
  (getJson as jest.Mock).mockResolvedValueOnce(deck);
  const first = await render(<GestureHandlerRootView><DeckStudy id="d1" /></GestureHandlerRootView>);
  expect(await screen.findByText('What makes ATP?')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Show answer' }));
  expect(screen.getByText('Mitochondria')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Next' }));
  expect(screen.getByText('Plant energy?')).toBeTruthy();
  await first.unmount();
  (getJson as jest.Mock).mockRejectedValueOnce(new TypeError('Network request failed'));
  await render(<GestureHandlerRootView><DeckStudy id="d1" /></GestureHandlerRootView>);
  expect(await screen.findByText(/Offline: studying the copy saved/)).toBeTruthy();
  expect(screen.getByText('What makes ATP?')).toBeTruthy();
});
