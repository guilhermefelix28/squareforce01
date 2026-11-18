# Serviço: match_engine (motor de partidas)

**Estado:** implementado (Entrega 5) como biblioteca pura e determinística. **Parâmetros provisórios, não
calibrados** (`params.py`, pendência PM-02).
**Skill:** [`match-engine`](../../.claude/skills/match-engine/SKILL.md) · **Detalhes:** [docs/architecture/motor-esportivo.md](../../docs/architecture/motor-esportivo.md)

Uso mínimo:

```python
from services.match_engine.engine import simulate
from services.match_engine.lineup import build_team_sheet
from services.match_engine.types import MatchInput

home = build_team_sheet(club_a, squad_a, formation)
away = build_team_sheet(club_b, squad_b, formation)
result = simulate(MatchInput("M-1", "liga", home, away, seed=123))
```

Limites: não acessa SQLite nem relógio de parede; não consolida classificação (`competition`); não decide
posturas dos bots (Entrega 6).
