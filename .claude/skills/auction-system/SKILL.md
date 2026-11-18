---
name: auction-system
description: Implementar e revisar o leilão de jogadores do SquadForce — ofertas fechadas, relógio autoritativo, desempate, orçamento, seleção de atletas por rodada e complementação automática dos elencos até 18 jogadores. Use somente quando a entrega do leilão estiver autorizada ou ao revisar contratos relacionados.
---

# auction-system

## Finalidade
Orientar o serviço `services/auction`. **Implementado na Entrega 3** (motor, regras, complementação, API e tela),
**bloqueado até o `AuctionModel` aprovado** — as fórmulas não podem ser inventadas (ver `docs/architecture/leilao.md`).

## Quando utilizar
- Entrega do leilão autorizada pelo usuário.
- Revisão de contratos/fases da sessão que envolvam o leilão.

## Responsabilidades
Rodadas, lances, relógio global, resultado por rodada, orçamento, reserva mínima por vaga, encerramento
antecipado, complementação automática e resumo final de elencos e saldos.

## Regras do Game Design aplicáveis (§4, §5, §7)
- Orçamento inicial **R$ 120 milhões**; nenhuma contratação gera saldo negativo ou jogador duplicado.
- Rodadas de **10 s** com **5 jogadores da mesma posição principal**; ofertas fechadas; **um lance ativo por clube**.
- Pode aumentar o lance ou mudar o alvo; **não pode reduzir** lance no mesmo jogador; se a troca falhar, o lance anterior vale.
- Vence o maior lance válido; empate → quem atingiu o valor primeiro (**timestamp do servidor**) → **ordem sequencial de aceitação**.
- Reservar ao menos **R$ 500 mil por vaga restante**.
- Duração global: Liga 2–10 = 10 min; Liga 11–20 = 15 min; Copa 2/4/8 = 10 min; Copa 16 = 15 min; Copa 32 = 20 min. Termina antes se todos tiverem 18.
- Posição elegível aparece ao menos 1× a cada 14 rodadas concluídas (se houver ≥ 5 elegíveis distintos).
- Interface oculta overall, atributos, valor interno e ofertas adversárias.
- Complementação: exatamente **18** (11 + 7); limite de melhorias = `min(18 − C, floor(C / 4))`; no máximo 1 destaque (percentil ≥ 85 do overall calibrado); preço = média entre valor de mercado e lance mínimo; sem compensação por mau desempenho.

## Contratos e dependências
- Regras aprovadas: `services/auction/rules.py` (única fonte das constantes do GDD).
- Fórmulas pendentes: `services/auction/model.py::AuctionModel` (carregado por `SQUADFORCE_AUCTION_MODEL`).
- Motor: `engine.py` (`AuctionEngine.start/tick/place_bid`), complementação `completion.py`, visões `service.py`.
- API: `POST /auction/start`, `GET /auction`, `POST /auction/bids` (Idempotency-Key = op_id), `GET /auction/summary`.
- Eventos WS: `auction.started`, `auction.round_started`, `auction.round_closed`, `auction.finished`.
- Atletas: `DataService.load_player_profiles()` → `PlayerProfile` (atributos só no servidor).
- Bots: `services/bot_ai/auction_bot.decide_bid(BotAuctionView, model, BotProfile)`.

## Procedimentos recomendados
1. Nunca colocar números de calibração no motor: novas fórmulas entram SOMENTE pelo `AuctionModel`.
2. Toda saída nova do modelo deve ser validada contra o GDD em `AuctionEngine._validate_model_outputs`/`completion`.
3. Relógio só do servidor (`clock` injetado); toda mutação dentro de `engine.lock`.
4. Testes com `tests/support/fake_auction_model.py` (falso, só para testes) e `ManualClock`.
5. Ao receber as fórmulas reais: implementar o modelo, rodar `tests/simulation` com ele e calibrar (mediana 70, >90 raro).

## Restrições e comportamentos proibidos
- Inventar fórmulas econômicas, pesos ou perfis pendentes; usar o modelo falso fora dos testes.
- Revelar ofertas de outros clubes ou dados ocultos a qualquer cliente.
- Pausar o relógio por desconexão.

## Critérios de teste
Saldo nunca negativo; sem duplicatas; desempate por timestamp e sequência; reserva por vaga; elencos finais = 18;
limite de complementação; determinismo com relógio simulado; concorrência de lances.

## Referências
- [Game Design §4, §5, §7](../../../docs/game-design/game-design-v5.2.md)
- [Pendências PE-*](../../../docs/game-design/pendencias.md)
- [README do serviço](../../../services/auction/README.md)
- [Leilão: regras implementadas e fórmulas pendentes](../../../docs/architecture/leilao.md)
- [Matriz de testes](../../../docs/architecture/matriz-de-testes.md)
