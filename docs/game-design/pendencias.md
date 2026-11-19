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
| PC-01 | P | **Critérios de desempate da classificação** da Liga — o responsável enviará (2026-11-18). Entrega 7: NENHUM critério aplicado; clubes com mesmos pontos compartilham a posição (`tied_with`) e empate no topo deixa o campeão indefinido (`tied_champions`). Critérios configuráveis já suportados (`services/competition/standings.py`). | Aguardando |
| PC-09 | D | **Pontuação da Liga** 3/1/0 (vitória/empate/derrota): o GDD não define a escala. Provisória e configurável (`PointsSystem`). | Confirmar |
| PC-10 | D | **Escalação e postura do usuário** antes da interface de partida: escolhidas automaticamente pelo mesmo algoritmo dos bots (postura inicial equilibrada, sem controlador automático). O núcleo aceita decisões de postura do usuário (`set_user_decisions`), ainda não expostas na API. | Provisória |
| PC-11 | D | **Formações usadas na execução**: lista de amostra do motor (4-3-3, 4-4-2, 5-3-2) até a lista oficial (PM-01). | Provisória |
| PC-02 | **C** | **Clubes elegíveis** = os 40 clubes importados que têm divisão (A ou B). A Copa sorteia entre todos eles; a Liga prioriza a Série A. Não há divergência de quantidade nas fontes: GDD §2 = 40 clubes (20 + 20) = planilha = listas 2026. | Resolvida |
| PC-03 | P | Efeito (se houver) do **mando de campo** no motor. | Aberta |
| PC-04 | **C** 2026-11-18 | **Escolha dentro da mesma série na Liga.** O GDD manda priorizar a Série A, mas não diz *quais* clubes da Série A entram quando há mais clubes do que vagas (ex.: Liga de 10). Implementado: **sorteio** entre os clubes da série (seleção automática dos clubes-bot), com semente automática da sessão. | Resolvida |
| PC-05 | **C** 2026-11-18 | **Mando na Copa = neutro** (`CupRules.neutral_venue = true`); confrontos usam `club_a`/`club_b`. | Resolvida |
| PC-06 | D | **Ordem do calendário da Liga.** Posição de cada clube no calendário sorteada; algoritmo do círculo (Berger). Turno: diferença casa/fora ≤ 1 e no máximo 2 jogos seguidos com o mesmo mando. Returno: espelho do turno com mandos invertidos (cada confronto uma vez em cada mando; até 3 jogos seguidos com o mesmo mando na virada). | Confirmar |
| PC-07 | D | **Momento do sorteio.** Participantes, calendário e chaveamento são gerados na criação da sessão (fase *setup*), antes do leilão, com semente automática não exposta (GDD §16). | Confirmar |
| PC-08 | D | **Nomes das fases da Copa:** Dezesseis-avos, Oitavas, Quartas, Semifinal e Final. | Informativo |

## Economia e leilão

> **Bloqueio da Entrega 3:** por decisão do responsável (2026-11-18) as fórmulas abaixo NÃO foram inventadas.
> O leilão está implementado, mas só roda com um `AuctionModel` aprovado — ver [leilão](../architecture/leilao.md).

| ID | Tipo | Tema |
|---|---|---|
| PE-01 | P | Fórmula do **overall calibrado** (mediana-alvo 70, >90 raro) e ponderações por posição. |
| PE-02 | P | Fórmulas de **valor de mercado** (overall calibrado + idade) e de **lance mínimo** (até R$ 30 mi). |
| PE-03 | P | Regra detalhada da **penalidade posicional** ("até 35% conforme a regra já definida"). |
| PE-04 | P | Tamanho e composição exatos das **reservas básica e complementar**. |
| PE-05 | P | Pesos do **sorteio ponderado** de posições do leilão. |
| PB-01 | P | **Parâmetros das personalidades** dos bots (Agressivo, Conservador, Equilibrado, Oportunista): tolerância a preço, agressividade do lance, ganho mínimo, sensibilidade a preço, gasto por vaga, urgência, tempos de decisão (ver `BotProfile`). |
| PE-06 | D | **Resultado público da rodada** mostra comprador e preço pago; lances perdedores continuam sigilosos. |
| PE-07 | D | Lances em múltiplos de R$ 100 mil para os bots (menor botão rápido); o usuário pode digitar qualquer valor inteiro. |
| PE-08 | D | **Complementação do clube do usuário** é automática (GDD §1/§7), com a mesma avaliação usada pelos bots; melhoria só é escolhida se aumentar a qualidade do elenco. |
| PE-09 | D | Percentil 85 calculado pelo método do posto mais próximo (*nearest-rank*) sobre o overall calibrado de toda a base. |
| PE-10 | D | Ao fim do leilão sem rodadas possíveis (nenhuma posição com 5 elegíveis), encerra com `no_eligible_players` e segue para a complementação. |

