# SquadForce

**Football Strategy Game** — simulador de futebol com leilão de jogadores, negociações, bots com IA,
Liga, Copa e motor de partidas. Implementação do **Game Design v5.2**.

**Estado:** Entrega 9 — homologação **BLOQUEADA** por insumos externos (fórmulas do leilão, critérios de desempate, aprovação das referências estatísticas); todo o restante verificado e dentro dos critérios. Ver [relatório final](docs/homologacao/relatorio-final.md).

## Estrutura

```text
.claude/skills/        11 Skills do projeto (+ Skills de terceiros já instaladas)
frontend/              React + TypeScript + Vite + Vitest
services/
  gateway/             API REST + WebSocket, idempotência, erros, composição
  session/             competição em memória, versão, trava de importação
  data/                SQLite, migrações, importação Excel, catálogo
  competition/         opções de formato, seleção de participantes, calendário e chaveamento
  auction/             leilão: regras, motor, complementação (fórmulas via AuctionModel)
  bot_ai/              avaliação 80/20, lances, trocas e tática de partidas dos bots
  trading/             mercado: propostas, decisões únicas, trocas atômicas
  match_engine/        motor de partidas: eventos, xG, disciplina, lesões, notas, determinismo
shared/python/squadforce_shared/   domínio puro, contratos Pydantic, códigos de erro
database/migrations/   SQL versionado (o banco .db não é versionado)
tests/                 unit · integration · contracts · end_to_end
docs/                  game-design · architecture · api  (índice: docs/README.md)
scripts/               export_openapi.py, match_engine_report.py, tactics_report.py
Dados/ Graphics/       fontes originais (somente leitura, fora do Git)
```

## Requisitos
- Python 3.12 · Node.js 20+ (testado com 26) · npm

## Como executar

### Para jogar (executor)

Dê dois cliques no atalho **SquadForce** da área de trabalho. Ele roda `scripts/launcher/iniciar-jogo.ps1`, que:
1. faz o build de produção da interface quando o código mudou;
2. sobe o servidor na porta 8000 e a interface na 5173;
3. abre o jogo no navegador.

- **Encerrar:** pressione Enter na janela do executor.
- **Porta ocupada:** o executor mostra quando o processo foi iniciado e pergunta se deve reiniciá-lo com a versão atual.
- **Registros:** `%TEMP%\squadforce\`.
- **Fluxo do jogo:** abertura → *Nova partida* (formato e clube) → tática → leilão → mercado → temporada
  (central da rodada → escalação → jogo ao vivo → pós-jogo) → encerramento. Cada tela tem uma ação principal no rodapé.
- **Atualizar as bases (área oculta):** `http://localhost:5173/#/admin`, senha `9153` (troque com
  `SQUADFORCE_ADMIN_PASSWORD`). A senha é verificada pelo servidor; a área não aparece em nenhum menu.
- **Som da torcida:** botão 🔊 na barra superior (lembrado no navegador).
- **Recriar o atalho:** aponte para
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\launcher\iniciar-jogo.ps1`, com o ícone
  `scripts\launcher\squadforce.ico`.

### Desenvolvimento

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

Primeira carga das bases: `#/admin` (senha `9153`) → importar `jogadores.xlsx` em *Base de clubes* e depois em
*Base de jogadores*. Depois, na abertura: **Nova partida** → formato e clube → tática → leilão.

Variáveis opcionais: `SQUADFORCE_DB_PATH` (padrão `database/squadforce.db`), `SQUADFORCE_GRAPHICS_DIR`
(padrão `Graphics/`), `SQUADFORCE_MAX_UPLOAD_MB` (25), `SQUADFORCE_CORS_ORIGINS`, `SQUADFORCE_ADMIN_PASSWORD` (9153).

## Testes

```bash
.venv/Scripts/python -m pytest             # backend: unit, integração, contratos, Skills, servidor real
cd frontend && npm test                    # componentes e cliente de API
cd frontend && npm run test:e2e            # frontend ↔ backend real (sobe o uvicorn com banco temporário)
cd frontend && npm run build               # checagem de tipos + build de produção
```

## Documentação
Comece por [docs/README.md](docs/README.md) e [CLAUDE.md](CLAUDE.md).
