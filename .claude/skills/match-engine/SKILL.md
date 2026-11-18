---
name: match-engine
description: Motor de partidas do SquadForce — simulação por eventos encadeados, atributos efetivos, adequação posicional, posturas, xG contextual, goleiros, faltas, cartões, lesões, desgaste, substituições, notas, Craque da Partida e determinismo por semente. Use somente quando a entrega do motor estiver autorizada ou ao revisar contratos relacionados.
---

# match-engine

## Finalidade
Orientar o serviço `services/match_engine` (ainda **não implementado**; ver `services/match_engine/README.md`).

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
Entrada: snapshot imutável da partida + semente + versão de parâmetros. Saída: lista de eventos e resumo. Decisões táticas de bots via `bot-intelligence`.

## Procedimentos recomendados
1. RNG semeado por partida; nenhum uso de relógio ou estado global.
2. Parâmetros versionados em um único módulo; calibração por simulação em lote contra referências (pendência PM-02).
3. Velocidade de apresentação é responsabilidade do cliente/gateway, nunca do motor.

## Restrições e comportamentos proibidos
Gols garantidos por postura; placar pré-sorteado; acesso a outras partidas; inventar parâmetros sem registrar como calibráveis.

## Critérios de teste
Determinismo bit a bit; distribuições estatísticas (gols, empates, 0×0, goleadas) dentro das faixas aprovadas; regra dos 7 jogadores; limites de substituições; notas no intervalo.

## Referências
- [Game Design §9–16](../../../docs/game-design/game-design-v5.2.md)
- [Pendências PM-*](../../../docs/game-design/pendencias.md)
- [README do serviço](../../../services/match_engine/README.md)
