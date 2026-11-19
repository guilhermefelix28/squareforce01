# Relatório final de homologação: SquadForce (Game Design v5.2)

Entrega 9, auditoria, calibração e homologação. Data: 2026-11-19. Branch `entrega-9`.

## Decisão final: **BLOQUEADA**

Todo o software implementável foi verificado e aprovado nos critérios definidos **antes** das medições
(`criterios.md`, commit `d2cda8e`):
- todos os testes funcionais passam;
- não há falha crítica ou importante aberta;
- as faixas estatísticas com referência foram atendidas;
- IA, determinismo, competições, desempenho e interface foram validados.

A versão **não pode ser declarada APROVADA**, porque depende de insumos que só o responsável pode fornecer:

1. **Fórmulas do leilão (`AuctionModel`).** Sem elas, o leilão real não inicia, e o jogo só roda de ponta a
   ponta com o modelo FALSO de testes. As decisões financeiras dos bots não podem ser validadas com as regras
   reais.
2. **Critérios de desempate da Liga (PC-01).** Hoje, um empate em pontos no topo deixa o campeão indefinido.
3. **Aprovação das referências estatísticas (PM-02).** A calibração usou agregados públicos. Várias métricas
   não têm referência confiável e não foram validadas (PH-03).
4. **Decisões provisórias a confirmar:**
   - pontuação 3/1/0 (PC-09);
   - formações oficiais (PM-01);
   - duração da suspensão;
   - limiares de interface e de desempenho (PI-02, PH-01, PH-02).

Com esses insumos, a homologação pode ser refeita com os scripts e critérios deste diretório, sem retrabalho
de arquitetura.

## 1. Resumo da implementação

| Entrega | Conteúdo |
|---|---|
| 1 | Fundação: SQLite e importação transacional do Excel, sessão em memória, gateway, WebSocket, idempotência, 11 Skills |
| 2 | Formatos, seleção de participantes, calendário da Liga (Berger), chaveamento da Copa |
| 3 | Leilão (relógio autoritativo, ofertas sigilosas, complementação até 18), bloqueado sem `AuctionModel` |
| 4 | Mercado de negociações 1×1 com dinheiro opcional, limites, prazos e atomicidade |
| 5 | Motor de partidas determinístico por eventos (xG, goleiros, faltas, cartões, lesões, substituições, notas, pênaltis) |
| 6 | IA tática (formação, escalação, posturas por utilidade esperada, sem trapaça) |
| 7 | Liga e Copa: snapshot por rodada, partidas em processos paralelos, consolidação atômica, premiações |
| 8 | Interface definitiva: central, escalação interativa, partida ao vivo, pós-partida, estatísticas, encerramento |
| 9 | Auditoria, testes adversos, calibração estatística, desempenho, homologação |

## 2. Versões das tecnologias

- **Backend:** Python 3.12.10 · FastAPI 0.164.0 · Starlette 1.10.0 · Pydantic 2.14.3 · Uvicorn 0.54.0 ·
  openpyxl 3.1.5 · SQLite 3.49.1 · pytest 9.2.0.
- **Frontend:** Node 26.13.1 · React 19.1.0 · TypeScript 5.8.3 · Vite 6.3.5 · Vitest 3.2.4 ·
  openapi-typescript 7.8.0.
- **Motor e IA:** motor `provisorio-0.6`, IA tática `provisorio-0.7`.

## 3. Inventário de serviços (`services/`)

| Serviço | Responsabilidade |
|---|---|
| `gateway` | REST e WebSocket, idempotência, erros padronizados, relógio do leilão e do mercado, composição |
| `data` | SQLite, migrações aditivas, importação transacional, catálogo |
| `session` | Sessão única em memória, fases, versão, bloqueio de importações |
| `competition` | Planejamento, temporada (`season`), classificação, execução isolada (`worker`), partida ao vivo (`live`), visões |
| `auction` | Leilão e complementação (fórmulas pendentes) |
| `trading` | Mercado de negociações |
| `bot_ai` | Avaliação, lances, trocas, tática de partida |
| `match_engine` | Motor de partidas, estatísticas, notas, disponibilidade, validação |

Contratos: 37 rotas, todas documentadas em `docs/api/contratos.md`. O OpenAPI exportado não mudou nesta
entrega, o que confirma que os contratos correspondem ao código.

## 4. Inventário das Skills (11, todas com a seção "Estado na homologação")

game-design-rules · project-architecture · database-import · session-management · auction-system ·
trading-system · bot-intelligence · match-engine · competition-system · frontend-ui · testing-validation.

## 5. Testes executados (resultados reais desta entrega)

| Suíte | Resultado |
|---|---|
| Auditoria inicial (suíte herdada da Entrega 8) | **734 passed** |
| `pytest`, final | **755 passed**: 580 unitários, 106 de integração, 45 de contrato, 23 de simulação, 1 com servidor real |
| `npm test` (Vitest) | **73 passed** |
| `npm run test:e2e` (backend real; inclui a jornada completa) | **6 passed** |
| `npm run build` / `tsc -b` | sem erros |

