import { useEffect, useState } from 'react';
import { ApiError, api, progressStream } from './api';
import type { Job } from './types';

export function useJob(jobId: string | null, onTerminal?: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null);
  useEffect(() => {
    if (!jobId) {
      setJob(null);
      return;
    }
    let stopped = false;
    let terminal = false;
    let after = 0;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const refresh = async () => {
      const next = await api<Job>(`/jobs/${jobId}`, { signal: controller.signal });
      if (stopped) return;
      setJob(next);
      if (['succeeded', 'failed', 'cancelled'].includes(next.status) && !terminal) {
        terminal = true;
        onTerminal?.(next);
      }
    };
    const reconnect = async () => {
      try {
        await refresh();
        if (terminal || stopped) return;
        await progressStream(jobId, after, controller.signal, (id) => {
          after = id;
          void refresh().catch(() => {});
        });
      } catch (error) {
        if (error instanceof ApiError && error.status === 410) {
          const current = await api<Job>(`/jobs/${jobId}`, { signal: controller.signal });
          after = current.last_event_id;
          await refresh();
        }
      }
      if (!stopped && !terminal) timer = setTimeout(reconnect, 1500);
    };
    setJob(null);
    void reconnect();
    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
    };
    // The durable job ID owns this subscription; callbacks read current state through their caller.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);
  return job;
}
