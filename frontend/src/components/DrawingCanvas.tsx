import { useRef } from 'react';
import { Excalidraw, MainMenu, exportToBlob } from '@excalidraw/excalidraw';
import '@excalidraw/excalidraw/index.css';

export interface DrawingSnapshot { image: string; scene: Record<string, unknown> }
interface Props { onReady: (snapshot: () => Promise<DrawingSnapshot>) => void; onDirty?: () => void; disabled?: boolean }

export default function DrawingCanvas({ onReady, onDirty, disabled }: Props) {
  const revision = useRef('');
  return <Excalidraw excalidrawAPI={value => {
    onReady(async () => {
      const elements = value.getSceneElements().filter(e => !e.isDeleted);
      if (!elements.length) throw new Error('Add a drawing before submitting.');
      if (elements.some(e => ['image', 'embeddable', 'iframe'].includes(e.type) || e.link))
        throw new Error('Use shapes, arrows and text only. Remove images and links.');
      const blob = await exportToBlob({ elements, appState: { ...value.getAppState(), exportBackground: true, viewBackgroundColor: '#ffffff' },
        files: {}, mimeType: 'image/png', maxWidthOrHeight: 1400 });
      if (blob.size > 1_000_000) throw new Error('This drawing is too large. Simplify it before submitting.');
      const image = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = reject; reader.readAsDataURL(blob);
      });
      return { image, scene: { type: 'excalidraw', version: 2, source: 'PreparationPalAI', elements, appState: { viewBackgroundColor: '#ffffff' }, files: {} } };
    });
  }} onChange={elements => {
    const next = elements.map(element => `${element.id}:${element.version}:${element.isDeleted}`).join('|');
    if (next !== revision.current) { revision.current = next; onDirty?.(); }
  }} theme="light" viewModeEnabled={disabled} handleKeyboardGlobally={false} autoFocus={false} aiEnabled={false}
    initialData={{ appState: { viewBackgroundColor: '#ffffff' } }}
    onPaste={() => false} validateEmbeddable={() => false}
    UIOptions={{ tools: { image: false }, canvasActions: { loadScene: false, export: false, saveToActiveFile: false, saveAsImage: false } }}>
    <MainMenu><MainMenu.DefaultItems.ClearCanvas /><MainMenu.DefaultItems.ChangeCanvasBackground /><MainMenu.DefaultItems.Help /></MainMenu>
  </Excalidraw>;
}
