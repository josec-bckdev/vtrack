from app.domain.ports import ICollectionStatusAdapter


class AsyncCollectionManagerAdapter(ICollectionStatusAdapter):
    def __init__(self, manager):
        self._manager = manager

    def is_running(self) -> bool:
        return self._manager._is_running

    def datapoints_collected(self) -> int:
        return self._manager.datapoints_collected

    async def start(self) -> None:
        await self._manager.start()
