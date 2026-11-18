# Serviço: bot_ai (inteligência dos bots)

**Estado:** planejado — sem implementação na Entrega 1.
**Skill:** [`bot-intelligence`](../../.claude/skills/bot-intelligence/SKILL.md) · **GDD:** seções 6, 8 e 15

## Responsabilidade
Decisões de leilão (4 personalidades ocultas; ganho marginal 80% titulares / 20% reservas),
negociações, formações e posturas táticas.

## Limites
- Usa **apenas informações públicas**: nunca ofertas secretas, eventos futuros ou outros jogos da rodada.
- Não altera estado diretamente: devolve decisões que os serviços dono do estado validam.
