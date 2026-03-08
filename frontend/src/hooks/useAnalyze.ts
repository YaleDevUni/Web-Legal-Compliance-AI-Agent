import { useState, useCallback, useRef } from 'react';
import type { ComplianceReport, AnalyzeRequest } from '../types';

type AnalyzeState = {
  reports: ComplianceReport[];
  loading: boolean;
  error: string | null;
  cached: boolean;
  done: boolean;
};

function parseSseChunk(
  chunk: string,
  onEvent: (event: string, data: string) => void
): string {
  const lines = chunk.split('\n');
  const remaining = lines.pop() ?? '';
  let event = '';
  let data = '';
  for (const line of lines) {
    if (line.startsWith('event: ')) {
      event = line.slice(7).trim();
    } else if (line.startsWith('data: ')) {
      data = line.slice(6).trim();
    } else if (line === '' && event && data) {
      onEvent(event, data);
      event = '';
      data = '';
    }
  }
  return remaining;
}

export function useAnalyze() {
  const [state, setState] = useState<AnalyzeState>({
    reports: [],
    loading: false,
    error: null,
    cached: false,
    done: false,
  });

  const abortRef = useRef<AbortController | null>(null);

  const run = useCallback(async (request: AnalyzeRequest) => {
    abortRef.current?.abort();
    const abort = new AbortController();
    abortRef.current = abort;

    setState({ reports: [], loading: true, error: null, cached: false, done: false });

    try {
      // 1. job 등록 → job_id 즉시 수신
      const enqueueRes = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: abort.signal,
      });

      if (!enqueueRes.ok) {
        const err = await enqueueRes.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${enqueueRes.status}`);
      }

      const { job_id, cached } = await enqueueRes.json();
      if (cached) {
        setState((prev) => ({ ...prev, cached: true }));
      }

      // 2. SSE 구독으로 결과 수신
      const sseRes = await fetch(`/api/analyze/${job_id}/events`, {
        signal: abort.signal,
      });

      if (!sseRes.ok) throw new Error(`SSE HTTP ${sseRes.status}`);

      const reader = sseRes.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        buffer = parseSseChunk(buffer, handleEvent);
      }
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') {
        setState((prev) => ({ ...prev, loading: false, error: (e as Error).message }));
      }
    }

    function handleEvent(event: string, data: string) {
      const payload = JSON.parse(data);
      if (event === 'report') {
        setState((prev) => ({ ...prev, reports: [...prev.reports, payload as ComplianceReport] }));
      } else if (event === 'error') {
        setState((prev) => ({ ...prev, loading: false, error: payload.message }));
      } else if (event === 'done') {
        setState((prev) => ({ ...prev, loading: false, done: true, cached: payload.cached ?? prev.cached }));
      }
    }
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setState((prev) => ({ ...prev, loading: false }));
  }, []);

  return { ...state, run, cancel };
}
