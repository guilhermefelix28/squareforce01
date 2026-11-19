# Pendências e lacunas do Game Design v5.2

Registro de regras **não definidas** nas fontes oficiais (`Dados/GAME DESIGN DOCUMENT — VERSÃO 5.2.docx`
e `Dados/ESPECIFICAÇÃO TÉCNICA DE IMPLEMENTAÇÃO.docx`) e de **decisões técnicas** que aguardam ou já
receberam confirmação do responsável pelo projeto.

> Regra: nenhuma Skill ou implementação pode preencher estas lacunas por conta própria.
> Ao encontrar uma, registre aqui e peça decisão. Ver [game-design-rules](../../.claude/skills/game-design-rules/SKILL.md).

Legenda: **P** = regra pendente · **D** = decisão técnica provisória (confirmar) · **C** = confirmada pelo responsável (data).

## Dados e catálogo

| ID | Tipo | Tema | Situação |
|---|---|---|---|
| PD-01 | **C** 2026-11-18 | **Divisão dos clubes.** A planilha não tem divisão; o responsável autorizou usar as listas públicas da temporada **2026** (20 da Série A e 20 da Série B), que correspondem exatamente aos 40 clubes de `jogadores.xlsx`. Gravadas na tabela de referência `club_divisions` (migração 0002) com as fontes. | Resolvida |
| PD-02 | **C** 2026-11-18 | **Base de clubes extraída de `jogadores.xlsx`** (colunas `club_*`). Planilha dedicada com as mesmas colunas continua aceita. | Resolvida |
| PD-03 | **C** 2026-11-18 | **Linhas sem `unique_id` recebem ID genérico estável** (hash de nome completo + nascimento + clube + nome, faixa ≥ 9.000.000.000, `players.id_generated = 1`). Na base real: 11 IDs gerados. Duas pessoas (Larson, Samuel) aparecem em dois clubes; ambas as linhas são importadas com aviso `POSSIBLE_DUPLICATE_PERSON`. | Resolvida (ver PD-07) |
| PD-04 | D | Limites de integridade (idade 10–60, altura 100–250 cm, atributos/familiaridade 1–100), observados na base real; não são regras de jogo. | Confirmar |
| PD-05 | **C** 2026-11-18 | A API pública **não** expõe `club_reputation`, atributos nem familiaridades. | Resolvida |
| PD-06 | — | Imagens: 23/40 escudos e 1294 fotos encontrados; o restante usa ícone padrão (iniciais). | Informativo |
| PD-07 | **C** 2026-11-18 | **Mesma pessoa duas vezes na planilha** — *mantém somente um registro* (prefere o ID real; depois, a primeira linha; aviso `DUPLICATE_PERSON_REMOVED`). Casos: *Larson Torna Ferreira dos Santos* (linha 864 sem ID, Goiás; linha 1221 ID 2000351881, Palmeiras) e *Samuel Félix Rodrigues* (linhas 1139 ID 2000516902 e 1146 sem ID, **ambas no Náutico**). Resultado: 1583 jogadores; Larson fica no Palmeiras (ID real) e Samuel com o ID real. | Resolvida |
| PD-08 | D | Clube importado **sem divisão** não é elegível para competições (aviso `CLUB_WITHOUT_DIVISION` na importação). | Confirmar |

## Competições (Entrega 2)

