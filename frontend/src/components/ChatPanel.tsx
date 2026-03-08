import React, { useState, useRef, useEffect } from 'react';
import type { Message } from '../types';

interface ChatPanelProps {
  history: Message[];
  streamingAnswer: string;
  loading: boolean;
  onSend: (text: string) => void;
  onReset: () => void;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  history,
  streamingAnswer,
  loading,
  onSend,
  onReset,
}) => {
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history, streamingAnswer]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    onSend(input);
    setInput('');
  };

  return (
    <div className="flex flex-col h-full bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      {/* 헤더 */}
      <div className="px-4 py-3 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
        <h2 className="font-semibold text-slate-700">💬 법률 상담</h2>
        <button 
          onClick={onReset}
          className="text-xs text-slate-400 hover:text-red-500 transition-colors"
        >
          대화 초기화
        </button>
      </div>

      {/* 대화 내역 */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {history.length === 0 && !streamingAnswer && (
          <div className="text-center py-10 text-slate-400">
            <p className="text-sm">부동산 법률에 대해 궁금한 점을 물어보세요.</p>
            <p className="text-xs mt-1">예: 전세보증금을 제때 못 받으면 어떻게 하나요?</p>
          </div>
        )}

        {history.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm ${
              msg.role === 'user' 
                ? 'bg-blue-600 text-white rounded-tr-none' 
                : 'bg-slate-100 text-slate-800 rounded-tl-none'
            }`}>
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
            </div>
          </div>
        ))}

        {streamingAnswer && (
          <div className="flex justify-start">
            <div className="max-w-[85%] px-4 py-2.5 rounded-2xl text-sm bg-slate-100 text-slate-800 rounded-tl-none border-l-4 border-blue-400">
              <p className="whitespace-pre-wrap leading-relaxed">{streamingAnswer}</p>
              {loading && <span className="inline-block w-1 h-4 ml-1 bg-blue-400 animate-pulse align-middle" />}
            </div>
          </div>
        )}
      </div>

      {/* 입력창 */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-slate-100">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            placeholder="질문을 입력하세요..."
            className="flex-1 px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 disabled:bg-slate-50 transition-all text-sm"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors shadow-sm text-sm"
          >
            {loading ? '...' : '전송'}
          </button>
        </div>
      </form>
    </div>
  );
};
