/** Small JSON cache on the device so flashcards stay studyable offline. Never stores tokens. */
import AsyncStorage from '@react-native-async-storage/async-storage';

export async function cached<T>(key: string, load: () => Promise<T>): Promise<{ value: T | null; offline: boolean }> {
  try {
    const value = await load();
    await AsyncStorage.setItem(`cache:${key}`, JSON.stringify(value));
    return { value, offline: false };
  } catch (error) {
    if ((error as { status?: number }).status && (error as { status: number }).status !== 0) throw error;   // a real API answer, not offline
    const raw = await AsyncStorage.getItem(`cache:${key}`);
    if (raw === null) throw error;
    return { value: JSON.parse(raw) as T, offline: true };
  }
}

export async function clearCache(): Promise<void> {
  const keys = (await AsyncStorage.getAllKeys()).filter(k => k.startsWith('cache:'));
  await AsyncStorage.multiRemove(keys);
}
