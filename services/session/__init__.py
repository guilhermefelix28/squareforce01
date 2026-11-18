"""Serviço de gerenciamento de sessão.

Mantém a competição ativa APENAS em memória (GDD v5.2, seção 23): uma competição ativa,
versão de estado, encerramento explícito, trava de importações e suporte à reconexão
enquanto o processo estiver vivo. Se o processo terminar, o estado é perdido de forma
definitiva — não há persistência, backup ou restauração.
"""
