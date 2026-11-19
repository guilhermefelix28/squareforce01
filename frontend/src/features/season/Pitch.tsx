/**
 * Campo interativo (GDD §9): 11 titulares, até 7 reservas.
 * - Arrastar e soltar (mouse: drag nativo; toque: Pointer Events) entre vagas, banco e elenco.
 * - O campo tem faixas por função (GOL, DEF, VOL, ME, ATA). Arrastar um titular para OUTRA FAIXA muda o desenho;
 *   se o novo desenho for uma das 11 formações oficiais, a formação é trocada automaticamente (aviso
 *   "Formação: 4-3-1-2"); senão a carta volta. Durante o arraste as faixas ficam visíveis com o nome.
 * - Toque/clique: selecione um atleta e depois o destino para trocar os dois (celular e teclado).
 * - As vagas são distribuídas por linha com espaçamento igual: as cartas nunca se sobrepõem.
 */
import { useEffect, useRef, useState, type DragEvent, type PointerEvent as ReactPointerEvent } from "react";
import { PlayerPhoto, PositionBadge } from "../../components/PlayerCard";
import { byPosition, displayPosition } from "../../domain/positions";
import type { FitLevel, Position, SquadPlayer } from "../../types/api";
import { BAND_LABELS, BAND_Y, moveToRow, slotLayout, slotRows, widestRow, type FormationDef } from "../lineup/layout";
import { FIT_LABEL } from "./labels";

/** `pool` com player -1 = área "fora da lista" (retirar um atleta sem colocar outro). */
export type Spot = { zone: "slot"; index: number } | { zone: "bench"; index: number } | { zone: "pool"; player: number };
export const POOL_AREA: Spot = { zone: "pool", player: -1 };

export interface Arrangement {
  formation: Position[];
  starters: (number | null)[];
  bench: number[];
}

type DropTarget = { kind: "spot"; spot: Spot } | { kind: "row"; row: number; at: number };

const ROW: Record<Position, number> = { GK: 0, DR: 1, DL: 1, DC: 1, DM: 2, MC: 3, STC: 4 };
const ORDER: Record<Position, number> = { DL: 0, DC: 1, DR: 2, GK: 1, DM: 1, MC: 1, STC: 1 };

/** Coordenadas (%) por tipo de vaga (usada quando a formação não tem nome oficial). */
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
const surname = (name: string) => {
  const parts = name.trim().split(/\s+/);
  return parts.length > 1 && name.length > 14 ? parts[parts.length - 1] : name;
};

/** Desenho oficial do campo (linhas em SVG, coordenadas 68 × 90). */
function FieldLines() {
  return (
    <svg className="field2__svg" viewBox="0 0 68 90" preserveAspectRatio="none" aria-hidden>
      <rect x="3" y="3" width="62" height="84" rx="0.6" />
      <line x1="3" y1="45" x2="65" y2="45" />
      <circle cx="34" cy="45" r="7.5" />
      <rect x="16" y="3" width="36" height="14" />
      <rect x="25" y="3" width="18" height="5" />
      <rect x="16" y="73" width="36" height="14" />
      <rect x="25" y="82" width="18" height="5" />
      <path d="M27.5 17 A7.5 7.5 0 0 0 40.5 17" />
      <path d="M27.5 73 A7.5 7.5 0 0 1 40.5 73" />
    </svg>
  );
}

