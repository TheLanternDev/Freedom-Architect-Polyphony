"""Stan procesu (Redis itd.) — jedna instancja na worker."""

from __future__ import annotations

from typing import Any

redis_client: Any = None
