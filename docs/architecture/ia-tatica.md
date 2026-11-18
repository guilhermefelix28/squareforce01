# IA tática dos bots (Entrega 6)

Implementação de GDD v5.2 §15. Código: `services/bot_ai/tactics.py`, `services/bot_ai/tactics_params.py`
(parâmetros **provisórios**, versão `provisorio-0.7`) e o gancho `TacticalController` em
`services/match_engine/engine.py`. Lotes de comportamento: [ia-tatica-lotes.md](ia-tatica-lotes.md).

## Antes da partida — `choose_lineup`

| Considera | Como |
|---|---|
| Jogadores disponíveis, lesões, suspensões | `AvailabilityLedger.is_available` (suspensão por competição) |
| Atributos efetivos e familiaridade | `slot_value` (composição de atributos da vaga × penalidade posicional). O overall não é usado. |
| Titulares e reservas | Atribuição ótima jogador → vaga (algoritmo húngaro); banco com goleiro reserva e o melhor de cada setor |
| Desempenhos anteriores | Nota média recente do PRÓPRIO elenco: fator ±4% por ponto (limitado a ±15%) |
| Histórico público do adversário | Gols marcados/sofridos por jogo: favorece formações com mais vagas defensivas contra ataques fortes e mais vagas ofensivas contra defesas frágeis |
| Formação de referência (antes do leilão) | Bônus de preferência (`reference_formation_bonus`) |
| Condição física | Todos começam com 100% (GDD §13): não diferencia escalações |
| Emergenciais | Só com menos de 11 aptos (delegado a `build_team_sheet`) |

As formações candidatas são **entrada**: a lista oficial está pendente (PM-01). Sem candidatas, o resultado
é um erro explícito. A formação escolhida fica fixa durante o jogo. A postura inicial sai do mesmo modelo
de utilidade.

## Durante a partida — `TacticalBot`

**Modelo leve de utilidade esperada (sem Monte Carlo).** Os gols restantes são estimados por duas Poisson
independentes, com médias que combinam:
- a expectativa anterior: média do motor, qualidade efetiva do próprio time e histórico público do adversário;
- o xG observado neste jogo (atualização gama-Poisson);
- os multiplicadores das posturas **medidos no motor** (próprio e da postura observável do adversário);
- a desvantagem numérica.

Daí saem P(vitória), P(empate) e P(derrota). A utilidade é calculada assim:

`U = Σ P × valor do resultado na situação − aversão à perda × queda esperada em relação ao placar atual − custos de desgaste`

**Situação da competição** (estado público no início da rodada): Liga 3/1/0; precisa vencer (o empate vale
pouco); evitar derrota (o empate vale quase uma vitória); Copa: avançar 1, pênaltis 0,5, eliminação 0.
`league_situation` é uma regra provisória a partir da classificação. A Entrega 7 a alimentará.

**Personalidades (ocultas e moderadas):** alteram a aversão à perda e pequenos bônus de valor. Em
situações claras (perdendo/vencendo) todas decidem igual; a personalidade só desloca a decisão em
empates. Não há bônus de atributos.

**Contra trocas excessivas:**
- reavaliação a cada 5 min de jogo, e também após gol, expulsão ou jogador perdido;
- ganho mínimo (`min_benefit × (0,15 + fração restante)`);
- histerese para voltar à postura recém-abandonada;
- intervalo mínimo de 10 min entre mudanças, com exceção para acontecimentos decisivos.

**Substituições:** o motor mantém as trocas por lesão, desgaste e rendimento (máximo de 5). Com controlador
presente, o bot pode pedir trocas **táticas**: perdendo e atacando, entra um atacante; vencendo e
protegendo no fim, entra um defensor. A troca por desgaste urgente tem prioridade.

## Informação permitida (sem trapaça)

O bot só recebe `TacticalObservation`:
- o próprio time: atletas, condição, cartões e banco;
- placar, tempo e jogadores em campo de cada lado;
- posturas observáveis;
- estatísticas e acontecimentos **desta partida**.

E o `PreMatchContext` público (situação e histórico do adversário).

Não recebe:
- o gerador aleatório nem a semente;
- eventos futuros;
- outros jogos;
- decisões futuras do usuário;
- atributos do adversário.

As decisões são determinísticas e **não consomem o RNG do motor**. Um controlador passivo produz
exatamente os mesmos eventos de uma partida sem IA (testado). O motor não foi alterado para partidas sem
controlador: 8 hashes de regressão continuam idênticos.

## Limitações conhecidas

- Os parâmetros da IA e do motor são provisórios (PB-03, PM-02). Com posturas lineares por degrau no motor,
  as escolhas tendem às pontas (Retranca/Ataque Total). Posturas intermediárias aparecem pouco.
- A regra `league_situation` e os valores das situações são provisórios; a classificação real virá da
  Entrega 7.
- A estimativa de força do adversário usa apenas o histórico público e o xG observado. Sem histórico, ela
  parte da média.
