/** Encerramento (GDD §21): campeão, campanha do usuário, rankings e premiações finais. Nova competição. */
import { useEffect, useState } from "react";
import { getSeasonSummary } from "../api/endpoints";
import { ActionBar, PhaseBanner } from "../components/GameUi";
import { Notice } from "../components/Notice";
import { Club, FixtureList } from "../features/season/SeasonParts";
import { useClubNames, useSeason } from "../features/season/useSeason";
import type { AwardEntry, SeasonSummary } from "../types/api";

function Award({ title, entries, unit, names }: { title: string; entries: AwardEntry[]; unit: string; names: Map<number, string> }) {
  return (
    <section className="card award">
      <span className="muted small">{title}</span>
      {entries.length === 0 ? <span className="muted">—</span> : entries.map((e) => (
        <div key={e.player}>
          <strong>{e.name}</strong> <span className="muted small">{names.get(e.club_uid) ?? ""}</span>
          <div className="small">{unit === "média" ? `média ${e.value.toFixed(2)}` : `${e.value} ${e.value === 1 ? unit.replace(/s$/, "").replace(/õe$/, "ão") : unit}`} · {e.appearances} {e.appearances === 1 ? "jogo" : "jogos"}</div>
        </div>
      ))}
      {entries.length > 1 && <span className="muted small">Empatados</span>}
    </section>
  );
}

export function EndPage({ navigate }: { navigate: (h: string) => void }) {
  const { sid, state } = useSeason();
  const names = useClubNames();
  const [summary, setSummary] = useState<SeasonSummary | null>(null);
  useEffect(() => {
    if (sid) getSeasonSummary(sid).then(setSummary).catch(() => undefined);
  }, [sid, state?.phase]);

  if (!sid || !state || !summary) return <p className="muted" role="status">Carregando encerramento…</p>;
  if (!summary.finished) {
    return <Notice kind="info" title="A competição ainda não terminou">As premiações são definidas no encerramento.</Notice>;
  }
  const user = state.user_club_uid;
  const mine = summary.user_campaign;
  return (
    <div className="stack">
      <PhaseBanner kicker="Fim de temporada" title="Encerramento" />
      <section className="card hero champion">
        <span className="trophy" aria-hidden>🏆</span>
        <span className="muted small">{state.kind === "cup" ? "Campeão da Copa" : "Campeão da Liga"}</span>
        {summary.champion_club_uid != null ? (
          <Club uid={summary.champion_club_uid} names={names} user={user} size={64} />
        ) : (
          <Notice kind="warning" title="Campeão indefinido">
            Empate no topo entre {summary.tied_champions.map((c) => names.get(c) ?? c).join(", ")}, não resolvido pelos critérios de desempate.
          </Notice>
        )}
      </section>

      <section className="card">
        <h3>Sua campanha · {mine.result}</h3>
        <dl className="stats">
          <div><dt>Jogos</dt><dd>{mine.played}</dd></div>
          <div><dt>Vitórias</dt><dd>{mine.wins}</dd></div>
          <div><dt>Empates</dt><dd>{mine.draws}</dd></div>
          <div><dt>Derrotas</dt><dd>{mine.losses}</dd></div>
          <div><dt>Gols</dt><dd>{mine.goals_for}–{mine.goals_against}</dd></div>
          {(mine.shootouts_won + mine.shootouts_lost) > 0 && <div><dt>Pênaltis</dt><dd>{mine.shootouts_won}V {mine.shootouts_lost}D</dd></div>}
        </dl>
        <FixtureList fixtures={mine.matches} names={names} user={user} onOpen={(id) => navigate(`#/pos/${id}`)} />
      </section>

      <div className="grid-2 grid-2--wide">
        <Award title="Artilheiro" entries={summary.top_scorers} unit="gols" names={names} />
        <Award title="Líder de assistências" entries={summary.top_assists} unit="assistências" names={names} />
        <Award title="Melhor média de notas (mín. 50% dos jogos)" entries={summary.best_average_rating} unit="média" names={names} />
        <Award title="Mais vezes Craque da Partida" entries={summary.most_man_of_the_match} unit="prêmios" names={names} />
      </div>

      <section className="card">
        <h3>Campanha dos clubes</h3>
        <div className="table-wrap">
          <table className="compact">
            <caption className="visually-hidden">Campanha dos clubes</caption>
            <thead><tr><th>Clube</th><th>Resultado</th><th className="num">J</th><th className="num">V</th><th className="num">E</th><th className="num">D</th><th className="num">GP</th><th className="num">GC</th></tr></thead>
            <tbody>
              {summary.campaigns.map((c) => (
                <tr key={c.club_uid} className={c.club_uid === user ? "is-user" : ""}>
                  <td><Club uid={c.club_uid} names={names} user={user} size={16} /></td><td>{c.result}</td>
                  <td className="num">{c.played}</td><td className="num">{c.wins}</td><td className="num">{c.draws}</td><td className="num">{c.losses}</td>
                  <td className="num">{c.goals_for}</td><td className="num">{c.goals_against}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h3>Histórico completo ({summary.history.length} partidas)</h3>
        <details>
          <summary>Mostrar todas as partidas</summary>
          <FixtureList fixtures={summary.history} names={names} user={user} onOpen={(id) => navigate(`#/pos/${id}`)} />
        </details>
      </section>

      <section className="card">
        <h3>Nova competição</h3>
        <p className="muted">O progresso não é salvo: ao iniciar outra competição, esta será encerrada (com confirmação).</p>
        <ActionBar>
          <button type="button" className="btn btn--cta" onClick={() => navigate("#/session")}>Nova partida ▶</button>
        </ActionBar>
      </section>
    </div>
  );
}
