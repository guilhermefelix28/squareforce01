import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { App, navItems, parseHash, phaseHome } from "../../app/App";
import { apiError, fakeApi, json, SESSION } from "../../test/fakeApi";
import {
  CALENDAR, LINEUP, LIVE, OPP, REPORT, SEASON_FINISHED, SEASON_PLAYED, SEASON_READY, SESSION_COMP, SID, SQUAD, STATS, SUMMARY, USER, baseRoutes,
} from "../../test/seasonFixtures";
import { slotCoordinates, swap } from "./Pitch";

const S = `/api/sessions/${SID}`;
const header = (init: RequestInit, name: string) => new Headers(init.headers).get(name);

beforeEach(() => {
  localStorage.setItem("squadforce.sessionId", SID);
});

function at(hash: string) {
  window.location.hash = hash;
  return render(<App />);
}

describe("navegação contextual", () => {
  it("mostra as telas de cada fase", () => {
    const labels = (phase: string | null) => navItems(phase ? ({ ...SESSION, phase } as never) : null).map((i) => i.label);
    expect(labels(null)).toEqual(["Início", "Nova partida"]);
    expect(labels("setup")).toContain("Tática");
    expect(labels("auction")).toContain("Leilão");
    expect(labels("trading")).toContain("Mercado");
    expect(labels("trading")).not.toContain("Leilão");
    expect(labels("competition")).toEqual(["Início", "Central", "Escalação", "Partida", "Competição (detalhes e encerrar)"]);
    expect(labels(null)).not.toContain("Dados"); // área de dados oculta (DR-04)
    expect(labels("finished")).toContain("Encerramento");
    expect(phaseHome({ ...SESSION, phase: "competition" } as never)).toBe("#/temporada/central");
    expect(phaseHome({ ...SESSION, phase: "setup" } as never)).toBe("#/tatica");
    expect(phaseHome({ ...SESSION, phase: "setup", user_formation: "4-2-2-2" } as never)).toBe("#/auction");
  });

  it("pular para o conteúdo move o foco sem trocar de tela", async () => {
    fakeApi({ ...baseRoutes(), [`GET ${S}/season`]: () => json(200, SEASON_PLAYED), [`GET ${S}/season/lineup`]: () => json(200, LINEUP) });
    at("#/temporada/central");
    await screen.findByText("Resultados · Rodada 1");
    await userEvent.tab();
    expect(screen.getByText("Pular para o conteúdo")).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    expect(document.getElementById("conteudo")).toHaveFocus();
    expect(window.location.hash).toBe("#/temporada/central");
  });

  it("interpreta rotas", () => {
    expect(parseHash("#/temporada/estatisticas")).toEqual({ page: "temporada", tab: "estatisticas" });
    expect(parseHash("#/temporada/xyz")).toEqual({ page: "temporada", tab: "central" });
    expect(parseHash("#/pos/C-R1-M01")).toEqual({ page: "pos", matchId: "C-R1-M01" });
    expect(parseHash("#/qualquer")).toEqual({ page: "home" });
    expect(parseHash("#/data")).toEqual({ page: "home" }); // a área de dados não é mais uma rota pública
    expect(parseHash("#/admin")).toEqual({ page: "admin" });
  });
});

