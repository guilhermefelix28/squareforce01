---
name: frontend-ui
description: Interface React + TypeScript do SquadForce — organização em app/pages/features/components/api/hooks/types, cliente de API com idempotência e repetição segura, temas claro/escuro com a identidade visual, responsividade e mensagens de erro claras. Use ao criar ou alterar qualquer tela, componente ou chamada de API no frontend.
---

# frontend-ui

## Finalidade
Manter o frontend (`frontend/`) consistente, tipado pelo contrato do backend e fiel ao GDD e à marca.

## Quando utilizar
Qualquer alteração em `frontend/src/**`, estilos, tipos gerados ou testes Vitest.

## Responsabilidades
| Pasta | Conteúdo |
|---|---|
| `app/` | shell, navegação (hash), tema, `SessionContext` (reconexão WS) |
| `pages/` | telas: Início, Dados, Competição |
| `features/` | blocos de domínio: imports, catalog, session, competition (calendário da Liga, chaveamento da Copa) |
| `components/` | genéricos: Notice, ConfirmDialog, ClubCrest |
| `api/` | `client.ts` (erros, retry, idempotência) e `endpoints.ts` |
| `types/` | `openapi.d.ts` **gerado** + aliases em `api.ts` |
| `domain/` | mapeamento de posições para exibição |

## Regras do Game Design aplicáveis
- §1/§22: web responsiva (computador e celular), temas claro e escuro, central de gerenciamento; leilão, mercado e partidas terão telas próprias (entregas futuras).
- §3: exibir posições como GOL, LD, LE, ZAG, VOL, ME, ATA.
- §2: escudo por ID, senão iniciais (`ClubCrest`).
- §5: nunca exibir overall, atributos ou valor interno no leilão.
- §23: confirmação para encerrar/substituir competição; aviso de que não há salvamento.
- Identidade: escuro = marca oficial (#99FA08 sobre preto); claro = versão secundária (#033A01 sobre branco).

## Contratos e dependências
- Tipos: `npm run gen:api` após `python scripts/export_openapi.py`. Nunca editar `openapi.d.ts` à mão.
- Toda chamada via `apiRequest`; comandos com `newIdempotencyKey()` — **uma chave por intenção do usuário**, reutilizada nas repetições.
- Vite faz proxy de `/api` e `/ws` para `http://127.0.0.1:8000`.

## Procedimentos recomendados
1. Validar no cliente para feedback rápido, mas tratar o backend como autoridade (mostrar `error.message`).
2. Estados de carregamento, vazio, erro e sucesso em toda tela.
3. Testar em 390 px e ≥ 1024 px; foco visível; rótulos acessíveis.

## Restrições e comportamentos proibidos
- `fetch` direto fora de `api/client.ts`; tipos de API escritos à mão divergentes do OpenAPI.
- Guardar estado de competição no navegador além do `id` da sessão.
- Implementar telas definitivas de leilão, mercado ou partidas antes da entrega autorizada.

## Critérios de teste
`npm test` (Vitest + Testing Library) e `npm run test:e2e` (cliente real contra uvicorn real); `npm run build` sem erros de tipo.

## Referências
- [Identidade visual](../../../docs/game-design/identidade-visual.md)
- [Contratos da API](../../../docs/api/contratos.md)
- [Game Design §1, §22, §23](../../../docs/game-design/game-design-v5.2.md)
