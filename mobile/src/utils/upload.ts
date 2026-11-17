/** Pick a PDF or image and queue it for the learner's notes (the server extracts and indexes it). */
import * as DocumentPicker from 'expo-document-picker';

import { request } from './api';

export async function pickAndUpload(): Promise<number> {
  const picked = await DocumentPicker.getDocumentAsync({ type: ['application/pdf', 'image/*'], copyToCacheDirectory: true, multiple: false });
  if (picked.canceled || !picked.assets?.length) return 0;
  const form = new FormData();
  for (const asset of picked.assets) {
    form.append('files', { uri: asset.uri, name: asset.name, type: asset.mimeType ?? 'application/octet-stream' } as unknown as Blob);
  }
  const result = await request<{ jobs: unknown[] }>('/api/kb/jobs/upload', { method: 'POST', body: form });
  return result.jobs.length;
}
