import { useRef, useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import { importBase } from "../../api/endpoints";
import { Notice } from "../../components/Notice";
import type { ImportBase, ImportReport } from "../../types/api";
import { ImportReportView } from "./ImportReportView";

const LABELS: Record<ImportBase, { title: string; hint: string }> = {
  clubs: {
    title: "Base de clubes",
    hint: "Planilha .xlsx com as colunas club_uid, club_name, club_short_name, club_nation_id e club_reputation. A própria jogadores.xlsx é aceita.",
  },
  players: {
    title: "Base de jogadores",
    hint: "Planilha jogadores.xlsx. Importe os clubes antes: cada jogador precisa de um club_uid existente.",
  },
};

export function ImportCard({
  base,
  blocked,
  onImported,
}: {
  base: ImportBase;
  blocked: boolean;
  onImported: (report: ImportReport) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const label = LABELS[base];

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      const r = await importBase(base, file);
      setReport(r);
      onImported(r);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : null;
      setError(apiErr);
      const rejected = apiErr?.details?.report as ImportReport | undefined;
      if (rejected) setReport(rejected);
    } finally {
      setBusy(false);
    }
  }

  const inputId = `import-${base}`;
  return (
    <section className="card" aria-labelledby={`${inputId}-title`}>
      <h3 id={`${inputId}-title`}>{label.title}</h3>
      <p className="muted small">{label.hint}</p>
      <form onSubmit={submit} className="import-form">
        <label htmlFor={inputId} className="file-picker">
          <span className="btn btn--ghost">Selecionar arquivo</span>
          <span className="file-picker__name">{file ? file.name : "Nenhum arquivo selecionado"}</span>
        </label>
        <input
          ref={inputRef}
          id={inputId}
          className="visually-hidden"
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          disabled={blocked || busy}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button type="submit" className="btn btn--primary" disabled={!file || blocked || busy}>
          {busy ? "Validando e importando…" : "Importar"}
        </button>
      </form>
      {blocked && (
        <Notice kind="warning" title="Importação bloqueada">
          Existe uma competição ativa. Encerre a sessão para importar novas bases.
        </Notice>
      )}
      {error && !report && (
        <Notice kind="error" title="Falha na importação">
          {error.message}
          {error.retryable && " Você pode tentar novamente."}
        </Notice>
      )}
      {report && <ImportReportView report={report} />}
    </section>
  );
}
