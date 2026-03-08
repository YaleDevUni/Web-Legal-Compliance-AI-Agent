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

const BRACKET_CITE_RE = /\[(\d+)\]/g;

/** assistant 답변용 Markdown 렌더러 */
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
  
  // [1] -> %%CITE:1%% 로 치환 (마크다운 파싱 전)
  // 볼드(**) 기호와 인접해도 파싱이 깨지지 않도록 백틱(`)으로 감싸 인라인 코드로 인식하게 함
  const processed = text.replace(BRACKET_CITE_RE, (_, p1) => {
    return `\`%%CITE:${p1}%%\``;
  });

  const components: Components = {
    // 인용 버튼 렌더러
    code({ children, className }) {
      if (!className) {
        const str = String(children);
        if (str.startsWith('%%CITE:') && str.endsWith('%%')) {
          const idx = parseInt(str.slice(7, -2));
          const citation = citations[idx - 1];
          const id = citation?.article_id;
          const isActive = id && activeCitationId === id;
          
          if (!id) return <span className="text-slate-400 text-[10px]">[{idx}]</span>;

          return (
            <button
              onClick={() => onCitationClick(id)}
              className={`inline-flex items-center justify-center min-w-[16px] h-[16px] px-1 mx-0.5 text-[9px] font-bold rounded cursor-pointer align-super transition-all ${
                isActive ? 'bg-blue-600 text-white shadow-sm scale-110' : 'bg-blue-50 text-blue-600 hover:bg-blue-100 border border-blue-200'
              }`}
            >
              {idx}
            </button>
          );
        }
        return <code className="px-1 py-0.5 bg-slate-100 text-slate-700 rounded text-[11px] font-mono">{children}</code>;
      }
      return <code className={`${className} text-[11px]`}>{children}</code>;
    },
    // 마크다운 기본 태그 스타일 정의 (볼드 누락 해결)
    p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
    strong: ({ children }) => <strong className="font-extrabold text-slate-900">{children}</strong>,
    em: ({ children }) => <em className="italic text-slate-800">{children}</em>,
    h1: ({ children }) => <h1 className="text-lg font-bold mb-2 mt-4 first:mt-0 text-slate-900 border-b pb-1">{children}</h1>,
    h2: ({ children }) => <h2 className="text-base font-bold mb-2 mt-4 first:mt-0 text-slate-800">{children}</h2>,
    h3: ({ children }) => <h3 className="text-sm font-bold mb-1 mt-3 first:mt-0 text-slate-800">{children}</h3>,
    ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
    ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
    li: ({ children }) => <li className="leading-relaxed">{children}</li>,
    blockquote: ({ children }) => (
      <blockquote className="border-l-4 border-slate-200 pl-4 py-1 my-3 text-slate-600 italic bg-slate-50/50 rounded-r">{children}</blockquote>
    ),
    hr: () => <hr className="border-slate-100 my-4" />,
    a: ({ href, children }) => (
      <a href={href} target="_blank" rel="noreferrer" className="text-blue-600 underline underline-offset-4 font-medium hover:text-blue-800">
        {children}
      </a>
    ),
  };

  return (
    <div className="text-sm leading-relaxed text-slate-800">
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
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [history, streamingAnswer]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    onSend(input);
    setInput('');
  };

  return (
    <div className="flex flex-col h-full bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100 flex justify-between items-center bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <h2 className="font-bold text-slate-800 text-sm flex items-center gap-2">
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
          법률 상담 어시스턴트
        </h2>
        <button
          onClick={onReset}
          className="text-[11px] font-semibold text-slate-400 hover:text-red-500 transition-colors bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100"
        >
          대화 초기화
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-8 scrollbar-thin scrollbar-thumb-slate-200">
        {history.length === 0 && !streamingAnswer && (
          <div className="text-center py-16">
            <div className="w-16 h-16 bg-blue-50 text-2xl rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-sm border border-blue-100/50">
              🏠
            </div>
            <p className="text-base font-bold text-slate-700">부동산 법률 상담을 시작합니다.</p>
            <p className="text-sm mt-3 text-slate-400 leading-relaxed max-w-[280px] mx-auto">
              궁금하신 법령이나 판례에 대해<br/>
              자유롭게 질문해 주세요.
            </p>
          </div>
        )}

        {history.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
            <div
              className={`max-w-[88%] px-5 py-3.5 rounded-2xl text-[14px] leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-none shadow-lg shadow-blue-100'
                  : 'bg-slate-50 text-slate-800 rounded-tl-none border border-slate-100'
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
                <p className="whitespace-pre-wrap">{msg.content}</p>
              )}
            </div>
          </div>
        ))}

        {streamingAnswer && (
          <div className="flex justify-start animate-in fade-in slide-in-from-bottom-1 duration-200">
            <div className="max-w-[88%] px-5 py-3.5 rounded-2xl text-[14px] leading-relaxed bg-slate-50 text-slate-800 rounded-tl-none border border-slate-100 border-l-4 border-l-blue-500 shadow-sm">
              <AssistantMarkdown
                text={streamingAnswer}
                citations={citations}
                activeCitationId={activeCitationId}
                onCitationClick={onCitationClick}
              />
              {loading && (
                <div className="flex gap-1 mt-2">
                  <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="p-5 bg-white border-t border-slate-100">
        <div className="flex gap-3 relative group">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            placeholder="부동산 법률에 대해 질문하세요..."
            className="flex-1 pl-5 pr-14 py-3.5 bg-slate-50 border border-slate-200 rounded-2xl focus:outline-none focus:ring-4 focus:ring-blue-500/5 focus:border-blue-500 focus:bg-white disabled:bg-slate-50 transition-all text-sm shadow-inner"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="absolute right-2 top-2 w-10 h-10 flex items-center justify-center bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 transition-all shadow-md active:scale-95"
          >
            {loading ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-7 20-4z" />
              </svg>
            )}
          </button>
        </div>
        <p className="text-[10px] text-slate-400 mt-3 text-center">AI 답변은 참고용이며 법적 효력을 갖지 않습니다.</p>
      </form>
    </div>
  );
};
