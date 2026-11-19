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
| `auction-system` | leilão e complementação de elencos |
| `trading-system` | mercado de negociações |
| `bot-intelligence` | decisões dos bots |
| `match-engine` | motor de partidas |
| `competition-system` | formatos, Liga, Copa, calendário, consolidação |
| `frontend-ui` | React/TS, temas, responsividade, cliente de API |
| `testing-validation` | testes obrigatórios e critérios de aceitação |

## Escopo atual
**Entregas 1 a 9 concluídas** (infraestrutura, dados, sessão; competições; leilão; mercado; motor esportivo; IA tática;
execução de Liga e Copa; interface; homologação). Conclusão em 2026-11-19: o `AuctionModel` oficial foi aprovado
(`docs/architecture/proposta-auction-model.md`, `services/auction/official_model.py`, carregado por padrão), assim como
as 11 formações (PM-01), o desempate Brasileirão (PC-01), a pontuação 3/1/0 (PC-09) e as referências do motor (PM-02).
Mudar fórmula, perfil de bot ou formação aprovados exige nova aprovação do responsável. Os parâmetros do motor
(`services/match_engine/params.py`) são os calibrados contra as referências aceitas; os da IA tática
(`services/bot_ai/tactics_params.py`) e da concorrência no leilão (PB-06) continuam provisórios.
**Experiência de jogo (2026-11-19):** as diretrizes do responsável prevalecem sobre o GDD (DR-01..DR-10 em
`pendencias.md`: lance redutível e cancelável, tática antes do leilão (confirmar já inicia o leilão), goleiro cansa
×0,35, área oculta de dados com senha, ordem de posições GOL-LD-ZAG-LE-VOL-ME-ATA, partida ao vivo com as duas
equipes e os outros jogos, formações 4-2-2-2 e 4-1-2-3 com faixas VOL/ME no campinho, pênaltis cobrança a cobrança,
cores dos uniformes extraídas do escudo).
Critérios de aceitação são fixos (`docs/homologacao/criterios.md`): nunca altere limites depois de ver resultados.
Não implemente novas entregas sem autorização
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
