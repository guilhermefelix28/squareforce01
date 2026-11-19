import { useMemo, useRef, useState } from "react";
import { ApiError, newIdempotencyKey } from "../../api/client";
import { actOnProposal, createProposal } from "../../api/endpoints";
import { ClubCrest } from "../../components/ClubCrest";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Notice } from "../../components/Notice";
import { formatClock, formatMoney, formatMoneyShort, parseMoney } from "../../domain/money";
import { PositionBadge } from "../../components/PlayerCard";
import { POSITION_ORDER, byPosition, displayPosition } from "../../domain/positions";
import type { Club, Proposal, TradingPlayer, TradingSquad, TradingState } from "../../types/api";

const ERRORS: Record<string, string> = {
  PENDING_PROPOSAL_EXISTS: "Você já tem uma proposta pendente. Aguarde a resposta ou cancele-a.",
  TRADE_LIMIT_REACHED: "Um dos clubes já concluiu 3 negociações.",
  INSUFFICIENT_FUNDS: "Saldo insuficiente para o dinheiro adicional.",
  PLAYER_NOT_OWNED: "Um dos jogadores já mudou de clube. Atualize a seleção.",
  PROPOSAL_NOT_PENDING: "Esta proposta já foi decidida.",
  PROPOSAL_INVALIDATED: "A troca não pode mais ser concluída.",
  MARKET_NOT_RUNNING: "O mercado está encerrado.",
};
const STATUS: Record<string, string> = {
  accepted: "aceita", rejected: "rejeitada", cancelled: "cancelada", expired: "expirada", invalidated: "invalidada", pending: "pendente",
};

const errText = (e: unknown) => (e instanceof ApiError ? ERRORS[e.code] ?? e.message : "Falha de comunicação. Tente novamente.");

function PlayerLine({ p }: { p: TradingPlayer }) {
  return (
    <span className="pline">
      <PositionBadge position={p.position} size="sm" /> <strong>{p.name}</strong>
      <span className="muted small"> {p.age} anos</span>
    </span>
  );
}

