import { Notice } from "../../components/Notice";
import type { ImportIssue, ImportReport } from "../../types/api";

function IssueList({ issues, total }: { issues: ImportIssue[]; total: number }) {
  const shown = issues.slice(0, 12);
  return (
    <ul className="issues">
      {shown.map((i, n) => (
        <li key={n}>
          {i.row != null && <span className="tag">linha {i.row}</span>}
          {i.column && <code>{i.column}</code>} {i.message}
        </li>
      ))}
      {total > shown.length && <li className="muted">… e mais {total - shown.length}.</li>}
    </ul>
  );
}

export function ImportReportView({ report }: { report: ImportReport }) {
  const ok = report.status === "imported";
  return (
    <div className="report">
      {ok ? (
        <Notice kind="success" title="Importação concluída">
          {report.rows_imported} {report.base === "clubs" ? "clubes" : "jogadores"} gravados
          {report.previous_count ? ` (substituindo ${report.previous_count})` : ""}. Aba: {report.sheet}.
        </Notice>
      ) : (
        <Notice kind="error" title="Importação rejeitada">
          {report.critical_error_count} erro(s) crítico(s). Nada foi alterado: a base anterior foi preservada.
        </Notice>
      )}
      <dl className="stats">
        <div><dt>Linhas lidas</dt><dd>{report.rows_read}</dd></div>
        <div><dt>Gravadas</dt><dd>{report.rows_imported}</dd></div>
        <div><dt>Descartadas</dt><dd>{report.rows_skipped}</dd></div>
        <div><dt>Avisos</dt><dd>{report.warning_count}</dd></div>
      </dl>
      {(report.critical_errors?.length ?? 0) > 0 && (
        <details open>
          <summary>Erros críticos</summary>
          <IssueList issues={report.critical_errors ?? []} total={report.critical_error_count ?? 0} />
        </details>
      )}
      {(report.warnings?.length ?? 0) > 0 && (
        <details>
          <summary>Avisos ({report.warning_count})</summary>
          <IssueList issues={report.warnings ?? []} total={report.warning_count ?? 0} />
        </details>
      )}
    </div>
  );
}
