/**
 * Partida (GDD §11, §16): placar, relógio, eventos, estatísticas, postura, condição física, substituições,
 * cartões e lesões. O relógio é do SERVIDOR (não pausa); o cliente só recebe eventos já ocorridos.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import { changePosture, changeSpeed, getLineup, getLive, playRound, startLive } from "../api/endpoints";
import { Notice } from "../components/Notice";
import { displayPosition } from "../domain/positions";
import { Club, EventFeed, StatsCompare } from "../features/season/SeasonParts";
import { POSTURES, SPEEDS, postureLabel } from "../features/season/labels";
import { useCommand } from "../features/season/useCommand";
import { useClubNames, useSeason } from "../features/season/useSeason";
import type { Lineup, LiveState, Position, Speed } from "../types/api";

export function MatchPage({ navigate }: { navigate: (h: string) => void }) {
  const { sid, state, refresh } = useSeason();
  const names = useClubNames();
  const [live, setLive] = useState<LiveState | null>(null);
  const [lineup, setLineup] = useState<Lineup | null>(null);
  const [speed, setSpeed] = useState<Speed>("30s");
  const [pollError, setPollError] = useState<string | null>(null);
  const cmd = useCommand();
  const inflight = useRef(false);

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
        <div className="season-head">
          <h2>Partida</h2>
          <button type="button" className="btn btn--ghost btn--small" onClick={() => navigate("#/escalacao")}>Escalação</button>
        </div>
        <section className="card next-match">
          <div className="versus">
            <Club uid={mine.home_club_uid} names={names} user={user} size={44} />
            <span className="fixture__x">×</span>
            <Club uid={mine.away_club_uid} names={names} user={user} size={44} />
          </div>
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
          <button type="button" className="btn btn--primary" onClick={begin} disabled={cmd.busy}>{cmd.busy ? "Iniciando…" : "Iniciar partida"}</button>
        </section>
      </div>
    );
  }

  const side = live.user_side;
  const myPosture = live.postures[side];
  const setPosture = (p: string) => void cmd.run(async (k) => setLive(await changePosture(sid, p as never, k)));
  const setLiveSpeed = (s: Speed) => void cmd.run(async (k) => setLive(await changeSpeed(sid, s, k)));
  const clock = live.finished ? "Encerrada" : `${live.minute}'`;

  return (
    <div className="stack match">
      <section className="card scoreboard" aria-live="polite" aria-label="Placar">
        <Club uid={live.home_club_uid} names={names} user={user} size={40} />
        <div className="scoreboard__score">
          <strong>{live.score[0]} – {live.score[1]}</strong>
          {live.shootout && <span className="muted small">Pênaltis {live.shootout[0]}–{live.shootout[1]}</span>}
          <span className={`pill${live.finished ? "" : " pill--ok"}`}>{clock}</span>
        </div>
        <Club uid={live.away_club_uid} names={names} user={user} size={40} />
      </section>
      <div className="match-bar" aria-hidden><span style={{ width: `${Math.min(100, (live.game_second / 5400) * 100)}%` }} /></div>
      {pollError && <Notice kind="warning">{pollError} Reconectando… o relógio da partida continua no servidor.</Notice>}
      {cmd.error && <Notice kind="error" onDismiss={() => cmd.setError(null)}>{cmd.error.message}</Notice>}

      <div className="match-grid">
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
          {live.finished && (
            <button type="button" className="btn btn--primary btn--block" onClick={finish} disabled={cmd.busy}>
              {cmd.busy ? "Processando a rodada…" : "Concluir rodada e ver pós-partida"}
            </button>
          )}
        </section>

        <section className="card">
          <h3>Acontecimentos</h3>
          <div className="scroll-y">
            <EventFeed events={[...live.events].reverse().filter((e) => e.type !== "save" || e.minute >= 0)} names={names} />
          </div>
        </section>

        <section className="card">
          <h3>Estatísticas</h3>
          <StatsCompare stats={live.stats} labels={[names.get(live.home_club_uid) ?? "Mandante", names.get(live.away_club_uid) ?? "Visitante"]} />
        </section>

        <section className="card">
          <h3>Condição física · substituições {live.substitutions_used}/{live.max_substitutions}</h3>
          <ul className="condition-list">
            {live.own_players.map((p) => (
              <li key={p.player} className={p.on_field ? "" : "is-off"}>
                <span className="tag">{displayPosition(p.slot as Position)}</span>
                <span className="condition-list__name">{p.name}{p.yellow_cards > 0 ? " 🟨" : ""}{p.on_field ? "" : " (fora)"}</span>
                <span className="condition" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(p.condition)} aria-label={`Condição de ${p.name}`}>
                  <span className={p.condition < 60 ? "is-low" : p.condition < 80 ? "is-mid" : ""} style={{ width: `${p.condition}%` }} />
                </span>
                <span className="num small">{Math.round(p.condition)}%</span>
              </li>
            ))}
          </ul>
          <p className="muted small">Substituições automáticas (até 5) conforme lesões, desgaste e situação do jogo.</p>
        </section>
      </div>
    </div>
  );
}
