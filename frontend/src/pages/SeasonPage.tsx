/**
 * Central principal da temporada (GDD §20–22): próximo confronto, elenco, calendário, classificação ou
 * chaveamento, estatísticas e resultados. Todas as ações chamam os serviços reais.
 */
import { useEffect, useState } from "react";
import { advanceRound, getCalendar, getLineup, getSquad, playRound, startSeason } from "../api/endpoints";
import { Jumbotron } from "../features/match/LiveParts";
import { ActionBar, Drawer, PhaseBanner } from "../components/GameUi";
import { Notice } from "../components/Notice";
import { PositionBadge } from "../components/PlayerCard";
import { byPosition } from "../domain/positions";
import { Club, BracketView, FixtureList, StandingsTable } from "../features/season/SeasonParts";
import { StatsCenter } from "../features/season/StatsCenter";
import { postureLabel } from "../features/season/labels";
import { useCommand } from "../features/season/useCommand";
import { useClubNames, useSeason } from "../features/season/useSeason";
import type { Calendar, Lineup, SeasonFixture, SeasonState, SquadPlayer } from "../types/api";

export type SeasonTab = "central" | "elenco" | "calendario" | "classificacao" | "estatisticas" | "resultados";
/** Painéis da central (abrem sobre a central, sem trocar de tela). */
const TABS: { id: Exclude<SeasonTab, "central">; label: string; icon: string; hint: string }[] = [
  { id: "elenco", label: "Meu elenco", icon: "👥", hint: "Situação e números" },
  { id: "calendario", label: "Calendário", icon: "📅", hint: "Todas as rodadas" },
  { id: "classificacao", label: "Classificação", icon: "🏆", hint: "Tabela completa" },
  { id: "estatisticas", label: "Estatísticas", icon: "📊", hint: "Rankings da temporada" },
  { id: "resultados", label: "Resultados", icon: "📋", hint: "Histórico de partidas" },
];

export function SeasonPage({ tab, navigate }: { tab: SeasonTab; navigate: (hash: string) => void }) {
  const { sid, state, setState, notStarted, error, refresh } = useSeason();
  const names = useClubNames();
  const cmd = useCommand();

  if (!sid) {
    return (
      <Notice kind="info" title="Temporada indisponível">
        A Liga ou Copa começa depois do leilão e do mercado de negociações.{" "}
        <button type="button" className="btn btn--small btn--ghost" onClick={() => navigate("#/session")}>Ver competição</button>
      </Notice>
    );
  }
  if (notStarted) {
    return (
      <div className="stack">
        <PhaseBanner kicker="Etapa 4" title="Tudo pronto para a temporada">
          Os elencos estão fechados. Comece a Liga/Copa e dispute o primeiro confronto.
        </PhaseBanner>
        {cmd.error && <Notice kind="error">{cmd.error.message}</Notice>}
        <ActionBar>
          <button type="button" className="btn btn--cta" disabled={cmd.busy}
            onClick={() => void cmd.run(async (k) => { setState(await startSeason(sid, k)); await refresh(); })}>
            {cmd.busy ? "Iniciando…" : "Iniciar competição ▶"}
          </button>
        </ActionBar>
      </div>
    );
  }
  if (!state) return <p className="muted" role="status">{error ?? "Carregando competição…"}</p>;

  const label = state.kind === "cup" ? "Chaveamento" : "Classificação";
  const panel = TABS.find((t) => t.id === tab);
  const close = () => navigate("#/temporada/central");
  const progress = state.phase === "finished" ? `${state.total_rounds} rodadas` : `rodada ${state.round_number} de ${state.total_rounds}`;
  return (
    <div className="stack">
      <PhaseBanner kicker={`${state.kind === "cup" ? "Copa" : "Liga"} · ${progress}`} title={state.phase === "finished" ? "Temporada encerrada" : state.round_label} />
      <nav className="hub-tiles" aria-label="Central da competição">
        {TABS.map((t) => (
          <button key={t.id} type="button" className="hub-tile" onClick={() => navigate(`#/temporada/${t.id}`)} aria-current={tab === t.id ? "page" : undefined}>
            <span className="hub-tile__icon" aria-hidden>{t.icon}</span>
            <strong>{t.id === "classificacao" ? label : t.label}</strong>
            <span>{t.hint}</span>
          </button>
        ))}
      </nav>
      {error && <Notice kind="warning">{error} Tentando sincronizar…</Notice>}
      <NextMatch sid={sid} state={state} names={names} navigate={navigate} onChange={(s) => { setState(s); void refresh(); }} />
      {panel && (
        <Drawer title={panel.id === "classificacao" ? label : panel.label} onClose={close}>
          {tab === "elenco" && <SquadView sid={sid} />}
          {tab === "calendario" && <CalendarView sid={sid} state={state} names={names} navigate={navigate} />}
          {tab === "classificacao" && <TableView sid={sid} state={state} names={names} navigate={navigate} />}
          {tab === "estatisticas" && <StatsCenter sid={sid} state={state} names={names} />}
          {tab === "resultados" && <ResultsView sid={sid} state={state} names={names} navigate={navigate} />}
        </Drawer>
      )}
    </div>
  );
}

