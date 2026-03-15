import React, { useRef, useEffect, useState } from 'react';
import type { Citation } from '../types';

interface CitationPanelProps {
  citations: Citation[];
  relatedCitations: Citation[];
  activeCitationId: string | null;
  onCitationClick: (id: string) => void;
}

function CitationCard({
  citation,
  index,
  isActive,
  onClick,
  cardRef,
}: {
  citation: Citation;
  index: number;
  isActive: boolean;
  onClick: () => void;
  cardRef: (el: HTMLDivElement | null) => void;
}) {
  const isCase = citation.article_id.startsWith('CASE_');
  return (
    <div
      ref={cardRef}
      onClick={onClick}
      className={`p-4 border rounded-lg bg-white shadow-sm cursor-pointer transition-all ${
        isActive
          ? 'border-blue-400 ring-2 ring-blue-200 bg-blue-50/40'
          : 'border-slate-100 hover:border-blue-200'
      }`}
    >
      <div className="flex justify-between items-start mb-2">
        <div className="flex items-center gap-1.5">
          <span
            className={`flex items-center justify-center w-5 h-5 rounded text-[10px] font-bold ${
              isActive ? 'bg-blue-600 text-white' : 'bg-blue-100 text-blue-700'
            }`}
          >
            {index}
          </span>
          <span
            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
              isCase
                ? 'bg-purple-50 text-purple-600 border border-purple-100'
                : 'bg-blue-50 text-blue-600 border border-blue-100'
            }`}
          >
            {isCase ? '판례' : '법령'}
          </span>
        </div>
        <a
          href={citation.url}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="text-[10px] text-slate-400 hover:text-blue-500 underline decoration-slate-200 underline-offset-2"
        >
          상세보기
        </a>
      </div>

      <h3 className="text-sm font-bold text-slate-800 mb-1 leading-tight">
        {isCase
          ? `${citation.court || ''} ${citation.case_number}`
          : `${citation.law_name} ${citation.article_number}`}
      </h3>

      <p className="text-[11px] text-slate-400 mb-2">
        {isCase
          ? `선고일: ${citation.decision_date?.split('T')[0] || citation.updated_at.split('T')[0]}`
          : `시행일: ${citation.updated_at.split('T')[0]}`}
      </p>

      {citation.article_content && (
        <div className="text-xs text-slate-600 bg-slate-50/50 p-2 rounded border border-slate-50 leading-relaxed max-h-32 overflow-y-auto whitespace-pre-wrap">
          {citation.article_content}
        </div>
      )}
    </div>
  );
}

export const CitationPanel: React.FC<CitationPanelProps> = ({
  citations,
  relatedCitations,
  activeCitationId,
  onCitationClick,
}) => {
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const [relatedOpen, setRelatedOpen] = useState(false);

  useEffect(() => {
    if (!activeCitationId) return;
    const el = cardRefs.current.get(activeCitationId);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [activeCitationId]);

  const setRef = (id: string) => (el: HTMLDivElement | null) => {
    if (el) cardRefs.current.set(id, el);
    else cardRefs.current.delete(id);
  };

  return (
    <div className="flex flex-col h-full bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      {/* 헤더 */}
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50">
        <h2 className="font-semibold text-slate-700 text-sm flex items-center gap-2">
          <span className="text-blue-500">📑</span> 근거 법령 / 판례
          {citations.length > 0 && (
            <span className="ml-auto text-[10px] font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded-full">
              {citations.length}
            </span>
          )}
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* 직접 인용 섹션 */}
        {citations.length === 0 ? (
          <div className="text-center py-10 text-slate-400">
            <p className="text-sm">
              답변에 인용된 법령이나 판례가
              <br />
              이곳에 표시됩니다.
            </p>
          </div>
        ) : (
          citations.map((c, i) => (
            <CitationCard
              key={c.article_id}
              citation={c}
              index={i + 1}
              isActive={activeCitationId === c.article_id}
              onClick={() => onCitationClick(c.article_id)}
              cardRef={setRef(c.article_id)}
            />
          ))
        )}

        {/* 연관 법령 섹션 */}
        {relatedCitations.length > 0 && (
          <div className="pt-2">
            <button
              onClick={() => setRelatedOpen((o) => !o)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-amber-50 border border-amber-100 text-[11px] font-bold text-amber-700 hover:bg-amber-100 transition-colors"
            >
              <span className="flex items-center gap-1.5">
                <span>🔗</span> 연관 법령
                <span className="bg-amber-200 text-amber-800 px-1.5 py-0.5 rounded-full text-[10px]">
                  {relatedCitations.length}
                </span>
              </span>
              <span className="text-amber-500">{relatedOpen ? '▲' : '▼'}</span>
            </button>

            {relatedOpen && (
              <div className="mt-3 space-y-2">
                {relatedCitations.map((c) => {
                  const isCase = c.article_id.startsWith('CASE_');
                  const isActive = activeCitationId === c.article_id;
                  return (
                    <div
                      key={c.article_id}
                      ref={setRef(c.article_id)}
                      onClick={() => onCitationClick(c.article_id)}
                      className={`px-3 py-2.5 border rounded-lg cursor-pointer transition-all ${
                        isActive
                          ? 'border-amber-400 ring-2 ring-amber-200 bg-amber-50/40'
                          : 'border-slate-100 hover:border-amber-200 bg-white'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span className="flex-none w-1.5 h-1.5 rounded-full bg-amber-400" />
                          <span
                            className={`flex-none px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${
                              isCase
                                ? 'bg-purple-50 text-purple-600 border border-purple-100'
                                : 'bg-amber-50 text-amber-700 border border-amber-100'
                            }`}
                          >
                            {isCase ? '판례' : '법령'}
                          </span>
                          <span className="text-xs font-semibold text-slate-700 truncate">
                            {isCase
                              ? `${c.court || ''} ${c.case_number}`
                              : `${c.law_name} ${c.article_number}`}
                          </span>
                        </div>
                        <a
                          href={c.url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="flex-none text-[10px] text-slate-400 hover:text-blue-500 underline underline-offset-2"
                        >
                          보기
                        </a>
                      </div>
                      {c.article_content && (
                        <p className="mt-1.5 text-[11px] text-slate-500 leading-relaxed line-clamp-2 pl-3">
                          {c.article_content}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
