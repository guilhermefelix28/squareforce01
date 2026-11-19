/** Escalação e preparação tática (GDD §9): formação, titulares, reservas, adequação e postura inicial. */
import { useEffect, useMemo, useState } from "react";
import { getLineup, getSquad, saveLineup } from "../api/endpoints";
import { ActionBar, PhaseBanner } from "../components/GameUi";
import { Notice } from "../components/Notice";
import { Pitch, type Arrangement } from "../features/season/Pitch";
import { POSTURES } from "../features/season/labels";
import { useCommand } from "../features/season/useCommand";
import { useClubNames, useSeason } from "../features/season/useSeason";
import { OpponentInfo } from "./SeasonPage";
import type { Lineup, Position, Posture, SquadPlayer } from "../types/api";

export function LineupPage({ navigate }: { navigate: (h: string) => void }) {
  const { sid, state } = useSeason();
  const names = useClubNames();
  const [lineup, setLineup] = useState<Lineup | null>(null);
  const [squad, setSquad] = useState<SquadPlayer[]>([]);
  const [arr, setArr] = useState<Arrangement | null>(null);
  const [posture, setPosture] = useState<Posture>("equilibrada");
  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const cmd = useCommand();

  const apply = (l: Lineup) => {
    setLineup(l);
    if (l.has_match && l.formation) {
      const f = l.formations.find((x) => x.id === l.formation);
      setArr({ formation: (f?.positions ?? (l.starters ?? []).map((s) => s.position)) as Position[], starters: (l.starters ?? []).map((s) => s.player), bench: (l.bench ?? []).map((b) => b.player) });
      setPosture((l.posture ?? "equilibrada") as Posture);
    }
    setDirty(false);
  };

  useEffect(() => {
    if (!sid) return;
    Promise.all([getLineup(sid), getSquad(sid)])
      .then(([l, s]) => {
        apply(l);
        setSquad(s);
      })
      .catch((e) => setLoadError(e?.message ?? "Falha ao carregar a escalação."));
  }, [sid, state?.round_number]);

  const missing = arr ? arr.starters.filter((x) => x == null).length : 0;
  const blocked = useMemo(() => {
    if (!arr) return [];
    const byId = new Map(squad.map((p) => [p.player, p]));
    return [...arr.starters, ...arr.bench].filter((id): id is number => id != null && byId.get(id)?.available === false);
  }, [arr, squad]);

  if (!sid) return <Notice kind="info">A escalação fica disponível durante a competição.</Notice>;
  if (loadError) return <Notice kind="error">{loadError}</Notice>;
  if (!lineup || !arr) return <p className="muted" role="status">Carregando escalação…</p>;
  if (!lineup.has_match) {
    return (
      <Notice kind="info" title="Sem partida nesta rodada">
        Seu clube folga, foi eliminado ou a competição terminou.{" "}
        <button type="button" className="btn btn--small btn--ghost" onClick={() => navigate("#/temporada/central")}>Voltar à central</button>
      </Notice>
    );
  }

  const changeFormation = (id: string) => {
    const f = lineup.formations.find((x) => x.id === id);
    if (!f) return;
    // mantém os mesmos atletas nas vagas (a adequação de cada um é recalculada para a nova posição)
    setArr({ ...arr, formation: f.positions as Position[] });
    setDirty(true);
  };
  const formationId = lineup.formations.find((f) => f.positions.join() === arr.formation.join())?.id ?? lineup.formation ?? "";
  const ready = !lineup.locked && missing === 0 && blocked.length === 0;

  const save = (then?: () => void) =>
    void cmd.run(async (k) => {
      const l = await saveLineup(sid, { formation: formationId, starters: arr.starters as number[], bench: arr.bench, posture }, k);
      apply(l);
      setSaved(true);
      then?.();
    });
  const play = () => (dirty ? save(() => navigate("#/partida")) : navigate("#/partida"));

  return (
    <div className="stack">
      <PhaseBanner kicker={state?.round_label ?? "Escalação"} title="Escalação e tática">
        Arraste os jogadores pelo campinho. Leve um titular para outra linha e a formação muda sozinha.
      </PhaseBanner>
      {lineup.locked && <Notice kind="info" title="Escalação fechada">A partida já começou: durante o jogo a formação é fixa e só a postura pode mudar.</Notice>}
      {lineup.note && <Notice kind="warning" title="Sua escalação anterior não pôde ser usada">{lineup.note}</Notice>}
      {cmd.error && <Notice kind="error" title="Escalação não salva">{cmd.error.message}</Notice>}
      {saved && !dirty && !cmd.error && <Notice kind="success" onDismiss={() => setSaved(false)}>Escalação salva no servidor.</Notice>}

      <section className="card lineup-controls">
        <label className="field">Formação
          <select value={formationId} disabled={lineup.locked} onChange={(e) => changeFormation(e.target.value)}>
            {lineup.formations.map((f) => <option key={f.id} value={f.id}>{f.id}</option>)}
          </select>
        </label>
        <fieldset className="segmented segmented--wrap" disabled={lineup.locked}>
          <legend>Postura inicial</legend>
          {POSTURES.map((p) => (
            <label key={p.id} className={posture === p.id ? "is-on" : ""}>
              <input type="radio" name="posture" value={p.id} checked={posture === p.id} onChange={() => { setPosture(p.id); setDirty(true); }} />
              {p.label}
            </label>
          ))}
        </fieldset>
        <ul className="fit-legend" aria-label="Legenda de adequação">
          <li className="fit--natural">Natural</li><li className="fit--boa">Boa</li><li className="fit--regular">Regular</li><li className="fit--improvisada">Improvisado</li>
        </ul>
      </section>

      <Pitch arrangement={arr} squad={squad} locked={lineup.locked} formations={lineup.formations}
        onChange={(a) => { setArr(a); setDirty(true); }} />

      {missing > 0 && <Notice kind="warning">Faltam {missing} titular(es) para completar as 11 vagas.</Notice>}
      {blocked.length > 0 && <Notice kind="error">Há atletas indisponíveis na lista: retire-os antes de salvar.</Notice>}

      {lineup.opponent && (
        <section className="card">
          <h3>Próximo adversário</h3>
          <OpponentInfo lineup={lineup} names={names} />
        </section>
      )}

      <ActionBar hint={`${formationId}${dirty ? " · alterações não salvas" : ""}`}>
        <button type="button" className="btn btn--ghost" onClick={() => navigate("#/temporada/central")}>← Central</button>
        <button type="button" className="btn btn--ghost" disabled={!ready || cmd.busy || !dirty} onClick={() => save()}>
          {cmd.busy ? "Salvando…" : dirty ? "Salvar escalação" : "Escalação salva"}
        </button>
        <button type="button" className="btn btn--cta" disabled={lineup.locked ? false : !ready || cmd.busy} onClick={lineup.locked ? () => navigate("#/partida") : play}>
          {lineup.locked ? "Voltar à partida ▶" : dirty ? "Salvar e jogar ▶" : "Ir para o jogo ▶"}
        </button>
      </ActionBar>
    </div>
  );
}
