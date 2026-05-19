from typing import Optional

import httpx

from conductor.domain.ports import IVtrackGateway


class HttpxVtrackGateway(IVtrackGateway):
    def __init__(self, base_url: str, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self._base = base_url.rstrip("/")
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport)

    async def health(self) -> bool:
        try:
            async with self._client() as client:
                resp = await client.get(f"{self._base}/monitor/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def guardian_status(self) -> dict:
        async with self._client() as client:
            resp = await client.get(f"{self._base}/monitor/guardian")
            resp.raise_for_status()
            return resp.json()

    async def activate_guardian(self, slot: str) -> None:
        async with self._client() as client:
            resp = await client.post(
                f"{self._base}/monitor/guardian/activate",
                params={"slot": slot},
            )
            resp.raise_for_status()

    async def collection_status(self) -> dict:
        async with self._client() as client:
            resp = await client.get(f"{self._base}/collect/status")
            resp.raise_for_status()
            return resp.json()
