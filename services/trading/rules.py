"""Regras APROVADAS do mercado de negociações (GDD v5.2 §8)."""

MARKET_SECONDS = 180.0  # duração global: três minutos, sem pausa
PROPOSAL_SECONDS = 10.0  # prazo máximo de cada proposta (ou até o fim do mercado)
MAX_COMPLETED_TRADES = 3  # até três negociações concluídas por clube
MAX_PENDING_PER_PROPONENT = 1  # uma proposta ativa por clube (como proponente — decisão TR-01)
SQUAD_SIZE = 18  # elenco sempre com 18 contratados
