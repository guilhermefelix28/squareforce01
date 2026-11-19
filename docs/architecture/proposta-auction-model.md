# Proposta do `AuctionModel` (PE-01 a PE-05, PM-01, PB-01, PB-02)

**Situação: APROVADA pelo responsável em 2026-11-19, com ajustes:** atletas abaixo da mediana bem mais baratos (§3),
maior chance de atletas acima da mediana nas rodadas (§5) e 11 formações (§6). O
modelo é implementado em `services/auction/official_model.py`, a pendência correspondente passa a **C** em
`pendencias.md` e a homologação do leilão é refeita com critérios fixados **antes** das medições.

Fonte de cada regra fixa: GDD v5.2 §3, §4, §5, §6, §7 e §8. Os números de exemplo foram medidos na base real
importada (1.583 atletas, 40 clubes), com script de análise de leitura apenas.

## 1. Overall calibrado (PE-01)

GDD: mediana-alvo 70; acima de 90 relativamente raro; base em ponderações por posição; o overall **não** é usado
para o rendimento em partida (o motor continua usando os atributos por ação).

1. **Índice bruto por posição** = média ponderada das mesmas composições de atributos que o motor usa nas ações
   (`services/match_engine/params.py::SKILLS`). Assim, o leilão valoriza o que de fato rende em campo.

   | Posição | Composição (peso) |
   |---|---|
   | GOL | goleiro 0,85 · construção 0,15 |
   | LD / LE | defesa de área 0,45 · pressão 0,20 · progressão 0,20 · movimentação ofensiva 0,15 |
   | ZAG | defesa de área 0,70 · jogo aéreo 0,20 · construção 0,10 |
   | VOL | defesa de meio 0,50 · construção 0,30 · pressão 0,20 |
   | ME | progressão 0,40 · criação 0,30 · construção 0,20 · pressão 0,10 |
   | ATA | finalização 0,45 · movimentação ofensiva 0,25 · jogo aéreo 0,15 · criação 0,15 |

2. **Calibração por posição principal**, para comparar posições na mesma escala:
   `overall = limite(30, 99, 70 + 8 × (bruto − mediana_posição) / σ_posição)`, com σ = intervalo interquartil / 1,349
   (robusto a valores extremos). A mediana e o σ de cada posição são recalculados sempre que a base for substituída.

**Resultado na base real:**
- mediana 70,0; percentil 85 = 76,1 (limite de **destaque**); percentil 95 = 79,6;
- **5 atletas acima de 90** (0,3%) e 17 acima de 85;
- maiores overalls: Neymar 96,1, Matheus Pereira 93,0, Arrascaeta 92,7, Pedro 90,7 e Kaio Jorge 90,5;
- média dos 14 melhores por clube: Flamengo 82,4, Cruzeiro 81,8 e Palmeiras 81,2; Londrina 70,2 e Ponte Preta 69,4.

## 2. Qualidade na posição e penalidade posicional (PE-03)

`qualidade(atleta, posição) = overall_na_escala_da_posição(bruto da posição) × (1 − 0,35 × (100 − familiaridade) / 99)`

- A penalidade é **linear**, de 0% (familiaridade 100) a **35%** (familiaridade 1). É a mesma curva que o motor já
  usa, então leilão, bots e partida avaliam a adequação da mesma forma.
- Um atacante avaliado como zagueiro usa a composição de zagueiro, que já é naturalmente baixa, **e** sofre a
  penalidade. O motor faz o mesmo nas ações.

## 3. Valor de mercado e lance mínimo (PE-02)

GDD: o valor depende **somente** do overall calibrado e da idade; teto de referência R$ 50 mi; lance mínimo até R$ 30 mi.

`valor = limite(R$ 100 mil, R$ 50 mi, arred_100mil(R$ 3,0 mi × e^(k × (overall − 70)) × fator_idade))`

com **k = 0,1228 a partir da mediana (overall ≥ 70)** e **k = 0,25 abaixo dela**. A curva abaixo da mediana é mais
inclinada, a pedido do responsável, para que esses atletas fiquem bem mais baratos.

| Idade | ≤ 23 | 24–29 | 30–31 | 32–33 | ≥ 34 |
|---|---|---|---|---|---|
| Fator | 1,10 | 1,00 | 0,85 | 0,70 | 0,55 |

- **Pontos da curva (24–29 anos):** overall 55 → R$ 0,1 mi; 60 → R$ 0,2 mi; 65 → R$ 0,9 mi; 68 → R$ 1,8 mi;
  70 → R$ 3,0 mi; 75 → R$ 5,5 mi; 80 → R$ 10,2 mi; 90 → R$ 35 mi; a partir de ~93 → R$ 50 mi (teto).
- **Lance mínimo** = `limite(R$ 100 mil, R$ 30 mi, arred_100mil(0,5 × valor))`.

