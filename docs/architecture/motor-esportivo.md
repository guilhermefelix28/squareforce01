# Motor esportivo (Entrega 5)

Implementação de GDD v5.2 §9–§16. Código: `services/match_engine/`. Lotes exploratórios:
[motor-calibracao-exploratoria.md](motor-calibracao-exploratoria.md).

> **Estado:** regras do GDD implementadas e verificadas; os números estão em `services/match_engine/params.py`
> (`MatchParams`, versão `provisorio-0.6`). **Entrega 9:** em 20.250 partidas, gols, empates, finalizações, xG, faltas e
> cartões ficaram dentro das faixas derivadas de referências públicas (`docs/homologacao/criterios.md`,
> `docs/homologacao/calibracao.md`); único ajuste: `xg_intercept` 0,75 → 0,88. As referências ainda não foram
> aprovadas oficialmente pelo responsável (PM-02) e várias métricas não têm referência (não validadas).
>
> **2026-11-19 (DR-03):** versão `calibrado-0.7` = `provisorio-0.6` + `gk_fatigue_multiplier = 0,35` (goleiros cansam
> pouco, decisão do responsável). Re-medido em 20.250 partidas: todos os critérios continuam aprovados
> (gols 2,368, empates 25,4%, xG 2,344; `docs/homologacao/calibracao.md`).

## Módulos

| Arquivo | Responsabilidade |
|---|---|
| `params.py` | Única fonte de números: tempos, probabilidades base, xG, disciplina, lesões, desgaste, notas e posturas (todos provisórios). Também agrupa os 59 atributos REAIS (técnicos, mentais, físicos e de goleiro) e as composições por ação. |
| `types.py` | `MatchPlayer`, `TeamSheet` (formação fixa, 11 titulares, até 7 reservas, postura), `MatchInput`, `Event`, `MatchResult`, `PostureChange`. |
| `attributes.py` | Atributo efetivo = base × (1 − penalidade posicional) × cansaço × forma do dia. |
| `engine.py` | `MatchSimulation`: posses encadeadas, progressão por zonas, disputas, faltas, cartões, lesões, substituições, finalizações, goleiro, gols, reinícios e encerramento administrativo. |
| `stats.py` | Estatísticas **derivadas exclusivamente dos eventos**. |
| `ratings.py` | Notas 0–10 a partir dos eventos e Craque da Partida. |
| `validation.py` | Invariantes: recusa gol sem finalização, placar ≠ gols, estatística impossível, > 5 substituições, inelegível em campo, nota fora da faixa, eventos duplicados ou fora de ordem. |
| `availability.py` | Lesões (qualquer competição), suspensões (por competição), folgas que não contam, histórico disciplinar e médico. |
| `lineup.py` | Escalação automática só com atletas aptos (atribuição ótima jogador → vaga) e emergenciais quando há menos de 11 aptos. |
| `presentation.py` | Velocidades de 15 s, 30 s, 60 s e instantânea sobre o mesmo motor. |
| `calibration.py` | Lotes exploratórios e faixas preliminares (não aprovadas). |

## Fluxo de uma posse

`possession` (reinício: saída, tiro de meta, lateral, falta, escanteio, pênalti) → progressão
**defesa → meio → terço final**. Em cada passo, a composição ofensiva da equipe é comparada com a composição
defensiva do adversário, ajustada pelas posturas → em caso de sucesso, `progression`; em caso de falha:
- **falta** (`foul`), com possível cartão, lesão da vítima, pênalti ou falta perigosa;
- **bola fora** (escanteio ou lateral);
- **desarme ou interceptação**.

No terço final pode surgir uma **oportunidade**, com tipo, finalizador, criador, distância, ângulo e pressão →
`shot` com **xG contextual** → `block`, `save` (defesa do goleiro, rebote ou escanteio), `goal` (com assistência)
ou `miss` (inclui bola na trave).

O placar só muda por eventos `goal`, cada um precedido do `shot` do mesmo jogador.

## Regras do GDD e onde estão

| Regra | Implementação |
|---|---|
| Atributos efetivos, adequação posicional, formação, postura, condição, aleatoriedade controlada (§10) | `attributes.py`, `engine._team_skill` (média por vaga nominal da formação: jogador a menos reduz a força) |
| Penalidade posicional proporcional de até 35% (§3) | `positional_factor`: 0% com familiaridade 100 → 35% com familiaridade 1. Curva **linear provisória** (PE-03) |
| xG contextual sem atributos (§12) | `contextual_xg(kind, distância, ângulo, pressão)`; finalizador e goleiro multiplicam **depois** e separadamente a probabilidade de gol (`shooter_effect`, `keeper_effect`) |
| Grandes chances (§12) | `is_big_chance`: xG ≥ limiar e pressão baixa (limiares provisórios) |
| Goleiro: reflexos, posicionamento, um contra um etc. (§12) | composição `goalkeeping` / `gk_penalty` |
| Faltas, cartões e lesões contextuais (§13) | risco do defensor (`aggression`, `dirtiness`), postura, zona, cansaço, `injury_proneness`; lesões de 0 a 3 jogos |
| Segundo amarelo = vermelho; expulso não volta nem é substituído (§13) | `_card`, `_send_off` |
| Até 5 substituições automáticas (desgaste, lesão, rendimento, contexto) (§13) | `_consider_substitution`, `_contact_injury` |
| Lesão sem substituição disponível → equipe com menos jogadores (§13) | evento `player_off` |
| Menos de 7 em campo → encerramento; 3 × 0 ou placar real se mais favorável ao adversário (§13) | `_check_minimum`, `result()`; placar oficial e esportivo separados |
| Desgaste só dentro do jogo; 100% de condição em cada nova partida (§13) | `condition` nasce 100 a cada `MatchSimulation` |
| Notas 0,0–10,0 com uma casa, contextuais, sem overall; Craque e desempates (§14) | `ratings.py` (desempate final por menor ID: decisão provisória MD-03) |
| 5 posturas moderadas; formação fixa; mudança só afeta eventos futuros (§11) | `PostureEffect`, `set_posture`, `PostureChange` |
| Sementes e determinismo; velocidades sem alterar resultados (§16) | `random.Random(seed)` único; decisões indexadas por tempo de jogo; `LivePresentation` |
| Copa: empate nos 90 min → pênaltis sem prorrogação, registrados à parte, fora da artilharia (§18) | `MatchInput.knockout`, `_shootout`; `MatchResult.shootout` e `winner_side` (5 cobranças alternadas, encerramento antecipado, depois alternadas) |
| Emergenciais só com menos de 11 aptos, fora do elenco (§9) | `lineup.emergency_player` (IDs negativos, `is_emergency`) |
| Lesões em qualquer competição; suspensões por competição; folgas não contam (§13) | `AvailabilityLedger.record_match` |

## Determinismo

O resultado é função de **(estado inicial, `ENGINE_VERSION`, `MatchParams`, semente, decisões)**:
- há um único gerador `random.Random(seed)`;
- formas do dia e acréscimos são sorteados no início, em ordem fixa;
- uma decisão de postura vale a partir da **primeira posse que começa no instante dela ou depois**. Por isso,
  simular de uma vez, em etapas ou por qualquer velocidade de apresentação produz os mesmos eventos (testado).

## Pendências do motor

Ver `docs/game-design/pendencias.md`: PM-01 (formações), PM-02 (referências e calibração), PM-03 (impacto
decisivo), PE-03 (curva da penalidade posicional) e MD-01 a MD-06 (decisões provisórias do motor).