function NextMatch({ sid, state, names, navigate, onChange }: {
  sid: string; state: SeasonState; names: Map<number, string>; navigate: (h: string) => void; onChange: (s: SeasonState) => void;
}) {
  const [lineup, setLineup] = useState<Lineup | null>(null);
  const cmd = useCommand();
  useEffect(() => {
    setLineup(null);
    if (state.phase !== "finished") getLineup(sid).then(setLineup).catch(() => undefined);
  }, [sid, state.phase, state.round_number]);

  const user = state.user_club_uid;
  const mine = state.fixtures.find((f) => f.is_user_match);
  const play = () => void cmd.run(async (k) => onChange(await playRound(sid, k)));
  const advance = () => void cmd.run(async (k) => onChange(await advanceRound(sid, k)));

  if (state.phase === "finished") {
    return (
      <section className="card hero">
        <h3>Competição encerrada</h3>
        {state.champion_club_uid != null ? (
          <p>Campeão: <Club uid={state.champion_club_uid} names={names} user={user} /></p>
        ) : (
          <Notice kind="warning" title="Campeão indefinido">Empate no topo não resolvido pelos critérios de desempate.</Notice>
        )}
        <ActionBar>
          <button type="button" className="btn btn--cta" onClick={() => navigate("#/encerramento")}>Ver encerramento e premiações ▶</button>
        </ActionBar>
      </section>
    );
  }

  return (
    <div className="stack">
      {cmd.error && (
        <Notice kind="error" title={cmd.error.code === "ROUND_FAILED" ? "A rodada não foi consolidada" : undefined}>
          {cmd.error.message}
          {cmd.error.code === "ROUND_FAILED" && " Nenhum resultado foi aplicado. Tente de novo: só as partidas que falharam serão repetidas."}
        </Notice>
      )}
      {state.failed_matches.length > 0 && !cmd.error && (
        <Notice kind="warning" title="Rodada pendente">
          {state.failed_matches.length} partida(s) falharam na última tentativa; nada foi consolidado.
        </Notice>
      )}
      {state.user_eliminated && <Notice kind="info" title="Seu clube foi eliminado">A Copa continua até a final entre os outros clubes. O avanço segue manual.</Notice>}

      {state.phase === "ready" && mine && lineup?.has_match && (
        <section className="card next-match">
          <span className="muted small">Seu próximo jogo · {state.round_label}{lineup.is_home == null ? " · campo neutro" : lineup.is_home ? " · em casa" : " · fora"}</span>
          <Jumbotron home={mine.home_club_uid} away={mine.away_club_uid} names={names} user={user} label="VS" />
          <p className="muted small">
            {lineup.formation} · postura inicial {postureLabel(lineup.posture ?? "equilibrada")} · escalação {lineup.source === "user" ? "sua" : "sugerida automaticamente"}
          </p>
          {lineup.note && <Notice kind="warning" title="Sua escalação precisou ser refeita">{lineup.note}</Notice>}
          <ActionBar>
            {!lineup.locked && <button type="button" className="btn btn--ghost" onClick={() => navigate("#/partida")}>Jogar com esta escalação</button>}
            <button type="button" className="btn btn--cta" onClick={() => navigate(lineup.locked ? "#/partida" : "#/escalacao")}>
              {lineup.locked ? "Voltar à partida ▶" : "Escalar e jogar ▶"}
            </button>
          </ActionBar>
          {lineup.opponent && (
            <details>
              <summary>Adversário: informações públicas</summary>
              <OpponentInfo lineup={lineup} names={names} />
            </details>
          )}
        </section>
      )}

      {state.phase === "ready" && !mine && (
        <section className="card">
          <h3>{state.round_label}</h3>
          <p className="muted">{state.byes.includes(user) ? "Seu clube folga nesta rodada." : "Seu clube não disputa esta fase."} Os demais confrontos serão simulados em paralelo.</p>
          <ActionBar>
            <button type="button" className="btn btn--cta" onClick={play} disabled={cmd.busy}>{cmd.busy ? "Simulando…" : "Simular rodada ▶"}</button>
          </ActionBar>
        </section>
      )}

      {state.phase === "ready" && mine && state.failed_matches.length > 0 && (
        <button type="button" className="btn btn--primary" onClick={play} disabled={cmd.busy}>{cmd.busy ? "Repetindo…" : "Repetir partidas que falharam"}</button>
      )}

      {state.phase === "awaiting_advance" && (
        <section className="card">
          <h3>Resultados · {state.round_label}</h3>
          <FixtureList fixtures={state.fixtures} names={names} user={user} onOpen={(id) => navigate(`#/pos/${id}`)} />
          {state.byes.length > 0 && <p className="muted small">Folga: {state.byes.map((b) => names.get(b) ?? b).join(", ")}</p>}
          <ActionBar>
            {mine && <button type="button" className="btn btn--ghost" onClick={() => navigate(`#/pos/${mine.match_id}`)}>Pós-partida</button>}
            <button type="button" className="btn btn--cta" onClick={advance} disabled={cmd.busy}>
              {state.round_number >= state.total_rounds ? "Encerrar competição ▶" : "Próximo confronto ▶"}
            </button>
          </ActionBar>
        </section>
      )}

      {state.kind === "league" && state.standings.length > 0 && (
        <section className="card">
          <h3>Classificação</h3>
          <StandingsTable rows={state.standings} names={names} user={user} compact />
        </section>
      )}
    </div>
  );
}

