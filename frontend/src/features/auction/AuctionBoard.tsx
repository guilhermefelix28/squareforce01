import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { ApiError, newIdempotencyKey } from "../../api/client";
import { placeBid, playerPhotoUrl } from "../../api/endpoints";
import { ClubCrest, clubInitials } from "../../components/ClubCrest";
import { Notice } from "../../components/Notice";
import { formatClock, formatMoney, formatMoneyShort, parseMoney } from "../../domain/money";
import { displayPosition } from "../../domain/positions";
import type { AuctionPlayer, AuctionState, Club } from "../../types/api";

function PlayerPhoto({ p }: { p: AuctionPlayer }) {
  const [failed, setFailed] = useState(!p.has_photo);
  if (failed) return <span className="photo photo--fallback" aria-hidden>{clubInitials(p.name)}</span>;
  return <img className="photo" src={playerPhotoUrl(p.unique_id)} alt="" loading="lazy" onError={() => setFailed(true)} />;
}

const BID_ERRORS: Record<string, string> = {
  BELOW_MINIMUM_BID: "Lance abaixo do mínimo deste atleta.",
  INSUFFICIENT_FUNDS: "Lance acima do disponível: é preciso preservar R$ 500 mil por vaga restante.",
  BID_NOT_INCREASED: "No mesmo atleta só é possível aumentar o lance.",
  STALE_ROUND: "A rodada terminou antes do lance chegar ao servidor.",
  ROUND_CLOSED: "A rodada terminou antes do lance chegar ao servidor.",
  SQUAD_FULL: "Seu elenco já tem 18 jogadores.",
};