**Testes novos desta entrega** (`tests/integration/test_homologation_robustness.py` e
`tests/unit/test_season.py`):
- nenhuma persistência: impressão digital lógica do SQLite idêntica antes e depois de uma competição inteira;
- 6 `play` simultâneos geram uma única consolidação;
- retransmissão com a mesma chave é repetida pelo cache, não reexecutada;
- isolamento de sessão substituída;
- validação de entradas (5 casos);
- POST sem `Idempotency-Key`;
- reconexão do WebSocket no meio da temporada;
- importação bloqueada;
- final da Copa decidida nos pênaltis.

**Cobertura herdada e reexecutada:**
- IDs, integridade e importação;
- orçamentos, contratações, exclusividade e elencos de 18, inclusive com lances concorrentes na base real;
- trocas atômicas e limites;
- relógios autoritativos, sessões, reconexão e idempotência;
- consolidação de rodadas com falhas paralelas;
- regras esportivas do motor;
- IA em todas as situações obrigatórias;
- determinismo (processos × threads, velocidades, sementes por partida);
- Ligas de 2 a 20 clubes (ímpares, turno e returno), Copas de 2 a 32, eliminação do usuário.

Matriz completa: `docs/architecture/matriz-de-testes.md`.

## 6–8. Calibração: partidas simuladas e distribuições observadas

- **Lote oficial:** **20.250 partidas** em 229 s com 10 processos (`calibracao.md`).
  - **Amplo:** 10.000 partidas entre os **40 clubes reais** da base. A escalação, a formação e as posturas
    foram escolhidas pela IA, com personalidades e situações variadas e 20% de jogos eliminatórios.
  - **Posturas:** 5.000 partidas.
  - **Diferença de qualidade:** 3.000 partidas.
  - **Formações:** 2.250 partidas.
- **Lotes de ajuste:** mais 34.550 partidas exploratórias, só para diagnóstico, antes do lote oficial.

| Métrica (por partida) | Observado | Faixa (definida antes) |
|---|---|---|
| Gols | **2,365** | 2,20–3,56 ✅ |
| Empates | **25,96%** | 22,5–33,0% ✅ |
| Finalizações | **24,31** | 22,1–30,1 ✅ |
| xG | **2,339** | 2,24–3,44 ✅ |
| Faltas | **26,67** | 23,3–31,4 ✅ |
| Amarelos | **5,11** | 2,88–5,26 ✅ (perto do limite superior, típico do Brasileirão) |
| Vermelhos | **0,218** | 0,071–0,54 ✅ |
| Gols × xG | diferença de 1,10% | ≤ 10% ✅ |

**Coerência com as regras (100% das partidas):**
- 0 partidas inválidas: estatísticas iguais às derivadas dos eventos;
- 0 divergências do Craque da Partida;
- 0 casos com mais de 5 substituições;
- 0 lesões fora de 0–3 jogos;
- 0 notas fora de 0–10.

**Comportamento esportivo:**
- **Qualidade:** a vitória do mais forte cresce com a diferença de nível (0 → 20 pontos): 33,2% → 48,8% →
  70,0% → 84,0% → 92,7%.
- **Resultados inesperados:** o mais fraco vence 4,5% com diferença de 15 e 2,7% com diferença de 20. Entre
  clubes reais, nos 20% de confrontos mais desiguais, vence 17,6%.
- **Posturas (moderadas e monótonas), em gols marcados/sofridos relativos à Equilibrada:**
  - Retranca: −22% / −18%
  - Defensiva: −11% / −10%
  - Ofensiva: +11% / +9%
  - Ataque Total: +20% / +15%
- **Inferioridade numérica:** o time com 10 passa a sofrer 1,56 gols por 90 minutos (eram 1,12) e a marcar
  0,82 (eram 0,99).

**Monitoradas, sem referência confiável e portanto NÃO validadas:**
- no alvo: 8,9 por partida (36,6%);
- grandes chances: 1,10;
- escanteios: 8,49;
- defesas: 6,54;
- lesões: 0,53;
- posse por time: entre 41% e 58% (desvio de 2,3 pontos);
- 0 × 0: 7,7%; 5 gols ou mais: 8,2%;
- notas: média 6,18, desvio 0,70.

Observação: a posse muito concentrada e as poucas grandes chances podem estar abaixo do futebol real (PH-03).

## 9. Referências de calibração

The Analyst/Opta (cinco grandes ligas 2022-23 e 2023-24), ESPN via Jornal de Brasília (cartões do
Brasileirão), Placar/Trivela e 90min (gols do Brasileirão 2023 e 2024), Flashscore/Soccerway (faltas),
FiveThirtyEight e Kitman Labs (empates). As URLs estão em `criterios.md`.

A faixa de cada métrica foi definida por uma regra mecânica: [menor referência × 0,9 ; maior × 1,1]. Os
lotes exploratórios da Entrega 5 já tinham sido observados antes; isso está registrado em `criterios.md`.

## 10. Desempenho medido (`desempenho.md`, todos os 19 critérios atendidos)

Ambiente: Windows 11, 12 CPUs lógicas.

