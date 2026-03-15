import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { Message, Citation, ChatContentEvent, ChatCitationsEvent } from '../types';

const SESSION_KEY = 'legal_ai_session_id';

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

export function useChat() {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<string>(() => {
    return localStorage.getItem(SESSION_KEY) || '';
  });

  const [streamingAnswer, setStreamingAnswer] = useState('');
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([]);
  const [activeCitationId, setActiveCitationId] = useState<string | null>(null);
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [relatedArticleIds, setRelatedArticleIds] = useState<string[]>([]);
  const [relatedCitations, setRelatedCitations] = useState<Citation[]>([]);
  const [hasInteracted, setHasInteracted] = useState(false);
  const prevHistoryLenRef = useRef(0);
  const historyRef = useRef<Message[]>([]);

  // 대화 내역 (백엔드 세션 히스토리)
  const { data: history = [] } = useQuery({
    queryKey: ['chatHistory', sessionId],
    queryFn: async () => {
      if (!sessionId) return [];
      const res = await fetch(`/api/sessions/${sessionId}/history`);
      if (!res.ok) return [];
      return res.json() as Promise<Message[]>;
    },
    enabled: !!sessionId,
  });

  // 전체 세션 통합 citations — history의 각 assistant 메시지에서 파생
  const sessionCitations = useMemo<Citation[]>(() => {
    const seen = new Set<string>();
    const result: Citation[] = [];
    for (const msg of history) {
      if (msg.role === 'assistant' && msg.citations) {
        for (const c of msg.citations) {
          if (!seen.has(c.article_id)) {
            seen.add(c.article_id);
            result.push(c);
          }
        }
      }
    }
    return result;
  }, [history]);

  historyRef.current = history;

  useEffect(() => {
    if (!pendingUserMessage) return;
    if (history.length > prevHistoryLenRef.current + 1) {
      setStreamingAnswer('');
      setStreamingCitations([]);
      setPendingUserMessage(null);
    }
  }, [history, pendingUserMessage]);

  const resetSession = useCallback(() => {
    localStorage.removeItem(SESSION_KEY);
    queryClient.removeQueries({ queryKey: ['chatHistory', sessionId] });
    setSessionId('');
    setActiveCitationId(null);
    setStreamingAnswer('');
    setStreamingCitations([]);
    setPendingUserMessage(null);
    setRelatedArticleIds([]);
    setRelatedCitations([]);
  }, [queryClient, sessionId]);

  const ask = useCallback(async (question: string) => {
    prevHistoryLenRef.current = historyRef.current.length;

    // ask() 시점의 누적 citation 수를 캡처 (이번 턴 offset)
    const citationOffset = sessionCitations.length;

    setHasInteracted(true);
    setLoading(true);
    setError(null);
    setStreamingAnswer('');
    setStreamingCitations([]);
    setActiveCitationId(null);
    setPendingUserMessage(question);

    let resolvedSessionId = sessionId;

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          session_id: sessionId || undefined,
          citation_offset: citationOffset,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        buffer = parseSseChunk(buffer, (event, data) => {
          const payload = JSON.parse(data);
          if (event === 'content') {
            const ev = payload as ChatContentEvent;
            setStreamingAnswer((prev) => prev + ev.text);
          } else if (event === 'citations') {
            const ev = payload as ChatCitationsEvent;

            // 1. 현재 Turn의 인용구 저장 (스트리밍 버블용)
            if (ev.citations && ev.citations.length > 0) {
              setStreamingCitations(ev.citations);
            }

            // 2. 관련 조문(그래프 확장) 누적
            if (ev.related_citations && ev.related_citations.length > 0) {
              setRelatedCitations((prev) => {
                const seen = new Set(prev.map((c) => c.article_id));
                const next = ev.related_citations!.filter((c) => !seen.has(c.article_id));
                return next.length > 0 ? [...prev, ...next] : prev;
              });
            }
            if (ev.related_articles) {
              setRelatedArticleIds((prev) => Array.from(new Set([...prev, ...ev.related_articles])));
            }

            if (!sessionId) {
              resolvedSessionId = ev.session_id;
              setSessionId(ev.session_id);
              localStorage.setItem(SESSION_KEY, ev.session_id);
            }
          } else if (event === 'error') {
            setError(payload.message);
          }
        });
      }

      setLoading(false);

      if (resolvedSessionId) {
        void queryClient.invalidateQueries({
          queryKey: ['chatHistory', resolvedSessionId],
        });
      }
    } catch (e: any) {
      setError(e.message);
      setStreamingAnswer('');
      setStreamingCitations([]);
      setPendingUserMessage(null);
      setLoading(false);
    }
  }, [sessionId, sessionCitations.length, queryClient]);

  const userInHistory = pendingUserMessage
    ? history.some((m) => m.role === 'user' && m.content === pendingUserMessage)
    : false;
  const displayHistory: Message[] = pendingUserMessage && !userInHistory
    ? [...history, { role: 'user', content: pendingUserMessage }]
    : history;

  return {
    sessionId,
    history: displayHistory,
    streamingAnswer,
    streamingCitations,
    citations: hasInteracted ? sessionCitations : [],
    relatedCitations,
    activeCitationId,
    setActiveCitationId,
    relatedArticleIds,
    loading,
    error,
    ask,
    resetSession,
  };
}
