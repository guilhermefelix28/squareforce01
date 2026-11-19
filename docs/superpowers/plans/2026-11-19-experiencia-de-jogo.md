# Experiência de jogo — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** transformar a interface do SquadForce num fluxo de jogo guiado e aplicar as diretrizes do responsável (lance redutível, tática antes do leilão, goleiro, partida ao vivo completa, área oculta de dados).

**Architecture:** backend recebe mudanças aditivas (contratos, sessão, leilão, motor, admin); o frontend troca a casca de abas por uma casca de jogo (fase → tela → ação principal) reaproveitando hooks e cliente de API; componentes visuais novos (carta, campo, telão, letreiro, som) são compartilhados por todas as telas.

**Tech Stack:** FastAPI/Pydantic, pytest; React 19 + TS + Vite, Vitest; SVG/CSS; Web Audio.

**Spec:** `docs/superpowers/specs/2026-11-19-experiencia-de-jogo-design.md`

## Global Constraints
- Diretrizes do responsável prevalecem sobre o GDD; toda regra alterada vai para `docs/game-design/pendencias.md` como decisão do responsável (2026-11-19).
- Ordem de exibição das posições: **GOL · LD · ZAG · LE · VOL · ME · ATA**. Só exibição: `POSITION_ORDER` do backend **não muda** (afeta sorteio do leilão homologado).
- Tema escuro padrão (ignora preferência do SO); claro pelo botão.
- Senha da área oculta: `9153`, `SQUADFORCE_ADMIN_PASSWORD` sobrepõe; verificação no servidor.
- Goleiro: `gk_fatigue_multiplier = 0.35`.
- Informação oculta nunca exposta: overall, atributos, valor interno, condição do adversário.
- Contrato mudou → `export_openapi.py` + `npm run gen:api` + `docs/api/contratos.md`.
- Bug → teste de regressão primeiro. Pronto só com pytest, Vitest, e2e e build verdes.
- Commits pequenos na branch `experiencia-de-jogo`, com a linha `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus
1. Escalação com 5 jogadores na mesma linha em tela de 360 px → cartas não se sobrepõem (teste de layout para todas as 11 formações).
2. Arrastar para uma linha que gera desenho não oficial → carta volta, aviso, escalação inalterada.
3. Ao vivo em velocidade "instantâneo" e após reconexão → outros jogos já finais e iguais ao resultado consolidado da rodada.
4. Lance reduzido abaixo do mínimo ou igual ao atual → erro claro (`BELOW_MINIMUM_BID` / `BID_UNCHANGED`), lance anterior preservado.
5. Importação sem token de admin (ou senha errada) → 401, nada importado.

---

### Task 1: Status dos serviços (bug)
**Files:** Modify `services/gateway/routes.py:88-96`; Test `tests/integration/test_health_and_assets.py`
- [ ] Teste `test_bot_ai_and_match_engine_are_ready`: `services["bot_ai"] == services["match_engine"] == "ready"`. Rodar → FAIL.
- [ ] Trocar os dois `"planned"` fixos por `"ready"`. Rodar → PASS. Commit.

### Task 2: Lance redutível
**Files:** `services/auction/engine.py:368-371`, `frontend/src/features/auction/AuctionBoard.tsx:19`; Test `tests/unit/test_auction_engine.py` (ou o arquivo de testes do motor existente)
- [ ] Testes: `test_club_may_reduce_own_bid_on_same_player` (300k→ reduz para mínimo ⇒ aceito, `r.bids[club].amount` = novo valor, timestamp/seq novos); `test_repeating_same_amount_is_rejected` (`BID_UNCHANGED`, lance anterior intacto); redução abaixo do mínimo → `BELOW_MINIMUM_BID`.
- [ ] Condição passa a `amount == current.amount` → `AuctionError("BID_UNCHANGED", "O lance já está neste valor.")`. Atualizar teste antigo de `BID_NOT_INCREASED`, mensagens do frontend, `docs/architecture/leilao.md`, `pendencias.md`. Commit.

### Task 3: Formação do usuário antes do leilão
**Files:** `services/session/manager.py` (campo `user_formation: str | None` em `SessionState`, método `set_user_formation(session_id, name)` só em `setup`), contrato `SessionOut.user_formation`, rota `POST /api/sessions/{id}/formation` body `{formation}` (`Idempotency-Key`), `services/competition/season.py` (`Season(..., user_formation: tuple[Position,...] | None = None)`; na escalação automática do usuário usa `[user_formation]` em `choose_lineup`), quem cria a Season passa a formação.
- [ ] Testes integração: definir "3-5-2" em setup → `SessionOut.user_formation == "3-5-2"`; fora de `setup` → 409; formação inválida → 422; após iniciar temporada, `GET season/lineup` sem escalação do usuário → `formation == "3-5-2"`.
- [ ] Implementar; exportar OpenAPI, `gen:api`, contratos.md. Commit.

### Task 4: Goleiro cansa menos
**Files:** `services/match_engine/params.py` (`gk_fatigue_multiplier: float = 0.35`), `engine.py:_tick` e `_exert` (multiplica o dreno quando `pl.slot is Position.GK`).
- [ ] Teste: partida simulada com semente fixa → condição final do goleiro titular ≥ 85 e maior que a média dos jogadores de linha.
- [ ] Implementar; rodar `scripts/homologation_calibration.py` e anexar resultado em `docs/homologacao/calibracao.md` (critérios intactos). Commit.

### Task 5: Área oculta de dados
**Files:** `services/gateway/settings.py` (`admin_password: str = "9153"`, env `SQUADFORCE_ADMIN_PASSWORD`), `services/gateway/admin.py` (tokens em memória: `login(password) -> str | None`, `check(token) -> bool`), rotas `POST /api/admin/login` → `{token}` (401 `ADMIN_AUTH_FAILED`) e dependência `X-Admin-Token` em `POST /imports/*`.
- [ ] Testes: senha certa → token; errada → 401; import sem/ com token inválido → 401 e base intacta; com token → 200. Ajustar testes de import existentes (fixture que faz login).
- [ ] Frontend: `api/endpoints.ts` `adminLogin`, token guardado em `sessionStorage`, enviado nos imports. Commit.

### Task 6: Ao vivo — adversário e outros jogos
**Files:** `services/competition/live.py` (`LiveMatch.others: list[tuple[FixtureTask, MatchSimulation]]` criados em `start` a partir de `snapshot.tasks` exceto a do usuário, controladores `TacticalBot` dos dois lados, avançados no mesmo `target`; `view()` devolve `opponent` e `others`), `views.py:start_live` passa as demais tarefas, contratos `LiveStateOut.opponent_players: list[LiveOpponentOut{player,name,slot,on_field,yellow_cards}]`, `other_matches: list[LiveOtherMatchOut{match_id,home_club_uid,away_club_uid,score,finished}]`.
- [ ] Testes: adversário com 11 em campo e sem `condition`; outros jogos começam 0×0; após `instant` todos `finished` e placares == resultados consolidados por `play`; rodada sem outros jogos → lista vazia.
- [ ] Implementar, OpenAPI, gen:api, contratos.md. Commit.

### Task 7: Base visual e casca de jogo
**Files:** `frontend/src/styles.css` (tokens novos: gramado, holofote, setores GOL/DEF/MEI/ATA, fonte display), `frontend/index.html` (fonte), `app/theme.ts` (padrão escuro sempre), `app/App.tsx` (rotas `#/` abertura, `#/nova`, `#/tatica`, `#/admin`; sem `<nav>` de abas), `app/GameShell.tsx` (barra superior: logo, etapas Tática▸Leilão▸Mercado▸Temporada▸Fim, clube/saldo, tema, som, menu ⋯ Encerrar), `components/ActionBar.tsx` (ação principal fixa), `components/PhaseBanner.tsx`, `domain/positions.ts` (`DISPLAY_ORDER`, `sector(pos)`), `audio/crowd.ts` (`playGoal(own: boolean)`, `playWhistle()`, `soundEnabled()/setSound()`).
- [ ] Testes Vitest: tema inicial "dark" mesmo com SO claro; `DISPLAY_ORDER` = GOL,LD,ZAG,LE,VOL,ME,ATA; casca mostra etapa ativa conforme fase; nenhuma `role="tablist"`/nav de abas; `#/admin` não aparece em nenhum link.
- [ ] Implementar. Atualizar `App.test.tsx`. Commit.

### Task 8: Componentes de jogo
**Files:** `components/PlayerCard.tsx` (foto/silhueta, escudo, nome, idade, selo de setor; variantes `full|compact|token`), `components/PositionBadge.tsx`, `components/PitchSvg.tsx` (gramado listrado, linhas, orientação vertical/horizontal), `components/Scoreboard.tsx` (telão), `features/lineup/layout.ts` (`slotLayout(formation: string[]): {x,y}[]` agrupa por linha e distribui igualmente; `detectFormation(lines: number[]): string | null`).
- [ ] Testes: `slotLayout` para as 11 formações → distância mínima entre vagas ≥ largura da carta compacta em 360 px; `detectFormation([4,4,2])` == "4-4-2" etc. (linhas: DEF, VOL, ME, ATA conforme slots oficiais).
- [ ] Implementar. Commit.

### Task 9: Abertura, nova partida, tática
**Files:** `pages/HomePage.tsx` (logo, chamada, 3 pilares, botão Nova partida/Continuar), `pages/NewGamePage.tsx` (assistente reaproveitando `SessionForm`/`validation.ts`), `pages/TacticPage.tsx` (11 formações no campo; salva via `setUserFormation`; ação "Começar leilão").
- [ ] Testes: Home sem sessão → botão "Nova partida"; com sessão → "Continuar"; Tática salva e chama `POST /formation` com `Idempotency-Key` e depois inicia leilão.
- [ ] Implementar. Commit.

### Task 10: Leilão
**Files:** `features/auction/AuctionBoard.tsx`, `AuctionSummaryView.tsx`, `pages/AuctionPage.tsx`.
- [ ] Testes: elenco agrupado em `DISPLAY_ORDER`; painel "vagas da sua formação" (ZAG 1/2); botões −/+ (100k/500k/1mi) e redução enviada; carimbo VENDIDO/SEM LANCE.
- [ ] Implementar com cartas, cronômetro circular. Commit.

### Task 11: Mercado, central e painéis
**Files:** `pages/TradingPage.tsx`, `features/trading/TradingBoard.tsx` (cartas por posição), `pages/SeasonPage.tsx` (Central da rodada + botões que abrem `components/Drawer.tsx` com elenco/calendário/classificação/estatísticas), `features/season/StatsCenter.tsx`.
- [ ] Testes existentes adaptados; Central mostra próximo jogo e ação "Escalar e jogar"; painel abre/fecha com Esc.
- [ ] Implementar. Commit.

### Task 12: Campinho com arrastar
**Files:** `features/season/Pitch.tsx` (usa `slotLayout`, `PlayerCard token`, Pointer Events), `pages/LineupPage.tsx`.
- [ ] Testes: arrastar carta sobre outra troca; arrastar zagueiro para a linha de meio num 4-4-2 → formação vira "3-5-2" ou aviso se não houver oficial; teclado/seleção continua; ação "Iniciar partida".
- [ ] Implementar. Commit.

### Task 13: Jogo ao vivo, pós-jogo, encerramento
**Files:** `pages/MatchPage.tsx`, `features/match/LivePitch.tsx` (dois times), `features/match/OtherMatches.tsx`, `features/match/StatBars.tsx`, `features/season/labels.ts` (texto pênalti), `pages/PostMatchPage.tsx`, `pages/EndPage.tsx`.
- [ ] Testes: pênalti renderiza "Falta de A em B"; outros jogos listados com placar; barras com rótulo central; som chamado ao surgir novo gol (mock de `playGoal`), não chamado com som desligado.
- [ ] Implementar. Commit.

### Task 14: Fechamento
- [ ] Atualizar e2e (`journey.e2e.test.ts`) ao novo fluxo; `pendencias.md` (4 decisões), README (link `#/admin`), CLAUDE.md escopo.
- [ ] Rodar `pytest`, `npm test`, `npm run test:e2e`, `npm run build`; mostrar saídas. Commit final.