| Medida | Resultado | Critério |
|---|---|---|
| Inicialização do gateway | 1,16 s | ≤ 5 s |
| Leituras (GET) | p95 1,4–22,9 ms | ≤ 150 ms |
| Lances | p95 1,27 ms | ≤ 100 ms |
| Proposta | p95 1,39 ms | ≤ 150 ms |
| Cancelamento de proposta | p95 13,5 ms | ≤ 150 ms |
| Uma partida com IA | 56 ms | ≤ 150 ms |
| Rodada de Liga 20 | p95 223 ms | ≤ 4 s |
| Liga 20 completa (380 jogos) | 12,0 s | ≤ 120 s |
| 1ª fase da Copa 32 | 0,30 s | ≤ 5 s |
| Memória da árvore do servidor | 284 MB | ≤ 600 MB |
| Paralelismo (1 × 8 processos) | 2,15× | ≥ 1,5× |
| Frontend: DOMContentLoaded | 82 ms | ≤ 2 s |
| Frontend: JS de produção | 91,7 kB gzip | ≤ 250 kB |

## 11. Defeitos encontrados e corrigidos nesta entrega

| Gravidade | Defeito | Correção | Evidência |
|---|---|---|---|
| **IMPORTANTE** | Gols e xG abaixo das faixas de referência: 2,19 e 2,16 por partida com elencos reais (1,86 e 1,66 em sintéticos) | Calibração de um único parâmetro provisório: `xg_intercept` de 0,75 para 0,88 (motor `provisorio-0.6`). Nenhuma regra do GDD foi alterada | Lote oficial dentro das faixas; os hashes da Entrega 5 se reproduzem com o parâmetro antigo, o que prova que o código não mudou; novos hashes calibrados |
| Teste (sem impacto no produto) | Teste do goleiro frágil: com 60 jogos, o ruído do xG por finalização (12,7%) passava da tolerância; com 400 jogos, a diferença real é de 3,3% | Amostra aumentada para 200 | `test_goalkeeper_skill_reduces_goals_without_changing_xg` |
| Ferramenta de medição | A memória era lida no processo lançador do `.venv` (4 MB), não no gateway | Soma da árvore de processos | `desempenho.md` |

- **Sem falhas críticas nesta auditoria:** integridade, finanças, regras esportivas, determinismo e
  consistência não tiveram falhas.
- **Falhas corrigidas na Entrega 8:**
  - workers órfãos;
  - barra fixa cobrindo o campo;
  - minutos das notas;
  - link de acessibilidade;
  - sincronização da versão da sessão;
  - mudança para a mesma postura.
- **IA re-medida com o motor calibrado:**
  - multiplicadores de postura com diferença ≤ 4% (mantidos);
  - 1,17 mudança de postura por time e por jogo (máximo 7);
  - 99–100% de coerência ao perder e ao vencer;
  - IA × time estático: 1,39 × 1,32 pontos por jogo.

## 12. Pendências restantes

Detalhes em `docs/game-design/pendencias.md`.

| Situação | Itens |
|---|---|
| **Bloqueiam a aprovação** | `AuctionModel` (PB-01/02); critérios de desempate (PC-01); aprovação das referências (PM-02) |
| **A confirmar** | pontuação (PC-09); formações (PM-01); efeito de mando (PC-03); duração de suspensão; parâmetros da IA (PB-03, PB-04, PB-05); interface (PI-01 a PI-04); homologação (PH-01 a PH-04) |
| **Cosméticas** | tipografia não definida no manual (PI-01); revisão do ícone em tamanho pequeno (PI-05) |

## 13. Como executar o jogo

```bash
# backend (raiz)
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m services.gateway --port 8000          # http://127.0.0.1:8000/docs
# frontend
cd frontend && npm install && npm run dev                     # http://localhost:5173
```

1. Importe as planilhas em **Dados**.
2. Configure a competição.
3. Siga o menu contextual: Leilão → Mercado → Central → Escalação → Partida → Pós-partida → Encerramento.

O leilão real exige o `AuctionModel` aprovado. **Somente para demonstração ou teste**, use o modelo falso:
```bash
PYTHONPATH=tests SQUADFORCE_AUCTION_MODEL=support.fake_auction_model:FakeAuctionModel .venv/Scripts/python -m services.gateway --port 8000
# opcional (somente teste): SQUADFORCE_CLOCK_SCALE=10 acelera os relógios do servidor
```

Para repetir a homologação:
```bash
.venv/Scripts/python -m pytest
cd frontend && npm test && npm run test:e2e && npm run build
.venv/Scripts/python scripts/homologation_calibration.py --broad 10000 --workers 10
.venv/Scripts/python scripts/homologation_performance.py
```

## 14. Decisão final

**BLOQUEADA.** A implementação está tecnicamente homologada nos critérios mensuráveis. A aprovação depende
do `AuctionModel`, dos critérios de desempate e da aprovação das referências estatísticas, que são insumos
externos. Nenhuma regra do GDD foi alterada para aprovar, e nenhuma evidência foi simulada.
