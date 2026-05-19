import httpx

from conductor.domain.ports import IVtrackGateway


class HttpxVtrackGateway(IVtrackGateway):
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self._base}/monitor/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def guardian_status(self) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._base}/monitor/guardian")
            resp.raise_for_status()
            return resp.json()

    async def activate_guardian(self, slot: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/monitor/guardian/activate",
                params={"slot": slot},
            )
            resp.raise_for_status()

    async def collection_status(self) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._base}/collect/status")
            resp.raise_for_status()
            return resp.json()
