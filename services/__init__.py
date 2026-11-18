"""Serviços especializados do SquadForce.

Cada subpacote tem responsabilidade única (ver docs/architecture/arquitetura.md).
Este __init__ apenas torna o pacote compartilhado `squadforce_shared` importável
quando a aplicação é executada a partir da raiz do repositório.
"""

import sys
from pathlib import Path

_SHARED = Path(__file__).resolve().parent.parent / "shared" / "python"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
