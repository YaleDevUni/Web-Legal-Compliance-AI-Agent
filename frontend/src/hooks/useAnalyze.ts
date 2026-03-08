import { useState, useCallback, useRef } from 'react';
import type { ComplianceReport, AnalyzeRequest } from '../types';

type AnalyzeState = {
  reports: ComplianceReport[];
  loading: boolean;
  error: string | null;
  cached: boolean;
  done: boolean;
};

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
    // 이전 요청 중단
    abortRef.current?.abort();
    const abort = new AbortController();
    abortRef.current = abort;

    setState({ reports: [], loading: true, error: null, cached: false, done: false });

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: abort.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        let event = '';
        let data = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            event = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            data = line.slice(6).trim();
          } else if (line === '') {
            if (event && data) {
              handleEvent(event, data);
              event = '';
              data = '';
            }
          }
        }
      }
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') {
        setState((prev) => ({ ...prev, loading: false, error: (e as Error).message }));
      }
    }

    function handleEvent(event: string, data: string) {
      const payload = JSON.parse(data);
      if (event === 'cached') {
        setState((prev) => ({ ...prev, cached: true }));
      } else if (event === 'report') {
        setState((prev) => ({ ...prev, reports: [...prev.reports, payload as ComplianceReport] }));
      } else if (event === 'error') {
        setState((prev) => ({ ...prev, loading: false, error: payload.message }));
      } else if (event === 'done') {
        setState((prev) => ({ ...prev, loading: false, done: true }));
      }
    }
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setState((prev) => ({ ...prev, loading: false }));
  }, []);

  return { ...state, run, cancel };
}
