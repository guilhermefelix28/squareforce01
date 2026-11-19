-- SquadForce — Migração 0003 (2026-11-19). Atualização dos IDs de clube pedida pelo responsável.
--
-- O responsável trocou o club_uid de 18 clubes em Dados/jogadores.xlsx para o ID do escudo existente em
-- Graphics/Clubes. A tabela de referência club_divisions (0002) acompanha: cada linha passa do ID antigo para o
-- novo, mantendo divisão, temporada e nome. Nenhuma divisão é removida ou criada (continuam 20 A e 20 B).
UPDATE club_divisions SET club_uid = 314 WHERE club_uid = 313;            -- Atlético Mineiro
UPDATE club_divisions SET club_uid = 319 WHERE club_uid = 318;            -- Corinthians
UPDATE club_divisions SET club_uid = 102555 WHERE club_uid = 102496;      -- Goiás
UPDATE club_divisions SET club_uid = 104749 WHERE club_uid = 104654;      -- Ceará
UPDATE club_divisions SET club_uid = 107201 WHERE club_uid = 106882;      -- América Mineiro
UPDATE club_divisions SET club_uid = 107208 WHERE club_uid = 107207;      -- Avaí
UPDATE club_divisions SET club_uid = 107236 WHERE club_uid = 107235;      -- Vila Nova
UPDATE club_divisions SET club_uid = 121265 WHERE club_uid = 121263;      -- Botafogo (SP)
UPDATE club_divisions SET club_uid = 301102 WHERE club_uid = 301101;      -- CRB
UPDATE club_divisions SET club_uid = 301151 WHERE club_uid = 301150;      -- Atlético Goianiense
UPDATE club_divisions SET club_uid = 301304 WHERE club_uid = 301303;      -- Chapecoense
UPDATE club_divisions SET club_uid = 301344 WHERE club_uid = 301343;      -- Mirassol
UPDATE club_divisions SET club_uid = 311086 WHERE club_uid = 311043;      -- Operário Ferroviário
UPDATE club_divisions SET club_uid = 318915 WHERE club_uid = 318914;      -- Cuiabá
UPDATE club_divisions SET club_uid = 900678 WHERE club_uid = 900205;      -- Londrina
UPDATE club_divisions SET club_uid = 2106553 WHERE club_uid = 2106413;    -- São Bernardo
UPDATE club_divisions SET club_uid = 19144990 WHERE club_uid = 19144923;  -- Grêmio Novorizontino
UPDATE club_divisions SET club_uid = 19342677 WHERE club_uid = 19342670;  -- Athletic (MG)
