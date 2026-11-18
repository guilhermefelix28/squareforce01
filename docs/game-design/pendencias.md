# Pendências e lacunas do Game Design v5.2

Registro de regras **não definidas** nas fontes oficiais (`Dados/GAME DESIGN DOCUMENT — VERSÃO 5.2.docx`
e `Dados/ESPECIFICAÇÃO TÉCNICA DE IMPLEMENTAÇÃO.docx`) e de **decisões técnicas** tomadas na Entrega 1
que aguardam confirmação do responsável pelo projeto.

> Regra: nenhuma Skill ou implementação pode preencher estas lacunas por conta própria.
> Ao encontrar uma, registre aqui e peça decisão. Ver [game-design-rules](../../.claude/skills/game-design-rules/SKILL.md).

Legenda: **P** = regra pendente (bloqueia a entrega que depende dela) · **D** = decisão técnica provisória da Entrega 1 (confirmar).

## Dados e catálogo

| ID | Tipo | Tema | Situação | Afeta |
|---|---|---|---|---|
| PD-01 | P | **Divisão dos clubes (Série A / Série B).** O GDD (seção 2) prioriza a Série A na seleção da Liga, mas a planilha não tem coluna de divisão. `club_reputation` existe, mas usá-la como divisão seria invenção. | Fornecer coluna/lista oficial. | Entrega de competições |
| PD-02 | D | **Não há planilha de clubes separada.** A base de clubes é extraída das colunas `club_*` de `jogadores.xlsx` (dados repetidos por linha; divergências para o mesmo `club_uid` são críticas). Uma planilha dedicada com as mesmas colunas também é aceita. | Confirmar ou fornecer `clubes.xlsx`. | Importação |
| PD-03 | D | **11 linhas sem `unique_id`** na planilha real (linhas 227, 458, 754, 864, 912, 918, 1113, 1146, 1268, 1310, 1311). São descartadas com aviso, pois não têm identificador estável; 2 delas (Larson, Samuel) repetem atletas que aparecem com ID em outro clube. Demais erros por linha são críticos. | Confirmar política ou corrigir a planilha. | Importação |
| PD-04 | D | **Limites de integridade** usados na validação (idade 10–60, altura 100–250 cm, atributos/familiaridade 1–100) foram observados na base real; não são regras de jogo. | Confirmar. | Importação |
| PD-05 | D | **Exposição de dados no catálogo.** A API pública não expõe `club_reputation`, atributos nem familiaridades (GDD seções 2 e 5: rankings e overall ocultos). | Confirmar o que a área de dados pode mostrar. | Catálogo/UI |
| PD-06 | — | **Imagens:** 23/40 escudos (`Graphics/Clubes/club_{id}.png`) e 1294/1574 fotos (`Graphics/Faces/{id}.png/jpg`) encontrados; os demais usam o ícone padrão (iniciais). Os `config.xml` (mapeamentos do FM) não são interpretados. | Informativo. | UI |

## Economia e leilão

| ID | Tipo | Tema |
|---|---|---|
| PE-01 | P | Fórmula do **overall calibrado** (mediana-alvo 70, >90 raro) e ponderações por posição. |
| PE-02 | P | Fórmulas de **valor de mercado** (overall calibrado + idade) e de **lance mínimo** (até R$ 30 mi). O GDD declara que dependem de calibração. |
| PE-03 | P | Regra detalhada da **penalidade posicional** ("até 35% conforme a regra já definida" — a regra não consta nos documentos). |
| PE-04 | P | Tamanho e composição exatos das **reservas básica e complementar** de atletas. |
| PE-05 | P | Pesos do **sorteio ponderado** de posições do leilão (necessidades, disponibilidade, histórico, aleatoriedade). |

## Partidas, bots e competições

| ID | Tipo | Tema |
|---|---|---|
| PM-01 | P | Lista oficial de **formações** disponíveis. |
| PM-02 | P | Parâmetros do motor (xG, grandes chances, faltas, lesões) e **referências estatísticas** para calibração. |
| PM-03 | P | Métrica de "**impacto das ações decisivas**" (2º desempate do Craque da Partida). |
| PC-01 | P | **Critérios de desempate da classificação** da Liga (pontos, saldo, gols…) — não definidos. |
| PC-02 | P | Critério de **"clubes elegíveis"** no sorteio da Copa. |
| PC-03 | P | Efeito (se houver) do **mando de campo** no motor. |
| PG-01 | P | **Requisitos de desempenho** citados nos critérios de aceitação (GDD seção 26) não estão quantificados. |
