# CLAUDE.md — SquadForce (Game Design v5.2)

Simulador de futebol web para um usuário contra bots: leilão, mercado, Liga/Copa e motor de partidas.
Stack: React + TypeScript (Vite) · Python 3.12 + FastAPI · SQLite · pytest · Vitest.

## Fontes oficiais (nesta ordem de autoridade)
1. `Dados/GAME DESIGN DOCUMENT — VERSÃO 5.2.docx` → transcrição: `docs/game-design/game-design-v5.2.md`
2. `Dados/ESPECIFICAÇÃO TÉCNICA DE IMPLEMENTAÇÃO.docx` → `docs/architecture/especificacao-tecnica-v5.2.md`
3. Identidade visual → `docs/game-design/identidade-visual.md` (logos em `Dados/Icon/`)
4. Lacunas e decisões provisórias → `docs/game-design/pendencias.md`

**Nunca invente regras de jogo.** Se algo não está nas fontes, registre em `pendencias.md` e pergunte.

## Skills do projeto (`.claude/skills/`)
Consulte a Skill correspondente **antes** de alterar um módulo. `game-design-rules` vale para todas.

| Skill | Use para |
|---|---|
| `game-design-rules` | qualquer regra de jogo; lacunas e conflitos |
| `project-architecture` | serviços, rotas, contratos, idempotência, erros |
| `database-import` | SQLite, migrações, importação Excel, catálogo |
| `session-management` | sessão em memória, versão, WebSocket, bloqueio de importação |
| `auction-system` | leilão e complementação de elencos (entrega futura) |
| `trading-system` | mercado de negociações (entrega futura) |
| `bot-intelligence` | decisões dos bots (entrega futura) |
| `match-engine` | motor de partidas (entrega futura) |
| `competition-system` | formatos, Liga, Copa, calendário, consolidação |
| `frontend-ui` | React/TS, temas, responsividade, cliente de API |
| `testing-validation` | testes obrigatórios e critérios de aceitação |

## Escopo atual
**Entregas 1 a 4** (infraestrutura, dados, sessão; competições; leilão; mercado de negociações). O leilão está implementado mas
**bloqueado até o `AuctionModel` aprovado** (fórmulas pendentes — `docs/architecture/leilao.md`); nunca invente
essas fórmulas. Não implemente o motor de partidas, a escalação ou a execução de rodadas sem autorização
explícita do usuário para a entrega correspondente.

## Comandos
```bash
# Backend (raiz do repositório)
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m services.gateway --port 8000        # API em http://127.0.0.1:8000/docs
.venv/Scripts/python -m pytest                              # todos os testes Python
.venv/Scripts/python scripts/export_openapi.py              # após mudar contratos
# Frontend (frontend/)
npm install && npm run dev                                  # http://localhost:5173
npm test && npm run test:e2e && npm run build
npm run gen:api                                             # após exportar o OpenAPI
```
Use sempre o `.venv` do projeto (Python 3.12). Terminais abertos antes da inclusão do Python no PATH podem
resolver `python` para o atalho da Microsoft Store.

## Regras de trabalho
- Estado de competição **somente em memória**; SQLite só para bases de clubes/jogadores.
- Todo POST exige `Idempotency-Key`; erros no formato `{"error": {code, message, retryable, details}}`.
- Testes usam bancos temporários; `Dados/` e `Graphics/` são somente leitura; nunca copie as planilhas.
- Migrações apenas aditivas; nada destrutivo sem autorização.
- Corrigiu bug → teste de regressão primeiro. Não declare nada pronto sem rodar as suítes e mostrar a saída.
- Mudou contrato → `export_openapi.py` + `npm run gen:api` + `docs/api/contratos.md`.
