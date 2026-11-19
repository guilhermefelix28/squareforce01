---
name: competition-system
description: Liga e Copa do SquadForce — opções de formato, seleção e sorteio de participantes, calendário todos-contra-todos, chaveamento eliminatório, processamento paralelo de rodadas, consolidação, classificação, estatísticas e encerramento. Use ao alterar services/competition ou as regras de formato compartilhadas.
---

# competition-system

## Finalidade
Orientar `services/competition`. **Implementado (Entregas 1–2):** `options.py` (formatos), `planner.py`
(seleção de participantes, calendário da Liga, chaveamento da Copa, validadores e progressão estrutural) e a
validação em `shared/python/squadforce_shared/domain/competition.py`. **Futuro:** execução das rodadas,
consolidação paralela, classificação, estatísticas.

## Quando utilizar
- Alterar formatos/limites, `GET /api/competitions/options` ou a validação de configuração.
- Entrega de competições autorizada (calendário, chave, consolidação, classificação).

## Responsabilidades
Formatos; participantes; calendário/chave; disparo paralelo das partidas; consolidação atômica de rodada; classificação e históricos.

## Regras do Game Design aplicáveis
- §2: Liga 2–20 com prioridade da Série A e depois Série B (divisões 2026 em `club_divisions`, PD-01 resolvida); Copa 2/4/8/16/32 sorteada entre os 40 elegíveis sem repetição (PC-02); clube do usuário obrigatório e primeiro em `participants`.
- §17: turno único ou turno e returno; todos-contra-todos sem duplicações; mandos equilibrados; número ímpar → um clube de folga por rodada (sem partida e sem reduzir afastamentos); classificação atualizada após a rodada completa.
- §18: jogo único, 90 min, pênaltis no empate, sem prorrogação; eliminado o usuário, a Copa segue até a final com avanço controlado pelo usuário.
- §19: partidas da rodada em paralelo, estado inicial imutável, sem acesso cruzado; consolidação só após todas validarem; falha crítica impede consolidação parcial.
- §20–21: central com 4 abas; média de notas exige ≥ 50% (arredondado para cima) das partidas da equipe; botão manual *Próximo confronto*.

## Contratos e dependências
- Contratos: `CompetitionOptions`, `CompetitionConfig`, `CompetitionOut`, `LeagueSchedule`/`LeagueRound`/`LeagueMatch`, `CupBracket`/`CupRound`/`CupMatch`/`CupRules` (`squadforce_shared.contracts`).
- Endpoints: `GET /api/sessions/{id}/competition`; temporada (Entrega 7): `POST .../season/start|play|advance`,
  `GET .../season`, `.../season/matches/{match_id}`, `.../season/summary` (`SeasonStateOut`, `MatchReportOut`,
  `SeasonSummaryOut`).
- Execução: `services/competition/season.py` (`Season`, `RoundSnapshot`), `standings.py`, `worker.py`
  (`FixtureTask`/`play_fixture`, serializável), `service.py` (`SeasonService`). Ver `docs/architecture/competicoes.md`.
- Porta: `CompetitionPlanner` = `plan_competition(config, eligible, rng) -> (participants, structure)`, injetada na sessão (ADR-09).
- Elegíveis: `DataService.eligible_clubs()` → `list[EligibleClub]` (clubes importados com divisão).
- IDs estáveis: `L-R{rodada:02}-M{jogo:02}` e `C-R{fase}-M{jogo:02}`.
- Para a IA tática (Entrega 6): fornecer `CompetitionSituation` (Liga/precisa vencer/evitar derrota/Copa) e
  `OpponentHistory` a partir do estado PÚBLICO no início da rodada (nunca de jogos em andamento).

## Procedimentos recomendados
1. Constantes de formato só em `domain/competition.py` (usadas por sessão e opções).
2. Toda aleatoriedade pelo `random.Random` recebido; nunca `random` global (determinismo).
3. Calendário: método do círculo (Berger) com slots sorteados; returno = espelho com mandos invertidos.
4. Toda estrutura nova passa por `validate_league_schedule`/`validate_cup_bracket` antes de ser aceita.
5. Progressão da Copa só por `register_cup_winner` (retorna cópia; empate → `decided_by="penalties"`).
6. Consolidação: validar TODOS os resultados e aplicar numa cópia do estado (`_State.copy`) trocada de uma vez;
   snapshot marcado como consolidado (nunca duas vezes). Falha => nada aplicado; repetir só as falhas com a mesma tarefa.
7. Nada que uma partida precise pode vir de fora da sua `FixtureTask` (isolamento entre confrontos simultâneos).
8. Avanço sempre manual (`advance`); nunca encadear rodadas automaticamente.
9. Escalação do usuário: `Season.set_user_lineup` (validada contra o estado oficial). Partida ao vivo:
   `live.py` (`LiveMatch`); antes de `play`, registrar as decisões e `expect_result` (resultado idêntico).

## Restrições e comportamentos proibidos
Inventar critérios de desempate (PC-01) ou efeito de mando (PC-03); atribuir mando na Copa (PC-05); expor a semente; consolidar rodada parcialmente; persistir progresso; expor `register_cup_winner` diretamente por API; aplicar critérios de desempate não enviados (lista padrão vazia);
usar `random` global ou semente dependente da ordem de execução.

## Critérios de teste
`tests/unit/test_competition_planner.py` (Ligas 2/3/5/7/10/19/20 × turnos × sementes; Copas 2–32; corrupções; determinismo), `tests/integration/test_competition_api.py`, `test_session_manager.py`, `CompetitionView.test.tsx`. Entrega 7: `test_standings.py`, `test_season.py`, `tests/integration/test_season_api.py`, `tests/simulation/test_season_batches.py`.

## Estado na homologação (Entrega 9)
Homologação: Ligas 2–20 (ímpares, turno/returno), Copa 32, final nos pênaltis, eliminação do usuário, falhas paralelas, consolidação única concorrente e reconexão testadas; Liga 20 e Copa 32 completas pela API medidas em desempenho.

## Referências
- [Game Design §2, §17–21](../../../docs/game-design/game-design-v5.2.md)
- [Pendências PC-*, PD-01](../../../docs/game-design/pendencias.md)
- [Matriz de testes](../../../docs/architecture/matriz-de-testes.md)
- [Contratos](../../../docs/api/contratos.md)
