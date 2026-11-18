# Leilão (Entrega 3)

Implementação de GDD v5.2 §4–§7. Código: `services/auction/` e `services/bot_ai/`.

## O que está implementado (regras aprovadas)

| Regra (GDD) | Onde |
|---|---|
| R$ 120 mi por clube; 18 contratados (11 + 7) | `rules.py` |
| Rodadas de 10 s com 5 atletas da mesma posição principal | `engine._open_round` |
| Ofertas fechadas; um lance ativo por clube; aumento ou troca de alvo atômicos; proibido reduzir no mesmo atleta; troca inválida mantém o lance anterior | `engine._accept` |
| Lance ≤ saldo − R$ 500 mil × vagas que restarão após a compra | `rules.max_affordable_bid` |
| Maior lance vence; empate → timestamp do servidor em que o valor final foi atingido → sequência de aceitação | `engine._close_round` |
| Relógio global autoritativo (10/15/20 min conforme formato) e encerramento antecipado com todos os elencos completos | `rules.auction_duration_seconds`, `engine._advance` |
| Resultado da rodada publicado enquanto a próxima já corre | rodadas contíguas + evento `auction.round_closed` |
| Posição elegível aparece ao menos 1× a cada 14 rodadas concluídas (se houver ≥ 5 elegíveis) | `engine._choose_position` (prazo mais próximo) |
| Jogadores vendidos nunca voltam; contagem de não vendidos repassada ao modelo | `engine._available_by_position`, `unsold_counts` |
| Overall, atributos, valor interno e ofertas adversárias ocultos | contratos `Auction*Out` + testes de vazamento |
| Identificador de operação impede lances duplicados | `Idempotency-Key` = `op_id` no motor |
| Bots: 4 personalidades ocultas, mesma avaliação, ganho marginal 0,8 × Δtitulares + 0,2 × Δreservas, só informação pública | `bot_ai/evaluation.py`, `bot_ai/auction_bot.py` |
| Complementação: 18 exatos, limite `min(18 − C, ⌊C/4⌋)`, ≤ 1 destaque (≥ percentil 85), preço = média(valor de mercado, lance mínimo), distribuição em turnos com ordem sorteada, sem compensação | `completion.py` |

## O que falta: o `AuctionModel` (fórmulas pendentes)

O leilão **não inicia** sem um modelo aprovado (`409 AUCTION_MODEL_NOT_CONFIGURED`). Para ativar, implemente a
interface `services/auction/model.py::AuctionModel` e aponte a variável de ambiente
`SQUADFORCE_AUCTION_MODEL="pacote.modulo:Objeto"`. Toda saída é **validada contra o GDD** pelo motor.

| Método | Pendência | Precisa definir | Validação automática |
|---|---|---|---|
| `overall(player)` | PE-01 | Overall calibrado (mediana-alvo 70; > 90 raro). Base do destaque (p85). | — |
| `player_quality(player, posição)` | PE-01, PE-03 | Rendimento por posição: ponderações de atributos + familiaridade (penalidade máx. 35%). | — |
| `market_value(player)` | PE-02 | Valor de mercado (overall calibrado + idade). | 0 < valor ≤ R$ 50 mi |
| `minimum_bid(player)` | PE-02 | Lance mínimo. | 0 < lance ≤ R$ 30 mi |
| `basic_price(player)` | PE-04 | Preço na reserva básica. | 0 < preço ≤ R$ 500 mil |
| `formations()` | PM-01 | Lista de formações (11 posições cada, códigos GK/DR/DL/DC/DM/MC/STC). | ≥ 1 formação, 11 vagas |
| `position_weights(...)` | PE-05 | Pesos do sorteio da posição (necessidade coletiva, disponibilidade, histórico, aleatoriedade). | pesos ≥ 0, soma > 0 |
| `pick_round_players(...)` | §5 | Escolha dos 5 com variedade de qualidade e limite de repetição de não vendidos. | 5 distintos, disponíveis, da posição |
| `build_reserves(...)` | PE-04 | Reserva básica (suficiente para todas as vagas) e complementar (intermediários e destaques). | disjuntas, só não vendidos, básica ≥ vagas |
| `bot_profile(personalidade)` | PB-01 | Parâmetros de Agressivo, Conservador, Equilibrado e Oportunista no leilão (ver `BotProfile`). | tempos dentro da rodada de 10 s |
| `trade_profile(personalidade)` | PB-02 | Parâmetros de negociação das personalidades (ver `TradeProfile` e [mercado](mercado.md)). | resposta < 10 s; intervalo > 0 |

Os testes usam `tests/support/fake_auction_model.py`, um modelo **falso e arbitrário**, nunca usado em produção.

## API

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/sessions/{id}/auction/start` | Inicia (fase `setup` → `auction`). 409 se o modelo não estiver configurado. |
| GET | `/api/sessions/{id}/auction` | Estado do usuário: rodada, 5 atletas (sem dados ocultos), tempos restantes, saldo, lance máximo, oferta ativa própria, resultados recentes, elencos/saldos públicos. |
| POST | `/api/sessions/{id}/auction/bids` | `{player_id, amount, round_number?}`; `Idempotency-Key` = identificador da operação. |
| GET | `/api/sessions/{id}/auction/summary` | Elencos finais (18) e saldos, após a complementação (fase `squad_completion`). |

Eventos WebSocket (`/ws/sessions/{id}`): `auction.started`, `auction.round_started`, `auction.round_closed`,
`auction.finished` — apenas números de rodada; o cliente consulta o estado pelo GET.

Erros de lance: `BELOW_MINIMUM_BID`, `INSUFFICIENT_FUNDS` (com `max_bid`), `BID_NOT_INCREASED`, `PLAYER_NOT_IN_ROUND`,
`SQUAD_FULL`, `STALE_ROUND`, `ROUND_CLOSED`, `AUCTION_NOT_RUNNING`, `OPERATION_ID_REUSED`.

## Relógio

`time.monotonic` no servidor. Uma tarefa assíncrona avança os leilões a cada 100 ms, e toda consulta ou lance
também avança o estado até o instante atual. As rodadas são contíguas e calculadas a partir do fim da anterior,
portanto o resultado não depende da frequência do relógio (testado). O cliente só exibe a contagem regressiva
com base nos milissegundos restantes informados pelo servidor.
