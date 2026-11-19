# Leilão (Entrega 3)

Implementação de GDD v5.2 §4–§7. Código: `services/auction/` e `services/bot_ai/`.

## O que está implementado (regras aprovadas)

| Regra (GDD) | Onde |
|---|---|
| R$ 120 mi por clube; 18 contratados (11 + 7) | `rules.py` |
| Rodadas de 10 s com 5 atletas da mesma posição principal | `engine._open_round` |
| Ofertas fechadas; um lance ativo por clube; aumento, redução (decisão do responsável, 2026-11-19) ou troca de alvo atômicos; repetir o valor é rejeitado; troca inválida mantém o lance anterior | `engine._accept` |
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

## `AuctionModel` oficial (aprovado em 2026-11-19)

Fórmulas, ajustes do responsável e lotes exploratórios: [proposta aprovada](proposta-auction-model.md).
Implementação: `services/auction/official_model.py`, carregado **por padrão**. O motor chama `for_pool(base)` a cada
leilão, então a calibração (overall por posição, percentil 85, mediana) é refeita com a base atual. Toda saída
continua **validada contra o GDD** pelo motor.

- `SQUADFORCE_AUCTION_MODEL="pacote.modulo:Objeto"` substitui o modelo (testes e demonstração).
- `SQUADFORCE_AUCTION_MODEL=none` desliga o leilão (`409 AUCTION_MODEL_NOT_CONFIGURED`).

| Método | Regra (proposta) |
|---|---|
| `overall` | §1: composições de atributos do motor por posição; escala por posição com mediana 70 |
| `player_quality` | §2: escala da posição × (1 − 0,35 × (100 − familiaridade)/99) |
| `market_value` / `minimum_bid` | §3: R$ 3 mi × e^(k(overall−70)) × idade (k = 0,1228 acima e 0,25 abaixo da mediana); lance mínimo 50% |
| `basic_price` / `build_reserves` | §4: min(R$ 500 mil, lance mínimo); reservas básica e complementar |
| `position_weights` / `pick_round_players` | §5: necessidade × disponibilidade × recência; peso 6 acima e 1 abaixo da mediana |
| `formations` | §6: 11 formações oficiais |
| `bot_profile` / `trade_profile` | §7 e §8 |

Bots (GDD §6, concorrência pública): rivais esperados por atleta e escolha mista do alvo (PB-06, parâmetros
provisórios da IA em `services/bot_ai/auction_bot.py`).

Testes unitários do motor usam também `tests/support/fake_auction_model.py`, um modelo **falso**, nunca usado em produção.

## API

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/sessions/{id}/auction/start` | Inicia (fase `setup` → `auction`). 409 se o leilão estiver desligado (`SQUADFORCE_AUCTION_MODEL=none`). |
| GET | `/api/sessions/{id}/auction` | Estado do usuário: rodada, 5 atletas (sem dados ocultos), tempos restantes, saldo, lance máximo, oferta ativa própria, resultados recentes, elencos/saldos públicos. |
| POST | `/api/sessions/{id}/auction/bids` | `{player_id, amount, round_number?}`; `Idempotency-Key` = identificador da operação. |
| GET | `/api/sessions/{id}/auction/summary` | Elencos finais (18) e saldos, após a complementação (fase `squad_completion`). |

Eventos WebSocket (`/ws/sessions/{id}`): `auction.started`, `auction.round_started`, `auction.round_closed`,
`auction.finished` — apenas números de rodada; o cliente consulta o estado pelo GET.

Erros de lance: `BELOW_MINIMUM_BID`, `INSUFFICIENT_FUNDS` (com `max_bid`), `BID_UNCHANGED`, `PLAYER_NOT_IN_ROUND`,
`SQUAD_FULL`, `STALE_ROUND`, `ROUND_CLOSED`, `AUCTION_NOT_RUNNING`, `OPERATION_ID_REUSED`.

## Relógio

`time.monotonic` no servidor. Uma tarefa assíncrona avança os leilões a cada 100 ms, e toda consulta ou lance
também avança o estado até o instante atual. As rodadas são contíguas e calculadas a partir do fim da anterior,
portanto o resultado não depende da frequência do relógio (testado). O cliente só exibe a contagem regressiva
com base nos milissegundos restantes informados pelo servidor.
