# Execução de Liga e Copa (Entrega 7)

Implementação do GDD v5.2 §17–§21. Código:
- `services/competition/season.py`: ciclo da temporada, snapshot e consolidação;
- `services/competition/standings.py`: classificação;
- `services/competition/worker.py`: execução isolada de uma partida;
- `services/competition/service.py`: uma temporada por sessão, mais as visões da API.

## Ciclo de uma rodada (avanço sempre manual)

```
ready ──play──▶ [partidas em paralelo] ──todas válidas──▶ consolidação atômica ──▶ awaiting_advance ──advance──▶ ready (próxima) | finished
  ▲                     │ alguma falhou
  └─── play (repete só as falhas, mesma tarefa) ◀── nada consolidado (ROUND_FAILED, retryable)
```

1. **Snapshot imutável** (`RoundSnapshot`), preparado antes de a rodada ser jogada. Contém:
   - a classificação oficial;
   - os confrontos e as folgas;
   - as lesões e suspensões;
   - uma `FixtureTask` por partida, com escalações (escolhidas pela IA da Entrega 6 a partir do estado
     consolidado), semente própria, contexto público e decisões do usuário.

   Todas as partidas usam o mesmo ponto de referência.
2. **Execução paralela.** Cada tarefa vai para um executor com limite de trabalhadores:
   - processos por padrão (`SQUADFORCE_MATCH_EXECUTOR=process`, `SQUADFORCE_MATCH_WORKERS`, padrão `min(4, CPUs)`);
   - cada partida tem estado, semente e evolução próprios e termina quando terminar;
   - em processo separado, ela não tem como ver outros confrontos nem o resultado do usuário.

   Os resultados ficam num **buffer**: a classificação oficial não muda durante a rodada (testado).
3. **Consolidação atômica.** Após todas as partidas:
   - verifica cada resultado, a integridade dos eventos (`validate_result`), estatísticas × placar, identidade
     (snapshot, partida, semente, competição) e duplicações;
   - aplica tudo numa **cópia** do estado (classificação ou chave, lesões e suspensões, estatísticas e
     histórico) e troca o estado de uma vez, marcando o snapshot como consolidado;
   - qualquer erro deixa o estado oficial intacto (testado com falha no meio da aplicação).
4. **Falhas.** Uma partida que falha (exceção, tempo limite ou resultado inválido) bloqueia a rodada inteira.
   Jogar de novo repete **somente** as falhas, com a mesma tarefa: estado inicial, semente e decisões. O
   resultado é idêntico ao de uma execução sem falha (testado).
5. **Pós-rodada.** O avanço é liberado, mas só acontece por ação do usuário (`advance`).

Seeds: `sha256(semente da sessão : competição : match_id)`. A ordem de processamento não muda nada, e
processos ou threads com qualquer número de trabalhadores produzem os mesmos resultados (testado).

## Liga
- Calendário da Entrega 2 (turno único ou turno e returno). Na folga o clube não joga, não registra partida
  nem cumpre afastamentos.
- **Pontuação:** 3/1/0, **provisória** (PC-09); o GDD não define a escala.
- **Desempate:** o GDD não define os critérios (PC-01). **Nenhum critério é aplicado.** Clubes com os
  mesmos pontos compartilham a posição e aparecem em `tied_with`. Se houver empate no topo ao final,
  `champion_club_uid = null` e `tied_champions` lista os empatados. A classificação já aceita critérios
  configuráveis (`wins`, `goal_difference`, `goals_for`, `goals_against_fewer`, `head_to_head_points`)
  para quando a ordem oficial for enviada.
- Situação de cada bot (Liga, precisa vencer, evitar derrota) vem da classificação do snapshot
  (`league_situation`, provisória).

## Copa
- Chave da Entrega 2 com mando neutro: jogo único de 90 minutos, sem prorrogação e com pênaltis no empate.
- Pênaltis são registrados à parte (`shootout`) e não entram na artilharia (testado).
- `register_cup_winner` faz a progressão (`decided_by = regular_time | penalties`), sem duplicar
  classificados.
- Se o usuário for eliminado, a Copa segue até a final entre bots, ainda com avanço manual.

## Lesões e suspensões
`AvailabilityLedger.record_match` na consolidação, em ordem fixa de calendário:
- lesões são cumpridas em qualquer competição; suspensões, por competição;
- os escalados do snapshot nunca incluem lesionados ou suspensos (testado em temporada inteira).

## Pós-partida e encerramento
- `GET /season/matches/{id}` traz:
  - resultado (placar, placar oficial, pênaltis);
  - principais eventos, com nomes;
  - estatísticas por lado;
  - avaliações e Craque da Partida;
  - versões do motor.
- `GET /season/summary` traz:
  - campeão;
  - campanha de todos os clubes: Liga = posição; Copa = fase de eliminação ou "Campeão";
  - artilharia;
  - assistências;
  - melhor média de notas (mínimo de `ceil(50% das partidas da própria equipe)`);
  - mais vezes Craque da Partida;
  - histórico completo e campanha do usuário.

  Empates nas premiações listam todos os empatados. Nenhuma premiação opcional foi adicionada.

## Limitações (ver pendências)
- PC-01: sem critérios de desempate.
- PC-09: pontuação provisória.
- PM-01: as formações são a lista de amostra do motor (`PROVISIONAL_FORMATIONS`).
- PC-10: a escalação do usuário é escolhida automaticamente pelo mesmo algoritmo dos bots, com postura
  equilibrada e sem controlador, até existir a interface de partida (não autorizada).
- O núcleo já aceita decisões de postura do usuário (`set_user_decisions`), mas a API ainda não as expõe.
- PM-02 e PB-03: parâmetros do motor e da IA provisórios.
