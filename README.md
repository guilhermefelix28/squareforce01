# SquadForce

**Football Strategy Game** — simulador de futebol com leilão de jogadores, negociações, bots com IA,
Liga, Copa e motor de partidas. Implementação do **Game Design v5.2**.

**Estado:** Entrega 1 — fundação, Skills, infraestrutura e dados.

## Estrutura

```text
.claude/skills/        11 Skills do projeto (+ Skills de terceiros já instaladas)
frontend/              React + TypeScript + Vite + Vitest
services/
  gateway/             API REST + WebSocket, idempotência, erros, composição
  session/             competição em memória, versão, trava de importação
  data/                SQLite, migrações, importação Excel, catálogo
  competition/         opções de formato (Liga/Copa)
  auction/ trading/ bot_ai/ match_engine/   estrutura reservada (entregas futuras)
shared/python/squadforce_shared/   domínio puro, contratos Pydantic, códigos de erro
database/migrations/   SQL versionado (o banco .db não é versionado)
tests/                 unit · integration · contracts · end_to_end
docs/                  game-design · architecture · api  (índice: docs/README.md)
scripts/               export_openapi.py
Dados/ Graphics/       fontes originais (somente leitura, fora do Git)
```

## Requisitos
- Python 3.12 · Node.js 20+ (testado com 26) · npm

## Como executar

```bash
# 1. Backend (na raiz)
python -m venv .venv                       # Windows: use o caminho completo do Python 3.12 se não estiver no PATH
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m services.gateway --port 8000
#   API: http://127.0.0.1:8000/api/health   ·   Swagger: http://127.0.0.1:8000/docs

# 2. Frontend (outro terminal)
cd frontend
npm install
npm run dev
#   http://localhost:5173  (proxy de /api e /ws para o backend)
```

Fluxo inicial na interface: **Dados** → importar `jogadores.xlsx` em *Base de clubes* e depois em
*Base de jogadores* → **Competição** → escolher formato e clube → *Iniciar sessão*.

Variáveis opcionais: `SQUADFORCE_DB_PATH` (padrão `database/squadforce.db`), `SQUADFORCE_GRAPHICS_DIR`
(padrão `Graphics/`), `SQUADFORCE_MAX_UPLOAD_MB` (25), `SQUADFORCE_CORS_ORIGINS`.

## Testes

```bash
.venv/Scripts/python -m pytest             # backend: unit, integração, contratos, Skills, servidor real
cd frontend && npm test                    # componentes e cliente de API
cd frontend && npm run test:e2e            # frontend ↔ backend real (sobe o uvicorn com banco temporário)
cd frontend && npm run build               # checagem de tipos + build de produção
```

## Documentação
Comece por [docs/README.md](docs/README.md) e [CLAUDE.md](CLAUDE.md).
