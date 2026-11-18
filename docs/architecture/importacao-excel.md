# Importação Excel → SQLite

Fonte inspecionada: `Dados/jogadores.xlsx` (2026-11-18) — 1 aba **`Jogadores`**, 1585 linhas de dados, 83 colunas.
O arquivo original nunca é modificado nem copiado (teste `test_real_spreadsheet.py` compara o SHA-256).

## Achados da inspeção

| Achado | Tratamento |
|---|---|
| Colunas numéricas com tipos mistos: ~50% das linhas trazem números como texto (`'189'`). | Conversão estrita: aceita inteiro, float integral e texto só de dígitos; rejeita frações, booleanos e textos não numéricos. |
| 11 linhas sem `unique_id`. | Descartadas com aviso `ROW_WITHOUT_ID` (ver [pendências PD-03](../game-design/pendencias.md)). |
| `natural_positions` / `accomplished_positions` já usam códigos internos (GK, DR, DL, DC, DM, MC, STC); um valor por célula. | Normalização aceita também os códigos de exibição (GOL, LD, LE, ZAG, VOL, ME, ATA) e listas separadas por `, ; / \|` ou espaço. |
| Dados de clube repetidos em cada linha (`club_uid`, `club_name`, `club_short_name`, `club_nation_id`, `club_reputation`); 40 clubes. | Fonte da base de clubes (PD-02). |
| Datas como texto `AAAA-MM-DD`. | Validadas como datas reais. |
| Nenhum `unique_id` duplicado; familiaridade da posição natural sempre 100. | Duplicatas seriam críticas. |

## Mapeamento de colunas

| Planilha | SQLite | Regra |
|---|---|---|
| `club_uid` | `clubs.club_uid` (PK) / `players.club_uid` (FK) | inteiro > 0 |
| `club_name`, `club_short_name` | `clubs.name`, `clubs.short_name` | texto obrigatório |
| `club_nation_id`, `club_reputation` | `clubs.nation_id`, `clubs.reputation` | inteiro ≥ 0 (reputação nunca exposta) |
| `unique_id` | `players.unique_id` (PK) | inteiro > 0, único |
| `name`, `full_name` | `players.name`, `players.full_name` | obrigatórios |
| `first_name`, `last_name` | idem | opcionais |
| `birth_date`, `club_join_date` | idem | data ISO (join opcional) |
| `age`, `height_cm`, `nation_id` | idem | 10–60 · 100–250 · ≥ 0 |
| `natural_positions`, `accomplished_positions` | `player_positions.is_natural/is_accomplished` | posições válidas; natural obrigatória |
| `positions_gk … positions_stc` (7) | `player_positions.familiarity` | 1–100 |
| `personality_*` (5), `attributes_*` (52), `left_foot`, `right_foot` | `player_attributes(attribute, value)` | 1–100; catálogo fechado em `attribute_definitions` |

## Classificação de erros

**Críticos (rejeitam a importação inteira):** `MISSING_COLUMNS`, `DUPLICATE_COLUMN`, `EMPTY_SHEET`, `INVALID_TYPE`,
`MISSING_VALUE`, `OUT_OF_RANGE`, `DUPLICATE_ID`, `INVALID_POSITION`, `INVALID_RELATIONSHIP`,
`INCONSISTENT_CLUB_DATA`, `CLUBS_NOT_IMPORTED`.

**Avisos (não bloqueiam):** `ROW_WITHOUT_ID` (linha descartada), `UNKNOWN_COLUMN` (ignorada).

**Arquivo:** `UNSUPPORTED_FILE` (415), `INVALID_WORKBOOK` (422), `FILE_TOO_LARGE` (413).

## Ordem e relacionamentos

1. Importar **clubes** (aceita a própria `jogadores.xlsx`).
2. Importar **jogadores** — todo `club_uid` precisa existir em `clubs`.
3. Reimportar clubes que removam um clube ainda referenciado por jogadores é rejeitado (`INVALID_RELATIONSHIP`).

Código: `services/data/importer.py` (validação) e `services/data/service.py` (transação).