**Resultado na base real:**
- valor: mediana R$ 2,6 mi, percentil 85 R$ 5,8 mi, percentil 95 R$ 8,8 mi; 2 atletas no teto e 11 com R$ 20 mi ou mais;
- abaixo da mediana (788 atletas): valor mediano **R$ 0,6 mi**; 359 valem até R$ 500 mil;
- lance mínimo: mediana R$ 1,3 mi, máximo R$ 25 mi;
- um titular mediano custa cerca de R$ 3 mi; com R$ 120 mi, um clube monta 11 titulares medianos por cerca de
  R$ 33 mi e escolhe onde concentrar o restante (1 ou 2 estrelas ou um elenco equilibrado acima da média).

## 4. Reservas da complementação (PE-04)

- **Preço na reserva básica** = `min(R$ 500 mil, lance mínimo)`.
- **Reserva básica:**
  - tamanho = vagas a preencher + 25% de margem;
  - escolhida entre os **não vendidos de menor overall**;
  - **distribuição protegida:** a cota de cada posição é proporcional à demanda média das formações oficiais,
    com pelo menos 1 goleiro por clube com vagas, quando houver.
  - Se uma posição não tiver atletas suficientes, a cota passa para as demais.
- **Reserva complementar:** os não vendidos fora da básica, do **maior overall para o menor**, por posição:
  - cota por posição = arred_cima(1,5 × nº de clubes × participação da posição na demanda);
  - **destaques** (≥ percentil 85): no máximo arred_cima(nº de clubes / 4) no total;
  - o limite de 1 destaque por clube continua imposto pelo motor.

## 5. Sorteio das posições (PE-05) e escolha dos 5 atletas (§5)

`peso(posição) = (0,25 + participação na necessidade coletiva) × min(1, disponíveis / 10) × recência`

- **Participação na necessidade coletiva** = necessidade da posição / soma das necessidades (1/7 quando a soma for 0).
- **Recência:** 0,4 se a posição saiu numa das 2 últimas rodadas; 0,7 se saiu da 3ª à 5ª rodada anterior; 1,0 nos demais casos.
- A aleatoriedade controlada vem do próprio sorteio ponderado.
- A regra das 14 rodadas continua garantida pelo motor.
- **Os 5 atletas da rodada (ajustado pelo responsável):**
  - excluem quem já ficou sem comprador 2 vezes, a menos que sobrem menos de 5;
  - são sorteados sem reposição, com **peso 6** para quem tem overall igual ou acima da mediana da base (70) e
    **peso 1** para quem está abaixo dela;
  - para manter a variedade de qualidade (§5), cada rodada traz **pelo menos 1 atleta de cada grupo**, quando
    houver os dois na posição;
  - com os dois grupos de tamanho parecido, a expectativa é de cerca de 4 atletas acima da mediana por rodada.

## 6. Formações oficiais (PM-01): 11, escolhidas pelo responsável

Usam somente os 7 códigos do GDD. Meias abertos e meias-atacantes são ME (MC), e alas são LD/LE. Valem para o
leilão, os bots, a escalação e o motor.

| Formação | Vagas |
|---|---|
| 4-4-2 | GOL, LD, ZAG, ZAG, LE, ME, ME, ME, ME, ATA, ATA |
| 4-3-3 | GOL, LD, ZAG, ZAG, LE, VOL, ME, ME, ATA, ATA, ATA |
| 4-2-3-1 | GOL, LD, ZAG, ZAG, LE, VOL, VOL, ME, ME, ME, ATA |
| 3-5-2 | GOL, ZAG, ZAG, ZAG, LD, LE, VOL, ME, ME, ATA, ATA |
| 3-4-3 | GOL, ZAG, ZAG, ZAG, LD, LE, VOL, ME, ATA, ATA, ATA |
| 5-3-2 | GOL, LD, ZAG, ZAG, ZAG, LE, VOL, ME, ME, ATA, ATA |
| 4-1-4-1 | GOL, LD, ZAG, ZAG, LE, VOL, ME, ME, ME, ME, ATA |
| 4-5-1 | GOL, LD, ZAG, ZAG, LE, ME, ME, ME, ME, ME, ATA |
| 4-3-2-1 | GOL, LD, ZAG, ZAG, LE, VOL, VOL, ME, ME, ME, ATA |
| 4-3-1-2 | GOL, LD, ZAG, ZAG, LE, VOL, ME, ME, ME, ATA, ATA |
| 5-4-1 | GOL, LD, ZAG, ZAG, ZAG, LE, VOL, ME, ME, ME, ATA |

Com só 7 códigos, alguns pares têm as **mesmas vagas** e diferem apenas no nome e no desenho:
3-5-2 = 5-3-2 e 4-3-2-1 = 4-2-3-1. Todos ficam disponíveis com o nome escolhido.

## 7. Personalidades dos bots no leilão (PB-01): revisadas e aprovadas em 2026-11-19

