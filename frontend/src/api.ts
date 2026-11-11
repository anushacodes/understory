let ownerToken = '';
export function setToken(value: string) { ownerToken = value.trim(); }

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message); }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/v1${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${ownerToken}`, ...options.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError('connection_failed', 'Cannot reach the local API. Start the API and database, then try again.', 503);
  }
  const body = await response.json();
  if (!response.ok) throw new ApiError(body.error?.code ?? 'request_failed', body.error?.message ?? 'Request failed. Please try again.', response.status);
  return body as T;
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify(body) });
}

export function params(values: Record<string, string | number | boolean | undefined | null>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) if (value !== undefined && value !== null && value !== '') query.set(key, String(value));
  return `?${query}`;
}

export async function progressStream(jobId: string, after: number, signal: AbortSignal, event: (id: number, kind: string) => void) {
  const response = await fetch(`/v1/jobs/${jobId}/events`, { signal, headers: { Authorization: `Bearer ${ownerToken}`, ...(after ? { 'Last-Event-ID': String(after) } : {}) } });
  if (response.status === 410) throw new ApiError('event_history_expired', 'Reload job state to resume progress.', 410);
  if (!response.ok || !response.body) throw new ApiError('progress_unavailable', 'Progress connection is unavailable.', response.status);
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
  try {
    while (true) {
      const result = await reader.read(); if (result.done) break;
      buffer += decoder.decode(result.value, { stream: true });
      let boundary: number;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
        const id = Number(block.match(/^id: (\d+)$/m)?.[1] ?? 0);
        const kind = block.match(/^event: (.+)$/m)?.[1] ?? 'progress';
        if (id > after) { after = id; event(id, kind); }
      }
    }
  } finally { reader.releaseLock(); }
}

export async function allPages<T>(path: string, signal?: AbortSignal): Promise<T[]> {
  const items: T[] = [];
  let cursor: string | null = null;
  do {
    const separator = path.includes('?') ? '&' : '?';
    const page: { items: T[]; next_cursor: string | null } = await api(path + separator + 'limit=100' + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''), { signal });
    items.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  return items;
}

export async function download(path: string, filename: string) {
  const body = await api(path);
  const url = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click();
  URL.revokeObjectURL(url);
}
