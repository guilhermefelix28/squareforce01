import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { ApiError, newIdempotencyKey } from "../../api/client";
import { cancelBid, placeBid } from "../../api/endpoints";
import { ClubCrest } from "../../components/ClubCrest";
import { Notice } from "../../components/Notice";
import { PlayerCard, PositionBadge } from "../../components/PlayerCard";
import { formatClock, formatMoney, formatMoneyShort, parseMoney } from "../../domain/money";
import { POSITION_ORDER, byPosition } from "../../domain/positions";
import type { AuctionState, Club, Formation } from "../../types/api";

const BID_ERRORS: Record<string, string> = {
  BELOW_MINIMUM_BID: "Lance abaixo do mínimo deste atleta.",
  INSUFFICIENT_FUNDS: "Lance acima do disponível: é preciso preservar R$ 500 mil por vaga restante.",
  BID_UNCHANGED: "Seu lance já está neste valor.",
  STALE_ROUND: "A rodada terminou antes do lance chegar ao servidor.",
  ROUND_CLOSED: "A rodada terminou antes do lance chegar ao servidor.",
  SQUAD_FULL: "Seu elenco já tem 18 jogadores.",
  NO_ACTIVE_BID: "Você não tem lance ativo nesta rodada.",
};

/** Cronômetro circular da rodada. */
function Ring({ remainingMs, totalMs }: { remainingMs: number; totalMs: number }) {
  const r = 46;
  const c = 2 * Math.PI * r;
  const frac = totalMs > 0 ? Math.max(0, Math.min(1, remainingMs / totalMs)) : 0;
  const urgent = remainingMs <= 3000;
  return (
    <div className={`ring${urgent ? " is-urgent" : ""}`} role="timer" aria-label={`Tempo da rodada: ${Math.ceil(remainingMs / 1000)} segundos`}>
      <svg viewBox="0 0 110 110" aria-hidden>
        <circle className="ring__bg" cx="55" cy="55" r={r} />
        <circle className="ring__fg" cx="55" cy="55" r={r} strokeDasharray={c} strokeDashoffset={c * (1 - frac)} />
      </svg>
      <span className="ring__label">{Math.ceil(remainingMs / 1000)}</span>
    </div>
  );
}

/** Vagas da formação escolhida antes do leilão (DR-02) × jogadores já contratados. */
export function FormationVacancies({ formation, owned }: { formation: Formation; owned: string[] }) {
  const need = new Map<string, number>();
  formation.positions.forEach((p) => need.set(p, (need.get(p) ?? 0) + 1));
  const have = new Map<string, number>();
  owned.forEach((p) => have.set(p, (have.get(p) ?? 0) + 1));
  return (
    <div className="vacancies" aria-label={`Vagas da formação ${formation.id}`}>
      {POSITION_ORDER.filter((p) => need.has(p)).map((p) => {
        const h = have.get(p) ?? 0;
        const n = need.get(p)!;
        return (
          <span key={p} className={`vacancy${h >= n ? " is-full" : " is-missing"}`}>
            <PositionBadge position={p} size="sm" /> {Math.min(h, 99)}/{n}
          </span>
        );
      })}
    </div>
  );
}

