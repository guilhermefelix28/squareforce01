-- SquadForce — Migração 0001: bases persistentes de clubes e jogadores.
-- Fonte das colunas: cabeçalhos reais de Dados/jogadores.xlsx (inspecionados em 2026-11-18).
-- O progresso de competições NÃO é armazenado no SQLite (GDD v5.2, seções 23 e 25).

-- Clubes. club_uid = identificador original da planilha (estável, usado nos escudos Graphics/Clubes/club_{id}.png).
CREATE TABLE clubs (
    club_uid    INTEGER PRIMARY KEY CHECK (club_uid > 0),
    name        TEXT    NOT NULL CHECK (length(trim(name)) > 0),
    short_name  TEXT    NOT NULL CHECK (length(trim(short_name)) > 0),
    nation_id   INTEGER NOT NULL CHECK (nation_id >= 0),
    reputation  INTEGER NOT NULL CHECK (reputation >= 0)  -- ranking interno: nunca exposto pela API pública
) STRICT;

CREATE INDEX idx_clubs_short_name ON clubs (short_name COLLATE NOCASE);

-- Jogadores. unique_id = identificador original da planilha (estável, usado nas fotos Graphics/Faces/{id}.png).
CREATE TABLE players (
    unique_id       INTEGER PRIMARY KEY CHECK (unique_id > 0),
    name            TEXT    NOT NULL CHECK (length(trim(name)) > 0),
    first_name      TEXT,
    last_name       TEXT,
    full_name       TEXT    NOT NULL CHECK (length(trim(full_name)) > 0),
    birth_date      TEXT    NOT NULL CHECK (date(birth_date) IS birth_date),
    age             INTEGER NOT NULL CHECK (age BETWEEN 10 AND 60),
    nation_id       INTEGER NOT NULL CHECK (nation_id >= 0),
    height_cm       INTEGER NOT NULL CHECK (height_cm BETWEEN 100 AND 250),
    club_uid        INTEGER NOT NULL REFERENCES clubs (club_uid) ON UPDATE RESTRICT ON DELETE RESTRICT,
    club_join_date  TEXT    CHECK (club_join_date IS NULL OR date(club_join_date) IS club_join_date)
) STRICT;

CREATE INDEX idx_players_club ON players (club_uid);
CREATE INDEX idx_players_name ON players (name COLLATE NOCASE);

-- Catálogo fechado de atributos aceitos (personalidade, atributos técnicos/mentais/físicos/goleiro, pés).
CREATE TABLE attribute_definitions (
    code      TEXT PRIMARY KEY,
    category  TEXT NOT NULL CHECK (category IN ('personality', 'attribute', 'foot'))
) STRICT, WITHOUT ROWID;

INSERT INTO attribute_definitions (code, category) VALUES
    ('personality_adaptability', 'personality'),
    ('personality_pressure', 'personality'),
    ('personality_professionalism', 'personality'),
    ('personality_sportsmanship', 'personality'),
    ('personality_temperament', 'personality'),
    ('attributes_crossing', 'attribute'),
    ('attributes_dribbling', 'attribute'),
    ('attributes_finishing', 'attribute'),
    ('attributes_heading', 'attribute'),
    ('attributes_long_shots', 'attribute'),
    ('attributes_marking', 'attribute'),
    ('attributes_off_the_ball', 'attribute'),
    ('attributes_passing', 'attribute'),
    ('attributes_penalty_taking', 'attribute'),
    ('attributes_tackling', 'attribute'),
    ('attributes_vision', 'attribute'),
    ('attributes_handling', 'attribute'),
    ('attributes_aerial_reach', 'attribute'),
    ('attributes_command_of_area', 'attribute'),
    ('attributes_communication', 'attribute'),
    ('attributes_kicking', 'attribute'),
    ('attributes_throwing', 'attribute'),
    ('attributes_anticipation', 'attribute'),
    ('attributes_decisions', 'attribute'),
    ('attributes_one_on_ones', 'attribute'),
    ('attributes_positioning', 'attribute'),
    ('attributes_reflexes', 'attribute'),
    ('attributes_first_touch', 'attribute'),
    ('attributes_technique', 'attribute'),
    ('attributes_flair', 'attribute'),
    ('attributes_corners', 'attribute'),
    ('attributes_teamwork', 'attribute'),
    ('attributes_work_rate', 'attribute'),
    ('attributes_long_throws', 'attribute'),
    ('attributes_eccentricity', 'attribute'),
    ('attributes_rushing_out', 'attribute'),
    ('attributes_punching', 'attribute'),
    ('attributes_acceleration', 'attribute'),
    ('attributes_free_kick_taking', 'attribute'),
    ('attributes_strength', 'attribute'),
    ('attributes_stamina', 'attribute'),
    ('attributes_pace', 'attribute'),
    ('attributes_jumping_reach', 'attribute'),
    ('attributes_leadership', 'attribute'),
    ('attributes_dirtiness', 'attribute'),
    ('attributes_balance', 'attribute'),
    ('attributes_bravery', 'attribute'),
    ('attributes_consistency', 'attribute'),
    ('attributes_aggression', 'attribute'),
    ('attributes_agility', 'attribute'),
    ('attributes_important_matches', 'attribute'),
    ('attributes_injury_proneness', 'attribute'),
    ('attributes_versatility', 'attribute'),
    ('attributes_natural_fitness', 'attribute'),
    ('attributes_determination', 'attribute'),
    ('attributes_composure', 'attribute'),
    ('attributes_concentration', 'attribute'),
    ('left_foot', 'foot'),
    ('right_foot', 'foot');

CREATE TABLE player_attributes (
    player_id  INTEGER NOT NULL REFERENCES players (unique_id) ON DELETE CASCADE,
    attribute  TEXT    NOT NULL REFERENCES attribute_definitions (code) ON DELETE RESTRICT,
    value      INTEGER NOT NULL CHECK (value BETWEEN 1 AND 100),
    PRIMARY KEY (player_id, attribute)
) STRICT, WITHOUT ROWID;

-- Familiaridade posicional (colunas positions_* da planilha) e posições natural/secundária.
-- Códigos internos conforme GDD seção 3: GK, DR, DL, DC, DM, MC, STC.
CREATE TABLE player_positions (
    player_id        INTEGER NOT NULL REFERENCES players (unique_id) ON DELETE CASCADE,
    position         TEXT    NOT NULL CHECK (position IN ('GK', 'DR', 'DL', 'DC', 'DM', 'MC', 'STC')),
    familiarity      INTEGER NOT NULL CHECK (familiarity BETWEEN 1 AND 100),
    is_natural       INTEGER NOT NULL DEFAULT 0 CHECK (is_natural IN (0, 1)),
    is_accomplished  INTEGER NOT NULL DEFAULT 0 CHECK (is_accomplished IN (0, 1)),
    PRIMARY KEY (player_id, position)
) STRICT, WITHOUT ROWID;

CREATE INDEX idx_player_positions_natural ON player_positions (position, is_natural);
