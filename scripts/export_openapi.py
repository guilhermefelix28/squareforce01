"""Exporta o contrato OpenAPI para docs/api/openapi.json (fonte dos tipos TypeScript do frontend).

Uso: .venv/Scripts/python scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import services  # noqa: E402,F401
from services.gateway.app import create_app  # noqa: E402

out = ROOT / "docs" / "api" / "openapi.json"
out.write_text(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"OpenAPI exportado: {out}")
