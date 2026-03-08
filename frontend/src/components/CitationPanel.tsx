import React from 'react';
import type { Citation } from '../types';

interface CitationPanelProps {
  citations: Citation[];
}

export const CitationPanel: React.FC<CitationPanelProps> = ({ citations }) => {
  return (
    <div className="flex flex-col h-full bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50">
        <h2 className="font-semibold text-slate-700">📑 관련 근거</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {citations.length === 0 ? (
          <div className="text-center py-10 text-slate-400">
            <p className="text-sm">답변에 인용된 법령이나 판례가<br/>이곳에 표시됩니다.</p>
          </div>
        ) : (
          citations.map((c) => (
            <div 
              key={c.article_id}
              className="p-4 border border-slate-100 rounded-lg bg-white shadow-sm hover:border-blue-200 transition-all group"
            >
              <div className="flex justify-between items-start mb-2">
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                  c.article_id.startsWith('CASE_') 
                    ? 'bg-purple-50 text-purple-600 border border-purple-100' 
                    : 'bg-blue-50 text-blue-600 border border-blue-100'
                }`}>
                  {c.article_id.startsWith('CASE_') ? '판례' : '법령'}
                </span>
                <a 
                  href={c.url} 
                  target="_blank" 
                  rel="noreferrer"
                  className="text-[10px] text-slate-400 hover:text-blue-500 underline decoration-slate-200 underline-offset-2"
                >
                  상세보기
                </a>
              </div>

              <h3 className="text-sm font-bold text-slate-800 mb-1 leading-tight">
                {c.article_id.startsWith('CASE_') 
                  ? `${c.court || ''} ${c.case_number}`
                  : `${c.law_name} ${c.article_number}`}
              </h3>
              
              <p className="text-[11px] text-slate-400 mb-2">
                {c.article_id.startsWith('CASE_') 
                  ? `선고일: ${c.decision_date?.split('T')[0] || c.updated_at.split('T')[0]}`
                  : `시행일: ${c.updated_at.split('T')[0]}`}
              </p>

              {c.article_content && (
                <div className="text-xs text-slate-600 bg-slate-50/50 p-2 rounded border border-slate-50 leading-relaxed max-h-32 overflow-y-auto whitespace-pre-wrap">
                  {c.article_content}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
