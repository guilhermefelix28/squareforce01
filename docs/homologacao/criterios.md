# Critérios de homologação (Entrega 9), definidos ANTES das medições

Este arquivo foi escrito e versionado (commit próprio) **antes** de rodar os lotes de calibração e as
medições de desempenho desta entrega. Os limites não podem ser alterados depois de observar os resultados.
Qualquer mudança exige um novo commit justificado e invalida a aprovação do item.

> **Transparência.** Lotes exploratórios da Entrega 5 (`docs/architecture/motor-calibracao-exploratoria.md`)
> já tinham sido observados. Para não usá-los como base, as faixas abaixo saem SOMENTE das referências
> públicas, por uma regra mecânica: **faixa = [menor referência × 0,9 ; maior referência × 1,1]**.

## 1. Referências estatísticas (futebol real)

| Métrica (por partida, soma dos dois times) | Referências | Fonte |
|---|---|---|
| Gols | 2,44 (Brasileirão 2024, até a 36ª rodada); 2,49 (Brasileirão 2023); 2,58–3,24 (cinco grandes ligas europeias 2023-24) | Placar/Trivela; 90min; The Analyst (Opta) |
| Empates | ~25–30% das partidas (grandes ligas europeias, séries longas) | FiveThirtyEight; Kitman Labs; estudo com 10.785 jogos |
| Finalizações | 24,6–27,4 (cinco grandes ligas 2023-24) | The Analyst |
| xG | 2,49–3,13 (cinco grandes ligas 2023-24) | The Analyst |
| Faltas | 25,89 (La Liga 2022-23, mínima da série); 28,53 (Brasileirão) | The Analyst; Flashscore/Soccerway |
| Cartões amarelos | 3,2 (Ligue 1 2022-23); 3,53 (Brasileirão 2023-24, ESPN); 4,78 (La Liga 2022-23) | The Analyst; Jornal de Brasília/ESPN |
| Cartões vermelhos | 0,079 (Premier League 2022-23: 30/380); 0,36 (La Liga 2022-23: 137/380); 0,49 (Brasileirão 2023-24, ESPN) | The Analyst; Jornal de Brasília/ESPN |

URLs:
- https://theanalyst.com/2024/03/numbers-behind-premier-league-goal-explosion/
- https://theanalyst.com/articles/top-five-league-stats-goals-cards-time-wasting
- https://placar.com.br/brasileirao/brasileirao-tem-recorde-de-gols-em-uma-mesma-rodada/
- https://www.90min.com/pt-br/posts/estatisticas-da-serie-a-do-campeonato-brasileiro-de-2023
- https://jornaldebrasilia.com.br/mais-esportes/qual-a-media-de-cartoes-no-campeonato-brasileiro-analise-estatistica-dos-cartoes-amarelos-e-vermelhos-na-temporada/
- https://br.soccerway.com/noticias/futebol-serie-b-serie-b-e-a-liga-mais-faltosa-do-mundo-veja-ranking/Ot5uJT05
- https://fivethirtyeight.com/features/home-field-advantage-english-premier-league
- https://www.kitmanlabs.com/?p=28689

**Limitações das referências:**
- São agregados jornalísticos e de provedores (Opta/ESPN), não uma base oficial aprovada pelo responsável
  (PM-02 continua aberta).
- Não encontrei referência pública confiável e comparável para: escanteios, defesas, lesões por jogo,
  grandes chances, percentual no alvo (definições divergem) e distribuição de notas. **Essas métricas são
  medidas e publicadas, mas NÃO são declaradas validadas.**

## 2. Faixas de aceitação (regra mecânica)

| Métrica (lote amplo, ≥ 10.000 partidas, equipes de força variada, bots com IA) | Faixa |
|---|---|
| Gols por partida | **2,20 – 3,56** |
| Empates | **22,5% – 33,0%** |
| Finalizações por partida | **22,1 – 30,1** |
| xG por partida | **2,24 – 3,44** |
| Faltas por partida | **23,3 – 31,4** |
| Amarelos por partida | **2,88 – 5,26** |
| Vermelhos por partida | **0,071 – 0,54** |