export function AuctionBoard({
  sessionId,
  state,
  clubs,
  roundRemainingMs,
  globalRemainingMs,
  onChanged,
}: {
  sessionId: string;
  state: AuctionState;
  clubs: Club[];
  roundRemainingMs: number;
  globalRemainingMs: number;
  onChanged: () => void;
}) {
  const round = state.round;
  const clubName = useMemo(() => new Map(clubs.map((c) => [c.club_uid, c.short_name])), [clubs]);
  const [selected, setSelected] = useState<number | null>(null);
  const [amountText, setAmountText] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const keyRef = useRef(newIdempotencyKey());

  // nova rodada: limpa seleção (mantém feedback do último lance)
  const roundNumber = round?.number;
  useEffect(() => {
    setSelected(null);
    setAmountText("");
  }, [roundNumber]);

  const player = round?.players.find((p) => p.unique_id === selected) ?? null;
  const amount = parseMoney(amountText);
  const active = state.active_bid && state.active_bid.round === round?.number ? state.active_bid : null;
  const activePlayer = active ? round?.players.find((p) => p.unique_id === active.player_id) : null;

  function choose(p: AuctionPlayer) {
    setSelected(p.unique_id);
    const base = active && active.player_id === p.unique_id ? active.amount + 100_000 : p.minimum_bid;
    setAmountText(String(base));
    setFeedback(null);
  }

  function add(step: number) {
    if (!player) return;
    const base = Number.isNaN(amount) ? player.minimum_bid : amount;
    setAmountText(String(base + step));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!player || !round || Number.isNaN(amount)) return;
    setBusy(true);
    setFeedback(null);
    try {
      const ack = await placeBid(sessionId, { player_id: player.unique_id, amount, round_number: round.number }, keyRef.current);
      setFeedback({
        kind: "success",
        text: `Lance de ${formatMoney(ack.amount)} em ${player.name} confirmado${ack.replaced_player_id ? " (alvo alterado)" : ""}.`,
      });
      onChanged();
    } catch (err) {
      const code = err instanceof ApiError ? err.code : "";
      setFeedback({ kind: "error", text: BID_ERRORS[code] ?? (err instanceof ApiError ? err.message : "Falha ao enviar o lance.") });
    } finally {
      keyRef.current = newIdempotencyKey(); // uma chave por confirmação do usuário
      setBusy(false);
    }
  }

  const canBid = !!round && state.open_slots > 0 && roundRemainingMs > 0;
  const urgent = roundRemainingMs <= 3000;

  return (
    <div className="auction">
      <section className="auction__main stack">
        <header className="auction__clocks card">
          <div>
            <span className="muted small">Rodada {round?.number ?? "—"} · {round ? displayPosition(round.position) : ""}</span>
            <strong className={`clock ${urgent ? "clock--urgent" : ""}`} aria-live="off">{formatClock(roundRemainingMs)}</strong>
            <div className="bar" aria-hidden>
              <span style={{ width: `${round ? (roundRemainingMs / round.duration_ms) * 100 : 0}%` }} />
            </div>
          </div>
          <div className="auction__global">
            <span className="muted small">Leilão termina em</span>
            <strong className="clock clock--small">{formatClock(globalRemainingMs)}</strong>
          </div>
        </header>

        <ul className="lot-grid" aria-label="Jogadores da rodada">
          {round?.players.map((p) => {
            const mine = active?.player_id === p.unique_id;
            return (
              <li key={p.unique_id}>
                <button
                  type="button"
                  className={`lot ${selected === p.unique_id ? "is-selected" : ""} ${mine ? "is-mine" : ""}`}
                  aria-pressed={selected === p.unique_id}
                  onClick={() => choose(p)}
                  disabled={!canBid}
                >
                  <PlayerPhoto p={p} />
                  <span className="lot__name">{p.name}</span>
                  <span className="lot__meta">
                    <span className="tag">{displayPosition(p.position)}</span> {p.age} anos
                  </span>
                  <span className="lot__club muted small">{p.club_short_name}</span>
                  <span className="lot__min">
                    <span className="muted small">mínimo</span> {formatMoneyShort(p.minimum_bid)}
                  </span>
                  {mine && <span className="tag tag--user">seu lance: {formatMoneyShort(active!.amount)}</span>}
                </button>
              </li>
            );
          })}
        </ul>

        <form className="card bid-panel" onSubmit={submit} aria-label="Fazer lance">
          <dl className="stats">
            <div><dt>Saldo</dt><dd>{formatMoneyShort(state.budget)}</dd></div>
            <div><dt>Lance máximo</dt><dd>{formatMoneyShort(state.max_bid)}</dd></div>
            <div><dt>Vagas</dt><dd>{state.open_slots}</dd></div>
            <div>
              <dt>Oferta ativa</dt>
              <dd>{active ? `${formatMoneyShort(active.amount)} · ${activePlayer?.name ?? ""}` : "nenhuma"}</dd>
            </div>
          </dl>
          {player ? (
            <>
              <label className="field">
                <span>Valor para {player.name} (mínimo {formatMoney(player.minimum_bid)})</span>
                <input
                  inputMode="numeric"
                  value={amountText}
                  onChange={(e) => setAmountText(e.target.value)}
                  aria-invalid={Number.isNaN(amount)}
                  placeholder="Ex.: 2500000 ou 2,5 mi"
                />
              </label>
              <div className="quick">
                <button type="button" className="btn btn--ghost btn--small" onClick={() => setAmountText(String(player.minimum_bid))}>
                  Lance mínimo
                </button>
                {state.bid_increments.map((inc) => (
                  <button key={inc} type="button" className="btn btn--ghost btn--small" onClick={() => add(inc)}>
                    +{formatMoneyShort(inc).replace("R$ ", "")}
                  </button>
                ))}
              </div>
              <p className="muted small">
                {Number.isNaN(amount) ? "Valor inválido." : `Você está oferecendo ${formatMoney(amount)}.`}
              </p>
              <button type="submit" className="btn btn--primary btn--block" disabled={!canBid || busy || Number.isNaN(amount)}>
                {busy ? "Enviando…" : "Confirmar lance"}
              </button>
            </>
          ) : (
            <p className="muted">{canBid ? "Selecione um jogador para fazer seu lance." : state.open_slots === 0 ? "Seu elenco está completo." : "Aguardando a próxima rodada…"}</p>
          )}
          {feedback && <Notice kind={feedback.kind}>{feedback.text}</Notice>}
          <p className="muted small">Ofertas são sigilosas: você vê apenas o seu próprio lance.</p>
        </form>
      </section>

      <aside className="auction__side stack" aria-label="Resultados">
        <section className="card">
          <h3>Resultados</h3>
          {state.recent_results.length === 0 && <p className="muted small">Nenhuma rodada encerrada ainda.</p>}
          <ol className="results">
            {state.recent_results.map((r) => (
              <li key={r.number}>
                <span className="muted small">Rodada {r.number} · {displayPosition(r.position)}</span>
                {r.sales.map((s) => (
                  <span key={s.player_id} className={`sale ${s.club_uid === state.user_club_uid ? "is-user" : ""}`}>
                    <strong>{s.player_name}</strong> → {clubName.get(s.club_uid) ?? `#${s.club_uid}`} · {formatMoneyShort(s.price)}
                  </span>
                ))}
                {r.unsold_player_ids.length > 0 && (
                  <span className="muted small">{r.unsold_player_ids.length} sem lance vencedor</span>
                )}
              </li>
            ))}
          </ol>
        </section>
        <section className="card">
          <h3>Clubes</h3>
          <table className="compact">
            <thead>
              <tr><th>Clube</th><th className="num">Elenco</th><th className="num">Saldo</th></tr>
            </thead>
            <tbody>
              {[...state.clubs].sort((a, b) => Number(b.is_user) - Number(a.is_user)).map((c) => (
                <tr key={c.club_uid} className={c.is_user ? "is-user" : ""}>
                  <td>
                    <span className="club-name">
                      <ClubCrest clubUid={c.club_uid} name={clubName.get(c.club_uid) ?? "?"} size={18} />
                      <span>{clubName.get(c.club_uid) ?? c.club_uid}</span>
                    </span>
                  </td>
                  <td className="num">{c.squad_count}/18</td>
                  <td className="num">{formatMoneyShort(c.budget)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        {state.squad.length > 0 && (
          <section className="card">
            <h3>Seu elenco ({state.squad.length}/18)</h3>
            <ul className="mini-squad">
              {state.squad.map((k) => (
                <li key={k.player_id}>
                  <span className="tag">{displayPosition(k.position)}</span> {k.name}
                  <span className="muted small">{formatMoneyShort(k.price)}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </aside>
    </div>
  );
}
