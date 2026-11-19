/** Peças da partida ao vivo: campo tático com as duas equipes, telão e outros jogos da rodada (DR-06). */
import { useEffect, useRef, useState } from "react";
import { ClubCrest, clubInitials } from "../../components/ClubCrest";
import type { LiveOtherMatch } from "../../types/api";

type OnPitch = { player: number; name: string; slot: string; on_field: boolean; yellow_cards: number };

/** Profundidade (0 = gol, 1 = meio-campo) de cada tipo de vaga para o desenho tático. */
const DEPTH: Record<string, number> = { GK: 0.06, DR: 0.3, DC: 0.26, DL: 0.3, DM: 0.5, MC: 0.66, STC: 0.88 };
const SIDE: Record<string, number> = { DL: -1, DR: 1 };

/** Coordenadas (%) dos jogadores em campo de UM time; `home` ataca para a direita. */
export function teamDots(players: OnPitch[], home: boolean): { p: OnPitch; x: number; y: number }[] {
  const field = players.filter((p) => p.on_field);
  const groups = new Map<number, OnPitch[]>();
  field.forEach((p) => {
    const d = DEPTH[p.slot] ?? 0.6;
    const key = Math.round(d * 100);
    groups.set(key, [...(groups.get(key) ?? []), p]);
  });
  // laterais ficam na mesma linha dos zagueiros
  const out: { p: OnPitch; x: number; y: number }[] = [];
  const lines = new Map<number, OnPitch[]>();
  [...groups.entries()].forEach(([k, ps]) => {
    const line = k === 30 ? 26 : k;
    lines.set(line, [...(lines.get(line) ?? []), ...ps]);
  });
  lines.forEach((ps, k) => {
    // ordem lateral: para quem ataca à direita, o lado esquerdo do time fica em cima
    const sorted = [...ps].sort((a, b) => (SIDE[a.slot] ?? 0) - (SIDE[b.slot] ?? 0) || a.player - b.player);
    sorted.forEach((p, i) => {
      const depth = (k / 100) * 50; // metade do campo
      const yRaw = ((i + 0.5) / sorted.length) * 100;
      out.push({ p, x: home ? depth : 100 - depth, y: home ? yRaw : 100 - yRaw });
    });
  });
  return out;
}

const surname = (n: string) => n.trim().split(/\s+/).slice(-1)[0];

export function LivePitch({ home, away, homeName, awayName, userSide = 0 }: {
  home: OnPitch[]; away: OnPitch[]; homeName: string; awayName: string; userSide?: number;
}) {
  // o seu time sempre em verde-lima; o adversário em prata
  const cls = (side: number) => (side === userSide ? "dot--user" : "dot--opp");
  const dots = [...teamDots(home, true).map((d) => ({ ...d, cls: cls(0) })), ...teamDots(away, false).map((d) => ({ ...d, cls: cls(1) }))];
  return (
    <figure className="stack" style={{ margin: 0, gap: "0.4rem" }}>
      <div className="live-pitch" role="img" aria-label={`Campo tático: ${homeName} (esquerda) e ${awayName} (direita)`}>
        <svg viewBox="0 0 105 68" preserveAspectRatio="none" aria-hidden>
          <rect className="ln" x="2" y="2" width="101" height="64" />
          <line className="ln" x1="52.5" y1="2" x2="52.5" y2="66" />
          <circle className="ln" cx="52.5" cy="34" r="9.15" />
          <rect className="ln" x="2" y="13.85" width="16.5" height="40.3" />
          <rect className="ln" x="86.5" y="13.85" width="16.5" height="40.3" />
          <rect className="ln" x="2" y="24.84" width="5.5" height="18.32" />
          <rect className="ln" x="97.5" y="24.84" width="5.5" height="18.32" />
        </svg>
        {dots.map(({ p, x, y, cls }) => (
          <span key={`${cls}-${p.player}`} className={`dot ${cls}`} style={{ left: `${2 + x * 0.96}%`, top: `${4 + y * 0.92}%` }} title={p.name}>
            <span className="dot__chip">{clubInitials(surname(p.name)).slice(0, 2)}</span>
            <span className="dot__name">{surname(p.name)}{p.yellow_cards > 0 ? " 🟨" : ""}</span>
          </span>
        ))}
      </div>
      <figcaption className="live-legend">
        <b className={userSide === 0 ? "user" : "opp"}>{homeName}</b>
        <b className={userSide === 1 ? "user" : "opp"}>{awayName}</b>
      </figcaption>
    </figure>
  );
}

export function Jumbotron({ home, away, names, user, score, minute, finished, shootout, flash, label }: {
  home: number; away: number; names: Map<number, string>; user: number; score?: [number, number] | number[];
  minute?: string; finished?: boolean; shootout?: number[] | null; flash?: boolean; label?: string;
}) {
  return (
    <section className="jumbotron" aria-live={label ? undefined : "polite"} aria-label={label ? "Confronto" : "Placar"}>
      <div className={`jumbotron__team${home === user ? " is-user" : ""}`}>
        <ClubCrest clubUid={home} name={names.get(home) ?? "?"} size={48} />
        <span className="jumbotron__name">{names.get(home) ?? home}</span>
      </div>
      <div className="jumbotron__center">
        <span className={`jumbotron__score${flash ? " is-flash" : ""}`}>{label ?? `${score?.[0] ?? 0} – ${score?.[1] ?? 0}`}</span>
        {shootout && <span className="jumbotron__sub">Pênaltis {shootout[0]}–{shootout[1]}</span>}
        {(finished || minute) && <span className="jumbotron__minute">{finished ? "FIM DE JOGO" : minute}</span>}
      </div>
      <div className={`jumbotron__team${away === user ? " is-user" : ""}`}>
        <ClubCrest clubUid={away} name={names.get(away) ?? "?"} size={48} />
        <span className="jumbotron__name">{names.get(away) ?? away}</span>
      </div>
    </section>
  );
}

/** Placares simultâneos da rodada; destaca o jogo que acabou de ter gol. */
export function OtherMatches({ matches, names }: { matches: LiveOtherMatch[]; names: Map<number, string> }) {
  const prev = useRef(new Map<string, string>());
  const [changed, setChanged] = useState<Set<string>>(new Set());
  useEffect(() => {
    const now = new Set<string>();
    matches.forEach((m) => {
      const key = m.score.join("-");
      const before = prev.current.get(m.match_id);
      if (before != null && before !== key) now.add(m.match_id);
      prev.current.set(m.match_id, key);
    });
    if (now.size) {
      setChanged(now);
      const t = setTimeout(() => setChanged(new Set()), 2500);
      return () => clearTimeout(t);
    }
  }, [matches]);
  if (matches.length === 0) return <p className="muted small">Nenhum outro jogo nesta rodada.</p>;
  return (
    <ul className="others" aria-label="Outros jogos da rodada">
      {matches.map((m) => (
        <li key={m.match_id} className={changed.has(m.match_id) ? "is-changed" : ""}>
          <span className="club-name">
            <ClubCrest clubUid={m.home_club_uid} name={names.get(m.home_club_uid) ?? "?"} size={18} />
            <span>{names.get(m.home_club_uid) ?? m.home_club_uid}</span>
          </span>
          <span className="others__score">{m.score[0]}–{m.score[1]}</span>
          <span className="club-name">
            <span>{names.get(m.away_club_uid) ?? m.away_club_uid}</span>
            <ClubCrest clubUid={m.away_club_uid} name={names.get(m.away_club_uid) ?? "?"} size={18} />
          </span>
          {m.finished && <span className="others__state">encerrado</span>}
        </li>
      ))}
    </ul>
  );
}
