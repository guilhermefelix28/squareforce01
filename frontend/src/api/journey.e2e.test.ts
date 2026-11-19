/**
 * Jornada REAL completa (Entrega 8), com o mesmo cliente de API da interface contra um uvicorn verdadeiro:
 * importação → competição → leilão → complementação → negociações → escalação → partida ao vivo →
 * pós-partida → avanço → encerramento → nova competição.
 *
 * O servidor desta jornada usa SQUADFORCE_CLOCK_SCALE=25 (somente teste) para que o leilão (10 s/rodada) e o
 * mercado (3 min) caibam no tempo do teste. O leilão usa o MODELO FALSO de testes: as fórmulas reais estão
 * pendentes e não foram inventadas.
 */
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeAll, describe, expect, inject, it } from "vitest";
import { ApiError, configureApi, newIdempotencyKey } from "./client";
import {
  advanceRound,
  changePosture,
  changeSpeed,
  closeSession,
  createProposal,
  createSession,
  getAuction,
  getAuctionSummary,
  getCalendar,
  getLineup,
  getLive,
  getMatchReport,
  getSeason,
  getSeasonStats,
  getSeasonSummary,
  getSession,
  getSquad,
  getTrading,
  getTradingSquads,
  adminLogin,
  importBase,
  placeBid,
  playRound,
  saveLineup,
  startAuction,
  startLive,
  startSeason,
  startTrading,
} from "./endpoints";

const REAL_XLSX = resolve(__dirname, "../../../Dados/jogadores.xlsx");
const hasReal = existsSync(REAL_XLSX);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function until<T>(fn: () => Promise<T>, ok: (v: T) => boolean, timeoutMs = 90_000, stepMs = 250): Promise<T> {
  const end = Date.now() + timeoutMs;
  for (;;) {
    const v = await fn();
    if (ok(v)) return v;
    if (Date.now() > end) throw new Error(`Tempo esgotado aguardando condição: ${JSON.stringify(v).slice(0, 300)}`);
    await sleep(stepMs);
  }
}

beforeAll(() => {
  configureApi({ baseUrl: inject("fastBackendUrl"), retryDelayMs: 50, fetchImpl: (...a) => fetch(...a) });
});

