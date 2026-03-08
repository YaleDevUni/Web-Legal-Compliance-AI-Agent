import { useState } from 'react';
import type { AnalyzeRequest } from '../types';

interface Props {
  onSubmit: (req: AnalyzeRequest) => void;
  loading: boolean;
}

type TabId = 'text' | 'url' | 'file';

export function InputPanel({ onSubmit, loading }: Props) {
  const [tab, setTab] = useState<TabId>('text');
  const [codeText, setCodeText] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [fileText, setFileText] = useState('');
  const [fileName, setFileName] = useState('');
  const [parseStatus, setParseStatus] = useState('');

  const tabs: { id: TabId; label: string }[] = [
    { id: 'text', label: '💬 코드/텍스트' },
    { id: 'url', label: '🌐 URL' },
    { id: 'file', label: '📄 파일/ZIP' },
  ];

  async function handleParseUrl() {
    if (!urlInput.trim()) return;
    setParseStatus('파싱 중...');
    try {
      const res = await fetch('/api/parse-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: urlInput }),
      });
      if (!res.ok) {
        const err = await res.json();
        setParseStatus(`오류: ${err.detail}`);
        return;
      }
      const data = await res.json();
      setParseStatus(`파싱 완료 — ${data.char_count.toLocaleString()}자 (서브페이지 ${data.subpage_count}개)`);
    } catch (e) {
      setParseStatus(`오류: ${(e as Error).message}`);
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    const form = new FormData();
    form.append('file', file);
    setParseStatus('파일 파싱 중...');
    try {
      const res = await fetch('/api/parse-file', { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json();
        setParseStatus(`오류: ${err.detail}`);
        return;
      }
      const data = await res.json();
      setFileText(data.combined);
      setParseStatus(`파싱 완료 — ${data.char_count.toLocaleString()}자`);
    } catch (e) {
      setParseStatus(`오류: ${(e as Error).message}`);
    }
  }

  function handleSubmit() {
    if (tab === 'text') {
      onSubmit({ code_text: codeText });
    } else if (tab === 'url') {
      onSubmit({ code_text: urlInput, url: urlInput });
    } else {
      onSubmit({ code_text: fileText });
    }
  }

  const canSubmit =
    !loading &&
    ((tab === 'text' && codeText.trim()) ||
      (tab === 'url' && urlInput.trim()) ||
      (tab === 'file' && fileText));

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      {/* 탭 헤더 */}
      <div className="flex border-b border-slate-200">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors ${
              tab === t.id
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="p-4 space-y-3">
        {tab === 'text' && (
          <textarea
            value={codeText}
            onChange={(e) => setCodeText(e.target.value)}
            rows={10}
            placeholder="코드 또는 텍스트를 직접 붙여넣기"
            className="w-full rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-y"
          />
        )}

        {tab === 'url' && (
          <div className="space-y-2">
            <div className="flex gap-2">
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleParseUrl()}
                placeholder="https://example.com"
                className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              <button
                onClick={handleParseUrl}
                className="rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-600 hover:bg-slate-200"
              >
                파싱
              </button>
            </div>
            {parseStatus && (
              <p className={`text-xs ${parseStatus.startsWith('오류') ? 'text-red-500' : 'text-green-600'}`}>
                {parseStatus}
              </p>
            )}
          </div>
        )}

        {tab === 'file' && (
          <div className="space-y-2">
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500 hover:border-blue-400 hover:text-blue-500 transition-colors">
              <span>📁 파일 선택 (.py .html .js .ts .txt .zip)</span>
              <input
                type="file"
                accept=".py,.html,.htm,.js,.css,.ts,.txt,.zip"
                onChange={handleFileUpload}
                className="hidden"
              />
            </label>
            {fileName && (
              <p className={`text-xs ${parseStatus.startsWith('오류') ? 'text-red-500' : 'text-green-600'}`}>
                {fileName} — {parseStatus}
              </p>
            )}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40 transition-colors"
        >
          {loading ? '⏳ 분석 중...' : '🔍 준수 여부 분석'}
        </button>
      </div>
    </div>
  );
}
