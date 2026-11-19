/** Central de estatísticas (GDD §20): Classificação, Jogadores, Clubes e Estatísticas avançadas. */
import { useEffect, useMemo, useState } from "react";
import { getCalendar, getSeasonStats } from "../../api/endpoints";
import type { Calendar, SeasonFixture, SeasonState, SeasonStats } from "../../types/api";
import { BracketView, Club, StandingsTable } from "./SeasonParts";

type Tab = "classificacao" | "jogadores" | "clubes" | "avancadas";
type PlayerSort = "goals" | "assists" | "average_rating" | "motm" | "appearances" | "yellow_cards" | "red_cards";
const SORTS: { id: PlayerSort; label: string }[] = [
  { id: "goals", label: "Gols" },
  { id: "assists", label: "Assistências" },
  { id: "average_rating", label: "Média de notas" },
  { id: "motm", label: "Craque da Partida" },
  { id: "appearances", label: "Jogos" },
  { id: "yellow_cards", label: "Amarelos" },
  { id: "red_cards", label: "Vermelhos" },
];

export function StatsCenter({ sid, state, names }: { sid: string; state: SeasonState; names: Map<number, string> }) {
  const [tab, setTab] = useState<Tab>("classificacao");
  const [stats, setStats] = useState<SeasonStats | null>(null);
  const [cal, setCal] = useState<Calendar | null>(null);
  const played = state.fixtures.filter((f) => f.played).length;
  useEffect(() => {
    getSeasonStats(sid).then(setStats).catch(() => undefined);
    getCalendar(sid).then(setCal).catch(() => undefined);
  }, [sid, state.round_number, state.phase, played]);

  const tabs: { id: Tab; label: string }[] = [
    { id: "classificacao", label: state.kind === "cup" ? "Chaveamento" : "Classificação" },
    { id: "jogadores", label: "Jogadores" },
    { id: "clubes", label: "Clubes" },
    { id: "avancadas", label: "Estatísticas avançadas" },
  ];
  return (
    <section className="card">
      <div role="tablist" aria-label="Estatísticas" className="segmented-tabs">
        {tabs.map((t) => (
          <button key={t.id} type="button" role="tab" id={`st-${t.id}`} aria-selected={tab === t.id} aria-controls={`sp-${t.id}`}
            className={tab === t.id ? "is-active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`sp-${tab}`} aria-labelledby={`st-${tab}`}>
        {tab === "classificacao" && (state.kind === "league"
          ? <StandingsTable rows={state.standings} names={names} user={state.user_club_uid} />
          : state.bracket && <BracketView bracket={state.bracket} names={names} user={state.user_club_uid}
              fixtures={new Map<string, SeasonFixture>((cal?.rounds ?? []).flatMap((r) => r.fixtures).map((f) => [f.match_id, f]))} />)}
        {tab !== "classificacao" && !stats && <p className="muted" role="status">Carregando estatísticas…</p>}
        {tab === "jogadores" && stats && <PlayersTab stats={stats} names={names} user={state.user_club_uid} />}
        {tab === "clubes" && stats && <ClubsTab stats={stats} names={names} user={state.user_club_uid} />}
        {tab === "avancadas" && stats && <AdvancedTab stats={stats} names={names} user={state.user_club_uid} />}
      </div>
    </section>
  );
}

function PlayersTab({ stats, names, user }: { stats: SeasonStats; names: Map<number, string>; user: number }) {
  const [sort, setSort] = useState<PlayerSort>("goals");
  const [club, setClub] = useState<number | "">("");
  const [search, setSearch] = useState("");
  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return stats.players
      .filter((p) => (club === "" || p.club_uid === club) && (!term || p.name.toLowerCase().includes(term)))
      .filter((p) => (sort === "average_rating" ? p.rating_eligible : true))
      .sort((a, b) => Number(b[sort] ?? 0) - Number(a[sort] ?? 0) || b.appearances - a.appearances || a.name.localeCompare(b.name))
      .slice(0, 50);
  }, [stats, sort, club, search]);
  return (
    <div className="stack">
      <div className="toolbar">
        <label className="field">Ranking
          <select value={sort} onChange={(e) => setSort(e.target.value as PlayerSort)}>
            {SORTS.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </label>
        <label className="field">Clube
          <select value={club} onChange={(e) => setClub(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Todos</option>
            {stats.clubs.map((c) => <option key={c.club_uid} value={c.club_uid}>{names.get(c.club_uid) ?? c.club_uid}</option>)}
          </select>
        </label>
        <label className="field">Buscar jogador
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Nome" />
        </label>
      </div>
      {sort === "average_rating" && <p className="muted small">Média de notas: somente quem jogou ao menos 50% das partidas da própria equipe (arredondado para cima).</p>}
      <div className="table-wrap">
        <table className="compact">
          <caption className="visually-hidden">Ranking de jogadores</caption>
          <thead><tr><th className="num">#</th><th>Jogador</th><th>Clube</th><th className="num">J</th><th className="num">Gols</th><th className="num">Assist.</th>
            <th className="num">Média</th><th className="num">Craque</th><th className="num">CA</th><th className="num">CV</th></tr></thead>
          <tbody>
            {rows.map((p, i) => (
              <tr key={p.player} className={p.club_uid === user ? "is-user" : ""}>
                <td className="num">{i + 1}</td><td>{p.name}</td><td><Club uid={p.club_uid} names={names} size={16} /></td>
                <td className="num">{p.appearances}</td><td className="num">{p.goals}</td><td className="num">{p.assists}</td>
                <td className="num">{p.average_rating != null ? p.average_rating.toFixed(2) : "—"}</td>
                <td className="num">{p.motm}</td><td className="num">{p.yellow_cards}</td><td className="num">{p.red_cards}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ClubsTab({ stats, names, user }: { stats: SeasonStats; names: Map<number, string>; user: number }) {
  const rows = [...stats.clubs].sort((a, b) => b.goals_for - a.goals_for || a.goals_against - b.goals_against);
  return (
    <div className="table-wrap">
      <table className="compact">
        <caption className="visually-hidden">Clubes</caption>
        <thead><tr><th>Clube</th><th className="num">J</th><th className="num">V</th><th className="num">E</th><th className="num">D</th>
          <th className="num">GP</th><th className="num">GC</th><th className="num">Finaliz.</th><th className="num">Posse média</th>
          <th className="num">Faltas</th><th className="num">CA</th><th className="num">CV</th></tr></thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.club_uid} className={c.club_uid === user ? "is-user" : ""}>
              <td><Club uid={c.club_uid} names={names} size={16} user={user} /></td>
              <td className="num">{c.played}</td><td className="num">{c.wins}</td><td className="num">{c.draws}</td><td className="num">{c.losses}</td>
              <td className="num">{c.goals_for}</td><td className="num">{c.goals_against}</td><td className="num">{c.totals.shots}</td>
              <td className="num">{c.played ? `${c.totals.possession_pct.toFixed(0)}%` : "—"}</td>
              <td className="num">{c.totals.fouls}</td><td className="num">{c.totals.yellow_cards}</td><td className="num">{c.totals.red_cards}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const per = (v: number, n: number) => (n ? (v / n).toFixed(2) : "—");

function AdvancedTab({ stats, names, user }: { stats: SeasonStats; names: Map<number, string>; user: number }) {
  const rows = [...stats.clubs].sort((a, b) => b.totals.xg - b.against.xg - (a.totals.xg - a.against.xg));
  return (
    <div className="stack">
      <p className="muted small">Somente números produzidos pelo motor (por jogo). xG = gols esperados; saldo xG = xG a favor − contra.</p>
      <div className="table-wrap">
        <table className="compact">
          <caption className="visually-hidden">Estatísticas avançadas</caption>
          <thead><tr><th>Clube</th><th className="num">xG/j</th><th className="num">xG contra/j</th><th className="num">Saldo xG</th>
            <th className="num">Gols − xG</th><th className="num">Grandes chances/j</th><th className="num">No alvo %</th>
            <th className="num">Desarmes/j</th><th className="num">Intercept./j</th><th className="num">Defesas/j</th></tr></thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.club_uid} className={c.club_uid === user ? "is-user" : ""}>
                <td><Club uid={c.club_uid} names={names} size={16} user={user} /></td>
                <td className="num">{per(c.totals.xg, c.played)}</td><td className="num">{per(c.against.xg, c.played)}</td>
                <td className="num">{(c.totals.xg - c.against.xg).toFixed(2)}</td>
                <td className="num">{(c.goals_for - c.totals.xg).toFixed(2)}</td>
                <td className="num">{per(c.totals.big_chances, c.played)}</td>
                <td className="num">{c.totals.shots ? `${((100 * c.totals.shots_on_target) / c.totals.shots).toFixed(0)}%` : "—"}</td>
                <td className="num">{per(c.totals.tackles, c.played)}</td><td className="num">{per(c.totals.interceptions, c.played)}</td>
                <td className="num">{per(c.totals.saves_made, c.played)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