describe.runIf(hasReal)("jornada completa contra o backend real", () => {
  it("do leilão ao encerramento e nova competição", async () => {
    const xlsx = () => new File([readFileSync(REAL_XLSX)], "jogadores.xlsx");
    await adminLogin("9153");
    expect((await importBase("clubs", xlsx())).rows_imported).toBe(40);
    expect((await importBase("players", xlsx())).rows_imported).toBeGreaterThan(1500);

    // 1. competição: Liga com 4 clubes, turno único
    const s = await createSession({ format: "league", num_clubs: 4, user_club_uid: 322, league_rounds: "single", confirm_replace: true });
    expect(s.phase).toBe("setup");

    // 2. leilão real (lance do usuário na primeira rodada)
    const st = await startAuction(s.id);
    const target = st.round!.players[0];
    try {
      await placeBid(s.id, { player_id: target.unique_id, amount: target.minimum_bid, round_number: st.round!.number });
    } catch (e) {
      // com o relógio acelerado a rodada pode fechar antes do lance: a recusa vem padronizada do servidor
      expect((e as ApiError).code).toMatch(/STALE_ROUND|ROUND_CLOSED/);
    }
    // 3. complementação automática dos elencos
    await until(() => getSession(s.id), (x) => x.phase === "squad_completion", 120_000, 500);
    await until(() => getAuction(s.id), (a) => a.phase === "completed");
    const auctionSummary = await getAuctionSummary(s.id);
    expect(auctionSummary.squads.every((sq) => sq.contracts.length === 18)).toBe(true);

    // 4. negociações: proposta real do usuário a um bot (aceita ou recusada pelo bot)
    await startTrading(s.id);
    const squads = await getTradingSquads(s.id);
    const mine = squads.find((x) => x.is_user)!;
    const other = squads.find((x) => !x.is_user)!;
    const give = mine.players[0];
    const take = other.players.find((p) => p.position === give.position) ?? other.players[0];
    const prop = await createProposal(s.id, { recipient_club_uid: other.club_uid, offered_player_id: give.unique_id, requested_player_id: take.unique_id, money: 0 });
    expect(prop.status).toBe("pending");
    const market = await until(() => getTrading(s.id), (m) => m.phase === "finished", 60_000, 500);
    expect(market.recent_decisions.some((d) => d.id === prop.id)).toBe(true);
    expect((await getSession(s.id)).phase).toBe("competition");

    // 5. competição: escalação definida pelo usuário
    const season = await startSeason(s.id);
    expect(season.phase).toBe("ready");
    const squad = await getSquad(s.id);
    expect(squad).toHaveLength(18);
    let lineup = await getLineup(s.id);
    if (lineup.has_match) {
      const starters = (lineup.starters ?? []).map((x) => x.player);
      [starters[9], starters[10]] = [starters[10], starters[9]];
      lineup = await saveLineup(s.id, { formation: lineup.formation!, starters, bench: (lineup.bench ?? []).map((b) => b.player), posture: "defensiva" });
      expect(lineup.source).toBe("user");
      expect(lineup.posture).toBe("defensiva");

      // 6. partida ao vivo com relógio do servidor, mudança de postura e de velocidade
      const live = await startLive(s.id, "60s");
      expect(live.finished).toBe(false);
      await sleep(600);
      const mid = await getLive(s.id);
      expect(mid.events.every((e) => e.second <= mid.game_second + 1e-6)).toBe(true);
      const changed = await changePosture(s.id, "ataque_total").catch((e: ApiError) => e);
      if (!(changed instanceof ApiError)) expect(changed.postures[changed.user_side]).toMatch(/ataque_total|defensiva/);
      const final = await changeSpeed(s.id, "instant").catch(() => getLive(s.id));
      const done = final.finished ? final : await until(() => getLive(s.id), (x) => x.finished, 30_000);

      // 7. rodada processada em paralelo reproduz exatamente a partida apresentada
      const played = await playRound(s.id);
      const userFixture = played.fixtures.find((f) => f.is_user_match)!;
      expect(userFixture.score).toEqual(done.score);
      const report = await getMatchReport(s.id, userFixture.match_id);
      expect(report.ratings.length).toBeGreaterThan(20);
      expect(report.lineups?.find((l) => l.club_uid === 322)?.initial_posture).toBe("defensiva");
    } else {
      await playRound(s.id);
    }

    // 8. avanço manual até o encerramento
    for (let i = 0; i < 10; i++) {
      const cur = await getSeason(s.id);
      if (cur.phase === "finished") break;
      if (cur.phase === "ready") await playRound(s.id, newIdempotencyKey());
      await advanceRound(s.id);
    }
    const end = await getSeason(s.id);
    expect(end.phase).toBe("finished");
    expect((await getSession(s.id)).phase).toBe("finished");
    const cal = await getCalendar(s.id);
    expect(cal.rounds.every((r) => r.fixtures.every((f) => f.played))).toBe(true);
    const stats = await getSeasonStats(s.id);
    expect(stats.matches_played).toBe(6);
    const summary = await getSeasonSummary(s.id);
    expect(summary.finished).toBe(true);
    expect(summary.history).toHaveLength(6);
    expect(summary.user_campaign.played).toBe(3);

    // 9. nova competição: substituir exige confirmação e encerra a anterior
    const refused = await createSession({ format: "cup", num_clubs: 2, user_club_uid: 322, league_rounds: null, confirm_replace: false }).catch((e) => e);
    expect(refused).toBeInstanceOf(ApiError);
    const next = await createSession({ format: "cup", num_clubs: 2, user_club_uid: 322, league_rounds: null, confirm_replace: true });
    expect(next.id).not.toBe(s.id);
    expect((await getSession(s.id)).status).toBe("closed");
    await closeSession(next.id);
  }, 240_000);
});