export function Pitch({ arrangement, squad, locked, onChange, formations = [] }: {
  arrangement: Arrangement;
  squad: SquadPlayer[];
  locked: boolean;
  onChange: (a: Arrangement) => void;
  /** Formações oficiais: permitem trocar de formação arrastando um titular para outra linha. */
  formations?: FormationDef[];
}) {
  const [selected, setSelected] = useState<Spot | null>(null);
  const [flash, setFlash] = useState<{ text: string; bad?: boolean } | null>(null);
  const [hoverRow, setHoverRow] = useState<number | null>(null);
  const [dragOn, setDragOn] = useState(false);
  const [touch, setTouch] = useState<{ spot: Spot; x: number; y: number; label: string; active: boolean } | null>(null);
  const fieldRef = useRef<HTMLDivElement>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(flashTimer.current), []);

  const byId = new Map(squad.map((p) => [p.player, p]));
  const used = new Set([...arrangement.starters.filter((x): x is number => x != null), ...arrangement.bench]);
  const pool = byPosition(squad.filter((p) => !used.has(p.player)), (p) => p.position);
  const def = formations.find((f) => f.positions.join() === arrangement.formation.join()) ?? null;
  const coords = def ? slotLayout(def) : slotCoordinates(arrangement.formation).map((c) => ({ ...c, row: 0 }));
  const rows = def ? slotRows(def) : [];
  const width = def ? Math.min(21, 100 / widestRow(def) - 1.2) : 21;

  const say = (text: string, bad = false) => {
    setFlash({ text, bad });
    clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setFlash(null), 1800);
  };

  const placeable = (s: Spot) => {
    const id = s.zone === "pool" ? s.player : s.zone === "slot" ? arrangement.starters[s.index] : arrangement.bench[s.index];
    return id == null || byId.get(id)?.available !== false;
  };

  /** Aplica um arraste/seleção: troca de lugares ou mudança de linha (formação). */
  const apply = (from: Spot, target: DropTarget) => {
    if (locked) return;
    if (target.kind === "row") {
      if (from.zone !== "slot" || !def) return;
      if (rows[target.row]?.includes(from.index)) return; // mesma linha: nada muda
      const r = moveToRow(def, arrangement.starters, from.index, target.row, target.at, formations);
      if (!r) {
        say("Essa formação não é oficial", true);
        return;
      }
      onChange({ formation: r.formation.positions as Position[], starters: r.starters, bench: arrangement.bench });
      say(`Formação: ${r.formation.id}`);
      return;
    }
    const to = target.spot;
    if (keyOf(from) === keyOf(to)) return;
    // um indisponível só pode sair do time (ir para o elenco), nunca entrar
    const entering = from.zone === "pool" ? from : to.zone === "pool" ? to : null;
    if (entering && !placeable(entering) && to.zone !== "pool") return;
    onChange(swap(arrangement, from, to));
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
    apply(selected, { kind: "spot", spot: target });
    setSelected(null);
  };

  /** Linha de destino e posição de inserção a partir de um ponto da tela. */
  const rowAt = (clientX: number, clientY: number): DropTarget | null => {
    const el = fieldRef.current;
    if (!el || !def) return null;
    const box = el.getBoundingClientRect();
    if (clientX < box.left || clientX > box.right || clientY < box.top || clientY > box.bottom) return null;
    const y = ((clientY - box.top) / box.height) * 100;
    const x = ((clientX - box.left) / box.width) * 100;
    let best = -1;
    let dist = Infinity;
    rows.forEach((_, r) => {
      if (r === 0) return;
      const d = Math.abs(BAND_Y[r] - y);
      if (d < dist) {
        dist = d;
        best = r;
      }
    });
    if (best < 0 || dist > 10.5) return null;
    return { kind: "row", row: best, at: rows[best].filter((s) => coords[s].x < x).length };
  };

  // ---------- mouse: drag nativo
  const drag = (s: Spot) => ({
    draggable: !locked,
    onDragStart: (e: DragEvent) => {
      e.dataTransfer.setData("text/plain", JSON.stringify(s));
      e.dataTransfer.effectAllowed = "move";
      setDragOn(s.zone === "slot");
    },
    onDragEnd: () => {
      setHoverRow(null);
      setDragOn(false);
    },
  });
  const readDrag = (e: DragEvent): Spot | null => {
    try {
      return JSON.parse(e.dataTransfer.getData("text/plain")) as Spot;
    } catch {
      return null; // arraste de outra origem: ignora
    }
  };
  const drop = (target: Spot) => ({
    "data-drop": JSON.stringify(target),
    onDragOver: (e: DragEvent) => {
      if (!locked) e.preventDefault();
    },
    onDrop: (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation(); // o destino mais interno decide (a seção do elenco também é destino)
      const from = readDrag(e);
      if (from && !(from.zone === "pool" && byId.get(from.player)?.available === false)) apply(from, { kind: "spot", spot: target });
      setSelected(null);
      setHoverRow(null);
    },
  });
  const fieldDrop = {
    onDragOver: (e: DragEvent) => {
      if (locked) return;
      e.preventDefault();
      const t = rowAt(e.clientX, e.clientY);
      setHoverRow(t && t.kind === "row" ? t.row : null);
    },
    onDragLeave: () => setHoverRow(null),
    onDrop: (e: DragEvent) => {
      e.preventDefault();
      const from = readDrag(e);
      const t = rowAt(e.clientX, e.clientY);
      if (from && t) apply(from, t);
      setHoverRow(null);
      setDragOn(false);
      setSelected(null);
    },
  };

  // ---------- toque: Pointer Events (o drag nativo não funciona em telas de toque)
  const touchStart = (s: Spot, label: string) => (e: ReactPointerEvent) => {
    if (locked || e.pointerType === "mouse") return;
    setTouch({ spot: s, x: e.clientX, y: e.clientY, label, active: false });
  };
  useEffect(() => {
    if (!touch) return;
    const move = (e: PointerEvent) => {
      setTouch((t) => {
        if (!t) return t;
        const moved = Math.hypot(e.clientX - t.x, e.clientY - t.y) > 10;
        return { ...t, x: e.clientX, y: e.clientY, active: t.active || moved };
      });
      const r = rowAt(e.clientX, e.clientY);
      setHoverRow(r && r.kind === "row" ? r.row : null);
    };
    const up = (e: PointerEvent) => {
      const t = touch;
      setTouch(null);
      setHoverRow(null);
      if (!t.active) return; // toque simples: o clique faz a seleção
      const el = document.elementFromPoint?.(e.clientX, e.clientY)?.closest("[data-drop]");
      if (el) {
        apply(t.spot, { kind: "spot", spot: JSON.parse(el.getAttribute("data-drop")!) as Spot });
      } else {
        const r = rowAt(e.clientX, e.clientY);
        if (r) apply(t.spot, r);
      }
      setSelected(null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up, { once: true });
    window.addEventListener("pointercancel", () => setTouch(null), { once: true });
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }); // reavalia a cada render (estado do arraste atual)

  const isSel = (s: Spot) => selected != null && keyOf(selected) === keyOf(s);
  const dragging = touch?.active ? keyOf(touch.spot) : null;

  return (
    <div className="lineup2">
      <div className={`field2${dragOn || (touch?.active && touch.spot.zone === "slot") ? " is-dragging" : ""}`} ref={fieldRef} role="group" aria-label="Campo: titulares por vaga" {...fieldDrop}>
        <FieldLines />
        {def && rows.map((_, r) =>
          r === 0 ? null : (
            <div key={r} className={`field2__row${hoverRow === r ? " is-target" : ""}`} style={{ top: `${BAND_Y[r]}%` }} aria-hidden data-band={BAND_LABELS[r]}>
              <span className="field2__row-label">{BAND_LABELS[r]}</span>
            </div>
          ),
        )}
        {flash && <span className={`formation-flash${flash.bad ? " formation-flash--bad" : ""}`} role="status">{flash.text}</span>}
        {arrangement.formation.map((pos, i) => {
          const id = arrangement.starters[i];
          const p = id != null ? byId.get(id) : undefined;
          const fit: FitLevel | undefined = p ? (p.fit[pos] as FitLevel) : undefined;
          const s: Spot = { zone: "slot", index: i };
          return (
            <button
              key={i}
              type="button"
              className={`token${isSel(s) ? " is-selected" : ""}${fit ? ` fit--${fit}` : " is-empty"}${p && !p.available ? " is-out" : ""}${dragging === keyOf(s) ? " is-dragging" : ""}`}
              style={{ left: `${coords[i].x}%`, top: `${coords[i].y}%`, ["--w" as string]: `${width}%` }}
              onClick={() => act(s)}
              onPointerDown={touchStart(s, p?.name ?? displayPosition(pos))}
              aria-pressed={isSel(s)}
              aria-label={`Vaga ${displayPosition(pos)}: ${p ? `${p.name}, ${FIT_LABEL[fit!]}${p.available ? "" : ", indisponível"}` : "vazia"}`}
              {...drag(s)}
              {...drop(s)}
            >
              <PositionBadge position={pos} size="sm" />
              {p ? <PlayerPhoto id={p.player} name={p.name} size={34} /> : <span className="photo photo--fallback" style={{ width: 34, height: 34 }} aria-hidden>?</span>}
              <span className="token__name">{p ? surname(p.name) : "—"}</span>
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
                    onClick={() => act(s)} onPointerDown={touchStart(s, p?.name ?? "")} aria-pressed={isSel(s)} {...drag(s)} {...drop(s)}>
                    <PositionBadge position={p?.position ?? "MC"} size="sm" />
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
                    onClick={() => act(s)} onPointerDown={p.available ? touchStart(s, p.name) : undefined} aria-pressed={isSel(s)} aria-disabled={!p.available}
                    {...(p.available ? drag(s) : {})} {...drop(s)}>
                    <PositionBadge position={p.position} size="sm" />
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
        {!locked && def && <p className="muted small">Dica: arraste um titular para outra faixa (DEF, VOL, ME, ATA) para mudar a formação.</p>}
      </div>
      {touch?.active && (
        <span className="drag-ghost token" style={{ left: touch.x, top: touch.y, ["--w" as string]: "84px", position: "fixed" }} aria-hidden>
          <span className="token__name">{surname(touch.label)}</span>
        </span>
      )}
    </div>
  );
}
