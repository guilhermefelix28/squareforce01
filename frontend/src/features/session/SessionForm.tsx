import { useMemo, useRef, useState, type FormEvent } from "react";
import { ApiError, newIdempotencyKey } from "../../api/client";
import { createSession } from "../../api/endpoints";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Notice } from "../../components/Notice";
import type { Club, CompetitionFormat, CompetitionOptions, LeagueRounds, Session, SessionCreate } from "../../types/api";
import { validateSessionConfig } from "./validation";

export function SessionForm({
  options,
  clubs,
  onCreated,
}: {
  options: CompetitionOptions;
  clubs: Club[];
  onCreated: (s: Session) => void;
}) {
  const [format, setFormat] = useState<CompetitionFormat>("league");
  const [leagueClubs, setLeagueClubs] = useState(Math.min(20, options.eligible_clubs || 20));
  const [cupSize, setCupSize] = useState(8);
  const [rounds, setRounds] = useState<LeagueRounds>("double");
  const [userClub, setUserClub] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmReplace, setConfirmReplace] = useState(false);
  // Uma chave por intenção do usuário: repetições automáticas reutilizam a mesma chave.
  const keyRef = useRef<string>(newIdempotencyKey());

  const byDivision = useMemo(() => {
    const sorted = [...clubs].sort((a, b) => a.short_name.localeCompare(b.short_name, "pt-BR"));
    return { A: sorted.filter((c) => c.division === "A"), B: sorted.filter((c) => c.division === "B") };
  }, [clubs]);

  const config: SessionCreate = {
    format,
    num_clubs: format === "league" ? leagueClubs : cupSize,
    user_club_uid: typeof userClub === "number" ? userClub : 0,
    league_rounds: format === "league" ? rounds : null,
    confirm_replace: false,
  };

  async function send(replace: boolean) {
    setBusy(true);
    setError(null);
    try {
      const s = await createSession({ ...config, confirm_replace: replace }, keyRef.current);
      keyRef.current = newIdempotencyKey();
      setConfirmReplace(false);
      onCreated(s);
    } catch (e) {
      keyRef.current = newIdempotencyKey();
      if (e instanceof ApiError && e.code === "SESSION_ALREADY_ACTIVE") setConfirmReplace(true);
      else setError(e instanceof ApiError ? e.message : "Não foi possível iniciar a sessão.");
    } finally {
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const problem = validateSessionConfig(config, options);
    if (problem) {
      setError(problem);
      return;
    }
    void send(false);
  }

  return (
    <form className="card session-form" onSubmit={submit} noValidate aria-labelledby="new-session-title">
      <h3 id="new-session-title">Nova competição</h3>
      <fieldset className="segmented">
        <legend>Formato</legend>
        {(["league", "cup"] as const).map((f) => (
          <label key={f} className={format === f ? "is-on" : ""}>
            <input type="radio" name="format" value={f} checked={format === f} onChange={() => setFormat(f)} />
            {f === "league" ? "Liga" : "Copa"}
          </label>
        ))}
      </fieldset>

      {format === "league" ? (
        <div className="grid-2">
          <label className="field">
            <span>Clubes ({options.league.min_clubs}–{options.league.max_clubs})</span>
            <input
              type="number"
              inputMode="numeric"
              min={options.league.min_clubs}
              max={options.league.max_clubs}
              value={Number.isNaN(leagueClubs) ? "" : leagueClubs}
              onChange={(e) => setLeagueClubs(e.target.valueAsNumber)}
            />
          </label>
          <label className="field">
            <span>Turnos</span>
            <select value={rounds} onChange={(e) => setRounds(e.target.value as LeagueRounds)}>
              <option value="single">Turno único</option>
              <option value="double">Turno e returno</option>
            </select>
          </label>
        </div>
      ) : (
        <label className="field">
          <span>Participantes</span>
          <select value={cupSize} onChange={(e) => setCupSize(Number(e.target.value))}>
            {options.cup.allowed_sizes.map((n) => (
              <option key={n} value={n} disabled={n > options.eligible_clubs}>
                {n}
              </option>
            ))}
          </select>
        </label>
      )}

      <label className="field">
        <span>Seu clube</span>
        <select value={userClub} onChange={(e) => setUserClub(e.target.value ? Number(e.target.value) : "")}>
          <option value="">Selecione…</option>
          {(["A", "B"] as const).map((d) =>
            byDivision[d].length ? (
              <optgroup key={d} label={"Série " + d}>
                {byDivision[d].map((c) => (
                  <option key={c.club_uid} value={c.club_uid}>
                    {c.short_name}
                  </option>
                ))}
              </optgroup>
            ) : null,
          )}
        </select>
      </label>
      <p className="muted small">
        Seu clube participa obrigatoriamente.{" "}
        {format === "league"
          ? "Os demais vêm primeiro da Série A e, se faltarem vagas, da Série B."
          : "Os demais são sorteados entre os " + options.eligible_clubs + " clubes elegíveis (Séries A e B)."}
      </p>

      {error && <Notice kind="error">{error}</Notice>}
      <button type="submit" className="btn btn--primary btn--block" disabled={busy}>
        {busy ? "Iniciando…" : "Iniciar sessão"}
      </button>

      <ConfirmDialog
        open={confirmReplace}
        title="Substituir competição ativa?"
        message="Já existe uma competição ativa. Ela será encerrada e todo o progresso será perdido, sem possibilidade de restauração."
        confirmLabel="Encerrar e iniciar nova"
        danger
        busy={busy}
        onConfirm={() => void send(true)}
        onCancel={() => setConfirmReplace(false)}
      />
    </form>
  );
}
