"""Small retry helper for rate-limited research APIs."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


async def get_with_retry(
    client: Any,
    path: str,
    *,
    params: dict[str, Any],
    attempts: int = 3,
) -> Any:
    """GET a resource with short, bounded retries for transient failures."""

    if attempts < 1:
        raise ValueError("attempts must be positive")
    last_error: httpx.RequestError | None = None
    for attempt in range(attempts):
        try:
            response = await client.get(path, params=params)
            status_code = getattr(response, "status_code", None)
            if status_code not in RETRYABLE_STATUS_CODES or attempt == attempts - 1:
                return response
            retry_after = getattr(response, "headers", {}).get("retry-after")
            delay = min(float(retry_after), 10.0) if retry_after else float(2**attempt)
        except httpx.RequestError as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
            delay = float(2**attempt)
        await asyncio.sleep(delay)

    if last_error is not None:  # pragma: no cover - loop always returns or raises
        raise last_error
    raise RuntimeError("retry loop exited unexpectedly")  # pragma: no cover
