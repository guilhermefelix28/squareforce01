---
name: auction-system
description: Implementar e revisar o leilão de jogadores do SquadForce — ofertas fechadas, relógio autoritativo, desempate, orçamento, seleção de atletas por rodada e complementação automática dos elencos até 18 jogadores. Use somente quando a entrega do leilão estiver autorizada ou ao revisar contratos relacionados.
---

# auction-system

## Finalidade
Orientar o serviço `services/auction` (ainda **não implementado**; estrutura em `services/auction/README.md`).

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
- Catálogo via serviço de dados; decisões de bots via `bot-intelligence`; estado na sessão (`session-management`).
- Comandos idempotentes; eventos no canal `/ws/sessions/{id}` (nomes a definir na entrega).

## Procedimentos recomendados
1. Confirmar pendências PE-01…PE-05 (overall, valor, lance mínimo, reservas, pesos do sorteio) antes de codificar.
2. Relógio e timestamps exclusivamente do servidor (monotônico); cliente só exibe.
3. Aceitação de lances serializada com número de sequência para o desempate.

## Restrições e comportamentos proibidos
- Inventar fórmulas econômicas ou pesos pendentes.
- Revelar ofertas de outros clubes ou dados ocultos a qualquer cliente.
- Pausar o relógio por desconexão.

## Critérios de teste
Saldo nunca negativo; sem duplicatas; desempate por timestamp e sequência; reserva por vaga; elencos finais = 18;
limite de complementação; determinismo com relógio simulado; concorrência de lances.

## Referências
- [Game Design §4, §5, §7](../../../docs/game-design/game-design-v5.2.md)
- [Pendências PE-*](../../../docs/game-design/pendencias.md)
- [README do serviço](../../../services/auction/README.md)
