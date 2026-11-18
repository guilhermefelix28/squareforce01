# Mercado de negociações (Entrega 4)

Implementação de GDD v5.2 §8. Código: `services/trading/` e `services/bot_ai/trade_bot.py`.

## Regras implementadas

| Regra (GDD §8) | Onde |
|---|---|
| Começa **somente** quando o usuário clica em *Iniciar negociações* (fase `squad_completion` → `trading`) | `POST /trading/start` |
| Duração global de **3 minutos**, sem pausa, relógio do servidor | `rules.MARKET_SECONDS`, `TradingEngine._advance` |
| Troca de **exatamente um jogador por outro** | `TradingEngine._create` / `_accept` |
| Dinheiro adicional **opcional, pago só pelo proponente**, nunca acima do saldo | `_create` (validação) e `_accept` (revalidação) |
| Até **3 negociações concluídas** por clube (proponente e destinatário) | `rules.MAX_COMPLETED_TRADES` |
| **Uma proposta pendente** por clube como proponente; um clube pode receber várias (decisão TR-01) | `PENDING_PROPOSAL_EXISTS` |
| Prazo de **10 s**, limitado ao fim do mercado; **expiração automática** | `expires_at = min(t + 10, fim)` |
| Aceitar ou rejeitar, **sem contraproposta**; **cancelamento** pelo proponente enquanto pendente | `respond`, `cancel` |
| Negociações usuário ↔ bots e **bot ↔ bot** | `_bot_propose`, `_bot_respond` |
| **18 jogadores** sempre, **sem duplicação**, **sem saldo negativo**, **troca atômica** | cópia-e-confirmação em `_accept` + `_validate_commit` |

## Garantias de concorrência

- Todo comando passa por uma única `RLock`. Cada proposta recebe **uma** decisão final:
  `accepted`, `rejected`, `cancelled`, `expired` ou `invalidated`. Aceitar, cancelar e expirar ao mesmo tempo
  resultam em uma única decisão; as demais tentativas recebem `PROPOSAL_NOT_PENDING`.
- **Idempotência em duas camadas:** `Idempotency-Key` no gateway e identificador de operação no motor.
  Reenviar o mesmo comando devolve o mesmo resultado (inclusive o mesmo erro definitivo) e nunca executa duas trocas.
- **Troca atômica:** os novos elencos e saldos são montados à parte e validados (18, sem duplicação, saldo ≥ 0)
  antes de substituir o estado. Uma falha nesse ponto (`TRADE_FAILED`, repetível) não altera nada; a proposta
  continua pendente e pode ser aceita de novo.
- Ao concluir uma troca, propostas pendentes que ficaram impossíveis (jogador já trocado ou limite de 3
  atingido) são **invalidadas** imediatamente.
- **Linha do tempo determinística:** expirações, respostas e propostas dos bots e o fechamento do mercado são
  processados em ordem de tempo do servidor. Consultas e comandos também avançam o relógio, portanto a
  desconexão de um cliente não pausa nada.

## Inteligência de negociação (bots)

Avaliação compartilhada (`trade_bot.py`): variação da qualidade 0,8 titulares / 0,2 reservas sobre a melhor
formação. Isso já considera posições necessárias, adequação às formações e composição do elenco.

**Aceitação** (o bot recebe o jogador oferecido mais o dinheiro e cede o pedido):
1. ganho esportivo ≥ 0 e saldo de valor ≥ −`value_tolerance` × valor cedido → aceita;
2. pequena perda (≤ `max_sport_loss`) com dinheiro ≥ perda × `money_per_quality` **e** saldo de valor ≥ 0 → aceita
   (justificativa econômica);
3. caso contrário, rejeita.

O **saldo de valor** (valor recebido + dinheiro − valor cedido) impede a exploração financeira sistemática:
ninguém leva um jogador valioso por um fraco sem pagar a diferença (teste `test_bots_cannot_be_systematically_exploited`).

**Propostas:** a cada `proposal_interval`, o bot busca uma troca que melhore o próprio elenco, oferecendo
preferencialmente um reserva da mesma posição, com o dinheiro necessário para que o rival provavelmente aceite.
Usa somente informação pública: elencos, saldos e valores de referência do modelo. As personalidades dos rivais
são ocultas, então a aceitação do rival é estimada com o próprio perfil.

Os **números** de cada personalidade (`TradeProfile`) estão pendentes (PB-02) e vêm do `AuctionModel` —
ver [leilão](leilao.md).

## API

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/sessions/{id}/trading/start` | Abre o mercado (exige leilão e complementação concluídos). |
| GET | `/api/sessions/{id}/trading` | Estado do usuário: relógio, saldo, negociações 0–3, proposta enviada, propostas recebidas com contagem regressiva, decisões recentes, histórico público, saldos dos clubes. |
| GET | `/api/sessions/{id}/trading/squads?search&club_uid&position` | Elencos públicos com filtros por nome, clube e posição. |
| POST | `/api/sessions/{id}/trading/proposals` | `{recipient_club_uid, offered_player_id, requested_player_id, money}` |
| POST | `/api/sessions/{id}/trading/proposals/{pid}/accept` · `reject` · `cancel` | Decisão do usuário. |

Erros: `PENDING_PROPOSAL_EXISTS`, `TRADE_LIMIT_REACHED`, `INSUFFICIENT_FUNDS`, `PLAYER_NOT_OWNED`, `SAME_CLUB`,
`INVALID_AMOUNT`, `NOT_RECIPIENT`, `NOT_PROPONENT`, `PROPOSAL_NOT_PENDING`, `PROPOSAL_INVALIDATED`,
`MARKET_NOT_RUNNING`, `TRADE_FAILED` (repetível), `OPERATION_ID_REUSED`, `MARKET_NOT_FOUND`.

Eventos WebSocket: `trading.started`, `trading.proposal_created`, `trading.proposal_decided`,
`trading.trade_completed` e `trading.finished`. Eles levam apenas o tipo e um indicador `involves_user`, nunca
os detalhes da proposta. Ao fim do mercado, a sessão passa para a fase `competition` (preparação das partidas,
entrega futura).

## Visibilidade

Públicos: elencos, saldos, número de negociações por clube e trocas concluídas. Uma proposta aparece apenas
para o proponente e o destinatário; propostas entre bots não são expostas ao usuário. Overall, atributos,
valores internos e personalidades nunca saem do servidor.
