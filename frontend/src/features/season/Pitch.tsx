/**
 * Campo interativo (GDD §9): formação fixa, 11 titulares, até 7 reservas.
 * - Arrastar e soltar (mouse) entre vagas, banco e elenco.
 * - Toque/clique: selecione um atleta e depois o destino para trocar os dois (celular e teclado).
 * - Indicadores de adequação por vaga; lesionados e suspensos não podem ser escalados.
 */
import { useState, type DragEvent } from "react";
import { displayPosition } from "../../domain/positions";
import type { FitLevel, Position, SquadPlayer } from "../../types/api";
import { FIT_LABEL } from "./labels";

/** `pool` com player -1 = área "fora da lista" (retirar um atleta sem colocar outro). */
export type Spot = { zone: "slot"; index: number } | { zone: "bench"; index: number } | { zone: "pool"; player: number };
export const POOL_AREA: Spot = { zone: "pool", player: -1 };

export interface Arrangement {
  formation: Position[];
  starters: (number | null)[];
  bench: number[];
}

const ROW: Record<Position, number> = { GK: 0, DR: 1, DL: 1, DC: 1, DM: 2, MC: 3, STC: 4 };
const ORDER: Record<Position, number> = { DL: 0, DC: 1, DR: 2, GK: 1, DM: 1, MC: 1, STC: 1 };

/** Coordenadas (%) de cada vaga: goleiro embaixo, ataque em cima, lateral esquerdo à esquerda. */
export function slotCoordinates(formation: Position[]): { x: number; y: number }[] {
  const rows = new Map<number, number[]>();
  formation.forEach((p, i) => rows.set(ROW[p], [...(rows.get(ROW[p]) ?? []), i]));
  const out: { x: number; y: number }[] = new Array(formation.length);
  rows.forEach((idx, row) => {
    const sorted = [...idx].sort((a, b) => ORDER[formation[a]] - ORDER[formation[b]] || a - b);
    sorted.forEach((i, k) => {
      out[i] = { x: ((k + 1) / (sorted.length + 1)) * 100, y: 90 - row * 20 };
    });
  });
  return out;
}

/** Aplica a troca entre duas posições (puro, testável). */
export function swap(a: Arrangement, from: Spot, to: Spot, maxBench = 7): Arrangement {
  if (from.zone === "pool" && to.zone === "pool") return a;
  const starters = [...a.starters];
  const bench: (number | null)[] = [...a.bench];
  const read = (s: Spot): number | null =>
    s.zone === "slot" ? starters[s.index] : s.zone === "bench" ? bench[s.index] ?? null : s.player < 0 ? null : s.player;
  // vagas esvaziadas viram null e são removidas no fim (sem deslocar índices durante a troca)
  const write = (s: Spot, v: number | null) => {
    if (s.zone === "slot") starters[s.index] = v;
    else if (s.zone === "bench") {
      if (s.index < bench.length) bench[s.index] = v;
      else if (v != null && bench.filter((x) => x != null).length < maxBench) bench.push(v);
    }
  };
  const va = read(from);
  const vb = read(to);
  if (to.zone === "bench" && to.index >= bench.length && va != null && bench.filter((x) => x != null).length >= maxBench) return a;
  write(to, va);
  write(from, vb);
  return { formation: a.formation, starters, bench: bench.filter((x): x is number => x != null) };
}

const keyOf = (s: Spot) => (s.zone === "pool" ? `pool:${s.player}` : `${s.zone}:${s.index}`);