export function TradingBoard({
  sessionId, state, squads, clubs, remainingMs, left, onChanged,
}: {
  sessionId: string;
  state: TradingState;
  squads: TradingSquad[];
  clubs: Club[];
  remainingMs: number;
  left: (ms: number) => number;
  onChanged: () => void;
}) {
  const names = useMemo(() => new Map(clubs.map((c) => [c.club_uid, c.short_name])), [clubs]);
  const clubName = (uid: number) => names.get(uid) ?? `#${uid}`;
  const mine = squads.find((s) => s.is_user);
  const rivals = squads.filter((s) => !s.is_user);

  const [search, setSearch] = useState("");
  const [clubFilter, setClubFilter] = useState<number | "">("");
  const [posFilter, setPosFilter] = useState("");
  const [offered, setOffered] = useState<number | null>(null);
  const [wanted, setWanted] = useState<TradingPlayer | null>(null);
  const [moneyText, setMoneyText] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const keyRef = useRef(newIdempotencyKey());

  const money = moneyText.trim() === "" ? 0 : parseMoney(moneyText);
  const limitReached = state.completed_trades >= state.max_trades;
  const canPropose = state.phase === "running" && !state.outgoing && !limitReached;

  const results = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("pt-BR");
    return rivals
      .filter((s) => clubFilter === "" || s.club_uid === clubFilter)
      .flatMap((s) => s.players.map((p) => ({ squad: s, p })))
      .filter(({ p }) => (!posFilter || p.position === posFilter) && (!term || p.name.toLocaleLowerCase("pt-BR").includes(term)))
      .map((x, i) => [x, i] as const)
      .sort((a, b) => POSITION_ORDER.indexOf(a[0].p.position) - POSITION_ORDER.indexOf(b[0].p.position) || a[1] - b[1])
      .map(([x]) => x);
  }, [rivals, search, clubFilter, posFilter]);

  const offeredPlayer = mine?.players.find((p) => p.unique_id === offered) ?? null;
  const ready = !!offeredPlayer && !!wanted && !Number.isNaN(money) && money >= 0 && money <= state.budget && canPropose;

  async function send() {
    if (!offeredPlayer || !wanted) return;
    setBusy("propose");
    try {
      await createProposal(sessionId, {
        recipient_club_uid: wanted.club_uid, offered_player_id: offeredPlayer.unique_id,
        requested_player_id: wanted.unique_id, money,
      }, keyRef.current);
      setFeedback({ kind: "success", text: `Proposta enviada a ${clubName(wanted.club_uid)}. Prazo de 10 segundos.` });
      setWanted(null);
      setOffered(null);
      setMoneyText("");
      onChanged();
    } catch (e) {
      setFeedback({ kind: "error", text: errText(e) });
    } finally {
      keyRef.current = newIdempotencyKey();
      setBusy(null);
      setConfirm(false);
    }
  }

  async function act(p: Proposal, action: "accept" | "reject" | "cancel") {
    setBusy(`${p.id}:${action}`);
    try {
      const r = await actOnProposal(sessionId, p.id, action);
      setFeedback({ kind: "success", text: `Proposta ${STATUS[r.status]}.${r.status === "accepted" ? " Troca concluída." : ""}` });
      onChanged();
    } catch (e) {
      setFeedback({ kind: "error", text: errText(e) });
      onChanged();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="auction trading">
      <section className="auction__main stack">
        <header className="auction__clocks card">
          <div>
            <span className="muted small">Mercado de negociações</span>
            <strong className={`clock ${remainingMs <= 15_000 ? "clock--urgent" : ""}`}>{formatClock(remainingMs)}</strong>
            <div className="bar" aria-hidden><span style={{ width: `${(remainingMs / state.duration_ms) * 100}%` }} /></div>
          </div>
          <dl className="stats stats--inline">
            <div><dt>Saldo</dt><dd>{formatMoneyShort(state.budget)}</dd></div>
            <div><dt>Negociações</dt><dd>{state.completed_trades}/{state.max_trades}</dd></div>
          </dl>
        </header>

        {state.outgoing && (
          <section className="card proposal proposal--out" aria-label="Sua proposta pendente">
            <div className="proposal__head">
              <strong>Sua proposta para {clubName(state.outgoing.recipient_club_uid)}</strong>
              <span className="clock clock--small">{formatClock(left(state.outgoing.remaining_ms))}</span>
            </div>
            <p className="swap">
              <span>Você dá <PlayerLine p={state.outgoing.offered} /></span>
              <span>Você recebe <PlayerLine p={state.outgoing.requested} /></span>
              {state.outgoing.money > 0 && <span>+ {formatMoney(state.outgoing.money)} pagos por você</span>}
            </p>
            <button type="button" className="btn btn--ghost btn--small" disabled={!!busy} onClick={() => void act(state.outgoing!, "cancel")}>
              Cancelar proposta
            </button>
          </section>
        )}

        <section className="card" aria-labelledby="new-proposal">
          <h3 id="new-proposal">Nova proposta</h3>
          {limitReached && <Notice kind="info">Você já concluiu as 3 negociações permitidas.</Notice>}
          <div className="toolbar">
            <label className="field">
              <span>Buscar jogador</span>
              <input type="search" value={search} placeholder="Nome" onChange={(e) => setSearch(e.target.value)} />
            </label>
            <label className="field">
              <span>Clube</span>
              <select value={clubFilter} onChange={(e) => setClubFilter(e.target.value ? Number(e.target.value) : "")}>
                <option value="">Todos os adversários</option>
                {rivals.map((s) => (
                  <option key={s.club_uid} value={s.club_uid}>{clubName(s.club_uid)} ({s.completed_trades}/3)</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Posição</span>
              <select value={posFilter} onChange={(e) => setPosFilter(e.target.value)}>
                <option value="">Todas</option>
                {POSITION_ORDER.map((p) => <option key={p} value={p}>{displayPosition(p)}</option>)}
              </select>
            </label>
          </div>
          <div className="table-wrap scroll-y" aria-label="Elencos adversários">
            <table>
              <thead><tr><th>Jogador</th><th>Pos.</th><th className="num">Idade</th><th>Clube</th><th /></tr></thead>
              <tbody>
                {results.slice(0, 120).map(({ squad, p }) => (
                  <tr key={p.unique_id} className={wanted?.unique_id === p.unique_id ? "is-user" : ""}>
                    <td>{p.name}</td>
                    <td><PositionBadge position={p.position} size="sm" /></td>
                    <td className="num">{p.age}</td>
                    <td><span className="club-name"><ClubCrest clubUid={squad.club_uid} name={clubName(squad.club_uid)} size={18} /><span>{clubName(squad.club_uid)}</span></span></td>
                    <td>
                      <button type="button" className="btn btn--ghost btn--small" disabled={squad.completed_trades >= 3}
                        aria-label={`Quero ${p.name}`} onClick={() => setWanted(p)}>
                        Quero
                      </button>
                    </td>
                  </tr>
                ))}
                {!results.length && <tr><td colSpan={5} className="muted">Nenhum jogador encontrado.</td></tr>}
              </tbody>
            </table>
          </div>
          {results.length > 120 && <p className="muted small">Mostrando 120 de {results.length}. Refine a busca.</p>}

          <div className="grid-2">
            <label className="field">
              <span>Jogador oferecido (seu elenco)</span>
              <select value={offered ?? ""} onChange={(e) => setOffered(e.target.value ? Number(e.target.value) : null)}>
                <option value="">Selecione…</option>
                {byPosition(mine?.players ?? [], (p) => p.position).map((p) => (
                  <option key={p.unique_id} value={p.unique_id}>{displayPosition(p.position)} · {p.name}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Dinheiro adicional (opcional, pago por você)</span>
              <input inputMode="numeric" value={moneyText} placeholder="0" onChange={(e) => setMoneyText(e.target.value)}
                aria-invalid={Number.isNaN(money) || money > state.budget} />
            </label>
          </div>
          <p className="muted small">
            Desejado: {wanted ? <><PlayerLine p={wanted} /> ({clubName(wanted.club_uid)})</> : "escolha na lista acima"}
            {money > 0 && !Number.isNaN(money) && ` · você paga ${formatMoney(money)}`}
            {money > state.budget && " · acima do seu saldo"}
          </p>
          <button type="button" className="btn btn--primary btn--block" disabled={!ready || !!busy} onClick={() => setConfirm(true)}>
            {state.outgoing ? "Aguardando resposta da proposta atual" : "Revisar e enviar proposta"}
          </button>
          {feedback && <Notice kind={feedback.kind}>{feedback.text}</Notice>}
          <p className="muted small">Troca de um jogador por outro; sem contrapropostas. O destinatário tem 10 segundos para responder.</p>
        </section>
      </section>

      <aside className="auction__side stack" aria-label="Propostas e histórico">
        <section className="card" aria-labelledby="incoming-title">
          <h3 id="incoming-title">Propostas recebidas</h3>
          {!state.incoming.length && <p className="muted small">Nenhuma proposta pendente.</p>}
          {state.incoming.map((p) => (
            <article key={p.id} className="proposal proposal--in">
              <div className="proposal__head">
                <strong>{clubName(p.proponent_club_uid)}</strong>
                <span className={`clock clock--small ${left(p.remaining_ms) <= 3000 ? "clock--urgent" : ""}`}>{formatClock(left(p.remaining_ms))}</span>
              </div>
              <p className="swap">
                <span>Pede <PlayerLine p={p.requested} /></span>
                <span>Oferece <PlayerLine p={p.offered} /></span>
                {p.money > 0 && <span>+ {formatMoney(p.money)} para você</span>}
              </p>
              <div className="quick">
                <button type="button" className="btn btn--primary btn--small" disabled={!!busy} onClick={() => void act(p, "accept")}>Aceitar</button>
                <button type="button" className="btn btn--ghost btn--small" disabled={!!busy} onClick={() => void act(p, "reject")}>Rejeitar</button>
              </div>
            </article>
          ))}
        </section>
        {state.recent_decisions.length > 0 && (
          <section className="card">
            <h3>Suas propostas recentes</h3>
            <ul className="mini-squad">
              {state.recent_decisions.map((p) => (
                <li key={p.id}>
                  <span className="tag">{STATUS[p.status]}</span>
                  {p.direction === "outgoing" ? `para ${clubName(p.recipient_club_uid)}` : `de ${clubName(p.proponent_club_uid)}`}
                  <span className="muted small">{p.requested.name}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
        <section className="card">
          <h3>Negociações concluídas ({state.history.length})</h3>
          {!state.history.length && <p className="muted small">Nenhuma troca ainda.</p>}
          <ol className="results">
            {state.history.map((r) => (
              <li key={r.proposal_id} className={state.user_club_uid === r.proponent_club_uid || state.user_club_uid === r.recipient_club_uid ? "sale is-user" : ""}>
                <span className="muted small">{formatClock(r.elapsed_ms)} · {clubName(r.proponent_club_uid)} ⇄ {clubName(r.recipient_club_uid)}</span>
                <span>{r.offered.name} ⇄ {r.requested.name}{r.money > 0 ? ` + ${formatMoneyShort(r.money)}` : ""}</span>
              </li>
            ))}
          </ol>
        </section>
      </aside>

      <ConfirmDialog
        open={confirm}
        title="Confirmar proposta?"
        message={offeredPlayer && wanted
          ? `Você entrega ${offeredPlayer.name} e recebe ${wanted.name} (${clubName(wanted.club_uid)})${money > 0 ? `, pagando ${formatMoney(money)}` : ""}. A troca só acontece se ${clubName(wanted.club_uid)} aceitar em até 10 segundos.`
          : ""}
        confirmLabel="Enviar proposta"
        busy={busy === "propose"}
        onConfirm={() => void send()}
        onCancel={() => setConfirm(false)}
      />
    </div>
  );
}
