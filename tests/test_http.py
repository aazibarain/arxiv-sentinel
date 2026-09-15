import asyncio
from typing import Any

from backend.ingestion import http


class StubResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}


class SequenceClient:
    def __init__(self, statuses: list[int]) -> None:
        self.statuses = iter(statuses)
        self.calls = 0

    async def get(self, path: str, *, params: dict[str, Any]) -> StubResponse:
        self.calls += 1
        return StubResponse(next(self.statuses))


def test_get_with_retry_retries_rate_limit(monkeypatch: Any) -> None:
    client = SequenceClient([429, 200])

    async def no_sleep(delay: float) -> None:
        return None

    monkeypatch.setattr(http.asyncio, "sleep", no_sleep)
    response = asyncio.run(http.get_with_retry(client, "/works", params={}))

    assert response.status_code == 200
    assert client.calls == 2