| ID | Tipo | Tema | Situação |
|---|---|---|---|
| PC-01 | **C** 2026-11-19 | **Critérios de desempate da Liga = padrão Brasileirão**: vitórias → saldo de gols → gols pró → confronto direto → menos cartões vermelhos → menos cartões amarelos → sorteio. Aplicados em cascata (cada critério só separa quem segue empatado). Interpretação: confronto direto = pontos nos jogos entre os dois, **somente quando exatamente dois clubes** seguem empatados; segundo amarelo conta como amarelo e vermelho; sorteio determinístico pela semente da competição. `BRASILEIRAO_TIEBREAKERS` em `services/competition/standings.py`. | Resolvida |
| PC-09 | **C** 2026-11-19 | **Pontuação da Liga** 3/1/0 (vitória/empate/derrota) confirmada pelo responsável. | Resolvida |
| PC-10 | D | **Escalação e postura do usuário** antes da interface de partida: escolhidas automaticamente pelo mesmo algoritmo dos bots (postura inicial equilibrada, sem controlador automático). O núcleo aceita decisões de postura do usuário (`set_user_decisions`), ainda não expostas na API. | Provisória |
| PC-11 | **C** 2026-11-19 | **Formações na execução** = as 11 oficiais (PM-01). | Resolvida |
| PC-02 | **C** | **Clubes elegíveis** = os 40 clubes importados que têm divisão (A ou B). A Copa sorteia entre todos eles; a Liga prioriza a Série A. Não há divergência de quantidade nas fontes: GDD §2 = 40 clubes (20 + 20) = planilha = listas 2026. | Resolvida |
| PC-03 | P | Efeito (se houver) do **mando de campo** no motor. | Aberta |
| PC-04 | **C** 2026-11-18 | **Escolha dentro da mesma série na Liga.** O GDD manda priorizar a Série A, mas não diz *quais* clubes da Série A entram quando há mais clubes do que vagas (ex.: Liga de 10). Implementado: **sorteio** entre os clubes da série (seleção automática dos clubes-bot), com semente automática da sessão. | Resolvida |
| PC-05 | **C** 2026-11-18 | **Mando na Copa = neutro** (`CupRules.neutral_venue = true`); confrontos usam `club_a`/`club_b`. | Resolvida |
| PC-06 | D | **Ordem do calendário da Liga.** Posição de cada clube no calendário sorteada; algoritmo do círculo (Berger). Turno: diferença casa/fora ≤ 1 e no máximo 2 jogos seguidos com o mesmo mando. Returno: espelho do turno com mandos invertidos (cada confronto uma vez em cada mando; até 3 jogos seguidos com o mesmo mando na virada). | Confirmar |
| PC-07 | D | **Momento do sorteio.** Participantes, calendário e chaveamento são gerados na criação da sessão (fase *setup*), antes do leilão, com semente automática não exposta (GDD §16). | Confirmar |
| PC-08 | D | **Nomes das fases da Copa:** Dezesseis-avos, Oitavas, Quartas, Semifinal e Final. | Informativo |

## Economia e leilão

> **Desbloqueado em 2026-11-19:** o responsável aprovou o `AuctionModel` oficial (com ajustes) —
> ver [proposta aprovada](../architecture/proposta-auction-model.md). Modelo carregado por padrão.

| ID | Tipo | Tema |
|---|---|---|
| PE-01 | **C** 2026-11-19 | **Overall calibrado**: composições de atributos do motor por posição, escala por posição (mediana 70, 8 pontos por desvio robusto), recalculado a cada base (ver `docs/architecture/proposta-auction-model.md` §1). |
| PE-02 | **C** 2026-11-19 | **Valor de mercado** = R$ 3 mi × e^(k(overall−70)) × fator de idade, k = 0,1228 acima e 0,25 abaixo da mediana (ajuste do responsável), teto R$ 50 mi; **lance mínimo** = 50% do valor (ver `docs/architecture/proposta-auction-model.md` §3). |
| PE-03 | **C** 2026-11-19 | **Penalidade posicional** linear de 0% a 35% (mesma curva do motor) (ver `docs/architecture/proposta-auction-model.md` §2). |
| PE-04 | **C** 2026-11-19 | **Reservas**: básica = vagas + 25%, menores overalls, cota por posição e ≥ 1 goleiro por clube; complementar = melhores não vendidos, 1,5 × clubes × participação da posição, destaques ≤ clubes/4 (ver `docs/architecture/proposta-auction-model.md` §4). |
| PE-05 | **C** 2026-11-19 | **Sorteio da posição**: (0,25 + participação na necessidade) × disponibilidade × recência; atletas da rodada com peso 6 acima da mediana contra 1 abaixo, pelo menos um de cada grupo (ajuste do responsável) (ver `docs/architecture/proposta-auction-model.md` §5). |
| PB-01 | **C** 2026-11-19 | **Personalidades no leilão**: perfis revisados pelo responsável (bots mais dispostos a pagar) (ver `docs/architecture/proposta-auction-model.md` §7). |
| PE-06 | D | **Resultado público da rodada** mostra comprador e preço pago; lances perdedores continuam sigilosos. |
| PE-07 | D | Lances em múltiplos de R$ 100 mil para os bots (menor botão rápido); o usuário pode digitar qualquer valor inteiro. |
| PE-08 | D | **Complementação do clube do usuário** é automática (GDD §1/§7), com a mesma avaliação usada pelos bots; melhoria só é escolhida se aumentar a qualidade do elenco. |
| PE-09 | D | Percentil 85 calculado pelo método do posto mais próximo (*nearest-rank*) sobre o overall calibrado de toda a base. |
| PE-10 | D | Ao fim do leilão sem rodadas possíveis (nenhuma posição com 5 elegíveis), encerra com `no_eligible_players` e segue para a complementação. |

## Mercado de negociações (Entrega 4)

