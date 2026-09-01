import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api/client";
import type { KBSource, IngestResponse, IngestionJob } from "../api/types";

interface KBState {
  jobs: IngestionJob[];
  count: number;
  sources: KBSource[];
  busy: boolean;
  refresh: () => Promise<void>;
  upload: (files: File[]) => Promise<string>;
  scrape: (topic: string, numResults?: number) => Promise<string>;
  clear: () => Promise<void>;
}

const KBContext = createContext<KBState | null>(null);

export function KnowledgeBaseProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [count, setCount] = useState(0);
  const [sources, setSources] = useState<KBSource[]>([]);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [{ count }, { sources }, queued] = await Promise.all([
        api.kbCount(),
        api.kbSources(),
        api.kbJobs(),
      ]);
      setCount(count);
      setSources(sources);
      setJobs(queued.jobs);
    } catch {
      /* leave previous state on transient failure */
    }
  }, []);

  const upload = useCallback(
    async (files: File[]) => {
      setBusy(true);
      try {
        const res = await finishIngestion(await api.kbUpload(files));
        await refresh();
        return res.detail || `Added ${res.chunks_added} chunks.`;
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  const scrape = useCallback(
    async (topic: string, numResults = 3) => {
      setBusy(true);
      try {
        const res = await finishIngestion(await api.kbScrape(topic, numResults));
        await refresh();
        return res.detail || `Added ${res.chunks_added} chunks.`;
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  const clear = useCallback(async () => {
    setBusy(true);
    try {
      await api.kbClear();
      await refresh();
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  const value = useMemo(
    () => ({ jobs, count, sources, busy: busy || jobs.some(j => j.state === 'pending' || j.state === 'running'), refresh, upload, scrape, clear }),
    [jobs, count, sources, busy, refresh, upload, scrape, clear],
  );

  return <KBContext.Provider value={value}>{children}</KBContext.Provider>;
}

async function finishIngestion(result: IngestResponse | { jobs: IngestionJob[] }): Promise<IngestResponse> {
  if (!('jobs' in result)) return result;
  let chunks = 0;
  for (const queued of result.jobs) {
    let complete = false;
    for (let attempt = 0; attempt < 600; attempt++) {
      const job = await api.kbJob(queued.id);
      if (job.state === 'failed') throw new Error(job.error || 'Ingestion failed. Retry from the jobs list.');
      if (job.state === 'completed') { chunks += job.result?.chunks_added ?? 0; complete = true; break; }
      await new Promise(resolve => window.setTimeout(resolve, 2000));
    }
    if (!complete) return { chunks_added: chunks, detail: 'Still processing. You can return later; your job is saved.' };
  }
  return { chunks_added: chunks, detail: `Added ${chunks} chunks.` };
}

export function useKnowledgeBase(): KBState {
  const ctx = useContext(KBContext);
  if (!ctx) throw new Error("useKnowledgeBase must be used within KnowledgeBaseProvider");
  return ctx;
}
