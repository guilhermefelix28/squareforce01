---
name: trading-system
description: Implementar e revisar o mercado de negociações do SquadForce — propostas de troca 1x1, pagamento adicional, limites por clube, prazos, cancelamento, atomicidade e negociações entre bots. Use somente quando a entrega do mercado estiver autorizada ou ao revisar contratos relacionados.
---

# trading-system

## Finalidade
Orientar o serviço `services/trading`. **Implementado na Entrega 4** (motor, IA de negociação, API e tela).
Parâmetros das personalidades pendentes (PB-02, via `AuctionModel.trade_profile`).

## Quando utilizar
Entrega do mercado autorizada, ou revisão de contratos/fases que envolvam negociações.

## Responsabilidades
Ciclo de propostas (criar, aceitar, recusar, expirar, cancelar), relógio global de 3 min, validação e
execução atômica das trocas, painel de propostas recebidas.

## Regras do Game Design aplicáveis (§8)
- Começa **somente** quando o usuário clica em *Iniciar negociações*; **3 minutos**, sem pausa.
- Troca de **um jogador por outro**; pagamento adicional **apenas do proponente**.
- Até **3 negociações concluídas por clube**; **uma proposta ativa por clube**.
- Prazo de **10 s** por proposta (ou até o fim do mercado); **sem contrapropostas**; proponente pode cancelar enquanto pendente.
- Transações **atômicas**; elenco sempre com **18**; nada de duplicação ou saldo negativo.
- Usuário e bots propõem, inclusive bot↔bot; bots avaliam ganho esportivo, adequação, orçamento, necessidades e personalidade.
- Interface: busca por nome, clube e posição; propostas recebidas em painel lateral com contagem regressiva.

## Contratos e dependências
- Regras: `services/trading/rules.py`; motor `engine.py` (`TradingEngine.start/tick/propose/respond/cancel`); visões `service.py`.
- API: `POST /trading/start`, `GET /trading`, `GET /trading/squads`, `POST /trading/proposals`, `POST /trading/proposals/{id}/{accept|reject|cancel}`.
- Eventos WS: `trading.started`, `trading.proposal_created`, `trading.proposal_decided`, `trading.trade_completed`, `trading.finished`.
- IA: `services/bot_ai/trade_bot.py` (`evaluate_offer`, `choose_proposal`).
- Fases: `squad_completion` → `trading` → `competition`.

## Procedimentos recomendados
1. Toda mutação sob `engine.lock`; cada proposta recebe uma única decisão final (`_decide`).
2. Trocas por cópia-e-confirmação (`_validate_commit` antes de aplicar); nunca alterar elencos diretamente.
3. Eventos de tempo (expiração, bots, fechamento) só pela linha do tempo `_advance`.
4. Erros definitivos de comandos são memorizados por op_id (reenvio = mesmo erro).
5. Testes com `tests/support/trading_fixtures.py` (`make_market`, perfis controlados) e `ManualClock`.

## Restrições e comportamentos proibidos
Contrapropostas; pagamento pelo receptor; trocas N×M; execução parcial; bots acessarem dados privados de outros clubes.

## Critérios de teste
Atomicidade sob concorrência; limite de 3; uma proposta ativa; expiração em 10 s; cancelamento; 18 jogadores e saldo ≥ 0 sempre;
dinheiro total conservado; dupla aceitação; falha na confirmação; bots sem exploração financeira. Ver `docs/architecture/matriz-de-testes.md`.

## Estado na homologação (Entrega 9)
Homologação: atomicidade, limites e conservação do dinheiro cobertos pelos testes da Entrega 4; latência de proposta/cancelamento medida em `docs/homologacao/desempenho.md`.

## Referências
- [Game Design §8](../../../docs/game-design/game-design-v5.2.md)
- [README do serviço](../../../services/trading/README.md)
- [Mercado: regras, concorrência e IA](../../../docs/architecture/mercado.md)
