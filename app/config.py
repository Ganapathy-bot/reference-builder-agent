"""Runtime settings. Thresholds are configurable and are not treated as universal truth."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    auto_threshold: float = 0.90
    warn_threshold: float = 0.70
    ambiguity_gap: float = 0.12
    min_match: float = 0.45
    max_retries: int = 2
    http_timeout: float = 12.0
    cache_ttl_seconds: int = 60 * 60 * 24
    miss_ttl_seconds: int = 60 * 60
    candidate_ttl_seconds: int = 60 * 60 * 6
    batch_limit: int = 40
    rate_limit_per_minute: int = 30
    mailto: str = "dev@localhost"
    data_dir: Path = ROOT / "data"

    @property
    def user_agent(self) -> str:
        return f"BibliographyIntelligenceAgent/1.0 (mailto:{self.mailto})"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "agent.sqlite"


def get_settings() -> Settings:
    data_dir = Path(os.getenv("BIBLIO_DATA_DIR", str(ROOT / "data")))
    return Settings(
        auto_threshold=_float("BIBLIO_AUTO_THRESHOLD", 0.90),
        warn_threshold=_float("BIBLIO_WARN_THRESHOLD", 0.70),
        ambiguity_gap=_float("BIBLIO_AMBIGUITY_GAP", 0.12),
        min_match=_float("BIBLIO_MIN_MATCH", 0.45),
        max_retries=_int("BIBLIO_MAX_RETRIES", 2),
        http_timeout=_float("BIBLIO_HTTP_TIMEOUT", 12.0),
        batch_limit=_int("BIBLIO_BATCH_LIMIT", 40),
        rate_limit_per_minute=_int("BIBLIO_RATE_LIMIT", 30),
        mailto=os.getenv("BIBLIO_MAILTO", "dev@localhost").strip() or "dev@localhost",
        data_dir=data_dir,
    )
