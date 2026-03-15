import { useMemo } from 'react';
import { ChatPanel } from './components/ChatPanel';
import { CitationPanel } from './components/CitationPanel';
import LawGraphView from './components/LawGraphView';
import { useChat } from './hooks/useChat';

function App() {
  const {
    history,
    streamingAnswer,
    streamingCitations,
    citations,
    relatedCitations,
    activeCitationId,
    setActiveCitationId,
    relatedArticleIds,
    loading,
    error,
    ask,
    resetSession,
  } = useChat();

  // 현재 인용된 조문 ID 목록 추출 (useMemo를 통해 참조값 유지)
  const citedArticleIds = useMemo(() => citations.map(c => c.article_id), [citations]);

  return (
    <div className="flex flex-col h-screen bg-slate-50 overflow-hidden">
      {/* 헤더 */}
      <header className="flex-none border-b border-slate-200 bg-white shadow-sm z-10">
        <div className="mx-auto max-w-7xl px-4 py-3 flex justify-between items-center">
          <div>
            <h1 className="text-lg font-bold text-slate-800 flex items-center gap-2">
              <span className="text-blue-600">🏠</span> 부동산 법률 AI 상담사
            </h1>
            <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Real Estate Legal Reasoning Agent</p>
          </div>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded-full">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              Service Online
            </span>
          </div>
        </div>
      </header>

      {/* 메인 레이아웃: 2컬럼 */}
      <main className="flex-1 flex overflow-hidden mx-auto max-w-7xl w-full p-4 gap-4">
        {/* 왼쪽: 채팅 (70%) */}
        <div className="flex-[7] min-w-0 h-full flex flex-col">
          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-700 flex justify-between items-center animate-in fade-in slide-in-from-top-2">
              <span>오류가 발생했습니다: {error}</span>
              <button onClick={() => window.location.reload()} className="text-xs font-bold hover:underline">새로고침</button>
            </div>
          )}
          <ChatPanel
            history={history}
            streamingAnswer={streamingAnswer}
            streamingCitations={streamingCitations}
            loading={loading}
            citations={citations}
            activeCitationId={activeCitationId}
            onCitationClick={setActiveCitationId}
            onSend={ask}
            onReset={resetSession}
          />
        </div>

        {/* 오른쪽: 인용 (30%) + 그래프 */}
        <div className="flex-[3] min-w-[300px] h-full hidden lg:flex flex-col gap-4 overflow-hidden">
          {/* 지식 그래프 뷰 */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-3 flex flex-col overflow-hidden h-[300px]">
            <h3 className="text-[11px] font-bold text-slate-500 mb-2 uppercase tracking-wider flex items-center gap-2">
              <span className="text-blue-500 text-sm">🕸️</span> 연관 법령망 (Citation Graph)
            </h3>
            <div className="flex-1 min-h-0 bg-slate-50 rounded-lg overflow-hidden border border-slate-100">
              <LawGraphView 
                citedArticleIds={citedArticleIds}
                relatedArticleIds={relatedArticleIds}
                onNodeClick={setActiveCitationId}
                width={320} 
                height={250}
              />
            </div>
            <div className="mt-2 flex items-center justify-between">
              <div className="flex gap-2 text-[9px]">
                <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 bg-red-500 rounded-full"></span>인용됨</span>
                <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 bg-amber-400 rounded-full"></span>참조됨</span>
              </div>
              <p className="text-[10px] text-slate-400">노드 클릭 시 조문 확인</p>
            </div>
          </div>
          
          {/* 인용 패널 */}
          <div className="flex-1 min-h-0 overflow-hidden">
            <CitationPanel
              citations={citations}
              relatedCitations={relatedCitations}
              activeCitationId={activeCitationId}
              onCitationClick={setActiveCitationId}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
