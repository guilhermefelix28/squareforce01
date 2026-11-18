-- SquadForce — Migração 0002 (Entrega 2). Somente aditiva.
--
-- 1) Divisões dos clubes (GDD §2: "20 da Série A e 20 da Série B"; prioridade da Série A na Liga).
--    A planilha jogadores.xlsx não tem coluna de divisão. Dados de referência da temporada 2026,
--    pesquisados em 2026-11-18 e autorizados pelo responsável do projeto:
--      Série A: https://www.mktesportivo.com/2025/12/equilibrio-inedito-libra-e-lfu-chegam-a-serie-a-de-2026-com-o-mesmo-numero-de-clubes/
--      Série B: https://www.tnh1.com.br/noticia/nid/serie-b-2026-tem-seus-20-participantes-definidos/
--    Tabela independente das importações (sem FK): reimportar clubes não apaga a divisão.
CREATE TABLE club_divisions (
    club_uid  INTEGER PRIMARY KEY CHECK (club_uid > 0),
    division  TEXT    NOT NULL CHECK (division IN ('A', 'B')),
    season    INTEGER NOT NULL CHECK (season BETWEEN 2000 AND 2100),
    label     TEXT    NOT NULL
) STRICT;

INSERT INTO club_divisions (club_uid, division, season, label) VALUES
    (322, 'A', 2026, 'Flamengo'),
    (329, 'A', 2026, 'Palmeiras'),
    (316, 'A', 2026, 'Botafogo'),
    (318, 'A', 2026, 'Corinthians'),
    (321, 'A', 2026, 'Cruzeiro'),
    (323, 'A', 2026, 'Fluminense'),
    (313, 'A', 2026, 'Atlético Mineiro'),
    (337, 'A', 2026, 'São Paulo'),
    (315, 'A', 2026, 'Bahia'),
    (335, 'A', 2026, 'Santos'),
    (339, 'A', 2026, 'Vasco da Gama'),
    (324, 'A', 2026, 'Grêmio'),
    (326, 'A', 2026, 'Internacional'),
    (317, 'A', 2026, 'Bragantino'),
    (301343, 'A', 2026, 'Mirassol'),
    (107206, 'A', 2026, 'Athletico Paranaense'),
    (340, 'A', 2026, 'Vitória'),
    (104776, 'A', 2026, 'Coritiba'),
    (334, 'A', 2026, 'Remo'),
    (301303, 'A', 2026, 'Chapecoense'),
    (104750, 'B', 2026, 'Fortaleza'),
    (102496, 'B', 2026, 'Goiás'),
    (338, 'B', 2026, 'Sport Recife'),
    (104654, 'B', 2026, 'Ceará'),
    (327, 'B', 2026, 'Juventude'),
    (320, 'B', 2026, 'Criciúma'),
    (106882, 'B', 2026, 'América Mineiro'),
    (301150, 'B', 2026, 'Atlético Goianiense'),
    (318914, 'B', 2026, 'Cuiabá'),
    (19144923, 'B', 2026, 'Grêmio Novorizontino'),
    (107207, 'B', 2026, 'Avaí'),
    (301101, 'B', 2026, 'CRB'),
    (311043, 'B', 2026, 'Operário Ferroviário'),
    (107235, 'B', 2026, 'Vila Nova'),
    (332, 'B', 2026, 'Ponte Preta'),
    (121263, 'B', 2026, 'Botafogo (SP)'),
    (328, 'B', 2026, 'Náutico'),
    (19342670, 'B', 2026, 'Athletic (MG)'),
    (2106413, 'B', 2026, 'São Bernardo'),
    (900205, 'B', 2026, 'Londrina');

CREATE INDEX idx_club_divisions_division ON club_divisions (division);

-- 2) Jogadores sem unique_id na planilha recebem ID genérico estável (decisão do responsável, 2026-11-18).
--    Faixa reservada >= 9.000.000.000 (IDs reais vão até ~2,0 bilhões). 1 = ID gerado pelo SquadForce.
ALTER TABLE players ADD COLUMN id_generated INTEGER NOT NULL DEFAULT 0 CHECK (id_generated IN (0, 1));
