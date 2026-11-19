---
name: game-design-rules
description: Guardião das regras aprovadas do Game Design v5.2 do SquadForce. Use antes de implementar, alterar ou revisar qualquer regra de jogo (clubes, posições, orçamento, leilão, negociações, partidas, Liga, Copa, sessão, importações) e sempre que uma regra parecer ausente, ambígua ou conflitante.
---

# game-design-rules

## Finalidade
Garantir que todo código e toda Skill do SquadForce respeitem **exatamente** as decisões aprovadas no
Game Design v5.2 e que lacunas sejam registradas — nunca inventadas. As demais 10 Skills se subordinam a esta.

## Quando utilizar
- Antes de iniciar qualquer módulo ou entrega.
- Ao encontrar um número, limite, fórmula ou comportamento de jogo no código ou num pedido.
- Quando duas fontes divergirem, ou quando a regra necessária não estiver escrita.

## Responsabilidades
1. Localizar a seção do GDD que rege o assunto e citá-la (ex.: "GDD §5").
2. Distinguir **regra aprovada**, **pendência** e **decisão técnica provisória**.
3. Manter `docs/game-design/pendencias.md` atualizado.

## Regras do Game Design aplicáveis (resumo-índice; o texto oficial prevalece)
| Tema | Seção | Pontos-chave |
|---|---|---|
| Ciclo do jogo | §1 | configurar → leilão → complementação → mercado → escalação → Liga/Copa → estatísticas → campeão |
| Clubes | §2 | 40 clubes (20 A + 20 B); clube do usuário obrigatório e sem duplicação; Liga 2–20; Copa 2/4/8/16/32; rankings internos ocultos; escudo por ID, senão iniciais |
| Posições | §3 | GOL=GK, LD=DR, LE=DL, ZAG=DC, VOL=DM, ME=MC, ATA=STC; penalidade posicional máx. 35% |
| Economia | §4 | R$ 120 mi por clube; referência máx. R$ 50 mi; lance mínimo até R$ 30 mi; overall mediano 70 |
| Leilão | §5–7 | rodadas de 10 s, 5 jogadores da mesma posição, ofertas fechadas, 18 jogadores, R$ 500 mil por vaga restante |
| Mercado | §8 | 3 min, trocas 1×1, ≤3 negociações por clube, proposta de 10 s, atomicidade |
| Partidas | §9–16 | eventos encadeados, 5 posturas, xG contextual, lesões 0–3 jogos, ≤5 substituições, notas 0–10, determinismo por semente |
| Liga/Copa | §17–19 | todos-contra-todos, folga em número ímpar; Copa jogo único + pênaltis; rodadas paralelas isoladas |
| Sessão | §23 | uma competição ativa; sem salvamento/backup/restauração; reconexão enquanto o estado existir em memória |
| Importações | §24 | validar, substituir só a base correspondente, transação, preservar em erro, bloquear com competição ativa |
| Arquitetura | §25 | serviços especializados, idempotência, relógios autoritativos, SQLite só para bases importadas |

## Contratos e dependências
- Fonte oficial: `Dados/GAME DESIGN DOCUMENT — VERSÃO 5.2.docx` (transcrito em `docs/game-design/game-design-v5.2.md`).
- Especificação técnica: `docs/architecture/especificacao-tecnica-v5.2.md`.
- Regras puras já codificadas: `shared/python/squadforce_shared/domain/` (posições, formatos de competição).

## Procedimentos recomendados
1. Ler a seção do GDD correspondente antes de escrever código.
2. Se a regra existe: implementá-la literalmente e citar a seção em docstring/teste.
3. Se não existe ou é ambígua: **parar**, registrar em `pendencias.md` (ID, tipo P/D, impacto) e perguntar ao usuário.
4. Toda decisão técnica provisória deve ser marcada como **D** e listada no relatório da entrega.

## Restrições e comportamentos proibidos
- Inventar fórmulas, pesos, limites, listas de formações, critérios de desempate ou divisões de clubes.
- Alterar uma regra aprovada para facilitar implementação ou fazer testes passarem.
- Inferir a divisão Série A/B a partir de `club_reputation`: a fonte é `club_divisions` (temporada 2026, PD-01).
- Expor informações declaradas ocultas (overall, atributos no leilão, reputação, personalidade dos bots).
- Persistir progresso de competição.
- Apresentar parâmetros provisórios (`services/match_engine/params.py`, `AuctionModel`) como calibrados ou aprovados.

## Critérios de teste
- Testes citam a regra do GDD que verificam (nome ou comentário).
- Valores do GDD aparecem como constantes nomeadas em um único lugar, e há teste que as compara ao GDD
  (ex.: `test_table_is_exactly_the_official_one`, `test_options_contract_matches_game_design`).

## Estado na homologação (Entrega 9)
Homologação: regras do GDD conferidas por testes; nenhuma regra alterada para aprovar. Bloqueios externos: fórmulas do leilão (`AuctionModel`) e critérios de desempate (PC-01). Novas decisões a confirmar: PH-01 a PH-03 em `pendencias.md`.

## Referências
- [Game Design v5.2](../../../docs/game-design/game-design-v5.2.md)
- [Pendências](../../../docs/game-design/pendencias.md)
- [Especificação técnica](../../../docs/architecture/especificacao-tecnica-v5.2.md)
- [Identidade visual](../../../docs/game-design/identidade-visual.md)
