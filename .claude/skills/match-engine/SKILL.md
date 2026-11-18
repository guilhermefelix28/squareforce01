---
name: match-engine
description: Motor de partidas do SquadForce — simulação por eventos encadeados, atributos efetivos, adequação posicional, posturas, xG contextual, goleiros, faltas, cartões, lesões, desgaste, substituições, notas, Craque da Partida e determinismo por semente. Use somente quando a entrega do motor estiver autorizada ou ao revisar contratos relacionados.
---

# match-engine

## Finalidade
Orientar o serviço `services/match_engine`. **Implementado na Entrega 5** como biblioteca pura e determinística;
**todos os números são provisórios** (`params.py`, `MatchParams.version`) e o motor **não está calibrado** (PM-02).

## Quando utilizar
Implementação, calibração ou revisão de qualquer parte da simulação de partidas.

## Responsabilidades
Simular uma partida a partir de um estado inicial imutável e produzir eventos, estatísticas, avaliações e resultado.

## Regras do Game Design aplicáveis (§3, §9–16)
- Fluxo: posse → construção → oposição → oportunidade → finalização → goleiro → resultado; placar **não predeterminado**.
- Usa atributos efetivos, adequação posicional (penalidade **até 35%**), formação, postura, condição física, contexto, aleatoriedade controlada; overall não decide sozinho.
- Posturas: Retranca, Defensiva, Equilibrada, Ofensiva, Ataque Total — efeitos moderados; mudança só afeta eventos ainda não simulados; formação fixa no jogo.
- xG contextual (distância, ângulo, tipo, pressão, posição, contexto) independente da execução; finalizador e goleiro modificam a probabilidade **sem dupla contagem**.
- Lesões 0–3 partidas (cumpridas em jogos oficiais de qualquer competição); cartões por competição; folgas não contam; condição física total no início de cada jogo; até **5 substituições automáticas**; expulsos não voltam; < 7 jogadores → encerramento, 3×0 ou placar mais favorável ao adversário.
- Notas 0,0–10,0 (uma casa) contextuais; Craque = maior nota interna, depois impacto decisivo.
- Velocidades 15 s / 30 s / 60 s / instantâneo usam o mesmo motor; **mesmo estado + versão + parâmetros + semente + decisões ⇒ mesmos eventos**.
- Copa: pênaltis registrados à parte, sem contar na artilharia.

## Contratos e dependências
- Entrada: `MatchInput` (dois `TeamSheet` com formação fixa, 11 titulares, até 7 reservas e postura; semente; competição).
- Execução: `simulate(input, params, decisions)` ou `MatchSimulation(...).advance_to(segundo)` + `set_posture(lado, postura)`.
- Saída: `MatchResult` (eventos, placar esportivo e oficial, estatísticas derivadas, notas, Craque, lesões, cartões).
- Invariantes: `validation.validate_result` (usar em TODO teste e lote).
- Entre partidas: `availability.AvailabilityLedger.record_match`; escalação: `lineup.build_team_sheet` (emergenciais).
- Apresentação: `presentation.LivePresentation` (15 s, 30 s, 60 s, instantânea).
- Decisões táticas dos bots: `simulate(..., controllers={lado: TacticalController})`; o controlador recebe só
  `TacticalObservation` e devolve posturas (viram `PostureChange`). Sem controlador o motor é bit a bit o da
  Entrega 5 (`tests/unit/test_match_engine_regression.py`).

## Procedimentos recomendados
1. RNG único semeado por partida; nenhum uso de relógio de parede ou estado global; ordem de iteração fixa.
2. Nenhum número fora de `params.py`; mudar parâmetros = nova `MatchParams.version`.
3. Estatísticas e notas SEMPRE derivadas dos eventos (`stats.py`, `ratings.py`); nunca contadores paralelos.
4. Atributos: só os 59 da base real; o overall nunca participa.
5. Ao calibrar: `scripts/match_engine_report.py` (gera `docs/architecture/motor-calibracao-exploratoria.md`)
   e `tests/simulation/test_match_batches.py`; não declarar "calibrado" sem referências aprovadas.
6. Velocidade de apresentação é responsabilidade do cliente/gateway, nunca do motor.

## Restrições e comportamentos proibidos
Gols garantidos por postura; placar pré-sorteado; acesso a outras partidas; inventar parâmetros sem registrar como provisórios;
estatísticas fora dos eventos; usar overall na nota; atributo inexistente na base sem regra de derivação aprovada.

## Critérios de teste
Determinismo bit a bit; distribuições estatísticas (gols, empates, 0×0, goleadas) dentro das faixas aprovadas; regra dos 7 jogadores; limites de substituições; notas no intervalo.

## Referências
- [Game Design §9–16](../../../docs/game-design/game-design-v5.2.md)
- [Pendências PM-*](../../../docs/game-design/pendencias.md)
- [README do serviço](../../../services/match_engine/README.md)
- [Motor esportivo: regras e módulos](../../../docs/architecture/motor-esportivo.md)
- [Lotes exploratórios](../../../docs/architecture/motor-calibracao-exploratoria.md)
