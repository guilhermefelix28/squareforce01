# Serviço: bot_ai (inteligência dos bots)

**Estado:** leilão implementado (Entrega 3); negociações e partidas em entregas futuras.
**Skill:** [`bot-intelligence`](../../.claude/skills/bot-intelligence/SKILL.md) · **GDD:** seções 6, 8 e 15

| Arquivo | Conteúdo |
|---|---|
| `evaluation.py` | escalação ótima por formação (algoritmo húngaro), qualidade de titulares/reservas, ganho marginal 0,8/0,2 |
| `auction_bot.py` | decisão de lance a partir de `BotAuctionView` (somente informação pública) e `BotProfile` |

Limites: usa **apenas informações públicas**; não altera estado (o motor valida e aplica); parâmetros das
personalidades vêm do `AuctionModel` (pendência PB-01).
