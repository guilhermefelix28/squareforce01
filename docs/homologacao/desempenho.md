# Desempenho — homologação (Entrega 9)

Medido por `scripts/homologation_performance.py` (gateways REAIS em portas livres, bancos temporários, modelo FALSO do leilão; Liga/Copa via API com relógio 25× e 4 processos de partidas) e no navegador (agent-browser). Critérios de `criterios.md` §4, definidos antes das medições.

**Ambiente de referência:** Windows 11 Pro, 12 CPUs lógicas, Python 3.12.10, Node 26, servidor local (sem rede). Tempo total do script: 128.4 s.

| Medida | Resultado | Critério | Situação |
|---|---|---|---|
| Inicialização do gateway | 1.164 s | ≤ 5 s | ✅ |
| GET health | p50 2.68 ms · p95 3.34 ms · máx 27.13 ms (n=200) | p95 ≤ 150 ms | ✅ |
| GET sessão | p50 1.26 ms · p95 1.51 ms · máx 19.48 ms (n=200) | p95 ≤ 150 ms | ✅ |
| GET catálogo (50 jogadores) | p50 3.7 ms · p95 4.54 ms · máx 27.6 ms (n=100) | p95 ≤ 150 ms | ✅ |
| GET leilão (durante rodadas) | p50 1.48 ms · p95 2.05 ms · máx 25.1 ms (n=60) | p95 ≤ 150 ms | ✅ |
| GET estatísticas da temporada (Liga 20 completa) | p50 9.36 ms · p95 22.86 ms · máx 33.85 ms (n=50) | p95 ≤ 150 ms | ✅ |
| GET resumo final (Liga 20) | p50 10.6 ms · p95 34.18 ms · máx 77.62 ms (n=50) | p95 ≤ 150 ms | ✅ |
| POST lance no leilão | p50 1.09 ms · p95 1.27 ms · máx 21.62 ms (n=120) · status {'200': 120} | p95 ≤ 100 ms | ✅ |
| POST proposta no mercado | p50 1.1 ms · p95 1.39 ms · máx 1.52 ms (n=30) | p95 ≤ 150 ms | ✅ |
| POST cancelamento de proposta | p50 1.1 ms · p95 1.36 ms · máx 1.45 ms (n=30) | p95 ≤ 150 ms | ✅ |
| Uma partida (motor + IA nos dois lados), em processo | 56,3 ms (média de 60; 36,0 ms sem IA) | ≤ 150 ms | ✅ |
| Rodada de Liga 20 (10 partidas paralelas + consolidação, via API) | p50 193.47 ms · p95 222.59 ms · máx 359.5 ms (n=38) | ≤ 4 s | ✅ |
| Liga 20 clubes turno e returno (380 partidas, via API) | 11.97 s | ≤ 120 s | ✅ |
| Fases da Copa 32 (partidas: ms) | 16: 299.5 ms, 8: 132.2 ms, 4: 69.2 ms, 2: 65.7 ms, 1: 57.0 ms | 1ª fase ≤ 5 s | ✅ |
| Memória da árvore do servidor após Liga 20 | 284.2 MB (processos: [4.2, 195.8, 21.3, 20.9, 21.2, 20.8]) | ≤ 600 MB | ✅ |
| Memória após Copa 32 | 282.2 MB | ≤ 600 MB | ✅ |
| Paralelismo: 1ª fase da Copa 32, 1 × 8 processos | 0.985 s × 0.458 s → 2.15× | ≥ 1,5× | ✅ |
| Frontend: DOMContentLoaded (build de produção, local) | 82 ms (frio); 8–9 ms (5 recargas) | ≤ 2 s | ✅ |
| Frontend: JS de produção (gzip) | 91,69 kB (CSS 5,23 kB) | ≤ 250 kB | ✅ |

Notas:
- O primeiro processo da árvore (~4 MB) é o lançador do `python.exe` do `.venv` no Windows; o gateway real é o filho; os demais são os processos de partidas.
- O ganho do paralelismo (2,15×) é limitado pelo custo fixo de despachar tarefas e pela consolidação sequencial (correta por projeto); a rodada inteira já fica em ~0,2–0,3 s.
- As medidas valem para este ambiente; não são garantia para máquinas mais lentas.

## Re-medição com o `AuctionModel` OFICIAL e as 11 formações (2026-11-19)

Mesmo script, agora sem o modelo falso (o servidor carrega o modelo oficial). Critérios inalterados; todos atendidos.

| Medida | Resultado | Critério |
|---|---|---|
| Inicialização do gateway | 1,157 s | ≤ 5 s ✅ |
| GET health / sessão / catálogo / leilão | p95 3,06 / 12,61 / 3,87 / 1,6 ms | ≤ 150 ms ✅ |
| GET estatísticas / resumo final (Liga 20) | p95 11,82 / 30,11 ms | ≤ 150 ms ✅ |
| POST lance no leilão | p95 1,2 ms (120 × 200) | ≤ 100 ms ✅ |
| POST proposta / cancelamento | p95 1,3 / 1,28 ms | ≤ 150 ms ✅ |
| Rodada de Liga 20 | p95 215,22 ms | ≤ 4 s ✅ |
| Liga 20 turno e returno (380 partidas) | 21,63 s | ≤ 120 s ✅ |
| 1ª fase da Copa 32 | 264,1 ms | ≤ 5 s ✅ |
| Memória após Liga 20 / Copa 32 | 286,6 / 285,3 MB | ≤ 600 MB ✅ |
| Paralelismo (1 × 8 processos) | 2,17× | ≥ 1,5× ✅ |

A Liga 20 completa passou de 12,0 s para 21,6 s: a IA agora avalia 11 formações em vez de 3, e continua bem
abaixo do limite.
