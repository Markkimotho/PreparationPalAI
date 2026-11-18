/** Incremental Server-Sent Events parser: feed text as it arrives, get one JSON object per `data:` frame. */
export function createSseParser(onFrame: (frame: Record<string, unknown>) => void) {
  let buffer = '';
  return (chunk: string) => {
    buffer += chunk.replace(/\r/g, '');
    let end = buffer.indexOf('\n\n');
    while (end !== -1) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const data = block.split('\n').filter(l => l.startsWith('data:')).map(l => l.slice(5).trimStart()).join('\n');
      if (data) {
        try { onFrame(JSON.parse(data)); } catch { /* not JSON: ignore */ }
      }
      end = buffer.indexOf('\n\n');
    }
  };
}