**Coerência interna (derivada das regras do motor e do GDD, independente de referência externa):**
- Gols ≈ xG: |gols − xG| / xG ≤ 10% no lote amplo (xG calibrado).
- Estatísticas idênticas às derivadas dos eventos: 100% das partidas (`validate_result` sem problemas).
- Notas entre 0,0 e 10,0; Craque = maior nota exibida (com desempate interno), em 100% das partidas.
- Lesões com afastamento de 0 a 3 jogos; no máximo 5 substituições; expulsos não retornam; encerramento
  administrativo abaixo de 7 jogadores (GDD §13), em 100% das partidas.
- **Qualidade (GDD §10):** a taxa de vitória do mais forte cresce com a diferença de nível.
- **Resultados inesperados possíveis (GDD §10):** com diferença ≥ 15 pontos de nível, o mais fraco vence em
  > 0% e < a taxa do mais forte.
- **Posturas moderadas (GDD §11):** em relação à Equilibrada, nenhuma postura muda os gols marcados ou
  sofridos em mais de ±35%; a ordem é monótona (mais ofensiva = mais gols marcados e sofridos). O limite de
  ±35% é uma INTERPRETAÇÃO de "moderadamente" e precisa de confirmação (pendência PH-01).
- **Inferioridade numérica:** quem fica com 10 sofre mais gols por minuto e marca menos depois da expulsão.

## 3. IA (Entrega 6), sem trapaça
- Nenhuma partida inválida com bots.
- No máximo 4 mudanças de postura por time e por jogo em média; nunca mais de 8.
- ≥ 80% das mudanças perdendo vão para ataque e ≥ 80% vencendo vão para proteção.
- IA contra estático de mesma força: diferença de pontos por jogo entre −0,15 e +0,6 (sem vantagem
  artificial).
- Observação limitada: sem RNG, futuro, outros jogos ou decisões futuras do usuário (testes existentes).

## 4. Desempenho

Ambiente de referência: a máquina de desenvolvimento desta homologação (Windows 11, 12 CPUs lógicas,
Python 3.12, Node 26), servidor local. Critérios (decisão técnica; o GDD não fixa números, ver PH-02):

| Medida | Critério |
|---|---|
| Inicialização do gateway (processo até `/api/health` = 200) | ≤ 5 s |
| GET de leitura (health, sessão, temporada, estatísticas) | p95 ≤ 150 ms |
| Lance no leilão (POST, ida e volta) | p95 ≤ 100 ms |
| Proposta/decisão no mercado | p95 ≤ 150 ms |
| Uma partida (motor + IA dos dois lados) | média ≤ 150 ms |
| Fase de Copa com 32 clubes (16 partidas em paralelo + consolidação) | ≤ 5 s |
| Rodada de Liga com 20 clubes (10 partidas em paralelo + consolidação) | ≤ 4 s |
| Liga com 20 clubes, turno e returno (380 partidas) | ≤ 120 s |
| Memória do gateway após uma Liga de 20 clubes completa | ≤ 600 MB |
| CPU: a rodada paralela usa mais de um núcleo (speedup ≥ 1,5× vs. 1 trabalhador) | sim |
| Frontend: carregamento inicial local (DOMContentLoaded) | ≤ 2 s |
| Frontend: pacote JS de produção (gzip) | ≤ 250 kB |

## 5. Critério final (prompt da Entrega 9)

APROVADA somente se:
- todos os testes funcionais obrigatórios passarem;
- não houver falhas CRÍTICAS ou IMPORTANTES;
- as faixas acima forem atendidas;
- a IA e o desempenho forem validados;
- Liga e Copa estiverem corretas;
- o determinismo for comprovado;
- a interface funcionar de ponta a ponta;
- as 11 Skills e a documentação estiverem atualizadas.

Funcionalidade bloqueada por insumo externo (fórmulas do leilão, critérios de desempate) impede a
aprovação.
