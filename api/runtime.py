"""Stan procesu (Redis itd.) — jedna instancja na worker."""

from __future__ import annotations

from typing import Any, Optional

redis_client: Any = None


def get_redis() -> Optional[Any]:
    """Zwraca aktywnego klienta Redis lub None gdy niedostępny."""
    return redis_client
