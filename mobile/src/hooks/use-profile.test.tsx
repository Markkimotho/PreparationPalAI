import AsyncStorage from '@react-native-async-storage/async-storage';
import { act, render, screen, waitFor } from '@testing-library/react-native';
import { Text } from 'react-native';

jest.mock('@/utils/api', () => ({ getJson: jest.fn(), putJson: jest.fn() }));
import { getJson, putJson } from '@/utils/api';
import { DEFAULT_PROFILE, ProfileProvider, useAccent, useProfile } from './use-profile';

const SERVER = { ...DEFAULT_PROFILE, display_name: 'Amani', accent: 'green', onboarded: true, updated_at: 'x' };
let exposed: ReturnType<typeof useProfile>;
function Probe() {
  exposed = useProfile();
  const accent = useAccent();
  return <Text>{`${exposed.status}|${exposed.profile.display_name}|${accent}`}</Text>;
}

beforeEach(async () => { jest.clearAllMocks(); await AsyncStorage.clear(); });
const api = (profile: object) => (getJson as jest.Mock).mockImplementation(async (path: string) => path === '/api/profile' ? profile : { workspace: 'u-x' });

test('loads the profile, exposes the accent and keeps a copy for offline', async () => {
  api(SERVER);
  await render(<ProfileProvider><Probe /></ProfileProvider>);
  await waitFor(() => expect(screen.getByText('ready|Amani|green')).toBeTruthy());
  expect(JSON.parse((await AsyncStorage.getItem('cache:profile'))!).display_name).toBe('Amani');
  expect(exposed.workspace).toBe('u-x');
});

test('offline, the saved copy keeps the app personal', async () => {
  await AsyncStorage.setItem('cache:profile', JSON.stringify(SERVER));
  (getJson as jest.Mock).mockRejectedValue(new TypeError('Network request failed'));
  await render(<ProfileProvider><Probe /></ProfileProvider>);
  await waitFor(() => expect(screen.getByText('ready|Amani|green')).toBeTruthy());
});

test('offline with nothing saved, the app still opens (unavailable, defaults)', async () => {
  (getJson as jest.Mock).mockRejectedValue(new TypeError('Network request failed'));
  await render(<ProfileProvider><Probe /></ProfileProvider>);
  await waitFor(() => expect(screen.getByText('unavailable||blue')).toBeTruthy());
});

test('saving changes at once, and a refused save rolls back', async () => {
  api(SERVER);
  await render(<ProfileProvider><Probe /></ProfileProvider>);
  await waitFor(() => expect(screen.getByText('ready|Amani|green')).toBeTruthy());
  (putJson as jest.Mock).mockResolvedValueOnce({ ...SERVER, accent: 'coral' });
  await act(() => exposed.save({ accent: 'coral' }));
  expect(screen.getByText('ready|Amani|coral')).toBeTruthy();
  expect((putJson as jest.Mock).mock.calls[0]).toEqual(['/api/profile', expect.objectContaining({ accent: 'coral', display_name: 'Amani' })]);
  (putJson as jest.Mock).mockRejectedValueOnce(new Error('Invalid'));
  await act(async () => { await expect(exposed.save({ accent: 'amber' })).rejects.toThrow('Invalid'); });
  expect(screen.getByText('ready|Amani|coral')).toBeTruthy();
});

test('outside a signed-in session it falls back to defaults instead of throwing', async () => {
  await render(<Probe />);
  expect(screen.getByText('unavailable||blue')).toBeTruthy();
});
