# Serviço: bot_ai (inteligência dos bots)

**Estado:** leilão (Entrega 3), mercado (Entrega 4) e tática de partidas (Entrega 6) implementados; parâmetros
provisórios (PB-01, PB-02, PB-03).
**Skill:** [`bot-intelligence`](../../.claude/skills/bot-intelligence/SKILL.md) · **GDD:** seções 6, 8 e 15

| Arquivo | Conteúdo |
|---|---|
| `evaluation.py` | escalação ótima por formação, qualidade de titulares/reservas, ganho marginal 0,8/0,2 |
| `auction_bot.py` | decisão de lance a partir de `BotAuctionView` |
| `trade_bot.py` | avaliação e proposta de trocas (`evaluate_offer`, `choose_proposal`) |
| `tactics.py` | formação, escalação, postura inicial e posturas durante o jogo (`TacticalBot`) |
| `tactics_params.py` | parâmetros provisórios da tática (multiplicadores de postura medidos no motor) |
| `tactics_report.py` | lotes de comportamento usados por testes e relatório |

Limites: usa **apenas informações públicas** e da própria equipe; não altera estado diretamente; não usa o RNG
do motor; não concede bônus de atributos.
