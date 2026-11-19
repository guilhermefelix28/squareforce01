/**
 * Partida ao vivo (GDD §11, §16; DR-06): telão, campo tático das duas equipes, outros jogos da rodada, narração,
 * estatísticas, postura, condição física e substituições. O relógio é do SERVIDOR (não pausa); o cliente só
 * recebe eventos já ocorridos. Som da torcida nos gols (pode ser desligado na barra superior).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import { changePosture, changeSpeed, getLineup, getLive, playRound, startLive } from "../api/endpoints";
import { playGoal, playWhistle, preloadGoal } from "../audio/crowd";
import { ActionBar, PhaseBanner } from "../components/GameUi";
import { Notice } from "../components/Notice";
import { PositionBadge } from "../components/PlayerCard";
import { Jumbotron, LivePitch, OtherMatches } from "../features/match/LiveParts";
import { StatsCompare } from "../features/season/SeasonParts";
import { EVENT_ICON, POSTURES, SPEEDS, describeEvent, eventLabel, postureLabel } from "../features/season/labels";
import { useCommand } from "../features/season/useCommand";
import { useClubNames, useSeason } from "../features/season/useSeason";
import type { Lineup, LiveState, Speed } from "../types/api";

const KEY_EVENTS = new Set(["goal", "red_card", "penalty_awarded", "injury", "yellow_card", "substitution", "posture_change", "half_time", "full_time",
  "shootout_start", "shootout_kick", "shootout_end"]);

/** Numera as cobranças de cada time (1ª, 2ª, ...) para narrar a disputa de pênaltis lance a lance. */
export function numberKicks<T extends { type: string; side?: number | null; data?: Record<string, unknown> }>(events: T[]): T[] {
  const count = [0, 0];
  return events.map((e) => {
    if (e.type !== "shootout_kick" || e.side == null) return e;
    count[e.side] += 1;
    return { ...e, data: { ...(e.data ?? {}), kick: count[e.side] } };
  });
}

/** Efeitos de torcida/apito quando o placar ou o estado mudam (não toca ao reconectar no meio do jogo). */
function useMatchSounds(live: LiveState | null) {
  const prev = useRef<{ id: string; score: number[]; finished: boolean } | null>(null);
  const [burst, setBurst] = useState<"us" | "them" | null>(null);
  useEffect(() => {
    if (!live) return;
    const p = prev.current;
    prev.current = { id: live.match_id, score: [...live.score], finished: live.finished };
    if (!p || p.id !== live.match_id) {
      if (live.minute <= 1 && !live.finished) playWhistle(1);
      return;
    }
    for (const side of [0, 1]) {
      if (live.score[side] > p.score[side]) {
        const ours = side === live.user_side;
        playGoal(ours);
        setBurst(ours ? "us" : "them");
      }
    }
    if (live.finished && !p.finished) playWhistle(3);
  }, [live]);
  useEffect(() => {
    if (!burst) return;
    const t = setTimeout(() => setBurst(null), 1800);
    return () => clearTimeout(t);
  }, [burst]);
  return burst;
}

