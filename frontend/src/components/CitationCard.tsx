import { useState } from 'react';
import type { Citation } from '../types';

interface Props {
  citation: Citation;
}

export function CitationCard({ citation }: Props) {
  const [expanded, setExpanded] = useState(false);
  const shortSha = citation.sha256.slice(0, 8);
  const date = citation.updated_at.split('T')[0];

  return (
    <div className="mt-2 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="font-medium text-slate-700">
          📚 {citation.law_name} {citation.article_number}
        </span>
        <span className="text-xs text-slate-400 font-mono">sha:{shortSha}</span>
        <span className="text-xs text-slate-400">{date}</span>
        <a
          href={citation.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-500 hover:underline"
        >
          원문 링크 →
        </a>
      </div>
      {citation.article_content && (
        <div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-1 text-xs text-slate-400 hover:text-slate-600"
          >
            {expanded ? '▲ 조문 닫기' : '▼ 법령 조문 내용 보기'}
          </button>
          {expanded && (
            <p className="mt-1 whitespace-pre-wrap text-xs text-slate-500">
              {citation.article_content}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