| ID | Tipo | Tema |
|---|---|---|
| PB-02 | **C** 2026-11-19 | **Personalidades no mercado** aprovadas (ver `docs/architecture/proposta-auction-model.md` §8). |
| TR-01 | D | "Uma proposta ativa por clube" = **uma pendente como proponente**; um clube pode **receber** várias (o GDD fala em "propostas recebidas" no plural). |
| TR-02 | D | Propostas entre bots não aparecem para o usuário; somente as trocas **concluídas** são públicas (histórico). |
| TR-03 | D | Pendentes que ficam impossíveis após outra troca (jogador já trocado ou limite de 3) são **invalidadas** na hora. |
| TR-04 | D | Ao fim dos 3 minutos, a sessão passa para a fase `competition`. Não há encerramento antecipado pelo usuário: o GDD diz "sem pausa" e não prevê esse encerramento. |
| TR-05 | D | Jogador trocado mantém o preço de contratação original (`source = "trade"`) no elenco. |

## Partidas e bots

| ID | Tipo | Tema |
|---|---|---|
| PM-01 | **C** 2026-11-19 | **11 formações oficiais** escolhidas pelo responsável: 4-4-2, 4-3-3, 4-2-3-1, 3-5-2, 3-4-3, 5-3-2, 4-1-4-1, 4-5-1, 4-3-2-1, 4-3-1-2, 5-4-1 (`squadforce_shared/domain/formations.py`). |
| PM-02 | **C** 2026-11-19 | **Referências estatísticas**: o responsável aceitou como oficiais os agregados públicos usados na homologação (`docs/homologacao/criterios.md`). Parâmetros do motor `provisorio-0.6` passam a ser os calibrados contra essas referências. Métricas sem referência continuam só monitoradas (PH-03). |
| PM-03 | P | Métrica de "**impacto das ações decisivas**" (desempate do Craque da Partida). |
| PG-01 | P | **Requisitos de desempenho** (GDD §26) não quantificados. (Observado: ~45 ms por partida instantânea.) |
| PB-03 | P | **Parâmetros da IA tática** (`services/bot_ai/tactics_params.py`): ganho mínimo, histerese, estabilidade, intervalos, aversão à perda por personalidade, custos de desgaste, pesos de escalação/formação. Os multiplicadores das posturas foram MEDIDOS no motor (e suavizados). |
| PB-04 | D | **Valores dos resultados por situação** (Liga 3/1/0; precisa vencer 3/0,4/0; evitar derrota 3/2,4/−1; Copa 1/0,5/0) e regra `league_situation` (poucas rodadas, distância do líder ou da zona de perigo). A Entrega 7 fornecerá a classificação. |
| PB-05 | P | **Formação de referência escolhida antes do leilão** pelos bots: o GDD prevê, mas não define como é escolhida (entrada de `choose_lineup`). |
| MD-01 | **C** 2026-11-19 | **Suspensão**: vermelho = 1 jogo na mesma competição; **sem** suspensão por acúmulo de amarelos. Confirmado pelo responsável. |
| MD-02 | D | Lesão de **0 jogos** retira o atleta da partida atual, sem afastamento nas seguintes. |
| MD-03 | D | Craque da Partida: após nota exibida, precisão interna e impacto decisivo, o último desempate é o menor ID. |
| MD-04 | D | Pesos das composições de atributos por ação (iguais dentro de cada composição) e efeitos das posturas: provisórios. |
| MD-05 | D | Emergenciais com atributos 30 (goleiro emergencial com atributos de goleiro; os demais com 5 nesses atributos). |
| MD-06 | D | Atleta com amarelo reduz o risco de faltas e de novo cartão (`booked_caution`), para evitar expulsões irreais por acúmulo dentro do jogo. |

## Interface (Entrega 8)

| ID | Tipo | Pendência | Estado |
|---|---|---|---|
| PI-01 | P | **Tipografia**: o manual de identidade visual não define fontes. Usada a fonte do sistema. | Aguardando |
| PI-02 | **C** 2026-11-19 | **Limiares dos indicadores de adequação** (≥ 90 Natural, ≥ 70 Boa, ≥ 40 Regular, abaixo Improvisado) confirmados. | Resolvida |
| PI-03 | D | **Partida ao vivo sem pausa**: o GDD não prevê pausa; o relógio da apresentação é do servidor e segue mesmo desconectado (coerente com §23). Velocidade pode ser trocada durante o jogo. | Confirmar |
| PI-04 | D | **Condição física exibida só do próprio time** (a do adversário não é informação pública). | Confirmar |
| PI-05 | I | **Ícone do app**: o manual pede revisão em tamanho pequeno antes da publicação (arquivo raster). | Aberta |
| PI-06 | I | `SQUADFORCE_CLOCK_SCALE` e o modelo falso do leilão existem SOMENTE para testes/demonstração. | Informativo |

## Homologação (Entrega 9)