export function MatchPage({ navigate }: { navigate: (h: string) => void }) {
  const { sid, state, refresh } = useSeason();
  const names = useClubNames();
  const [live, setLive] = useState<LiveState | null>(null);
  const [lineup, setLineup] = useState<Lineup | null>(null);
  const [speed, setSpeed] = useState<Speed>("30s");
  const [pollError, setPollError] = useState<string | null>(null);
  const cmd = useCommand();
  const inflight = useRef(false);
  const burst = useMatchSounds(live);
  useEffect(() => preloadGoal(), []);

  const poll = useCallback(async () => {
    if (!sid || inflight.current) return;
    inflight.current = true;
    try {
      setLive(await getLive(sid));
      setPollError(null);
    } catch (e) {
      if (e instanceof ApiError && e.code === "LIVE_NOT_FOUND") setLive(null);
      else setPollError(e instanceof ApiError ? e.message : "Sem conexão com o servidor.");
    } finally {
      inflight.current = false;
    }
  }, [sid]);

  useEffect(() => {
    if (!sid) return;
    void poll();
    getLineup(sid).then(setLineup).catch(() => undefined);
  }, [sid, poll, state?.round_number]);

  const running = !!live && !live.finished;
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => void poll(), 400);
    return () => clearInterval(t);
  }, [running, poll]);

  if (!sid || !state) return <p className="muted" role="status">Carregando…</p>;
  const user = state.user_club_uid;
  const mine = state.fixtures.find((f) => f.is_user_match);

  if (state.phase === "awaiting_advance" && mine) {
    return (
      <Notice kind="info" title="Partida encerrada">
        <button type="button" className="btn btn--small btn--primary" onClick={() => navigate(`#/pos/${mine.match_id}`)}>Ver pós-partida</button>
      </Notice>
    );
  }
  if (!mine || state.phase !== "ready") {
    return (
      <Notice kind="info" title="Nenhuma partida sua agora">
        <button type="button" className="btn btn--small btn--ghost" onClick={() => navigate("#/temporada/central")}>Voltar à central</button>
      </Notice>
    );
  }

  const begin = () => void cmd.run(async (k) => setLive(await startLive(sid, speed, k)));
  const finish = () =>
    void cmd.run(async (k) => {
      await playRound(sid, k);
      await refresh();
      navigate(`#/pos/${mine.match_id}`);
    });

  if (!live) {
    return (
      <div className="stack">
        <PhaseBanner kicker={state.round_label} title="Dia de jogo" />
        <section className="card next-match">
          <Jumbotron home={mine.home_club_uid} away={mine.away_club_uid} names={names} user={user} label="VS" />
          {lineup?.has_match && <p className="muted small">{lineup.formation} · postura inicial {postureLabel(lineup.posture ?? "equilibrada")}</p>}
          <fieldset className="segmented segmented--wrap">
            <legend>Velocidade de apresentação</legend>
            {SPEEDS.map((s) => (
              <label key={s.id} className={speed === s.id ? "is-on" : ""}>
                <input type="radio" name="speed" value={s.id} checked={speed === s.id} onChange={() => setSpeed(s.id)} />
                {s.label}
              </label>
            ))}
          </fieldset>
          <p className="muted small">A velocidade muda só a apresentação: com as mesmas decisões, os acontecimentos são idênticos. O relógio não pausa.</p>
          {cmd.error && <Notice kind="error">{cmd.error.message}</Notice>}
        </section>
        <ActionBar>
          <button type="button" className="btn btn--ghost" onClick={() => navigate("#/escalacao")}>Escalação</button>
          <button type="button" className="btn btn--cta" onClick={begin} disabled={cmd.busy}>{cmd.busy ? "Entrando em campo…" : "Iniciar partida ▶"}</button>
        </ActionBar>
      </div>
    );
  }

  const side = live.user_side;
  const myPosture = live.postures[side];
  const setPosture = (p: string) => void cmd.run(async (k) => setLive(await changePosture(sid, p as never, k)));
  const setLiveSpeed = (s: Speed) => void cmd.run(async (k) => setLive(await changeSpeed(sid, s, k)));
  const ownOnPitch = live.own_players;
  const oppOnPitch = live.opponent_players ?? [];
  const homePlayers = side === 0 ? ownOnPitch : oppOnPitch;
  const awayPlayers = side === 0 ? oppOnPitch : ownOnPitch;
  const feed = numberKicks(live.events).reverse().filter((e) => KEY_EVENTS.has(e.type));

  return (
    <div className="stack match">
      {burst && (
        <div className={`goal-burst${burst === "them" ? " goal-burst--them" : ""}`} aria-hidden>
          <span>{burst === "us" ? "GOOOL!" : "Gol do adversário"}</span>
        </div>
      )}
      <Jumbotron home={live.home_club_uid} away={live.away_club_uid} names={names} user={user} score={live.score}
        minute={`${live.minute}'`} finished={live.finished} shootout={live.shootout} flash={!!burst} />
      <div className="match-bar" aria-hidden><span style={{ width: `${Math.min(100, (live.game_second / 5400) * 100)}%` }} /></div>
      {pollError && <Notice kind="warning">{pollError} Reconectando… o relógio da partida continua no servidor.</Notice>}
      {cmd.error && <Notice kind="error" onDismiss={() => cmd.setError(null)}>{cmd.error.message}</Notice>}

      <section className="card live-feed" aria-label="Lance a lance">
        <h3>Lance a lance</h3>
        {feed.length === 0 ? <p className="muted small">A bola vai rolar…</p> : (
          <ol className="feed">
            {feed.map((e) => (
              <li key={e.seq} className={e.type === "goal" || (e.type === "shootout_kick" && e.data?.scored) ? "is-goal"
                : ["penalty_awarded", "red_card", "shootout_kick", "shootout_start", "shootout_end"].includes(e.type) ? "is-key" : ""}>
                <span className="feed__min">{e.type === "shootout_kick" ? "pên." : `${e.minute}'`}</span>
                <span aria-hidden>{EVENT_ICON[e.type] ?? "•"}</span>
                <span>
                  <strong>{eventLabel(e.type)}</strong> {describeEvent(e)}
                  {e.club_uid != null && <span className="muted small"> · {names.get(e.club_uid) ?? ""}</span>}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>
      <div className="live-layout">
        <aside className="live-left">
          <section className="card">
            <h3>Condição física</h3>
            <span className="muted small">Substituições {live.substitutions_used}/{live.max_substitutions} (automáticas)</span>
            <ul className="condition-list">
              {live.own_players.map((p) => (
                <li key={p.player} className={p.on_field ? "" : "is-off"}>
                  <PositionBadge position={p.slot} size="sm" />
                  <span className="condition-list__name">{p.name}{p.yellow_cards > 0 ? " 🟨" : ""}{p.on_field ? "" : " (fora)"}</span>
                  <span className="condition" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(p.condition)} aria-label={`Condição de ${p.name}`}>
                    <span className={p.condition < 60 ? "is-low" : p.condition < 80 ? "is-mid" : ""} style={{ width: `${p.condition}%` }} />
                  </span>
                  <span className="num small">{Math.round(p.condition)}%</span>
                </li>
              ))}
            </ul>
          </section>
        </aside>
        <div className="live-main">
          <section className="card">
            <h3>Sua postura</h3>
            <div className="posture-buttons" role="group" aria-label="Postura tática">
              {POSTURES.map((p) => (
                <button key={p.id} type="button" className={`btn btn--small${myPosture === p.id ? " btn--primary" : " btn--ghost"}`}
                  aria-pressed={myPosture === p.id} disabled={live.finished || cmd.busy || myPosture === p.id} onClick={() => setPosture(p.id)}>
                  {p.label}
                </button>
              ))}
            </div>
            <p className="muted small">Adversário: {postureLabel(live.postures[1 - side])}. A mudança vale a partir do lance seguinte; a formação é fixa.</p>
            <div className="speed-row">
              <span className="muted small">Velocidade</span>
              {SPEEDS.map((s) => (
                <button key={s.id} type="button" className={`btn btn--small${live.speed === s.id ? " btn--primary" : " btn--ghost"}`}
                  aria-pressed={live.speed === s.id} disabled={live.finished || cmd.busy || live.speed === s.id} onClick={() => setLiveSpeed(s.id)}>
                  {s.label}
                </button>
              ))}
            </div>
          </section>
          <section className="card">
            <LivePitch home={homePlayers} away={awayPlayers}
              homeName={names.get(live.home_club_uid) ?? "Mandante"} awayName={names.get(live.away_club_uid) ?? "Visitante"}
              homeUid={live.home_club_uid} awayUid={live.away_club_uid} userSide={side} />
          </section>
        </div>
        <aside className="live-side">
          <section className="card">
            <h3>Outros jogos</h3>
            <OtherMatches matches={live.other_matches ?? []} names={names} />
          </section>
          <section className="card">
            <h3>Estatísticas</h3>
            <StatsCompare stats={live.stats} uids={[live.home_club_uid, live.away_club_uid]} labels={[names.get(live.home_club_uid) ?? "Mandante", names.get(live.away_club_uid) ?? "Visitante"]} />
          </section>
        </aside>
      </div>
      {live.finished && (
        <ActionBar hint="Fim de jogo">
          <button type="button" className="btn btn--cta" onClick={finish} disabled={cmd.busy}>
            {cmd.busy ? "Processando a rodada…" : "Concluir rodada e ver pós-partida ▶"}
          </button>
        </ActionBar>
      )}
    </div>
  );
}
