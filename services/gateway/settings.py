"""Configuração por variáveis de ambiente (sem segredos)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _env_list(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    db_path: Path = field(
        default_factory=lambda: Path(os.environ.get("SQUADFORCE_DB_PATH", ROOT / "database" / "squadforce.db"))
    )
    graphics_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("SQUADFORCE_GRAPHICS_DIR", ROOT / "Graphics"))
    )
    max_upload_mb: int = field(default_factory=lambda: int(os.environ.get("SQUADFORCE_MAX_UPLOAD_MB", "25")))
    cors_origins: list[str] = field(
        default_factory=lambda: _env_list(
            "SQUADFORCE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        )
    )
    idempotency_ttl_seconds: int = 3600
