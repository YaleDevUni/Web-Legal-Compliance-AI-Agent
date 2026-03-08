import { ChatPanel } from './components/ChatPanel';
import { CitationPanel } from './components/CitationPanel';
import { useChat } from './hooks/useChat';

function App() {
  const {
    history,
    streamingAnswer,
    currentCitations,
    activeCitationId,
    setActiveCitationId,
    loading,
    error,
    ask,
    resetSession,
  } = useChat();

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
            loading={loading}
            citations={currentCitations}
            activeCitationId={activeCitationId}
            onCitationClick={setActiveCitationId}
            onSend={ask}
            onReset={resetSession}
          />
        </div>

        {/* 오른쪽: 인용 (30%) */}
        <div className="flex-3 min-w-75 h-full hidden lg:block">
          <CitationPanel
            citations={currentCitations}
            activeCitationId={activeCitationId}
            onCitationClick={setActiveCitationId}
          />
        </div>
      </main>
    </div>
  );
}

export default App;
