import type { ComplianceReport } from '../types';
import { ReportCard } from './ReportCard';

interface Props {
  reports: ComplianceReport[];
  loading: boolean;
  cached: boolean;
  done: boolean;
}

export function ResultsPanel({ reports, loading, cached, done }: Props) {
  if (!loading && !done && reports.length === 0) return null;

  const violations = reports.filter((r) => r.status === 'violation');
  const compliant = reports.filter((r) => r.status === 'compliant');
  const unverifiable = reports.filter((r) => r.status === 'unverifiable');

  return (
    <div className="space-y-6">
      {/* 상태 배너 */}
      {loading && (
        <div className="flex items-center gap-2 rounded-lg bg-blue-50 px-4 py-3 text-sm text-blue-700">
          <span className="animate-spin">⏳</span> AI 에이전트 분석 중... (결과가 순차 표시됩니다)
        </div>
      )}
      {cached && (
        <div className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-700">
          ⚡ 캐시된 결과 (동일 URL 이전 분석)
        </div>
      )}
      {done && reports.length === 0 && (
        <div className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-500">
          분석 결과가 없습니다. 법령 관련 코드를 입력해주세요.
        </div>
      )}

      {/* 요약 메트릭 */}
      {reports.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          <MetricCard label="⚠️ 보완 필요" count={violations.length} color="text-red-600" />
          <MetricCard label="✅ 준수" count={compliant.length} color="text-green-600" />
          <MetricCard label="🔍 확인 불가" count={unverifiable.length} color="text-slate-500" />
        </div>
      )}

      {/* 결과 섹션 */}
      {violations.length > 0 && (
        <section>
          <h2 className="mb-3 text-base font-semibold text-red-700">⚠️ 보완 필요 항목</h2>
          <div className="space-y-3">
            {violations.map((r, i) => (
              <ReportCard key={i} report={r} />
            ))}
          </div>
        </section>
      )}

      {compliant.length > 0 && (
        <section>
          <h2 className="mb-3 text-base font-semibold text-green-700">✅ 준수 항목</h2>
          <div className="space-y-3">
            {compliant.map((r, i) => (
              <ReportCard key={i} report={r} />
            ))}
          </div>
        </section>
      )}

      {unverifiable.length > 0 && (
        <section>
          <h2 className="mb-3 text-base font-semibold text-slate-600">🔍 확인 불가 항목</h2>
          <p className="mb-2 text-xs text-slate-400">
            소스코드 부재(SPA, 서버사이드 로직 등)로 인해 준수 여부를 판단할 수 없는 항목입니다.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {unverifiable.map((r, i) => (
              <ReportCard key={i} report={r} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function MetricCard({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-center shadow-sm">
      <p className={`text-2xl font-bold ${color}`}>{count}</p>
      <p className="mt-0.5 text-xs text-slate-500">{label}</p>
    </div>
  );
}
