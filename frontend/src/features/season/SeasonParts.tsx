import { ClubCrest } from "../../components/ClubCrest";
import { displayPosition } from "../../domain/positions";
import type { CupBracket, MatchReport, Position, SeasonFixture, StandingRow, TeamLineup } from "../../types/api";
import { EVENT_ICON, STAT_LABELS, describeEvent, eventLabel, formatStat, postureLabel } from "./labels";

export function Club({ uid, names, user, size = 22 }: { uid: number; names: Map<number, string>; user?: number; size?: number }) {
  const name = names.get(uid) ?? `Clube ${uid}`;
  return (
    <span className={`club-name${uid === user ? " is-user" : ""}`}>
      <ClubCrest clubUid={uid} name={name} size={size} />
      <span>{name}</span>
      {uid === user && <span className="tag tag--user">Você</span>}
    </span>
  );
}

export function scoreText(f: Pick<SeasonFixture, "score" | "shootout" | "played">): string {
  if (!f.played || !f.score) return "×";
  const base = `${f.score[0]} – ${f.score[1]}`;
  return f.shootout ? `${base} (${f.shootout[0]}–${f.shootout[1]} pên.)` : base;
}

export function FixtureList({ fixtures, names, user, onOpen }: {
  fixtures: SeasonFixture[];
  names: Map<number, string>;
  user: number;
  onOpen?: (matchId: string) => void;
}) {
  return (
    <ul className="fixtures">
      {fixtures.map((f) => (
        <li key={f.match_id} className={f.is_user_match ? "is-user" : ""}>
          <Club uid={f.home_club_uid} names={names} user={user} />
          {f.played && onOpen ? (
            <button type="button" className="btn btn--ghost btn--small score-btn" onClick={() => onOpen(f.match_id)}
              aria-label={`Ver partida ${names.get(f.home_club_uid) ?? ""} ${scoreText(f)} ${names.get(f.away_club_uid) ?? ""}`}>
              {scoreText(f)}
            </button>
          ) : (
            <span className="fixture__x">{scoreText(f)}</span>
          )}
          <Club uid={f.away_club_uid} names={names} user={user} />
        </li>
      ))}
    </ul>
  );
}