| Parâmetro (`BotProfile`) | Agressivo | Conservador | Equilibrado | Oportunista |
|---|---|---|---|---|
| Teto sobre o valor de mercado | 2,0× | 1,2× | 1,6× | 1,3× |
| Lance inicial (fração entre mínimo e teto) | 0,85 | 0,5 | 0,7 | 0,3 |
| Ganho mínimo para disputar | 0,0 | 0,5 | 0,2 | 0,1 |
| Sensibilidade a preço | 0,1 | 0,6 | 0,3 | 0,9 |
| Gasto por vaga (× média disponível) | 2,0 | 1,1 | 1,5 | 1,3 |
| Urgência no fim do relógio | +50% | +20% | +35% | +40% |
| Primeiro lance (s após abrir a rodada) | 0,5–3 | 1–5 | 0,5–4 | 2–6 |
| Reavaliação (s antes do fim da rodada) | 2,0 | 1,5 | 2,0 | 3,0 |

Escala do ganho: trocar um titular de 70 por um de 80 vale cerca de 0,73.

### Por que os perfis foram revisados (lotes exploratórios, sementes 500+, fora do lote oficial)

1. **Primeiro teste (perfis originais, 1 semente por formato):** na Liga 20 só 1,8 dos 5 atletas de cada rodada
   eram vendidos. Os bots miravam todos o mesmo alvo, e os Equilibrados terminavam com 1,3 contratação.
   - O GDD §6 manda **considerar a concorrência com base em informação pública**, e o bot recebia as vagas e
     os saldos dos rivais, mas não os usava.
   - Implementado em `services/bot_ai/auction_bot.py`: o bot estima quantos rivais com vaga e saldo devem
     disputar cada atleta e usa a chance de vencer na pontuação.
   - O alvo passou a ser escolhido de forma **mista**: sorteio proporcional a pontuação², determinístico por
     clube e rodada. Bots que pensam igual deixam de colidir.
   - Os parâmetros da IA (`COMPETITION_WEIGHT` = 0,5 e `SAMPLING_POWER` = 2) são provisórios, como os da IA
     tática. Foram escolhidos em lotes exploratórios.
   - Resultado: 3,8 vendas por rodada, e todos os bots completam o elenco no leilão.
2. **Com os perfis originais**, o gasto mediano ficou em ~41% (L3 exige 50–95%). Lance mínimo de 70% levou a
   46,5%, e uma curva menos inclinada abaixo da mediana, a 40,7%. A causa era o comportamento de lance.
   **O responsável escolheu bots mais dispostos a pagar.**
3. **Perfis revisados (12 leilões exploratórios):** L1–L6 atendidos; gasto mediano de 66%, entre 62% e 71% por formato.

## 8. Personalidades dos bots no mercado (PB-02)

Escala: 1 ponto de ganho equivale a cerca de 14 pontos de overall em um titular, ou R$ 7 a 10 mi de diferença de
valor perto da mediana.

| Parâmetro (`TradeProfile`) | Agressivo | Conservador | Equilibrado | Oportunista |
|---|---|---|---|---|
| Maior perda esportiva aceitável | 0,6 | 0,2 | 0,4 | 0,5 |
| R$ exigidos por ponto perdido | R$ 6 mi | R$ 12 mi | R$ 8 mi | R$ 7 mi |
| Tolerância de valor cedido | 20% | 5% | 10% | 5% |
| Ganho mínimo para propor | 0,3 | 0,8 | 0,5 | 0,4 |
| Fração máxima do saldo oferecida | 30% | 10% | 20% | 25% |
| Intervalo entre propostas (s) | 6–15 | 15–30 | 10–20 | 5–12 |
| Tempo de resposta (s, < 10) | 1–4 | 3–8 | 2–6 | 1–5 |

## 9. Validação após a aprovação (critérios fixados antes de medir)

Lote de leilões completos e simulados (Liga 20, Liga 10, Copa 8 e Copa 32; 50 sementes cada), com todos os clubes
como bots e o usuário passivo. Critérios:

1. 100% dos clubes terminam com 18 atletas, nenhum saldo negativo e nenhuma duplicação.
2. Todas as saídas do modelo passam pelas validações do motor, com zero `AuctionModelError`.
3. Mediana do gasto por clube no leilão entre 50% e 95% do orçamento.
4. Pelo menos 60% dos atletas oferecidos com 2 ou menos aparições sem venda.
5. As personalidades se distinguem: o gasto médio do Agressivo é maior que o do Conservador, e o preço médio pago
   em relação ao valor de mercado é menor no Oportunista.
6. Diferença de qualidade dos titulares entre o melhor e o pior bot (mediana entre sementes) de no máximo 25%
   da qualidade mediana. Isso evita elencos degenerados sem impor igualdade artificial.

Depois disso: o modelo oficial é ligado por padrão, a jornada e2e passa a rodar com o modelo real, e o
relatório de homologação é refeito.
