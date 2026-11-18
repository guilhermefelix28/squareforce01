---
name: competition-system
description: Liga e Copa do SquadForce — opções de formato, seleção e sorteio de participantes, calendário todos-contra-todos, chaveamento eliminatório, processamento paralelo de rodadas, consolidação, classificação, estatísticas e encerramento. Use ao alterar services/competition ou as regras de formato compartilhadas.
---

# competition-system

## Finalidade
Orientar `services/competition`. **Entrega 1:** somente `options.py` (formatos válidos) e a validação em
`shared/python/squadforce_shared/domain/competition.py`. O restante é de entregas futuras.

## Quando utilizar
- Alterar formatos/limites, `GET /api/competitions/options` ou a validação de configuração.
- Entrega de competições autorizada (calendário, chave, consolidação, classificação).

## Responsabilidades
Formatos; participantes; calendário/chave; disparo paralelo das partidas; consolidação atômica de rodada; classificação e históricos.

## Regras do Game Design aplicáveis
- §2: Liga 2–20 (Série A tem prioridade na seleção — **pendência PD-01**: divisão não está na planilha); Copa 2/4/8/16/32 sorteada entre elegíveis sem repetição; clube do usuário obrigatório.
- §17: turno único ou turno e returno; todos-contra-todos sem duplicações; mandos equilibrados; número ímpar → um clube de folga por rodada (sem partida e sem reduzir afastamentos); classificação atualizada após a rodada completa.
- §18: jogo único, 90 min, pênaltis no empate, sem prorrogação; eliminado o usuário, a Copa segue até a final com avanço controlado pelo usuário.
- §19: partidas da rodada em paralelo, estado inicial imutável, sem acesso cruzado; consolidação só após todas validarem; falha crítica impede consolidação parcial.
- §20–21: central com 4 abas; média de notas exige ≥ 50% (arredondado para cima) das partidas da equipe; botão manual *Próximo confronto*.

## Contratos e dependências
`CompetitionOptions`, `CompetitionConfig` (`squadforce_shared.contracts`); motor via `match-engine`; estado na sessão.

## Procedimentos recomendados
1. Constantes de formato só em `domain/competition.py` (usadas por sessão e opções).
2. Algoritmo de calendário determinístico (método do círculo) com teste de pares únicos e mandos.
3. Consolidação: aplicar todos os resultados em uma única mutação de estado com `version + 1`.

## Restrições e comportamentos proibidos
Inventar critérios de desempate (PC-01) ou de elegibilidade (PC-02); consolidar rodada parcialmente; persistir progresso.

## Critérios de teste
E1: `tests/unit/test_session_manager.py`, `test_options_contract_matches_game_design`. Futuro: pares únicos, folgas, mandos, chave 2–32, pênaltis fora da artilharia, consolidação atômica.

## Referências
- [Game Design §2, §17–21](../../../docs/game-design/game-design-v5.2.md)
- [Pendências PC-*, PD-01](../../../docs/game-design/pendencias.md)
- [Contratos](../../../docs/api/contratos.md)
