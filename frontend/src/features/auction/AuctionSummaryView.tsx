import { useMemo } from "react";
import { ClubCrest } from "../../components/ClubCrest";
import { formatMoneyShort } from "../../domain/money";
import { POSITION_ORDER, displayPosition } from "../../domain/positions";
import type { AuctionSummary, Club } from "../../types/api";

const SOURCE: Record<string, string> = { auction: "leilão", improvement: "melhoria", basic: "reserva básica" };
const REASON: Record<string, string> = {
  time_up: "O relógio global chegou ao fim.",
  all_squads_complete: "Todos os elencos foram completados no leilão.",
  no_eligible_players: "Não havia mais jogadores elegíveis para novas rodadas.",
};

export function AuctionSummaryView({ summary, clubs }: { summary: AuctionSummary; clubs: Club[] }) {
  const names = useMemo(() => new Map(clubs.map((c) => [c.club_uid, c.short_name])), [clubs]);
  const squads = [...summary.squads].sort((a, b) => Number(b.is_user) - Number(a.is_user));
  return (
    <section className="stack" aria-labelledby="summary-title">
      <div className="card">
        <h2 id="summary-title">Resumo dos elencos</h2>
        <p className="muted">
          {REASON[summary.finish_reason] ?? ""} {summary.rounds_completed} rodadas. Todos os clubes terminaram com 18 jogadores
          após a complementação automática.
        </p>
      </div>
      <div className="summary-grid">
        {squads.map((q) => {
          const name = names.get(q.club_uid) ?? `#${q.club_uid}`;
          const sorted = [...q.contracts].sort(
            (a, b) => POSITION_ORDER.indexOf(a.position) - POSITION_ORDER.indexOf(b.position) || b.price - a.price,
          );
          return (
            <details key={q.club_uid} className={`card squad ${q.is_user ? "is-user" : ""}`} open={q.is_user}>
              <summary>
                <span className="club-name">
                  <ClubCrest clubUid={q.club_uid} name={name} size={28} />
                  <strong>{name}</strong>
                  {q.is_user && <span className="tag tag--user">você</span>}
                </span>
                <span className="muted small">
                  {q.contracts.length}/18 · gasto {formatMoneyShort(q.spent)} · saldo {formatMoneyShort(q.budget)}
                </span>
              </summary>
              <p className="muted small">
                {q.auction_signings} no leilão · limite de melhorias {q.improvement_limit}
              </p>
              <table className="compact">
                <thead>
                  <tr><th>Pos.</th><th>Jogador</th><th className="hide-sm">Origem</th><th className="num">Preço</th></tr>
                </thead>
                <tbody>
                  {sorted.map((k) => (
                    <tr key={k.player_id}>
                      <td>{displayPosition(k.position)}</td>
                      <td>{k.name}</td>
                      <td className="hide-sm muted small">{SOURCE[k.source]}</td>
                      <td className="num">{formatMoneyShort(k.price)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          );
        })}
      </div>
    </section>
  );
}
