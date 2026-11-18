"""Serviço de dados e importações.

Responsável exclusivo pelo SQLite: migrações, importação de planilhas Excel
(clubes e jogadores) com validação e substituição transacional, e consultas de catálogo.
Nenhum outro serviço acessa o banco diretamente.
"""
