import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import type { Message, Citation } from '../types';

interface ChatPanelProps {
  history: Message[];
  streamingAnswer: string;
  loading: boolean;
  citations: Citation[];
  activeCitationId: string | null;
  onCitationClick: (id: string) => void;
  onSend: (text: string) => void;
  onReset: () => void;
}

const CITE_RE = /^%%CITE:([^:]+):(\d+)%%$/;

/** citation 패턴을 특수 마커(인라인 코드)로 치환 — ReactMarkdown이 code로 파싱함
 *  **패턴** / *패턴* 등 마크다운 강조 안에 있어도 닫는 기호 밖에 마커를 붙여
 *  볼드/이탤릭이 깨지지 않게 한다.
 */
function injectCiteMarkers(
  text: string,
  patterns: Array<{ pattern: string; id: string; index: number }>
): string {
  let result = text;
  for (const p of patterns) {
    const esc = p.pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    // 1~3개 * 또는 _ 로 감싼 패턴 전체를 먼저 시도, 없으면 일반 텍스트 매칭
    result = result.replace(
      new RegExp(`(\\*{1,3}${esc}\\*{1,3}|_{1,3}${esc}_{1,3}|${esc})`, 'g'),
      `$1\`%%CITE:${p.id}:${p.index}%%\``
    );
  }
  return result;
}

/** assistant 답변용 Markdown 렌더러 (citation 마커 + MD 포맷 지원) */
function AssistantMarkdown({
  text,
  citations,
  activeCitationId,
  onCitationClick,
}: {
  text: string;
  citations: Citation[];
  activeCitationId: string | null;
  onCitationClick: (id: string) => void;
}) {
  const patterns = citations
    .map((c, i) => ({
      // 판례: LLM이 사건번호(예: "2024다123")로 언급 → case_number(=article_number) 매칭
      // 법령: "주택법 제1조" 형태 매칭
      pattern: c.article_id.startsWith('CASE_')
        ? c.article_number
        : `${c.law_name} ${c.article_number}`,
      id: c.article_id,
      index: i + 1,
    }))
    .sort((a, b) => b.pattern.length - a.pattern.length);

  const processed = patterns.length ? injectCiteMarkers(text, patterns) : text;

  const components: Components = {
    // citation 마커 처리 + 일반 인라인 코드 스타일
    code({ children, className }) {
      if (!className) {
        const str = String(children);
        const m = str.match(CITE_RE);
        if (m) {
          const [, id, idx] = m;
          const isActive = activeCitationId === id;
          return (
            <button
              onClick={() => onCitationClick(id)}
              className={`inline-flex items-center justify-center w-[18px] h-[18px] ml-0.5 text-[9px] font-bold rounded cursor-pointer align-super transition-colors ${
                isActive ? 'bg-blue-600 text-white' : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
              }`}
            >
              {idx}
            </button>
          );
        }
        return <code className="px-1 py-0.5 bg-slate-200 text-slate-700 rounded text-[11px] font-mono">{children}</code>;
      }
      // 펜스드 코드 블록
      return <code className={`${className} text-[11px]`}>{children}</code>;
    },
    p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
    h1: ({ children }) => <h1 className="text-base font-bold mb-1 mt-3 first:mt-0">{children}</h1>,
    h2: ({ children }) => <h2 className="text-sm font-bold mb-1 mt-3 first:mt-0">{children}</h2>,
    h3: ({ children }) => <h3 className="text-sm font-semibold mb-1 mt-2 first:mt-0">{children}</h3>,
    ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
    ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
    li: ({ children }) => <li className="leading-relaxed">{children}</li>,
    strong: ({ children }) => <strong className="font-bold">{children}</strong>,
    em: ({ children }) => <em className="italic">{children}</em>,
    blockquote: ({ children }) => (
      <blockquote className="border-l-2 border-slate-400 pl-3 my-2 text-slate-600 italic">{children}</blockquote>
    ),
    hr: () => <hr className="border-slate-300 my-2" />,
    a: ({ href, children }) => (
      <a href={href} target="_blank" rel="noreferrer" className="text-blue-600 underline underline-offset-2 hover:text-blue-800">
        {children}
      </a>
    ),
  };

  return (
    <div className="text-sm leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {processed}
      </ReactMarkdown>
    </div>
  );
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  history,
  streamingAnswer,
  loading,
  citations,
  activeCitationId,
  onCitationClick,
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
            <div
              className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-none'
                  : 'bg-slate-100 text-slate-800 rounded-tl-none'
              }`}
            >
              {msg.role === 'assistant' ? (
                <AssistantMarkdown
                  text={msg.content}
                  citations={citations}
                  activeCitationId={activeCitationId}
                  onCitationClick={onCitationClick}
                />
              ) : (
                <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              )}
            </div>
          </div>
        ))}

        {streamingAnswer && (
          <div className="flex justify-start">
            <div className="max-w-[85%] px-4 py-2.5 rounded-2xl text-sm bg-slate-100 text-slate-800 rounded-tl-none border-l-4 border-blue-400">
              <AssistantMarkdown
                text={streamingAnswer}
                citations={citations}
                activeCitationId={activeCitationId}
                onCitationClick={onCitationClick}
              />
              {loading && (
                <span className="inline-block w-1 h-4 mt-1 bg-blue-400 animate-pulse align-middle" />
              )}
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
