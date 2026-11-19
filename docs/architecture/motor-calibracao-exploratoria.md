# Motor esportivo — lotes exploratórios

> **HISTÓRICO (Entrega 5).** Substituído pela calibração da homologação: [critérios](../homologacao/criterios.md) ·
> [calibração](../homologacao/calibracao.md) (motor `provisorio-0.6`).

> **NÃO CALIBRADO.** Motor `0.1.0`, parâmetros `provisorio-0.5` (PROVISÓRIO — pendente de calibração estatística e aprovação (PM-02)).
> As faixas de referência abaixo são **preliminares** (ordem de grandeza de ligas profissionais) e **não foram
> aprovadas** (pendência PM-02). Servem apenas para detectar comportamento absurdo.

Gerado por `scripts/match_engine_report.py`: 2000 partidas entre clubes reais da base (elencos originais da
planilha, formações de teste 4-3-3/4-4-2/5-3-2, postura equilibrada), em 87 s
(43 ms por partida). Partidas estruturalmente inválidas: **0**; encerramentos administrativos: 0.

## Estatísticas observadas

| Métrica | Observado | Faixa preliminar | Situação |
|---|---|---|---|
| goals_per_match | 2.301 | 2.3–3.0 | dentro |
| goals_sd | 1.477 | — |  |
| draw_rate | 0.253 | 0.2–0.32 | dentro |
| nil_nil_rate | 0.099 | 0.05–0.11 | dentro |
| five_plus_goals_rate | 0.082 | — |  |
| shots_per_team | 12.792 | 10.0–15.0 | dentro |
| on_target_per_team | 4.632 | 3.2–5.5 | dentro |
| xg_per_team | 1.136 | 1.1–1.6 | dentro |
| conversion_per_shot | 0.090 | 0.08–0.13 | dentro |
| big_chances_per_team | 0.497 | — |  |
| fouls_per_match | 26.381 | 20.0–28.0 | dentro |
| yellows_per_match | 5.061 | 3.0–5.5 | dentro |
| reds_per_match | 0.246 | 0.08–0.3 | dentro |
| corners_per_match | 8.592 | 8.0–12.0 | dentro |
| injuries_per_match | 0.527 | — |  |
| subs_per_team | 4.561 | — |  |
| blocked_per_team | 2.926 | — |  |

## Placares mais frequentes (vencedor–perdedor)

| Placar | Partidas |
|---|---|
| 1-0 | 459 |
| 2-1 | 284 |
| 2-0 | 281 |
| 1-1 | 229 |
| 0-0 | 198 |
| 3-0 | 148 |
| 3-1 | 123 |
| 2-2 | 71 |
| 3-2 | 61 |
| 4-0 | 43 |
| 4-1 | 40 |
| 5+ | 32 |

## Força relativa (clubes reais, 200 jogos cada, mando neutro)

Força = média da qualidade efetiva na vaga dos 11 titulares escolhidos automaticamente (4-3-3).

| Confronto | Forças | Vitória | Empate | Derrota |
|---|---|---|---|---|
| Flamengo × Londrina | 71.3 × 59.8 | 79% | 16% | 6% |
| Flamengo × América Mineiro | 71.3 × 64.6 | 70% | 22% | 8% |
| Atlético Mineiro × Ceará | 66.5 × 62.8 | 57% | 26% | 17% |
| América Mineiro × Remo | 64.6 × 64.3 | 26% | 35% | 40% |

## Efeito das posturas (mesmo confronto equilibrado, 200 jogos cada)

| Postura do mandante | Finalizações do mandante/jogo | Vitória | Empate | Derrota |
|---|---|---|---|---|
| retranca | 7.3 | 30% | 30% | 40% |
| defensiva | 8.9 | 24% | 34% | 42% |
| equilibrada | 10.0 | 26% | 35% | 40% |
| ofensiva | 11.4 | 28% | 25% | 47% |
| ataque_total | 12.9 | 32% | 21% | 47% |

## Leitura

- Estrutura: todas as partidas passaram em `validate_result` (gols só por finalização, placar = gols,
  estatísticas derivadas dos eventos, ≤ 5 substituições, ≤ 11 em campo, notas 0–10, sem duplicação).
- Os números ficaram dentro das faixas preliminares após ajuste exploratório dos parâmetros provisórios.
- Isso NÃO equivale a calibração: falta aprovar referências estatísticas oficiais, pesos por posição,
  curva da penalidade posicional, parâmetros de notas, disciplina e lesões (ver pendências).