export function StandingsTable({ rows, names, user, compact }: { rows: StandingRow[]; names: Map<number, string>; user: number; compact?: boolean }) {
  const tied = rows.some((r) => r.tied_with.length > 0);
  return (
    <div className="stack">
      <div className="table-wrap">
        <table className={compact ? "compact" : ""}>
          <caption className="visually-hidden">Classificação</caption>
          <thead>
            <tr>
              <th className="num">#</th><th>Clube</th><th className="num">P</th><th className="num">J</th><th className="num">V</th>
              <th className="num">E</th><th className="num">D</th><th className="num">GP</th><th className="num">GC</th><th className="num">SG</th>
              {!compact && <th>Últimos</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.club_uid} className={r.club_uid === user ? "is-user" : ""}>
                <td className="num">{r.position}{r.tied_with.length > 0 ? "*" : ""}</td>
                <td><Club uid={r.club_uid} names={names} user={user} size={18} /></td>
                <td className="num"><strong>{r.points}</strong></td>
                <td className="num">{r.played}</td><td className="num">{r.wins}</td><td className="num">{r.draws}</td>
                <td className="num">{r.losses}</td><td className="num">{r.goals_for}</td><td className="num">{r.goals_against}</td>
                <td className="num">{r.goal_difference}</td>
                {!compact && <td><span className="form">{r.form.map((x, i) => <span key={i} className={`form__${x}`}>{x}</span>)}</span></td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {tied && (
        <p className="muted small">
          * Empate em pontos sem critério de desempate oficial (pendência PC-01): os clubes dividem a posição.
        </p>
      )}
    </div>
  );
}

export function BracketView({ bracket, fixtures, names, user, onOpen }: {
  bracket: CupBracket;
  fixtures: Map<string, SeasonFixture>;
  names: Map<number, string>;
  user: number;
  onOpen?: (matchId: string) => void;
}) {
  return (
    <div className="bracket" role="list" aria-label="Chaveamento">
      {bracket.rounds.map((r) => (
        <div className="bracket__round" key={r.number} role="listitem">
          <h4>{r.name}</h4>
          {r.matches.map((m) => {
            const f = fixtures.get(m.id);
            const mine = m.club_a_uid === user || m.club_b_uid === user;
            return (
              <div key={m.id} className={`cup-match${mine ? " is-user" : ""}`}>
                {[m.club_a_uid, m.club_b_uid].map((c, i) => (
                  <div key={i} className={`cup-side${m.winner_club_uid != null && c === m.winner_club_uid ? " is-winner" : ""}`}>
                    {c != null ? <Club uid={c} names={names} user={user} size={18} /> : <span className="muted small">A definir</span>}
                    {f?.played && f.score && <strong className="num">{f.score[i]}{f.shootout ? ` (${f.shootout[i]})` : ""}</strong>}
                  </div>
                ))}
                {f?.played && onOpen && (
                  <button type="button" className="btn btn--ghost btn--small" onClick={() => onOpen(m.id)}>Ver partida</button>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function LineupList({ lineup, names }: { lineup: TeamLineup; names: Map<number, string> }) {
  return (
    <section className="card">
      <h4>{names.get(lineup.club_uid) ?? lineup.club_uid} · {lineup.formation} · {postureLabel(lineup.initial_posture)}</h4>
      <ol className="mini-squad">
        {lineup.starters.map((p) => (
          <li key={p.player}><span className="tag">{displayPosition(p.slot as Position)}</span>{p.name}</li>
        ))}
      </ol>
      {lineup.bench.length > 0 && <p className="muted small">Reservas: {lineup.bench.map((p) => p.name).join(", ")}</p>}
    </section>
  );
}

export function MatchReportView({ report, names, user }: { report: MatchReport; names: Map<number, string>; user: number }) {
  const sides = [report.home_club_uid, report.away_club_uid];
  const motm = report.man_of_the_match;
  return (
    <div className="stack">
      <section className="card scoreboard" aria-label="Placar final">
        <Club uid={sides[0]} names={names} user={user} size={40} />
        <div className="scoreboard__score">
          <strong>{report.score[0]} – {report.score[1]}</strong>
          {report.shootout && <span className="muted small">Pênaltis {report.shootout[0]}–{report.shootout[1]}</span>}
          {report.status !== "completed" && <span className="pill">Encerramento administrativo · oficial {report.official_score[0]}–{report.official_score[1]}</span>}
        </div>
        <Club uid={sides[1]} names={names} user={user} size={40} />
      </section>
      {motm && (
        <section className="card motm">
          <span className="muted small">Craque da Partida</span>
          <strong>{motm.name}</strong>
          <span>{names.get(motm.club_uid) ?? ""} · nota {motm.rating.toFixed(1)}</span>
        </section>
      )}
      <div className="grid-2">
        <section className="card">
          <h3>Principais acontecimentos</h3>
          <EventFeed events={report.events.filter((e) => !["half_time", "full_time", "save"].includes(e.type))} names={names} />
        </section>
        <section className="card">
          <h3>Estatísticas</h3>
          <StatsCompare stats={report.stats} labels={[names.get(sides[0]) ?? "Mandante", names.get(sides[1]) ?? "Visitante"]} />
        </section>
      </div>
      <section className="card">
        <h3>Avaliações</h3>
        <div className="grid-2">
          {sides.map((c) => (
            <div key={c} className="table-wrap">
              <table className="compact">
                <caption>{names.get(c) ?? c}</caption>
                <thead><tr><th>Jogador</th><th className="num">Min</th><th className="num">Nota</th></tr></thead>
                <tbody>
                  {report.ratings.filter((r) => r.club_uid === c).map((r) => (
                    <tr key={r.player} className={r.player === motm?.player ? "is-user" : ""}>
                      <td>{r.name}{r.player === motm?.player ? " ★" : ""}</td>
                      <td className="num">{Math.round(r.minutes)}</td>
                      <td className="num">{r.rating.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      </section>
      {(report.lineups ?? []).length > 0 && (
        <div className="grid-2">{(report.lineups ?? []).map((l) => <LineupList key={l.club_uid} lineup={l} names={names} />)}</div>
      )}
    </div>
  );
}

export function EventFeed({ events, names }: { events: MatchReport["events"]; names: Map<number, string> }) {
  if (events.length === 0) return <p className="muted small">Nenhum acontecimento ainda.</p>;
  return (
    <ol className="events">
      {events.map((e) => (
        <li key={e.seq} className={`event event--${e.type}`}>
          <span className="event__min">{e.type === "shootout_kick" ? "pên." : `${e.minute}'`}</span>
          <span className="event__icon" aria-hidden>{EVENT_ICON[e.type] ?? "•"}</span>
          <span className="event__text">
            <strong>{eventLabel(e.type)}</strong> {describeEvent(e)}
            {e.club_uid != null && <span className="muted small"> · {names.get(e.club_uid) ?? ""}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

export function StatsCompare({ stats, labels = ["Mandante", "Visitante"] }: { stats: Record<string, Record<string, unknown>>; labels?: [string, string] }) {
  const h = stats.home ?? {};
  const a = stats.away ?? {};
  return (
    <table className="compact stat-compare">
      <caption className="visually-hidden">Estatísticas do confronto</caption>
      <thead><tr><th className="num">{labels[0]}</th><th>Estatística</th><th className="num">{labels[1]}</th></tr></thead>
      <tbody>
        {STAT_LABELS.map((s) => (
          <tr key={s.key}>
            <td className="num">{formatStat(h[s.key], s)}</td>
            <td className="muted">{s.label}</td>
            <td className="num">{formatStat(a[s.key], s)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
