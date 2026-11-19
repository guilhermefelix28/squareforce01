---
name: bot-intelligence
description: Decisões dos clubes controlados por IA no SquadForce — personalidades ocultas, lances no leilão, avaliação de trocas, escolha de formação e posturas táticas durante as partidas, usando apenas informação pública. Use somente quando a entrega da IA estiver autorizada ou ao revisar contratos relacionados.
---

# bot-intelligence

## Finalidade
Orientar o serviço `services/bot_ai`. **Leilão implementado** (Entrega 3): `evaluation.py` (escalação ótima por
formação via algoritmo húngaro; ganho 0,8/0,2) e `auction_bot.py` (decisão de lance com concorrência estimada por
informação pública e escolha mista do alvo, PB-06 provisório). Perfis aprovados (PB-01, `AuctionModel.bot_profile`).
**Mercado implementado** (Entrega 4): `trade_bot.py` (`evaluate_offer` com proteção contra exploração;
`choose_proposal`), perfis aprovados (PB-02).
**Tática implementada** (Entrega 6): `tactics.py` (`choose_lineup`, `TacticalBot`, `CompetitionSituation`,
`PreMatchContext`), parâmetros provisórios em `tactics_params.py` (PB-03). Ver `docs/architecture/ia-tatica.md`.

## Quando utilizar
Implementação/revisão de qualquer decisão automática de bot (leilão, mercado, escalação, postura).

## Responsabilidades
Produzir **decisões** (lance, proposta, aceite, formação, postura); quem valida e aplica é o serviço dono do estado.

## Regras do Game Design aplicáveis
- §6: quatro personalidades **ocultas** — Agressivo, Conservador, Equilibrado, Oportunista; mesma capacidade de avaliação, diferindo em risco e estratégia.
- Ganho esportivo marginal = **80%** variação dos 11 titulares + **20%** variação dos 7 reservas; preço, saldo, necessidades e oportunidades considerados separadamente.
- Otimizar elenco como conjunto (formações, familiaridade); limites dinâmicos; preservar recursos; urgência gradual sem desespero artificial; **não consultar ofertas secretas**.
- §8: podem aceitar pequenas perdas esportivas com justificativa financeira/estratégica.
- §15: adaptar formação antes do jogo (referência: formação escolhida antes do leilão); formação fixa durante o jogo; posturas por placar, tempo, força, estatísticas, físico, inferioridade numérica, classificação/risco; modelo probabilístico leve; reavaliações periódicas e por eventos, com intervalo de estabilidade; **sem acesso a eventos futuros nem a outros jogos da rodada**.

## Contratos e dependências
Entrada: `BotAuctionView` (somente informação pública + próprio lance). Saída: `BidIntent` ou None. O motor
valida e aplica; decisão inválida é descartada mantendo o lance anterior. Determinismo: RNG e relógio do motor.

## Procedimentos recomendados
1. Construir a visão pública explicitamente (whitelist de campos) e passá-la ao bot (`BotAuctionView`,
   `TacticalObservation`, `PreMatchContext`).
2. Decisões táticas determinísticas e SEM o RNG do motor; uma instância de `TacticalBot` por partida.
3. Parâmetros em um único módulo, nunca expostos pela API; multiplicadores de postura MEDIDOS no motor
   (medir de novo se `MatchParams` mudar).
4. Antes de alterar a IA: rodar `scripts/tactics_report.py` e `tests/simulation/test_tactics_batches.py`.

## Restrições e comportamentos proibidos
Ler ofertas adversárias, estado futuro, outros jogos simultâneos, decisões futuras do usuário, atributos do adversário
ou o RNG/semente do motor; expor personalidade; dar bônus de atributos; inventar pesos sem registrá-los como provisórios.

## Critérios de teste
Teste de "vazamento" (visão pública não contém campos privados); determinismo por semente; coerência por personalidade em simulações em lote.

## Estado na homologação (Entrega 9)
Homologação: no lote amplo (10.000 partidas com IA nos dois lados) 0 partidas inválidas, 1,17 mudança de postura por time (máx. 7), sem vantagem artificial. Multiplicadores de postura re-medidos com o motor `provisorio-0.6`: diferenças ≤ 4% (mantidos).

## Referências
- [Game Design §6, §8, §15](../../../docs/game-design/game-design-v5.2.md)
- [README do serviço](../../../services/bot_ai/README.md)
- [IA tática](../../../docs/architecture/ia-tatica.md) · [lotes de comportamento](../../../docs/architecture/ia-tatica-lotes.md)
