---
name: bot-intelligence
description: Decisões dos clubes controlados por IA no SquadForce — personalidades ocultas, lances no leilão, avaliação de trocas, escolha de formação e posturas táticas durante as partidas, usando apenas informação pública. Use somente quando a entrega da IA estiver autorizada ou ao revisar contratos relacionados.
---

# bot-intelligence

## Finalidade
Orientar o serviço `services/bot_ai`. **Leilão implementado** (Entrega 3): `evaluation.py` (escalação ótima por
formação via algoritmo húngaro; ganho 0,8/0,2) e `auction_bot.py` (decisão de lance). Parâmetros das
personalidades pendentes (PB-01, via `AuctionModel.bot_profile`). **Mercado implementado** (Entrega 4):
`trade_bot.py` (`evaluate_offer` com proteção contra exploração; `choose_proposal`), parâmetros PB-02 pendentes.
Partidas: entrega futura.

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
1. Construir a visão pública explicitamente (whitelist de campos) e passá-la ao bot.
2. Toda aleatoriedade via RNG semeado recebido.
3. Parâmetros de personalidade em um único módulo, nunca expostos pela API.

## Restrições e comportamentos proibidos
Ler ofertas adversárias, estado futuro, outros jogos simultâneos ou dados privados; expor personalidade; inventar pesos não aprovados.

## Critérios de teste
Teste de "vazamento" (visão pública não contém campos privados); determinismo por semente; coerência por personalidade em simulações em lote.

## Referências
- [Game Design §6, §8, §15](../../../docs/game-design/game-design-v5.2.md)
- [README do serviço](../../../services/bot_ai/README.md)
