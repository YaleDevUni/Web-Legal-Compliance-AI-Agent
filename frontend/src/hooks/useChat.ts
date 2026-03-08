import { useState, useCallback } from 'react';
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
  const [currentCitations, setCurrentCitations] = useState<Citation[]>([]);
  const [activeCitationId, setActiveCitationId] = useState<string | null>(null);
  // 현재 진행 중인 사용자 질문 (즉시 UI 반영용)
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 대화 내역 조회
  const { data: history = [], refetch: refetchHistory } = useQuery({
    queryKey: ['chatHistory', sessionId],
    queryFn: async () => {
      if (!sessionId) return [];
      const res = await fetch(`/api/sessions/${sessionId}/history`);
      if (!res.ok) return [];
      return res.json() as Promise<Message[]>;
    },
    enabled: !!sessionId,
  });

  // 세션 초기화
  const resetSession = useCallback(() => {
    localStorage.removeItem(SESSION_KEY);
    setSessionId('');
    queryClient.setQueryData(['chatHistory', ''], []);
    setCurrentCitations([]);
    setActiveCitationId(null);
    setStreamingAnswer('');
    setPendingUserMessage(null);
  }, [queryClient]);

  // 질문 전송 (SSE)
  const ask = useCallback(async (question: string) => {
    setLoading(true);
    setError(null);
    setStreamingAnswer('');
    setActiveCitationId(null);
    // 사용자 메시지 즉시 표시
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
            setCurrentCitations(ev.citations);
            if (!sessionId) {
              resolvedSessionId = ev.session_id;
              setSessionId(ev.session_id);
              localStorage.setItem(SESSION_KEY, ev.session_id);
            }
          } else if (event === 'error') {
            setError(payload.message);
          }
          // done은 루프 밖에서 처리
        });
      }

      // 스트림 종료 후: history 갱신 → streamingAnswer + pendingUserMessage 제거
      if (resolvedSessionId) {
        await queryClient.fetchQuery({
          queryKey: ['chatHistory', resolvedSessionId],
          queryFn: async () => {
            const res = await fetch(`/api/sessions/${resolvedSessionId}/history`);
            if (!res.ok) return [];
            return res.json() as Message[];
          },
        });
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStreamingAnswer('');
      setPendingUserMessage(null);
      setLoading(false);
    }
  }, [sessionId, queryClient]);

  // history에 pendingUserMessage 병합 (서버 확정 전까지만)
  const displayHistory: Message[] = pendingUserMessage
    ? [...history, { role: 'user', content: pendingUserMessage }]
    : history;

  return {
    sessionId,
    history: displayHistory,
    streamingAnswer,
    currentCitations,
    activeCitationId,
    setActiveCitationId,
    loading,
    error,
    ask,
    resetSession,
  };
}