## Mercado de negociações (Entrega 4)

| ID | Tipo | Tema |
|---|---|---|
| PB-02 | P | **Parâmetros de negociação das personalidades** (`TradeProfile`): perda esportiva tolerada, R$ exigidos por ponto de qualidade, tolerância de valor, ganho mínimo para propor, fração do saldo oferecível, intervalos de proposta e de resposta. |
| TR-01 | D | "Uma proposta ativa por clube" = **uma pendente como proponente**; um clube pode **receber** várias (o GDD fala em "propostas recebidas" no plural). |
| TR-02 | D | Propostas entre bots não aparecem para o usuário; somente as trocas **concluídas** são públicas (histórico). |
| TR-03 | D | Pendentes que ficam impossíveis após outra troca (jogador já trocado ou limite de 3) são **invalidadas** na hora. |
| TR-04 | D | Ao fim dos 3 minutos, a sessão passa para a fase `competition`. Não há encerramento antecipado pelo usuário: o GDD diz "sem pausa" e não prevê esse encerramento. |
| TR-05 | D | Jogador trocado mantém o preço de contratação original (`source = "trade"`) no elenco. |

## Partidas e bots

| ID | Tipo | Tema |
|---|---|---|
| PM-01 | P | Lista oficial de **formações**. |
| PM-02 | P | **Referências estatísticas oficiais e calibração** do motor. Todos os números de `services/match_engine/params.py` são provisórios; lotes exploratórios em `docs/architecture/motor-calibracao-exploratoria.md` (dentro de faixas PRELIMINARES não aprovadas; grandes chances observadas ≈ 0,5 por time, possivelmente baixas). |
| PM-03 | P | Métrica de "**impacto das ações decisivas**" (desempate do Craque da Partida). |
| PG-01 | P | **Requisitos de desempenho** (GDD §26) não quantificados. (Observado: ~45 ms por partida instantânea.) |
| PB-03 | P | **Parâmetros da IA tática** (`services/bot_ai/tactics_params.py`): ganho mínimo, histerese, estabilidade, intervalos, aversão à perda por personalidade, custos de desgaste, pesos de escalação/formação. Os multiplicadores das posturas foram MEDIDOS no motor (e suavizados). |
| PB-04 | D | **Valores dos resultados por situação** (Liga 3/1/0; precisa vencer 3/0,4/0; evitar derrota 3/2,4/−1; Copa 1/0,5/0) e regra `league_situation` (poucas rodadas, distância do líder ou da zona de perigo). A Entrega 7 fornecerá a classificação. |
| PB-05 | P | **Formação de referência escolhida antes do leilão** pelos bots: o GDD prevê, mas não define como é escolhida (entrada de `choose_lineup`). |
| MD-01 | P | **Duração da suspensão por vermelho** (provisório: 1 jogo na mesma competição) e **suspensão por acúmulo de amarelos** (desligada até definição). |
| MD-02 | D | Lesão de **0 jogos** retira o atleta da partida atual, sem afastamento nas seguintes. |
| MD-03 | D | Craque da Partida: após nota exibida, precisão interna e impacto decisivo, o último desempate é o menor ID. |
| MD-04 | D | Pesos das composições de atributos por ação (iguais dentro de cada composição) e efeitos das posturas: provisórios. |
| MD-05 | D | Emergenciais com atributos 30 (goleiro emergencial com atributos de goleiro; os demais com 5 nesses atributos). |
| MD-06 | D | Atleta com amarelo reduz o risco de faltas e de novo cartão (`booked_caution`), para evitar expulsões irreais por acúmulo dentro do jogo. |

## Interface (Entrega 8)

| ID | Tipo | Pendência | Estado |
|---|---|---|---|
| PI-01 | P | **Tipografia**: o manual de identidade visual não define fontes. Usada a fonte do sistema. | Aguardando |
| PI-02 | D | **Limiares dos indicadores de adequação** (familiaridade ≥ 90 Natural, ≥ 70 Boa, ≥ 40 Regular, abaixo Improvisado): apresentação provisória; o motor usa o valor contínuo (`positional_factor`). | Confirmar |
| PI-03 | D | **Partida ao vivo sem pausa**: o GDD não prevê pausa; o relógio da apresentação é do servidor e segue mesmo desconectado (coerente com §23). Velocidade pode ser trocada durante o jogo. | Confirmar |
| PI-04 | D | **Condição física exibida só do próprio time** (a do adversário não é informação pública). | Confirmar |
| PI-05 | I | **Ícone do app**: o manual pede revisão em tamanho pequeno antes da publicação (arquivo raster). | Aberta |
| PI-06 | I | `SQUADFORCE_CLOCK_SCALE` e o modelo falso do leilão existem SOMENTE para testes/demonstração. | Informativo |
