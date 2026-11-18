# Serviço: match_engine (motor de partidas)

**Estado:** planejado — sem implementação na Entrega 1.
**Skill:** [`match-engine`](../../.claude/skills/match-engine/SKILL.md) · **GDD:** seções 10 a 16

## Responsabilidade
Simulação por eventos encadeados (posse → construção → oposição → oportunidade → finalização →
goleiro → resultado), xG contextual, faltas/cartões/lesões, substituições, notas, Craque da
Partida, determinismo por semente.

## Limites
- Recebe um estado inicial imutável por partida; não acessa outras partidas simultâneas.
- Não consolida classificação (responsabilidade de `competition`).
