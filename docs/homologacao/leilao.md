# Homologação do leilão com o `AuctionModel` oficial

Modelo `oficial-1.0`. 200 leilões completos na base real (1583 atletas), 967 s. Critérios fixados antes da medição em `criterios.md` §6.

| # | Critério | Limite | Observado | Resultado |
|---|---|---|---|---|
| L1 | Clubes com 18 atletas, saldo ≥ 0, sem duplicação | 100% | 100.0%, 0 duplicações | ✅ |
| L2 | AuctionModelError | 0 | 0 | ✅ |
| L3 | Mediana do gasto no leilão (bots) | 50%–95% | 60.4% | ✅ |
| L4 | Oferecidos com ≤ 2 aparições sem venda | ≥ 60% | 100.0% | ✅ |
| L5 | Agressivo gasta mais que Conservador; Oportunista paga menos/valor | sim | gasto médio aggressive R$ 111.4 mi, balanced R$ 88.7 mi, conservative R$ 58.5 mi, opportunist R$ 54.5 mi; preço/valor aggressive 1.78, balanced 1.31, conservative 0.88, opportunist 0.80 | ✅ |
| L6 | Diferença de titulares melhor × pior bot (mediana) | ≤ 25% | 7.8% | ✅ |

## Por configuração

| Configuração | Leilões | Rodadas (média) | Encerramento | Gasto mediano dos bots | Tempo médio |
|---|---|---|---|---|---|
| Liga 20 | 50 | 90 | time_up 50 | 61.3% | 49.4 s |
| Liga 10 | 50 | 60 | time_up 50 | 58.4% | 15.8 s |
| Copa 8 | 50 | 60 | time_up 50 | 59.0% | 11.5 s |
| Copa 32 | 50 | 120 | time_up 50 | 60.7% | 115.1 s |