describe("campo interativo (lógica)", () => {
  const base = { formation: ["GK", "DR", "DC"] as never, starters: [1, 2, 3], bench: [4, 5] };
  it("troca titulares, banco e elenco", () => {
    expect(swap(base, { zone: "slot", index: 0 }, { zone: "slot", index: 2 }).starters).toEqual([3, 2, 1]);
    const r = swap(base, { zone: "slot", index: 1 }, { zone: "bench", index: 0 });
    expect(r.starters).toEqual([1, 4, 3]);
    expect(r.bench).toEqual([2, 5]);
    const p = swap(base, { zone: "pool", player: 9 }, { zone: "slot", index: 0 });
    expect(p.starters).toEqual([9, 2, 3]); // o titular anterior volta ao elenco
    const add = swap(base, { zone: "pool", player: 9 }, { zone: "bench", index: 2 });
    expect(add.bench).toEqual([4, 5, 9]);
    const out = swap(base, { zone: "bench", index: 0 }, { zone: "pool", player: -1 });
    expect(out.bench).toEqual([5]); // retirado para fora da lista
    const exch = swap(base, { zone: "bench", index: 0 }, { zone: "pool", player: 9 });
    expect(exch.bench).toEqual([9, 5]); // trocado por um atleta de fora
    const full = { ...base, bench: [4, 5, 6, 7, 8, 10, 11] };
    expect(swap(full, { zone: "pool", player: 9 }, { zone: "bench", index: 7 }).bench).toHaveLength(7);
  });
  it("posiciona goleiro embaixo e laterais nas pontas", () => {
    const c = slotCoordinates(["GK", "DR", "DC", "DC", "DL", "DM", "MC", "MC", "STC", "STC", "STC"] as never);
    expect(c[0].y).toBeGreaterThan(c[8].y);
    expect(c[4].x).toBeLessThan(c[2].x); // LE à esquerda
    expect(c[1].x).toBeGreaterThan(c[3].x); // LD à direita
  });
});

describe("central da temporada", () => {
  it("inicia a competição pelo serviço real com idempotência", async () => {
    let started = false;
    const { calls } = fakeApi({
      ...baseRoutes(),
      [`GET ${S}/season`]: () => (started ? json(200, SEASON_READY) : apiError(404, "SEASON_NOT_FOUND")),
      [`POST ${S}/season/start`]: () => { started = true; return json(201, SEASON_READY); },
      [`GET ${S}/season/lineup`]: () => json(200, LINEUP),
    });
    at("#/temporada/central");
    await userEvent.click(await screen.findByRole("button", { name: /Iniciar competição/ }));
    expect(await screen.findByRole("button", { name: /Escalar e jogar/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Jogar com esta escalação" })).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST")!;
    expect(header(post.init, "Idempotency-Key")).toBeTruthy();
  });

  it("após a rodada mostra resultados e avança somente por clique", async () => {
    let advanced = false;
    const { calls } = fakeApi({
      ...baseRoutes(),
      [`GET ${S}/season`]: () => json(200, advanced ? { ...SEASON_READY, round_number: 2, round_label: "Rodada 2" } : SEASON_PLAYED),
      [`POST ${S}/season/advance`]: () => { advanced = true; return json(200, { ...SEASON_READY, round_number: 2, round_label: "Rodada 2" }); },
      [`GET ${S}/season/lineup`]: () => json(200, LINEUP),
    });
    at("#/temporada/central");
    expect(await screen.findByText("Resultados · Rodada 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ver partida .*2 – 1/ })).toBeInTheDocument();
    expect(calls.some((c) => c.path.endsWith("/advance"))).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: /Próximo confronto/ }));
    expect(await screen.findByRole("heading", { name: /Rodada 2/ })).toBeInTheDocument();
  });

  it("explica falha de rodada sem consolidação parcial", async () => {
    fakeApi({
      ...baseRoutes(),
      [`GET ${S}/season`]: () => json(200, { ...SEASON_READY, fixtures: SEASON_READY.fixtures.map((f) => ({ ...f, is_user_match: false })), byes: [322] }),
      [`POST ${S}/season/play`]: () => apiError(500, "ROUND_FAILED", "1 partida(s) falharam; nada foi consolidado.", false),
      [`GET ${S}/season/lineup`]: () => json(200, { ...LINEUP, has_match: false }),
    });
    at("#/temporada/central");
    expect(await screen.findByText(/Seu clube folga/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Simular rodada/ }));
    expect(await screen.findByText("A rodada não foi consolidada")).toBeInTheDocument();
    expect(screen.getByText(/só as partidas que falharam serão repetidas/)).toBeInTheDocument();
  });

  it("estatísticas: quatro abas, rankings e filtros", async () => {
    fakeApi({
      ...baseRoutes(),
      [`GET ${S}/season`]: () => json(200, SEASON_PLAYED),
      [`GET ${S}/season/stats`]: () => json(200, STATS),
      [`GET ${S}/season/calendar`]: () => json(200, CALENDAR),
    });
    at("#/temporada/estatisticas");
    // painel sobre a central (sem trocar de tela)
    expect(await screen.findByRole("dialog", { name: "Estatísticas" })).toBeInTheDocument();
    const tabs = await screen.findAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual(["Classificação", "Jogadores", "Clubes", "Estatísticas avançadas"]);
    await userEvent.click(screen.getByRole("tab", { name: "Jogadores" }));
    const table = await screen.findByRole("table", { name: "Ranking de jogadores" });
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Atleta 9");
    await userEvent.selectOptions(screen.getByLabelText("Ranking"), "assists");
    expect(within(screen.getByRole("table", { name: "Ranking de jogadores" })).getAllByRole("row")[1]).toHaveTextContent("Rival");
    await userEvent.type(screen.getByLabelText("Buscar jogador"), "Atleta");
    expect(within(screen.getByRole("table", { name: "Ranking de jogadores" })).getAllByRole("row")).toHaveLength(2);
    await userEvent.click(screen.getByRole("tab", { name: "Estatísticas avançadas" }));
    expect(await screen.findByRole("table", { name: "Estatísticas avançadas" })).toBeInTheDocument();
  });

  it("calendário e histórico abrem o pós-partida", async () => {
    fakeApi({
      ...baseRoutes(),
      [`GET ${S}/season`]: () => json(200, SEASON_PLAYED),
      [`GET ${S}/season/calendar`]: () => json(200, CALENDAR),
      [`GET ${S}/season/matches/L-R01-M01`]: () => json(200, REPORT),
    });
    at("#/temporada/calendario");
    expect(await screen.findByText("Rodada 2")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: /Somente meus jogos/ }));
    await userEvent.click(screen.getAllByRole("button", { name: /Ver partida/ })[0]);
    expect(await screen.findByText("Craque da Partida")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Próxima rodada/ })).toBeInTheDocument();
  });
});

