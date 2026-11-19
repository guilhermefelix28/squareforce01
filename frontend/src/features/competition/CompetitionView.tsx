import { useMemo, useState } from "react";
import { ClubCrest } from "../../components/ClubCrest";
import type { Club, CompetitionOut, CupBracket, CupMatch, LeagueSchedule } from "../../types/api";

type ClubMap = Map<number, Club>;

function ClubName({ uid, clubs, user }: { uid: number; clubs: ClubMap; user: number }) {
  const c = clubs.get(uid);
  const name = c?.short_name ?? `#${uid}`;
  return (
    <span className={`club-name ${uid === user ? "is-user" : ""}`}>
      <ClubCrest clubUid={uid} name={name} size={22} />
      <span>{name}</span>
      {uid === user && <span className="tag tag--user">você</span>}
    </span>
  );
}

function Participants({ ids, clubs, user }: { ids: number[]; clubs: ClubMap; user: number }) {
  return (
    <details className="participants">
      <summary>Participantes ({ids.length})</summary>
      <ul>
        {ids.map((id) => (
          <li key={id}>
            <ClubName uid={id} clubs={clubs} user={user} />
            {clubs.get(id)?.division && <span className="tag">Série {clubs.get(id)!.division}</span>}
          </li>
        ))}
      </ul>
    </details>
  );
}

