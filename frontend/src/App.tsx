import { InputPanel } from './components/InputPanel';
import { ResultsPanel } from './components/ResultsPanel';
import { useAnalyze } from './hooks/useAnalyze';

function App() {
  const { reports, loading, cached, done, error, run } = useAnalyze();

  return (
    <div className="min-h-screen bg-slate-50">
      {/* 헤더 */}
      <header className="border-b border-slate-200 bg-white shadow-sm">
        <div className="mx-auto max-w-5xl px-4 py-4">
          <h1 className="text-xl font-bold text-slate-800">⚖️ Web Legal Compliance AI Agent</h1>
          <p className="text-xs text-slate-400 mt-0.5">한국 개인정보·보안·서비스 규정 자동 준수 검사</p>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6 space-y-6">
        <InputPanel onSubmit={run} loading={loading} />

        {error && (
          <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            오류: {error}
          </div>
        )}

        <ResultsPanel reports={reports} loading={loading} cached={cached} done={done} />
      </main>
    </div>
  );
}

export default App;
