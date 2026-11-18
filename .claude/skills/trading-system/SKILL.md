---
name: trading-system
description: Implementar e revisar o mercado de negociações do SquadForce — propostas de troca 1x1, pagamento adicional, limites por clube, prazos, cancelamento, atomicidade e negociações entre bots. Use somente quando a entrega do mercado estiver autorizada ou ao revisar contratos relacionados.
---

# trading-system

## Finalidade
Orientar o serviço `services/trading` (ainda **não implementado**; ver `services/trading/README.md`).

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
Estado na sessão; avaliação via `bot-intelligence`; comandos idempotentes; eventos WS (a definir).

## Procedimentos recomendados
1. Validar todas as pré-condições e aplicar a troca em uma única seção crítica.
2. Expirar propostas pelo relógio do servidor.
3. Registrar contador de negociações concluídas por clube.

## Restrições e comportamentos proibidos
Contrapropostas; pagamento pelo receptor; trocas N×M; execução parcial; bots acessarem dados privados de outros clubes.

## Critérios de teste
Atomicidade sob concorrência; limite de 3; uma proposta ativa; expiração em 10 s; cancelamento; 18 jogadores e saldo ≥ 0 sempre.

## Referências
- [Game Design §8](../../../docs/game-design/game-design-v5.2.md)
- [README do serviço](../../../services/trading/README.md)