// ------------------------------------------------------------------ Liga
function LeagueView({ s, clubs, user }: { s: LeagueSchedule; clubs: ClubMap; user: number }) {
  const [round, setRound] = useState(1);
  const [onlyMine, setOnlyMine] = useState(false);
  const current = s.rounds[round - 1];
  const myGames = useMemo(
    () => s.rounds.flatMap((r) => r.matches).filter((m) => m.home_club_uid === user || m.away_club_uid === user),
    [s, user],
  );
  const myHome = myGames.filter((m) => m.home_club_uid === user).length;
  const myByes = s.rounds.filter((r) => r.bye_club_uid === user).length;

  return (
    <div className="stack">
      <dl className="stats">
        <div><dt>Clubes</dt><dd>{s.participants.length}</dd></div>
        <div><dt>Turnos</dt><dd>{s.rounds_mode === "double" ? "Turno e returno" : "Turno único"}</dd></div>
        <div><dt>Rodadas</dt><dd>{s.total_rounds}</dd></div>
        <div><dt>Partidas</dt><dd>{s.total_matches}</dd></div>
        <div><dt>Seus jogos</dt><dd>{myGames.length} ({myHome} em casa)</dd></div>
        {myByes > 0 && <div><dt>Suas folgas</dt><dd>{myByes}</dd></div>}
      </dl>
      <Participants ids={s.participants} clubs={clubs} user={user} />

      <div className="toolbar toolbar--center">
        <label className="check">
          <input type="checkbox" checked={onlyMine} onChange={(e) => setOnlyMine(e.target.checked)} />
          Somente jogos do meu clube
        </label>
      </div>

      {onlyMine ? (
        <ol className="fixtures">
          {myGames.map((m) => (
            <li key={m.id} className="has-round">
              <span className="fixture__round">R{m.round}</span>
              <ClubName uid={m.home_club_uid} clubs={clubs} user={user} />
              <span className="fixture__x">×</span>
              <ClubName uid={m.away_club_uid} clubs={clubs} user={user} />
            </li>
          ))}
        </ol>
      ) : (
        <>
          <div className="round-nav">
            <button type="button" className="btn btn--ghost btn--small" disabled={round === 1} onClick={() => setRound(round - 1)} aria-label="Rodada anterior">
              ‹
            </button>
            <label className="field field--inline">
              <span className="visually-hidden">Rodada</span>
              <select value={round} onChange={(e) => setRound(Number(e.target.value))}>
                {s.rounds.map((r) => (
                  <option key={r.number} value={r.number}>
                    Rodada {r.number}{s.rounds_mode === "double" ? ` · ${r.turn === 1 ? "turno" : "returno"}` : ""}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="btn btn--ghost btn--small" disabled={round === s.total_rounds} onClick={() => setRound(round + 1)} aria-label="Próxima rodada">
              ›
            </button>
          </div>
          <ol className="fixtures" aria-label={`Rodada ${current.number}`}>
            {current.matches.map((m) => (
              <li key={m.id} className={m.home_club_uid === user || m.away_club_uid === user ? "is-user" : ""}>
                <ClubName uid={m.home_club_uid} clubs={clubs} user={user} />
                <span className="fixture__x">×</span>
                <ClubName uid={m.away_club_uid} clubs={clubs} user={user} />
              </li>
            ))}
          </ol>
          {current.bye_club_uid != null && (
            <p className="muted small bye">
              Folga: <ClubName uid={current.bye_club_uid} clubs={clubs} user={user} /> (não conta como partida)
            </p>
          )}
        </>
      )}
      <p className="muted small">Mandante à esquerda. Resultados na Central da competição.</p>
    </div>
  );
}

// ------------------------------------------------------------------ Copa
function CupSide({ uid, source, clubs, user, byId }: {
  uid?: number | null; source?: string | null; clubs: ClubMap; user: number; byId: Map<string, CupMatch>;
}) {
  if (uid != null) return <ClubName uid={uid} clubs={clubs} user={user} />;
  const src = source ? byId.get(source) : undefined;
  return <span className="muted small">Vencedor de {src ? `${src.round}ª fase, jogo ${src.slot}` : "—"}</span>;
}

function CupView({ b, clubs, user }: { b: CupBracket; clubs: ClubMap; user: number }) {
  const byId = useMemo(() => new Map(b.rounds.flatMap((r) => r.matches).map((m) => [m.id, m])), [b]);
  return (
    <div className="stack">
      <dl className="stats">
        <div><dt>Clubes</dt><dd>{b.participants.length}</dd></div>
        <div><dt>Fases</dt><dd>{b.total_rounds}</dd></div>
        <div><dt>Confrontos</dt><dd>{b.total_matches}</dd></div>
        <div><dt>Formato</dt><dd>Jogo único</dd></div>
      </dl>
      <p className="muted small">
        Mando neutro. 90 minutos, sem prorrogação. Empate decidido nos pênaltis (não contam na artilharia). Se o seu clube for
        eliminado, a Copa continua até a final.
      </p>
      <Participants ids={b.participants} clubs={clubs} user={user} />
      <div className="bracket" role="list" aria-label="Chaveamento">
        {b.rounds.map((r) => (
          <section key={r.number} className="bracket__round" role="listitem" aria-label={r.name}>
            <h4>{r.name}</h4>
            {r.matches.map((m) => (
              <div key={m.id} className={`cup-match ${m.club_a_uid === user || m.club_b_uid === user ? "is-user" : ""}`}>
                <CupSide uid={m.club_a_uid} source={m.source_a} clubs={clubs} user={user} byId={byId} />
                <CupSide uid={m.club_b_uid} source={m.source_b} clubs={clubs} user={user} byId={byId} />
              </div>
            ))}
          </section>
        ))}
      </div>
    </div>
  );
}

export function CompetitionView({ competition, clubs }: { competition: CompetitionOut; clubs: Club[] }) {
  const map = useMemo(() => new Map(clubs.map((c) => [c.club_uid, c])), [clubs]);
  const st = competition.structure;
  return (
    <section className="card" aria-labelledby="competition-title">
      <h3 id="competition-title">{st.kind === "league" ? "Calendário da Liga" : "Chaveamento da Copa"}</h3>
      {st.kind === "league" ? (
        <LeagueView s={st} clubs={map} user={competition.user_club_uid} />
      ) : (
        <CupView b={st} clubs={map} user={competition.user_club_uid} />
      )}
    </section>
  );
}