export function OpponentInfo({ lineup, names }: { lineup: Lineup; names: Map<number, string> }) {
  const o = lineup.opponent!;
  const c = o.campaign;
  return (
    <div className="stack small">
      <p><Club uid={o.club_uid} names={names} /> · {c.played} jogos: {c.wins}V {c.draws}E {c.losses}D · {c.goals_for} gols marcados, {c.goals_against} sofridos</p>
      {o.previous_formations.length > 0 && <p>Formações anteriores: {o.previous_formations.join(", ")}</p>}
      {o.top_players.length > 0 && <p>Destaques: {o.top_players.map((p) => `${p.name} (${p.value} gols)`).join(", ")}</p>}
      {c.matches.length > 0 && (
        <p>Últimos resultados: {c.matches.slice(-5).map((m) => {
          const oppo = m.home_club_uid === o.club_uid ? m.away_club_uid : m.home_club_uid;
          return `${m.score?.join("–")} vs ${names.get(oppo) ?? oppo}`;
        }).join(" · ")}</p>
      )}
    </div>
  );
}

function SquadView({ sid }: { sid: string }) {
  const [squad, setSquad] = useState<SquadPlayer[] | null>(null);
  useEffect(() => {
    getSquad(sid).then(setSquad).catch(() => setSquad([]));
  }, [sid]);
  if (!squad) return <p className="muted" role="status">Carregando elenco…</p>;
  return (
    <section className="card">
      <h3>Meu elenco ({squad.length})</h3>
      <div className="table-wrap">
        <table>
          <caption className="visually-hidden">Meu elenco</caption>
          <thead>
            <tr><th>Pos.</th><th>Jogador</th><th className="num">Idade</th><th>Situação</th><th className="num">J</th><th className="num">Gols</th>
              <th className="num">Assist.</th><th className="num">Média</th><th className="num">Craque</th><th className="num">CA</th><th className="num">CV</th></tr>
          </thead>
          <tbody>
            {byPosition(squad, (p) => p.position).map((p) => (
              <tr key={p.player}>
                <td><PositionBadge position={p.position} size="sm" /></td>
                <td className="player-name">{p.name}</td>
                <td className="num">{p.age ?? "—"}</td>
                <td>{p.available ? <span className="pill pill--ok">Apto</span> : <span className="pill pill--danger">{p.unavailable_reason}</span>}</td>
                <td className="num">{p.appearances}</td><td className="num">{p.goals}</td><td className="num">{p.assists}</td>
                <td className="num">{p.average_rating != null ? p.average_rating.toFixed(2) : "—"}</td>
                <td className="num">{p.motm}</td><td className="num">{p.yellow_cards}</td><td className="num">{p.red_cards}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function useCalendar(sid: string, state: SeasonState) {
  const [cal, setCal] = useState<Calendar | null>(null);
  const played = state.fixtures.filter((f) => f.played).length;
  useEffect(() => {
    getCalendar(sid).then(setCal).catch(() => undefined);
  }, [sid, state.round_number, state.phase, played]);
  return cal;
}

function CalendarView({ sid, state, names, navigate }: { sid: string; state: SeasonState; names: Map<number, string>; navigate: (h: string) => void }) {
  const cal = useCalendar(sid, state);
  const [onlyMine, setOnlyMine] = useState(false);
  if (!cal) return <p className="muted" role="status">Carregando calendário…</p>;
  return (
    <section className="card">
      <div className="toolbar toolbar--center">
        <h3>Calendário</h3>
        <label className="check"><input type="checkbox" checked={onlyMine} onChange={(e) => setOnlyMine(e.target.checked)} /> Somente meus jogos</label>
      </div>
      {cal.rounds.map((r) => {
        const fx = onlyMine ? r.fixtures.filter((f) => f.is_user_match) : r.fixtures;
        if (fx.length === 0 && onlyMine) return null;
        return (
          <div key={r.number} className={`cal-round${r.number === cal.current_round ? " is-current" : ""}`}>
            <h4>{r.label}{r.number === cal.current_round && state.phase !== "finished" ? " · atual" : ""}</h4>
            {fx.length > 0 ? <FixtureList fixtures={fx} names={names} user={state.user_club_uid} onOpen={(id) => navigate(`#/pos/${id}`)} />
              : <p className="muted small">Confrontos definidos após a fase anterior.</p>}
            {r.byes.length > 0 && !onlyMine && <p className="muted small">Folga: {r.byes.map((b) => names.get(b) ?? b).join(", ")}</p>}
          </div>
        );
      })}
    </section>
  );
}

function TableView({ sid, state, names, navigate }: { sid: string; state: SeasonState; names: Map<number, string>; navigate: (h: string) => void }) {
  const cal = useCalendar(sid, state);
  if (state.kind === "league") {
    return (
      <section className="card">
        <h3>Classificação</h3>
        <StandingsTable rows={state.standings} names={names} user={state.user_club_uid} />
        <p className="muted small">Pontuação {state.points_system?.win}/{state.points_system?.draw}/{state.points_system?.loss} (vitória/empate/derrota). Desempate: vitórias, saldo de gols, gols pró, confronto direto (entre dois clubes), menos cartões vermelhos, menos cartões amarelos e sorteio. Atualizada somente após a rodada completa.</p>
      </section>
    );
  }
  const fixtures = new Map<string, SeasonFixture>((cal?.rounds ?? []).flatMap((r) => r.fixtures).map((f) => [f.match_id, f]));
  return (
    <section className="card">
      <h3>Chaveamento</h3>
      {state.bracket && <BracketView bracket={state.bracket} fixtures={fixtures} names={names} user={state.user_club_uid} onOpen={(id) => navigate(`#/pos/${id}`)} />}
    </section>
  );
}

function ResultsView({ sid, state, names, navigate }: { sid: string; state: SeasonState; names: Map<number, string>; navigate: (h: string) => void }) {
  const cal = useCalendar(sid, state);
  const [onlyMine, setOnlyMine] = useState(false);
  const [club, setClub] = useState<number | "">("");
  if (!cal) return <p className="muted" role="status">Carregando resultados…</p>;
  const played = cal.rounds.flatMap((r) => r.fixtures.filter((f) => f.played)).reverse();
  const clubs = [...new Set(played.flatMap((f) => [f.home_club_uid, f.away_club_uid]))];
  const shown = played.filter((f) => (!onlyMine || f.is_user_match) && (club === "" || f.home_club_uid === club || f.away_club_uid === club));
  return (
    <section className="card">
      <div className="toolbar toolbar--center">
        <h3>Histórico de partidas ({played.length})</h3>
        <label className="check"><input type="checkbox" checked={onlyMine} onChange={(e) => setOnlyMine(e.target.checked)} /> Somente meus jogos</label>
        <label className="field field--inline">Clube
          <select value={club} onChange={(e) => setClub(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Todos</option>
            {clubs.map((c) => <option key={c} value={c}>{names.get(c) ?? c}</option>)}
          </select>
        </label>
      </div>
      {shown.length === 0 ? <p className="muted">Nenhuma partida concluída ainda.</p>
        : <FixtureList fixtures={shown} names={names} user={state.user_club_uid} onOpen={(id) => navigate(`#/pos/${id}`)} />}
      <p className="muted small">Cada partida guarda eventos, estatísticas, escalações, posturas observáveis e avaliações.</p>
    </section>
  );
}
