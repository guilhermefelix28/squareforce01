/**
 * Comunicação REAL frontend <-> backend: usa o mesmo cliente de API da interface contra o
 * uvicorn iniciado em backend.global-setup.ts (banco temporário; planilha real só leitura).
 */
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeAll, describe, expect, inject, it } from "vitest";
import { ApiError, configureApi, newIdempotencyKey } from "./client";
import {
  closeSession,
  createSession,
  getAuction,
  getAuctionSummary,
  getCompetition,
  getCompetitionOptions,
  placeBid,
  startAuction,
  getHealth,
  getSession,
  importBase,
  listClubs,
  listPlayers,
  sessionSocketUrl,
} from "./endpoints";

const REAL_XLSX = resolve(__dirname, "../../../Dados/jogadores.xlsx");
const hasReal = existsSync(REAL_XLSX);

beforeAll(() => {
  configureApi({ baseUrl: inject("backendUrl"), retryDelayMs: 50, fetchImpl: (...a) => fetch(...a) });
});

const xlsx = () => new File([readFileSync(REAL_XLSX)], "jogadores.xlsx");

describe("frontend <-> backend real", () => {
  it("consulta o health check", async () => {
    const h = await getHealth();
    expect(h.status).toBe("ok");
    expect(h.database.schema_version).toBe(2);
  });

  it("recebe erro padronizado em sessão inexistente", async () => {
    const err = await getSession("inexistente").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("SESSION_NOT_FOUND");
  });

  it.runIf(hasReal)("importa as bases reais e consulta o catálogo", async () => {
    const clubs = await importBase("clubs", xlsx());
    expect(clubs.rows_imported).toBe(40);
    const players = await importBase("players", xlsx());
    expect(players.rows_imported).toBe(1583);
    expect(players.warnings?.filter((w) => w.code === "GENERATED_ID")).toHaveLength(11);
    expect((await listClubs()).total).toBe(40);
    const goalkeepers = await listPlayers({ position: "GOL", limit: 5 });
    expect(goalkeepers.items.every((p) => p.natural_positions.includes("GK"))).toBe(true);
    const opts = await getCompetitionOptions();
    expect(opts.catalog_ready).toBe(true);
    expect(opts.division_counts).toEqual({ A: 20, B: 20 });
  });

  it.runIf(hasReal)("cria sessão, bloqueia importação, notifica via WebSocket e encerra", async () => {
    const key = newIdempotencyKey();
    const cfg = { format: "cup" as const, num_clubs: 16, user_club_uid: 322, league_rounds: null, confirm_replace: false };
    const s = await createSession(cfg, key);
    // repetição do mesmo comando (ex.: resposta perdida) devolve a mesma sessão
    expect((await createSession(cfg, key)).id).toBe(s.id);

    const comp = await getCompetition(s.id);
    expect(comp.structure.kind).toBe("cup");
    expect(comp.structure.participants[0]).toBe(322);
    expect(comp.structure.participants).toEqual(s.participants);
    expect(comp.structure.total_matches).toBe(15);

    const blocked = await importBase("players", xlsx()).catch((e) => e);
    expect(blocked.code).toBe("IMPORT_BLOCKED_ACTIVE_COMPETITION");

    const ws = new WebSocket(sessionSocketUrl(s.id));
    const messages: { type: string; version?: number }[] = [];
    const closedEvt = new Promise<void>((ok) => {
      ws.onmessage = (ev) => {
        const m = JSON.parse(String(ev.data));
        messages.push(m);
        if (m.type === "session.closed") ok();
      };
    });
    await new Promise<void>((ok) => (ws.onopen = () => ok()));
    await expect.poll(() => messages.length).toBeGreaterThan(0);
    expect(messages[0]).toMatchObject({ type: "session.snapshot", version: 1 });

    const closed = await closeSession(s.id, s.version);
    expect(closed.status).toBe("closed");
    await closedEvt;
    expect(messages.at(-1)).toMatchObject({ type: "session.closed", version: 2 });
    ws.close();
  });

  it.runIf(hasReal)("leilão com relógio real: lance, resultado da rodada via WebSocket e sigilo", async () => {
    const s = await createSession({ format: "cup", num_clubs: 2, user_club_uid: 322, league_rounds: null, confirm_replace: true });
    const ws = new WebSocket(sessionSocketUrl(s.id));
    const types: string[] = [];
    const roundClosed = new Promise<void>((ok) => {
      ws.onmessage = (ev) => {
        const m = JSON.parse(String(ev.data));
        types.push(m.type);
        if (m.type === "auction.round_closed") ok();
      };
    });
    await new Promise<void>((ok) => (ws.onopen = () => ok()));

    const st = await startAuction(s.id);
    expect(st.phase).toBe("running");
    expect(st.round!.players).toHaveLength(5);
    const target = st.round!.players[0];
    const ack = await placeBid(s.id, { player_id: target.unique_id, amount: target.minimum_bid, round_number: st.round!.number });
    expect(ack.amount).toBe(target.minimum_bid);
    const view = await getAuction(s.id);
    expect(view.active_bid?.player_id).toBe(target.unique_id);
    expect(JSON.stringify(view)).not.toMatch(/overall|market_value|personality|"bids"/);

    await roundClosed; // relógio do servidor fecha a rodada sozinho (~10 s)
    const after = await getAuction(s.id);
    expect(after.rounds_completed).toBeGreaterThanOrEqual(1);
    const sale = after.recent_results.at(-1)!.sales.find((x) => x.player_id === target.unique_id);
    if (sale) expect(sale.price).toBeGreaterThanOrEqual(target.minimum_bid);
    expect(types).toContain("auction.round_started");
    await expect(getAuctionSummary(s.id)).rejects.toMatchObject({ code: "AUCTION_NOT_FINISHED" });
    ws.close();
    await closeSession(s.id);
  });
});
