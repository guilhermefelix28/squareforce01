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
| PD-07 | P | **Mesma pessoa duas vezes na planilha:** *Larson Torna Ferreira dos Santos* (linha 864 sem ID, Goiás; linha 1221 ID 2000351881, Palmeiras) e *Samuel Félix Rodrigues* (linhas 1139 ID 2000516902 e 1146 sem ID, **ambas no Náutico**). Com os IDs gerados, cada um vira dois atletas no catálogo. Antes do leilão: corrigir a planilha ou definir regra. | Aberta |
| PD-08 | D | Clube importado **sem divisão** não é elegível para competições (aviso `CLUB_WITHOUT_DIVISION` na importação). | Confirmar |

## Competições (Entrega 2)

| ID | Tipo | Tema | Situação |
|---|---|---|---|
| PC-01 | P | **Critérios de desempate da classificação** da Liga (pontos, saldo, gols…) — não definidos. Necessário na entrega de execução das rodadas. | Aberta |
| PC-02 | **C** | **Clubes elegíveis** = os 40 clubes importados que têm divisão (A ou B). A Copa sorteia entre todos eles; a Liga prioriza a Série A. Não há divergência de quantidade nas fontes: GDD §2 = 40 clubes (20 + 20) = planilha = listas 2026. | Resolvida |
| PC-03 | P | Efeito (se houver) do **mando de campo** no motor. | Aberta |
| PC-04 | D | **Escolha dentro da mesma série na Liga.** O GDD manda priorizar a Série A, mas não diz *quais* clubes da Série A entram quando há mais clubes do que vagas (ex.: Liga de 10). Implementado: **sorteio** entre os clubes da série, com semente automática da sessão. | Confirmar |
| PC-05 | D | **Mando na Copa.** O GDD não define mandante em jogo único; o chaveamento usa `club_a`/`club_b` sem mando. | Confirmar |
| PC-06 | D | **Ordem do calendário da Liga.** Posição de cada clube no calendário sorteada; algoritmo do círculo (Berger). Turno: diferença casa/fora ≤ 1 e no máximo 2 jogos seguidos com o mesmo mando. Returno: espelho do turno com mandos invertidos (cada confronto uma vez em cada mando; até 3 jogos seguidos com o mesmo mando na virada). | Confirmar |
| PC-07 | D | **Momento do sorteio.** Participantes, calendário e chaveamento são gerados na criação da sessão (fase *setup*), antes do leilão, com semente automática não exposta (GDD §16). | Confirmar |
| PC-08 | D | **Nomes das fases da Copa:** Dezesseis-avos, Oitavas, Quartas, Semifinal e Final. | Informativo |

## Economia e leilão

| ID | Tipo | Tema |
|---|---|---|
| PE-01 | P | Fórmula do **overall calibrado** (mediana-alvo 70, >90 raro) e ponderações por posição. |
| PE-02 | P | Fórmulas de **valor de mercado** (overall calibrado + idade) e de **lance mínimo** (até R$ 30 mi). |
| PE-03 | P | Regra detalhada da **penalidade posicional** ("até 35% conforme a regra já definida"). |
| PE-04 | P | Tamanho e composição exatos das **reservas básica e complementar**. |
| PE-05 | P | Pesos do **sorteio ponderado** de posições do leilão. |

## Partidas e bots

| ID | Tipo | Tema |
|---|---|---|
| PM-01 | P | Lista oficial de **formações**. |
| PM-02 | P | Parâmetros do motor e **referências estatísticas** para calibração. |
| PM-03 | P | Métrica de "**impacto das ações decisivas**" (desempate do Craque da Partida). |
| PG-01 | P | **Requisitos de desempenho** (GDD §26) não quantificados. |