describe("escalação", () => {
  it("troca por toque, bloqueia indisponível e salva com idempotência", async () => {
    let body: Record<string, unknown> | null = null;
    const { calls } = fakeApi({
      ...baseRoutes(),
      [`GET ${S}/season`]: () => json(200, SEASON_READY),
      [`GET ${S}/season/lineup`]: () => json(200, LINEUP),
      [`GET ${S}/season/squad`]: () => json(200, SQUAD),
      [`POST ${S}/season/lineup`]: (_u, init) => {
        body = JSON.parse(String(init.body));
        return json(200, { ...LINEUP, source: "user", posture: "ofensiva" });
      },
    });
    at("#/escalacao");
    const gk = await screen.findByRole("button", { name: /Vaga GOL: Atleta 1,/ });
    // toque em dois atletas troca as posições
    await userEvent.click(gk);
    await userEvent.click(screen.getByRole("button", { name: /Vaga ATA: Atleta 9,/ }));
    expect(screen.getByRole("button", { name: /Vaga GOL: Atleta 9, Improvisado/ })).toBeInTheDocument();
    // indisponível não entra
    const out = screen.getByRole("button", { name: /Atleta 18/ });
    expect(out).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(out);
    expect(screen.queryByText(/Selecionado: escolha o destino/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Ofensiva" }));
    await userEvent.click(screen.getByRole("button", { name: "Salvar escalação" }));
    expect(await screen.findByText("Escalação salva no servidor.")).toBeInTheDocument();
    expect(screen.queryByText(/não é oficial/)).not.toBeInTheDocument();
    expect(body!.posture).toBe("ofensiva");
    expect((body!.starters as number[])[0]).toBe(1008);
    expect(header(calls.find((c) => c.method === "POST")!.init, "Idempotency-Key")).toBeTruthy();
  });

  it("arrastar e soltar entre banco e campo", async () => {
    fakeApi({
      ...baseRoutes(),
      [`GET ${S}/season`]: () => json(200, SEASON_READY),
      [`GET ${S}/season/lineup`]: () => json(200, LINEUP),
      [`GET ${S}/season/squad`]: () => json(200, SQUAD),
    });
    at("#/escalacao");
    const target = await screen.findByRole("button", { name: /Vaga ZAG: Atleta 3,/ });
    const source = screen.getByRole("button", { name: /Atleta 13/ });
    const data = new Map<string, string>();
    const dataTransfer = { setData: (k: string, v: string) => data.set(k, v), getData: (k: string) => data.get(k) ?? "", effectAllowed: "" };
    fireEvent.dragStart(source, { dataTransfer });
    fireEvent.dragOver(target, { dataTransfer });
    fireEvent.drop(target, { dataTransfer });
    expect(screen.getByRole("button", { name: /Vaga ZAG: Atleta 13,/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salvar escalação" })).toBeEnabled();
  });

  it("arrastar um titular para outra faixa (DEF/VOL/ME/ATA) troca a formação; desenho não oficial volta", async () => {
    fakeApi({
      ...baseRoutes(),
      [`GET ${S}/season`]: () => json(200, SEASON_READY),
      [`GET ${S}/season/lineup`]: () => json(200, LINEUP),
      [`GET ${S}/season/squad`]: () => json(200, SQUAD),
    });
    at("#/escalacao");
    await screen.findByRole("button", { name: /Vaga ZAG: Atleta 3,/ });
    const field = screen.getByRole("group", { name: "Campo: titulares por vaga" });
    field.getBoundingClientRect = () => ({ left: 0, top: 0, right: 680, bottom: 900, width: 680, height: 900, x: 0, y: 0, toJSON() {} });
    // faixas de função visíveis, com VOL e ME separados
    expect([...field.querySelectorAll("[data-band]")].map((e) => e.getAttribute("data-band"))).toEqual(["DEF", "VOL", "ME", "ATA"]);
    const data = new Map<string, string>();
    const dataTransfer = { setData: (k: string, v: string) => data.set(k, v), getData: (k: string) => data.get(k) ?? "", effectAllowed: "" };
    // jsdom não tem DragEvent com coordenadas: evento de mouse com dataTransfer
    const dropAt = (type: string, x: number, y: number) => {
      const e = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y });
      Object.defineProperty(e, "dataTransfer", { value: dataTransfer });
      fireEvent(field, e);
    };
    // 4-1-2-3: meia levado à faixa de volantes (y = 53,5%) => 4-2-1-3
    const me = screen.getAllByRole("button", { name: /^Vaga ME/ })[0];
    fireEvent.dragStart(me, { dataTransfer });
    expect(field).toHaveClass("is-dragging");
    dropAt("dragover", 340, 481);
    dropAt("drop", 340, 481);
    expect(await screen.findByText("Formação: 4-2-1-3")).toBeInTheDocument();
    expect(screen.getByLabelText("Formação")).toHaveValue("4-2-1-3");
    expect(screen.getAllByRole("button", { name: /^Vaga VOL/ })).toHaveLength(2);
    // volante levado ao ataque (y = 13%) => 4-1-1-4: não oficial, nada muda
    const vol = screen.getAllByRole("button", { name: /^Vaga VOL/ })[0];
    fireEvent.dragStart(vol, { dataTransfer });
    dropAt("drop", 340, 117);
    expect(await screen.findByText("Essa formação não é oficial")).toBeInTheDocument();
    expect(screen.getByLabelText("Formação")).toHaveValue("4-2-1-3");
  });

  it("mostra recusa do servidor", async () => {
    fakeApi({
      ...baseRoutes(),
      [`GET ${S}/season`]: () => json(200, SEASON_READY),
      [`GET ${S}/season/lineup`]: () => json(200, LINEUP),
      [`GET ${S}/season/squad`]: () => json(200, SQUAD),
      [`POST ${S}/season/lineup`]: () => apiError(422, "INVALID_LINEUP", "Indisponíveis: Atleta 2 (suspenso)."),
    });
    at("#/escalacao");
    await userEvent.click(await screen.findByRole("radio", { name: "Retranca" }));
    await userEvent.click(screen.getByRole("button", { name: "Salvar escalação" }));
    expect(await screen.findByText(/Indisponíveis: Atleta 2/)).toBeInTheDocument();
  });
});

describe("partida", () => {
  it("inicia na velocidade escolhida, muda postura e conclui a rodada", async () => {
    let live: Record<string, unknown> | null = null;
    let played = false;
    const { calls } = fakeApi({
      ...baseRoutes(),
      [`GET ${S}/season`]: () => json(200, played ? SEASON_PLAYED : SEASON_READY),
      [`GET ${S}/season/lineup`]: () => json(200, LINEUP),
      [`GET ${S}/season/live`]: () => (live ? json(200, live) : apiError(404, "LIVE_NOT_FOUND")),
      [`POST ${S}/season/live/start`]: (_u, init) => { live = { ...LIVE, speed: JSON.parse(String(init.body)).speed }; return json(201, live); },
      [`POST ${S}/season/live/posture`]: (_u, init) => {
        live = { ...LIVE, postures: [JSON.parse(String(init.body)).posture, "defensiva"] };
        return json(200, live);
      },
      [`POST ${S}/season/live/speed`]: () => { live = { ...LIVE, finished: true, minute: 94, speed: "instant" }; return json(200, live); },
      [`POST ${S}/season/play`]: () => { played = true; return json(200, SEASON_PLAYED); },
      [`GET ${S}/season/matches/L-R01-M01`]: () => json(200, REPORT),
    });
    at("#/partida");
    await userEvent.click(await screen.findByRole("radio", { name: "60 s" }));
    await userEvent.click(screen.getByRole("button", { name: /Iniciar partida/ }));
    expect(await screen.findByText("34'")).toBeInTheDocument();
    expect(screen.getByLabelText("Placar")).toHaveTextContent("1 – 0");
    expect(screen.getAllByRole("meter")).toHaveLength(11);
    expect(screen.getByText(/Substituições 0\/5/)).toBeInTheDocument();
    // DR-06: campo das duas equipes e outros jogos da rodada
    expect(screen.getByRole("img", { name: /Campo tático/ })).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Outros jogos da rodada" })).getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByText(/Falta de Rival 4 em Atleta 9/)).toBeInTheDocument(); // autor e vítima do pênalti
    expect(JSON.parse(String(calls.find((c) => c.path.endsWith("/live/start"))!.init.body)).speed).toBe("60s");
    await userEvent.click(screen.getByRole("button", { name: "Ataque Total" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Ataque Total" })).toHaveAttribute("aria-pressed", "true"));
    await userEvent.click(screen.getByRole("button", { name: "Instantâneo" }));
    await userEvent.click(await screen.findByRole("button", { name: /Concluir rodada/ }));
    expect(await screen.findByText("Craque da Partida")).toBeInTheDocument();
    expect(window.location.hash).toBe("#/pos/L-R01-M01");
  });
});

describe("pênaltis ao vivo", () => {
  it("narra cada cobrança com o batedor, o goleiro e o placar parcial", async () => {
    const kick = (seq: number, side: number, name: string, scored: boolean, sc: number[], gk: string) => ({
      seq, minute: 96, second: 5700, period: 2, type: "shootout_kick", side, club_uid: side === 0 ? USER : OPP, player: 1, player_name: name,
      other: 2, other_name: gk, data: { scored, shootout: sc },
    });
    const live = {
      ...LIVE, minute: 96, score: [1, 1], shootout: [1, 0],
      events: [...LIVE.events, { ...LIVE.events[0], seq: 40, minute: 96, type: "full_time", player_name: null },
        { ...LIVE.events[0], seq: 41, minute: 96, type: "shootout_start", player_name: null, club_uid: null, side: null },
        kick(42, 0, "Atleta 9", true, [1, 0], "Rival 1"), kick(43, 1, "Rival 7", false, [1, 0], "Atleta 1")],
    };
    fakeApi({
      ...baseRoutes(),
      [`GET ${S}/season`]: () => json(200, SEASON_READY),
      [`GET ${S}/season/lineup`]: () => json(200, LINEUP),
      [`GET ${S}/season/live`]: () => json(200, live),
    });
    at("#/partida");
    expect(await screen.findByText(/1ª cobrança: Atleta 9 bate e marca · pênaltis 1–0/)).toBeInTheDocument();
    expect(screen.getByText(/1ª cobrança: Rival 7 bate e perde \(goleiro Atleta 1\) · pênaltis 1–0/)).toBeInTheDocument();
    expect(screen.getByText(/decidida nos pênaltis, cobrança a cobrança/)).toBeInTheDocument();
    expect(screen.getByLabelText("Placar")).toHaveTextContent("Pênaltis 1–0"); // parcial, ainda sem o vencedor
  });
});

describe("encerramento", () => {
  it("mostra campeão, campanha do usuário e premiações", async () => {
    fakeApi({
      ...baseRoutes({ ...SESSION_COMP, phase: "finished" }),
      [`GET ${S}/season`]: () => json(200, SEASON_FINISHED),
      [`GET ${S}/season/summary`]: () => json(200, SUMMARY),
    });
    at("#/encerramento");
    expect(await screen.findByText("Campeão da Liga")).toBeInTheDocument();
    expect(screen.getByText(/Sua campanha · 1º lugar/)).toBeInTheDocument();
    expect(screen.getByText("Artilheiro")).toBeInTheDocument();
    expect(screen.getByText("Melhor média de notas (mín. 50% dos jogos)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Nova partida/ })).toBeInTheDocument();
  });

  it("encerra a partida e volta ao início (com confirmação)", async () => {
    let closed = false;
    const { calls } = fakeApi({
      ...baseRoutes({ ...SESSION_COMP, phase: "finished" }),
      [`GET ${S}/season`]: () => json(200, SEASON_FINISHED),
      [`GET ${S}/season/summary`]: () => json(200, SUMMARY),
      [`POST ${S}/close`]: () => {
        closed = true;
        return json(200, { ...SESSION_COMP, phase: "finished", status: "closed" });
      },
    });
    at("#/encerramento");
    await userEvent.click(await screen.findByRole("button", { name: /Encerrar e voltar ao início/ }));
    await userEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: /^Encerrar (liga|copa)$/ }));
    await waitFor(() => expect(window.location.hash).toBe("#/home"));
    expect(closed).toBe(true);
    expect((calls.find((c) => c.method === "POST")!.init.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^sf-/);
  });

  it("campeão indefinido quando o desempate não resolve", async () => {
    fakeApi({
      ...baseRoutes({ ...SESSION_COMP, phase: "finished" }),
      [`GET ${S}/season`]: () => json(200, { ...SEASON_FINISHED, champion_club_uid: null, tied_champions: [322, 329] }),
      [`GET ${S}/season/summary`]: () => json(200, { ...SUMMARY, champion_club_uid: null, tied_champions: [322, 329] }),
    });
    at("#/encerramento");
    expect(await screen.findByText("Campeão indefinido")).toBeInTheDocument();
    expect(screen.getByText(/não resolvido pelos critérios de desempate/)).toBeInTheDocument();
  });
});

describe("sincronização de versão", () => {
  it("fim da temporada atualiza a fase da sessão e a navegação", async () => {
    let finished = false;
    fakeApi({
      ...baseRoutes(),
      [`GET ${S}`]: () => json(200, finished ? { ...SESSION_COMP, phase: "finished", version: 9 } : SESSION_COMP),
      [`GET ${S}/season`]: () => json(200, finished ? SEASON_FINISHED : { ...SEASON_PLAYED, round_number: 3 }),
      [`POST ${S}/season/advance`]: () => { finished = true; return json(200, SEASON_FINISHED); },
      [`GET ${S}/season/lineup`]: () => json(200, LINEUP),
      [`GET ${S}/season/summary`]: () => json(200, SUMMARY),
    });
    at("#/temporada/central");
    expect(await screen.findByRole("listitem", { current: "step" })).toHaveTextContent("Temporada");
    await userEvent.click(await screen.findByRole("button", { name: /Encerrar competição/ }));
    expect(await screen.findByText("Competição encerrada")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Fim"));
  });
});

describe("reconexão", () => {
  it("avisa quando a sessão não pode mais ser recuperada", async () => {
    fakeApi({ ...baseRoutes(), [`GET ${S}`]: () => apiError(404, "SESSION_NOT_FOUND", "Sessão inexistente.") });
    at("#/temporada/central");
    expect(await screen.findByText("Sua competição não pode mais ser recuperada.")).toBeInTheDocument();
    await act(async () => undefined);
  });
});
