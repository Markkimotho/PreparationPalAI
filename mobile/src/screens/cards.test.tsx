import AsyncStorage from '@react-native-async-storage/async-storage';
import { fireEvent, render, screen } from '@testing-library/react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';

jest.mock('expo-router', () => ({
  Link: ({ children }: { children: React.ReactNode }) => children,
  useFocusEffect: (effect: () => void) => { require('react').useEffect(() => effect(), [effect]); },
}));
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

test('studying a deck: flip, answer with Got it and Still learning, see the tally, review only what is left', async () => {
  (getJson as jest.Mock).mockResolvedValueOnce(deck);
  const first = await render(<GestureHandlerRootView><DeckStudy id="d1" /></GestureHandlerRootView>);
  expect(await screen.findByText('What makes ATP?')).toBeTruthy();
  expect(screen.getByText('1 / 2')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Show answer' }));
  expect(screen.getByText('Mitochondria')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Got it' }));
  expect(screen.getByText('Plant energy?')).toBeTruthy();
  expect(screen.getByText('2 / 2')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Still learning' }));
  expect(screen.getByText('You know 1 of 2')).toBeTruthy();
  expect(screen.getByText('1 still learning')).toBeTruthy();
  expect(JSON.parse((await AsyncStorage.getItem('cache:mastery:d1'))!)).toEqual(['c1']);
  await fireEvent.press(screen.getByRole('button', { name: 'Review the 1 still learning' }));
  expect(screen.getByText('Plant energy?')).toBeTruthy();
  expect(screen.getByText('1 / 1')).toBeTruthy();
  await first.unmount();
  (getJson as jest.Mock).mockRejectedValueOnce(new TypeError('Network request failed'));
  await render(<GestureHandlerRootView><DeckStudy id="d1" /></GestureHandlerRootView>);
  expect(await screen.findByText(/Offline: studying the copy saved/)).toBeTruthy();
  expect(screen.getByText('What makes ATP?')).toBeTruthy();
});

test('deck tiles show how much of each deck is mastered', async () => {
  await AsyncStorage.setItem('cache:mastery:d1', JSON.stringify(['c1']));
  (getJson as jest.Mock).mockResolvedValue({ decks: [{ id: 'd1', name: 'Biology', card_count: 2 }, { id: 'd2', name: 'Empty one', card_count: 0 }] });
  await render(<Cards />);
  expect(await screen.findByText('1 of 2 mastered')).toBeTruthy();
  expect(screen.getByText('Empty deck')).toBeTruthy();
  expect(screen.getByRole('link', { name: 'Biology, 2 cards, 1 of 2 mastered' })).toBeTruthy();
});
