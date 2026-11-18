# Serviço: trading (mercado de negociações)

**Estado:** implementado (Entrega 4). Depende do leilão concluído; os parâmetros de negociação das
personalidades (`TradeProfile`) vêm do `AuctionModel` pendente.
**Skill:** [`trading-system`](../../.claude/skills/trading-system/SKILL.md) · **Detalhes:** [docs/architecture/mercado.md](../../docs/architecture/mercado.md)

| Arquivo | Conteúdo |
|---|---|
| `rules.py` | 3 min, 10 s por proposta, 3 negociações, 1 pendente por proponente, 18 jogadores |
| `engine.py` | motor: propostas, decisões únicas, trocas atômicas, linha do tempo do servidor, bots |
| `service.py` | um mercado por sessão (memória) e visões públicas |

Limites: não acessa SQLite; recebe elencos e atletas do leilão concluído; decisões dos bots em
`services/bot_ai/trade_bot.py`; nada é persistido.