| ID | Tipo | Pendência | Estado |
|---|---|---|---|
| PH-01 | **C** 2026-11-19 | **"Posturas moderadas" = no máximo ±35%** de gols marcados/sofridos em relação à Equilibrada, confirmado (medido: −22% a +20%). | Resolvida |
| PH-02 | **C** 2026-11-19 | **Critérios de desempenho** (`docs/homologacao/criterios.md` §4) confirmados. | Resolvida |
| PH-03 | O | **Métricas sem referência confiável** (não validadas): posse por time muito concentrada (41–58%, desvio 2,3 pontos), grandes chances 1,1 por partida, escanteios 8,5, defesas 6,5, lesões 0,53, notas média 6,18 (DP 0,70). Recomenda-se fornecer referências oficiais (PM-02) para avaliá-las. | Aberta |
| PH-04 | **C** 2026-11-19 | **Referências usadas** (agregados públicos) aceitas como oficiais (ver PM-02). | Resolvida |

## Conclusão (2026-11-19)

| ID | Tipo | Pendência | Estado |
|---|---|---|---|
| PB-06 | D | **Concorrência e escolha mista no leilão** (GDD §6, "considerar concorrência com base apenas em informações públicas"): rivais esperados por atleta pela proporção dos lances mínimos; alvo sorteado ∝ pontuação², determinístico por clube e rodada. `COMPETITION_WEIGHT` = 0,5 e `SAMPLING_POWER` = 2 são parâmetros provisórios da IA, escolhidos em lotes exploratórios. | Provisória |

## Diretrizes do responsável — experiência de jogo (2026-11-19)

O responsável determinou que suas novas diretrizes **prevalecem sobre o GDD v5.2**. Spec:
`docs/superpowers/specs/2026-11-19-experiencia-de-jogo-design.md`.

| ID | Tipo | Decisão | Estado |
|---|---|---|---|
| DR-01 | **C** 2026-11-19 | **Lance redutível** (sobrepõe GDD §5 "proibição de reduzir o lance vigente"): qualquer clube pode reduzir o próprio lance no mesmo atleta durante a rodada, respeitando lance mínimo e saldo. Repetir o mesmo valor é rejeitado (`BID_UNCHANGED`). O desempate usa o instante do valor final. Bots mantêm o comportamento. | Resolvida |
| DR-02 | **C** 2026-11-19 | **Tática do usuário antes do leilão**: o usuário escolhe uma das 11 formações oficiais na fase `setup`; ela é a formação inicial da escalação automática e orienta o painel de vagas do leilão. | Resolvida |
| DR-03 | **C** 2026-11-19 | **Goleiros cansam pouco**: desgaste do goleiro × 0,35 (`gk_fatigue_multiplier`). | Resolvida |
| DR-04 | **C** 2026-11-19 | **Área oculta de dados**: importações só com senha (padrão 9153, `SQUADFORCE_ADMIN_PASSWORD`), verificada no servidor; tela em `#/admin`, fora da navegação. | Resolvida |
| DR-05 | **C** 2026-11-19 | **Ordem de exibição das posições**: GOL · LD · ZAG · LE · VOL · ME · ATA (somente interface; a ordem interna do sorteio do leilão não muda). | Resolvida |
| DR-06 | **C** 2026-11-19 | **Partida ao vivo**: mostra os dois times em campo (sem condição física do adversário), os placares simultâneos dos outros jogos da rodada e autor/vítima do pênalti. | Resolvida |
| DR-07 | **C** 2026-11-19 | **Cancelar o lance**: o usuário pode retirar o próprio lance durante a rodada (`POST /auction/bids/cancel`); sem lance ativo, não compra ninguém na rodada e pode dar outro lance até o fim. Bots não cancelam. | Resolvida |
| DR-08 | **C** 2026-11-19 | **Formações corrigidas**: o antigo 4-4-2 (4 ME) passa a **4-2-2-2** (2 VOL + 2 ME); o 4-3-3 é renomeado **4-1-2-3** (mesmas vagas). O campinho tem faixas próprias de VOL e ME (GOL, DEF, VOL, ME, ATA); arrastar um titular para outra faixa troca a formação quando a nova composição é oficial. Composições iguais (3-5-2 = 5-3-2; 4-2-3-1 = 4-3-2-1) aparecem iguais no campo. | Resolvida |
| DR-09 | **C** 2026-11-19 | **Pênaltis cobrança a cobrança**: na partida ao vivo, cada cobrança da disputa é revelada em sequência (450 s de jogo por cobrança: ~2,5 s reais a 30 s), com batedor, goleiro e placar parcial; no instantâneo, tudo de uma vez. Só muda a apresentação: o resultado é o mesmo. | Resolvida |
| DR-10 | **C** 2026-11-19 | **Apresentação**: cores dos uniformes no campinho ao vivo extraídas do escudo do clube (a base não tem cores): mandante com a primária, visitante com a primária ou, se parecida, a secundária. Silhueta genérica única para atletas sem foto. Som de gol: arquivo fornecido pelo responsável (`frontend/public/sounds/goal-crowd.mp4`), tocado a partir de 3,5 s por 3 s com fade. Logo sem fundo do responsável. | Resolvida |
