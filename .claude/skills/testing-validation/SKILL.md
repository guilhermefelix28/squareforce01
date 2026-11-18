---
name: testing-validation
description: Testes obrigatórios e critérios de aceitação do SquadForce — pytest, Vitest, testes de contrato, efeitos reais no banco, e2e com servidor real, determinismo e calibração estatística. Use ao criar funcionalidades, corrigir bugs, fazer regressão ou antes de declarar qualquer entrega concluída.
---

# testing-validation

## Finalidade
Garantir que nenhuma funcionalidade seja declarada pronta sem evidência executada e reprodutível.

## Quando utilizar
Sempre que código for criado/alterado, ao corrigir um bug (regressão primeiro) e antes do relatório de uma entrega.

## Responsabilidades
| Camada | Local | Comando |
|---|---|---|
| Unitários Python | `tests/unit/` | `.venv/Scripts/python -m pytest tests/unit` |
| Integração (API + SQLite) | `tests/integration/` | `… -m pytest tests/integration` |
| Contratos | `tests/contracts/` | `… -m pytest tests/contracts` |
| Servidor real | `tests/end_to_end/` | `… -m pytest -m e2e` |
| Frontend | `frontend/src/**/*.test.ts(x)` | `npm test` |
| Frontend ↔ backend real | `frontend/src/**/*.e2e.test.ts` | `npm run test:e2e` |
| Simulação/calibração | `tests/simulation/` (futuro) | — |

## Regras do Game Design aplicáveis
§26: pronto somente com todos os testes obrigatórios aprovados, sem falhas críticas/importantes, regras
financeiras e esportivas respeitadas, determinismo comprovado, calibração estatística, IA coerente, desempenho
e integração paralela validados. Especificação §8/§9: não declarar concluído sem evidência.

## Contratos e dependências
Fixtures em `tests/conftest.py` (bancos temporários, construtor de `.xlsx` em memória, helpers de sessão).
A planilha real é usada **somente leitura** (`@pytest.mark.real_data`).

## Procedimentos recomendados
1. Bug → teste que reproduz → correção → rodar o teste e a suíte afetada.
2. Verificar **efeitos** (linhas no SQLite, estado da sessão, ausência de mudança após erro), não só o status HTTP.
3. Injetar falhas (monkeypatch) para provar rollback e repetição segura.
4. Ao final, rodar todas as suítes e colar a saída real no relatório.

## Restrições e comportamentos proibidos
- Declarar testes aprovados sem executá-los ou apresentar resultados simulados.
- Alterar regras aprovadas ou afrouxar asserções para "passar".
- Testes destrutivos em `database/squadforce.db` ou em `Dados/`.
- `skip` silencioso de testes obrigatórios.

## Critérios de teste (Entrega 1 — matriz obrigatória)
1 inicialização · 2 comunicação FE/BE · 3 contratos · 4 importação e consulta · 5 IDs duplicados · 6 tipos inválidos ·
7 relacionamentos inválidos · 8 normalização de posições · 9 importação válida · 10 inválida com rollback ·
11 preservação da base · 12 criar/encerrar sessão · 13 configurações inválidas · 14 bloqueio de importação ·
15 comandos duplicados · 16 falhas de comunicação recuperáveis. Mapeamento em `docs/architecture/matriz-de-testes.md`.

**Entrega 2:** Ligas 2, 3, 5, 7, 10, 19, 20 em turno único e returno (partidas, rodadas, folgas, mandos, inclusão
do usuário, confrontos indevidos); Copas 2, 4, 8, 16, 32 (chaveamento, eliminação, progressão até a final,
duplicações); cada cenário com várias sementes e conferido de forma independente do validador interno.

## Referências
- [Matriz de testes da Entrega 1](../../../docs/architecture/matriz-de-testes.md)
- [Especificação técnica §8–9](../../../docs/architecture/especificacao-tecnica-v5.2.md)
- [Game Design §26](../../../docs/game-design/game-design-v5.2.md)
