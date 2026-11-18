# Serviço: auction (leilão)

**Estado:** planejado — sem implementação na Entrega 1.
**Skill:** [`auction-system`](../../.claude/skills/auction-system/SKILL.md) · **GDD:** seções 4, 5 e 7 de [game-design-v5.2.md](../../docs/game-design/game-design-v5.2.md)

## Responsabilidade
Rodadas de 10 s com 5 jogadores da mesma posição, ofertas fechadas, relógio global autoritativo,
desempate por timestamp do servidor e ordem de aceitação, orçamento (R$ 120 mi), reserva mínima de
R$ 500 mil por vaga restante, complementação automática até 18 jogadores.

## Limites
- Não acessa SQLite diretamente: lê o catálogo via serviço de dados.
- Não decide lances dos bots: consome o serviço `bot_ai`.
- Estado do leilão vive na sessão em memória (serviço `session`); nada é persistido.

## Contratos previstos (a detalhar na entrega do leilão)
Comandos REST idempotentes (`Idempotency-Key`) para lances; eventos WebSocket no canal
`/ws/sessions/{id}` para relógio e resultado de rodada. Nomes e payloads ainda não definidos.