export function Pitch({ arrangement, squad, locked, onChange }: {
  arrangement: Arrangement;
  squad: SquadPlayer[];
  locked: boolean;
  onChange: (a: Arrangement) => void;
}) {
  const [selected, setSelected] = useState<Spot | null>(null);
  const byId = new Map(squad.map((p) => [p.player, p]));
  const used = new Set([...arrangement.starters.filter((x): x is number => x != null), ...arrangement.bench]);
  const pool = squad.filter((p) => !used.has(p.player));
  const coords = slotCoordinates(arrangement.formation);

  const placeable = (s: Spot) => {
    const id = s.zone === "pool" ? s.player : s.zone === "slot" ? arrangement.starters[s.index] : arrangement.bench[s.index];
    return id == null || byId.get(id)?.available !== false;
  };
  const act = (target: Spot) => {
    if (locked) return;
    if (!selected) {
      if (target.zone === "pool" && !placeable(target)) return;
      setSelected(target);
      return;
    }
    if (keyOf(selected) === keyOf(target)) {
      setSelected(null);
      return;
    }
    // um indisponível só pode sair do time (ir para o elenco), nunca entrar
    const entering = selected.zone === "pool" ? selected : target.zone === "pool" ? target : null;
    if (entering && !placeable(entering) && target.zone !== "pool") {
      setSelected(null);
      return;
    }
    onChange(swap(arrangement, selected, target));
    setSelected(null);
  };
  const drag = (s: Spot) => ({
    draggable: !locked,
    onDragStart: (e: DragEvent) => {
      e.dataTransfer.setData("text/plain", JSON.stringify(s));
      e.dataTransfer.effectAllowed = "move";
    },
  });
  const drop = (target: Spot) => ({
    onDragOver: (e: DragEvent) => {
      if (!locked) e.preventDefault();
    },
    onDrop: (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation(); // o destino mais interno decide (a seção do elenco também é destino)
      try {
        const from = JSON.parse(e.dataTransfer.getData("text/plain")) as Spot;
        if (from.zone === "pool" && byId.get(from.player)?.available === false) return;
        onChange(swap(arrangement, from, target));
      } catch {
        /* arraste de outra origem: ignora */
      }
      setSelected(null);
    },
  });
  const isSel = (s: Spot) => selected != null && keyOf(selected) === keyOf(s);

  return (
    <div className="lineup-board">
      <div className="pitch" role="group" aria-label="Campo: titulares por vaga">
        <div className="pitch__lines" aria-hidden />
        {arrangement.formation.map((pos, i) => {
          const id = arrangement.starters[i];
          const p = id != null ? byId.get(id) : undefined;
          const fit: FitLevel | undefined = p ? (p.fit[pos] as FitLevel) : undefined;
          const s: Spot = { zone: "slot", index: i };
          return (
            <button
              key={i}
              type="button"
              className={`pitch__slot${isSel(s) ? " is-selected" : ""}${fit ? ` fit--${fit}` : " is-empty"}${p && !p.available ? " is-out" : ""}`}
              style={{ left: `${coords[i].x}%`, top: `${coords[i].y}%` }}
              onClick={() => act(s)}
              aria-pressed={isSel(s)}
              aria-label={`Vaga ${displayPosition(pos)}: ${p ? `${p.name}, ${FIT_LABEL[fit!]}${p.available ? "" : ", indisponível"}` : "vazia"}`}
              {...drag(s)}
              {...drop(s)}
            >
              <span className="pitch__pos">{displayPosition(pos)}</span>
              <span className="pitch__name">{p ? p.name : "—"}</span>
              {fit && <span className="pitch__fit">{FIT_LABEL[fit]}</span>}
            </button>
          );
        })}
      </div>
      <div className="lineup-side">
        <section>
          <h4>Reservas ({arrangement.bench.length}/7)</h4>
          <ul className="roster">
            {arrangement.bench.map((id, i) => {
              const p = byId.get(id);
              const s: Spot = { zone: "bench", index: i };
              return (
                <li key={id}>
                  <button type="button" className={`roster__item${isSel(s) ? " is-selected" : ""}${p?.available === false ? " is-out" : ""}`}
                    onClick={() => act(s)} aria-pressed={isSel(s)} {...drag(s)} {...drop(s)}>
                    <span className="tag">{displayPosition((p?.position ?? "MC") as Position)}</span>
                    <span>{p?.name ?? id}</span>
                    {p && !p.available && <span className="pill pill--danger">{p.unavailable_reason}</span>}
                  </button>
                </li>
              );
            })}
            {arrangement.bench.length < 7 && (
              <li>
                <button type="button" className="roster__item roster__item--empty" onClick={() => act({ zone: "bench", index: arrangement.bench.length })}
                  {...drop({ zone: "bench", index: arrangement.bench.length })} disabled={locked}>
                  + Vaga no banco
                </button>
              </li>
            )}
          </ul>
        </section>
        <section {...drop(POOL_AREA)}>
          <div className="lineup-side__head">
            <h4>Fora da lista ({pool.length})</h4>
            {selected && selected.zone !== "pool" && !locked && (
              <button type="button" className="btn btn--ghost btn--small" onClick={() => act(POOL_AREA)}>Retirar selecionado</button>
            )}
          </div>
          <ul className="roster">
            {pool.map((p) => {
              const s: Spot = { zone: "pool", player: p.player };
              return (
                <li key={p.player}>
                  <button type="button" className={`roster__item${isSel(s) ? " is-selected" : ""}${p.available ? "" : " is-out"}`}
                    onClick={() => act(s)} aria-pressed={isSel(s)} aria-disabled={!p.available}
                    {...(p.available ? drag(s) : {})} {...drop(s)}>
                    <span className="tag">{displayPosition(p.position as Position)}</span>
                    <span>{p.name}</span>
                    {!p.available && <span className="pill pill--danger">{p.unavailable_reason}</span>}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
        {selected && !locked && (
          <p className="muted small" role="status">Selecionado: escolha o destino para trocar (ou toque de novo para cancelar).</p>
        )}
      </div>
    </div>
  );
}
