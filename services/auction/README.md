# Serviço: auction (leilão)

**Estado:** implementado (Entrega 3), **aguardando o `AuctionModel` aprovado** (fórmulas pendentes).
**Skill:** [`auction-system`](../../.claude/skills/auction-system/SKILL.md) · **Detalhes:** [docs/architecture/leilao.md](../../docs/architecture/leilao.md)

| Arquivo | Conteúdo |
|---|---|
| `rules.py` | regras aprovadas (orçamento, 18, 10 s, 5 atletas, R$ 500 mil/vaga, janela de 14, durações, limite de melhorias) |
| `model.py` | interface `AuctionModel` das fórmulas pendentes + carregamento por `SQUADFORCE_AUCTION_MODEL` |
| `engine.py` | motor com relógio autoritativo, lances sigilosos, desempate, idempotência |
| `completion.py` | complementação automática até 18 |
| `service.py` | um motor por sessão (memória) e visões públicas |

Limites: não acessa SQLite (recebe `PlayerProfile` do serviço de dados); decisões dos bots vêm de `bot_ai`;
nada é persistido.
