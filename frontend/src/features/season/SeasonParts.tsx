import type { CSSProperties } from "react";
import { ClubCrest } from "../../components/ClubCrest";
import { Jumbotron } from "../match/LiveParts";
import { css, useKitColors, type Rgb } from "../match/clubColors";
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
          * Clubes iguais em todos os critérios de desempate dividem a posição.
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
      <Jumbotron home={sides[0]} away={sides[1]} names={names} user={user} score={report.score} minute="" finished shootout={report.shootout} />
      {report.status !== "completed" && <span className="pill">Encerramento administrativo · oficial {report.official_score[0]}–{report.official_score[1]}</span>}
      {motm && (
        <section className="card motm">
          <span className="trophy" style={{ fontSize: "2rem" }} aria-hidden>⭐</span>
          <span className="muted small">Craque da Partida</span>
          <strong className="display">{motm.name}</strong>
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
          <StatsCompare stats={report.stats} uids={[sides[0], sides[1]]} labels={[names.get(sides[0]) ?? "Mandante", names.get(sides[1]) ?? "Visitante"]} />
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

/** Barras comparativas nas cores dos uniformes dos dois clubes (mesma regra do campinho ao vivo). */
export function StatsCompare({ stats, uids, labels = ["Mandante", "Visitante"] }: { stats: Record<string, Record<string, unknown>>; uids?: [number, number]; labels?: [string, string] }) {
  return uids ? <KitStats stats={stats} uids={uids} labels={labels} /> : <StatBars stats={stats} labels={labels} />;
}

function KitStats({ stats, uids, labels }: { stats: Record<string, Record<string, unknown>>; uids: [number, number]; labels: [string, string] }) {
  const kits = useKitColors(uids[0], uids[1]);
  return <StatBars stats={stats} labels={labels} kits={kits} />;
}

function StatBars({ stats, labels, kits }: { stats: Record<string, Record<string, unknown>>; labels: [string, string]; kits?: [Rgb, Rgb] }) {
  const h = stats.home ?? {};
  const a = stats.away ?? {};
  const legend = (i: 0 | 1) => (kits ? ({ "--kit": css(kits[i]) } as CSSProperties) : undefined);
  const kit = (i: 0 | 1) => (kits ? { background: css(kits[i]) } : undefined);
  return (
    <div className={`statbars${kits ? " statbars--kits" : ""}`} aria-label={`Estatísticas: ${labels[0]} × ${labels[1]}`}>
      <div className="live-legend">
        <b className={kits ? "home kit" : "home"} style={legend(0)}>{labels[0]}</b>
        <b className={kits ? "away kit" : "away"} style={legend(1)}>{labels[1]}</b>
      </div>
      {STAT_LABELS.map((s) => {
        const hv = Number(h[s.key] ?? 0);
        const av = Number(a[s.key] ?? 0);
        const max = s.pct ? 100 : Math.max(hv, av, s.dec ? 0.5 : 1);
        return (
          <div key={s.key} className="statbar" role="group" aria-label={`${s.label}: ${formatStat(hv, s)} × ${formatStat(av, s)}`}>
            <span className="statbar__label">{s.label}</span>
            <span className="statbar__v">{formatStat(hv, s)}</span>
            <span className="statbar__track" aria-hidden>
              <span><i data-testid="statbar-home" style={{ width: `${(hv / max) * 100}%`, ...kit(0) }} /></span>
              <span><i data-testid="statbar-away" style={{ width: `${(av / max) * 100}%`, ...kit(1) }} /></span>
            </span>
            <span className="statbar__v">{formatStat(av, s)}</span>
          </div>
        );
      })}
    </div>
  );
}
