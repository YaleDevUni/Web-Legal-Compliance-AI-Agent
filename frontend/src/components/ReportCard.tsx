import { useState } from 'react';
import type { ComplianceReport } from '../types';
import { CitationCard } from './CitationCard';

interface Props {
  report: ComplianceReport;
}

const STATUS_CONFIG = {
  violation: {
    label: '위반',
    icon: '⚠️',
    border: 'border-red-300',
    bg: 'bg-red-50',
    badge: 'bg-red-100 text-red-700',
    header: 'text-red-800',
  },
  compliant: {
    label: '준수',
    icon: '✅',
    border: 'border-green-300',
    bg: 'bg-green-50',
    badge: 'bg-green-100 text-green-700',
    header: 'text-green-800',
  },
  unverifiable: {
    label: '확인 불가',
    icon: '🔍',
    border: 'border-slate-300',
    bg: 'bg-slate-50',
    badge: 'bg-slate-100 text-slate-600',
    header: 'text-slate-700',
  },
} as const;

export function ReportCard({ report }: Props) {
  const [open, setOpen] = useState(report.status === 'violation');
  const cfg = STATUS_CONFIG[report.status];

  return (
    <div className={`rounded-lg border ${cfg.border} ${cfg.bg} overflow-hidden`}>
      <button
        onClick={() => setOpen(!open)}
        className={`w-full px-4 py-3 flex items-start gap-2 text-left ${cfg.header}`}
      >
        <span className="text-base">{cfg.icon}</span>
        <span className={`text-xs font-semibold rounded px-1.5 py-0.5 ${cfg.badge} shrink-0 mt-0.5`}>
          {cfg.label}
        </span>
        <span className="flex-1 text-sm font-medium leading-snug">{report.description}</span>
        <span className="text-slate-400 text-xs mt-0.5">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-2">
          {report.source_location && (
            <div>
              <p className="text-xs font-semibold text-slate-500 mb-1">
                문제 코드 위치 (라인 {report.source_location.line_start}–{report.source_location.line_end})
              </p>
              <pre className="rounded bg-slate-800 text-slate-100 text-xs p-3 overflow-x-auto whitespace-pre-wrap">
                {report.source_location.snippet}
              </pre>
            </div>
          )}
          {!report.source_location && report.recommendation && (
            <div>
              <p className="text-xs font-semibold text-slate-500 mb-1">문제 코드</p>
              <pre className="rounded bg-slate-800 text-slate-100 text-xs p-3 overflow-x-auto whitespace-pre-wrap">
                {report.recommendation}
              </pre>
            </div>
          )}
          {report.citations.map((c) => (
            <CitationCard key={`${c.article_id}-${c.sha256}`} citation={c} />
          ))}
        </div>
      )}
    </div>
  );
}
