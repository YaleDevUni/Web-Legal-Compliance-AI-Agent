import { useState, useEffect, useRef, useCallback } from 'react';
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
  const [activeCitationId, setActiveCitationId] = useState<string | null>(null);
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [relatedArticleIds, setRelatedArticleIds] = useState<string[]>([]);
  const prevHistoryLenRef = useRef(0);
  const historyRef = useRef<Message[]>([]);

  // 대화 내역
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

  // 세션 citations
  const { data: citations = [] } = useQuery<Citation[]>({
    queryKey: ['citations', sessionId],
    queryFn: () => {
      if (!sessionId) return [];
      const stored = localStorage.getItem(`citations:${sessionId}`);
      return stored ? (JSON.parse(stored) as Citation[]) : [];
    },
    staleTime: Infinity,
    gcTime: Infinity,
  });

  historyRef.current = history;

  useEffect(() => {
    if (!pendingUserMessage) return;
    if (history.length > prevHistoryLenRef.current + 1) {
      setStreamingAnswer('');
      setPendingUserMessage(null);
    }
  }, [history, pendingUserMessage]);

  const resetSession = useCallback(() => {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(`citations:${sessionId}`);
    queryClient.removeQueries({ queryKey: ['chatHistory', sessionId] });
    queryClient.removeQueries({ queryKey: ['citations', sessionId] });
    setSessionId('');
    setActiveCitationId(null);
    setStreamingAnswer('');
    setPendingUserMessage(null);
    setRelatedArticleIds([]);
  }, [queryClient, sessionId]);

  const ask = useCallback(async (question: string) => {
    prevHistoryLenRef.current = historyRef.current.length;

    setLoading(true);
    setError(null);
    setStreamingAnswer('');
    setActiveCitationId(null);
    setPendingUserMessage(question);

    let resolvedSessionId = sessionId;

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, session_id: sessionId || undefined }),
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
            const sid = ev.session_id || resolvedSessionId;
            
            // 관련 조문 ID 업데이트
            if (ev.related_articles) {
              setRelatedArticleIds((prev) => Array.from(new Set([...prev, ...ev.related_articles])));
            }

            queryClient.setQueryData<Citation[]>(['citations', sid], (prev = []) => {
              const existingIds = new Set(prev.map((c) => c.article_id));
              const newOnes = ev.citations.filter((c) => !existingIds.has(c.article_id));
              if (newOnes.length === 0) return prev;
              const updated = [...prev, ...newOnes];
              localStorage.setItem(`citations:${sid}`, JSON.stringify(updated));
              return updated;
            });
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
      setPendingUserMessage(null);
      setLoading(false);
    }
  }, [sessionId, queryClient]);

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
    citations,
    activeCitationId,
    setActiveCitationId,
    relatedArticleIds,
    loading,
    error,
    ask,
    resetSession,
  };
}