export function AuctionBoard({
  sessionId,
  state,
  clubs,
  formation,
  roundRemainingMs,
  globalRemainingMs,
  onChanged,
}: {
  sessionId: string;
  state: AuctionState;
  clubs: Club[];
  formation?: Formation | null;
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
  const steps = [...state.bid_increments].sort((a, b) => a - b);
  const small = steps[0] ?? 100_000; // botões − e + (passo de R$ 100 mil)
  const quick = steps.filter((s) => s > small); // atalhos: −1 mi, −500 mil, +500 mil, +1 mi

  function choose(id: number) {
    const p = round?.players.find((x) => x.unique_id === id);
    if (!p) return;
    setSelected(id);
    setAmountText(String(active && active.player_id === id ? active.amount : p.minimum_bid));
    setFeedback(null);
  }

  /** Aumenta ou reduz o valor (redução permitida: decisão DR-01), nunca abaixo do mínimo nem acima do máximo. */
  function add(step: number) {
    if (!player) return;
    const base = Number.isNaN(amount) ? player.minimum_bid : amount;
    const next = Math.min(state.max_bid, Math.max(player.minimum_bid, base + step));
    setAmountText(String(next));
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

  async function withdraw() {
    if (!active || !round) return;
    setBusy(true);
    setFeedback(null);
    try {
      await cancelBid(sessionId, round.number, keyRef.current);
      setFeedback({ kind: "success", text: `Lance em ${activePlayer?.name ?? "atleta"} cancelado. Você pode dar outro lance até o fim da rodada.` });
      onChanged();
    } catch (err) {
      const code = err instanceof ApiError ? err.code : "";
      setFeedback({ kind: "error", text: BID_ERRORS[code] ?? (err instanceof ApiError ? err.message : "Falha ao cancelar o lance.") });
    } finally {
      keyRef.current = newIdempotencyKey();
      setBusy(false);
    }
  }

  const canBid = !!round && state.open_slots > 0 && roundRemainingMs > 0;
  const squad = byPosition(state.squad, (k) => k.position);
  const last = state.recent_results[0];
  const lowering = active && player && active.player_id === player.unique_id && !Number.isNaN(amount) && amount < active.amount;

  return (
    <div className="auction">
      <section className="auction__main stack">
        <header className="card auction-head">
          <Ring remainingMs={roundRemainingMs} totalMs={round?.duration_ms ?? 10_000} />
          <div className="auction-head__info">
            <span className="muted small">Rodada {round?.number ?? "—"}</span>
            <h2>{round ? <><PositionBadge position={round.position} /> em disputa</> : "Aguardando rodada"}</h2>
            <span className="muted small">Leilão termina em <strong className="tabular">{formatClock(globalRemainingMs)}</strong></span>
          </div>
          <dl className="stats stats--inline">
            <div><dt>Saldo</dt><dd>{formatMoneyShort(state.budget)}</dd></div>
            <div><dt>Lance máximo</dt><dd>{formatMoneyShort(state.max_bid)}</dd></div>
            <div><dt>Vagas</dt><dd>{state.open_slots}</dd></div>
          </dl>
        </header>

        <ul className="card-grid" aria-label="Jogadores da rodada">
          {round?.players.map((p) => {
            const mine = active?.player_id === p.unique_id;
            return (
              <li key={p.unique_id}>
                <button
                  type="button"
                  className={`lot2 ${selected === p.unique_id ? "is-selected" : ""} ${mine ? "is-mine" : ""}`}
                  aria-pressed={selected === p.unique_id}
                  aria-label={`${p.name}, ${p.age} anos, ${p.club_short_name}, mínimo ${formatMoneyShort(p.minimum_bid)}`}
                  onClick={() => choose(p.unique_id)}
                  disabled={!canBid}
                >
                  <PlayerCard
                    id={p.unique_id}
                    name={p.name}
                    position={p.position}
                    age={p.age}
                    club={{ name: p.club_short_name, uid: p.club_uid ?? undefined }}
                    hasPhoto={p.has_photo}
                    footer={
                      <>
                        <span className="muted small">mínimo</span> <strong className="tabular">{formatMoneyShort(p.minimum_bid)}</strong>
                        {mine && <div><span className="tag tag--user">seu lance: {formatMoneyShort(active!.amount)}</span></div>}
                      </>
                    }
                  />
                </button>
              </li>
            );
          })}
        </ul>

        <form className="card bid-panel" onSubmit={submit} aria-label="Fazer lance">
          {player ? (
            <>
              <h3>Lance em {player.name}</h3>
              <div className="stepper-input">
                <button type="button" className="btn btn--ghost" onClick={() => add(-small)} aria-label="Diminuir lance"
                  disabled={!Number.isNaN(amount) && amount <= player.minimum_bid}>−</button>
                <input
                  inputMode="numeric"
                  aria-label={`Valor para ${player.name} (mínimo ${formatMoney(player.minimum_bid)})`}
                  value={amountText}
                  onChange={(e) => setAmountText(e.target.value)}
                  aria-invalid={Number.isNaN(amount)}
                  placeholder="Ex.: 2500000 ou 2,5 mi"
                />
                <button type="button" className="btn btn--ghost" onClick={() => add(small)} aria-label="Aumentar lance">+</button>
              </div>
              <div className="steps" role="group" aria-label="Atalhos de valor">
                {[...quick].reverse().map((inc) => (
                  <button key={`-${inc}`} type="button" className="btn btn--ghost btn--small step--down" onClick={() => add(-inc)} aria-label={`Reduzir ${formatMoneyShort(inc)}`}>
                    −{formatMoneyShort(inc).replace("R$ ", "")}
                  </button>
                ))}
                {quick.map((inc) => (
                  <button key={`+${inc}`} type="button" className="btn btn--ghost btn--small step--up" onClick={() => add(inc)}>
                    +{formatMoneyShort(inc).replace("R$ ", "")}
                  </button>
                ))}
              </div>
              <p className="muted small" style={{ textAlign: "center" }}>
                {Number.isNaN(amount) ? "Valor inválido." : `Você está oferecendo ${formatMoney(amount)}.`}
                {lowering && " Você está reduzindo seu lance."}
              </p>
              <button type="submit" className="btn btn--cta btn--block" disabled={!canBid || busy || Number.isNaN(amount)}>
                {busy ? "Enviando…" : lowering ? "Confirmar novo valor" : "Confirmar lance"}
              </button>
            </>
          ) : (
            <p className="muted" style={{ textAlign: "center" }}>
              {canBid ? "Toque em um jogador para fazer seu lance." : state.open_slots === 0 ? "Seu elenco está completo." : "Aguardando a próxima rodada…"}
            </p>
          )}
          {active && (
            <div className="active-bid">
              <span className="small">Oferta ativa: <strong>{formatMoneyShort(active.amount)}</strong> em {activePlayer?.name ?? ""}</span>
              <button type="button" className="btn btn--danger-ghost btn--small" onClick={() => void withdraw()} disabled={busy || roundRemainingMs <= 0}>
                ✕ Cancelar meu lance
              </button>
            </div>
          )}
          {feedback && <Notice kind={feedback.kind}>{feedback.text}</Notice>}
          <p className="muted small" style={{ textAlign: "center" }}>Ofertas são sigilosas: você vê apenas o seu próprio lance. Você pode aumentar, reduzir ou cancelar o seu lance até o fim da rodada.</p>
        </form>
      </section>

      <aside className="auction__clubs stack" aria-label="Clubes no leilão">
        <section className="card">
          <h3>Clubes no leilão</h3>
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
      </aside>

      <aside className="auction__side stack" aria-label="Seu elenco e resultados">
        <section className="card">
          <h3>Seu elenco ({state.squad.length}/18)</h3>
          {formation && (
            <>
              <span className="muted small">Vagas da formação {formation.id}</span>
              <FormationVacancies formation={formation} owned={state.squad.map((k) => k.position)} />
            </>
          )}
          {squad.length === 0 ? (
            <p className="muted small">Nenhum jogador contratado ainda.</p>
          ) : (
            <div className="pos-groups">
              {POSITION_ORDER.filter((p) => squad.some((k) => k.position === p)).map((pos) => (
                <div key={pos} className="pos-group">
                  <PositionBadge position={pos} size="sm" />
                  <div className="pos-group__items">
                    {squad.filter((k) => k.position === pos).map((k) => (
                      <span key={k.player_id} className="chip"><span>{k.name}</span><span className="muted">{formatMoneyShort(k.price)}</span></span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
        <section className="card">
          <h3>Última rodada</h3>
          {!last && <p className="muted small">Nenhuma rodada encerrada ainda.</p>}
          {last && (
            <ol className="results">
              {state.recent_results.map((r) => (
                <li key={r.number}>
                  <span className="muted small">Rodada {r.number} · <PositionBadge position={r.position} size="sm" /></span>
                  {r.sales.map((s) => (
                    <span key={s.player_id} className={`sale ${s.club_uid === state.user_club_uid ? "is-user" : ""}`}>
                      <span className={`tag ${s.club_uid === state.user_club_uid ? "tag--user" : ""}`}>{s.club_uid === state.user_club_uid ? "SEU" : "VENDIDO"}</span>
                      <strong>{s.player_name}</strong> → {clubName.get(s.club_uid) ?? `#${s.club_uid}`} · {formatMoneyShort(s.price)}
                    </span>
                  ))}
                  {r.unsold_player_ids.length > 0 && <span className="muted small">{r.unsold_player_ids.length} sem lance vencedor</span>}
                </li>
              ))}
            </ol>
          )}
        </section>
      </aside>
    </div>
  );
}
