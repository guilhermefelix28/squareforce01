# Serviço: trading (mercado de negociações)

**Estado:** planejado — sem implementação na Entrega 1.
**Skill:** [`trading-system`](../../.claude/skills/trading-system/SKILL.md) · **GDD:** seção 8

## Responsabilidade
Mercado de 3 minutos iniciado pelo usuário; trocas 1×1 com pagamento adicional opcional do
proponente; até 3 negociações concluídas por clube; uma proposta ativa por clube; prazo de 10 s;
sem contrapropostas; transações atômicas mantendo 18 jogadores e saldo não negativo.

## Limites
- Avaliação dos bots é delegada a `bot_ai`.
- Estado em memória na sessão; nada persistido.
