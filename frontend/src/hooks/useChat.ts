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
  const [currentCitations, setCurrentCitations] = useState<Citation[]>([]);
  const [activeCitationId, setActiveCitationId] = useState<string | null>(null);
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 스트림이 끝나고 history 갱신을 기다리는 중인지 표시
  const [awaitingHistory, setAwaitingHistory] = useState(false);

  // ask() 호출 전의 history 길이를 기억 (새 메시지 도착 감지용)
  const prevHistoryLenRef = useRef(0);
  // 항상 최신 history를 참조 (useCallback 클로저 stale 방지)
  const historyRef = useRef<Message[]>([]);

  // 대화 내역 조회
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

  historyRef.current = history;

  // history가 갱신되면 스트리밍 표시 상태 해제
  useEffect(() => {
    if (!awaitingHistory) return;
    // ask() 시작 전보다 history가 늘어났으면 서버가 새 대화를 확정한 것
    if (history.length > prevHistoryLenRef.current) {
      setStreamingAnswer('');
      setPendingUserMessage(null);
      setLoading(false);
      setAwaitingHistory(false);
    }
  }, [history, awaitingHistory]);

  // 세션 초기화
  const resetSession = useCallback(() => {
    localStorage.removeItem(SESSION_KEY);
    setSessionId('');
    queryClient.setQueryData(['chatHistory', ''], []);
    setCurrentCitations([]);
    setActiveCitationId(null);
    setStreamingAnswer('');
    setPendingUserMessage(null);
    setAwaitingHistory(false);
  }, [queryClient]);

  // 질문 전송 (SSE)
  const ask = useCallback(async (question: string) => {
    // ask 시작 전 history 길이 기록
    prevHistoryLenRef.current = historyRef.current.length;

    setLoading(true);
    setError(null);
    setStreamingAnswer('');
    setActiveCitationId(null);
    setPendingUserMessage(question); // 질문 즉시 표시

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
        });
      }

      // 스트림 종료: history 갱신을 트리거하고 useEffect가 완료를 처리
      if (resolvedSessionId) {
        void queryClient.invalidateQueries({
          queryKey: ['chatHistory', resolvedSessionId],
        });
      }
      setAwaitingHistory(true);
      // loading / streamingAnswer / pendingUserMessage는 history 갱신 후 useEffect에서 해제
    } catch (e: any) {
      setError(e.message);
      setStreamingAnswer('');
      setPendingUserMessage(null);
      setLoading(false);
    }
  }, [sessionId, queryClient]);

  // displayHistory: pendingUserMessage는 history에 아직 없을 때만 추가
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
