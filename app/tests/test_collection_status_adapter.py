"""
Tests for ICollectionStatusAdapter port and AsyncCollectionManagerAdapter.

Section 1: Port contract — ICollectionStatusAdapter is an importable ABC
            with is_running() and start() abstract methods.

Section 2: Adapter behaviour — AsyncCollectionManagerAdapter correctly
            delegates is_running and start to an AsyncCollectionManager.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# PORT CONTRACT TESTS  (RED until app/domain/ports.py is updated)
# =============================================================================

class TestCollectionStatusAdapterPortContract:

    def test_port_is_importable(self):
        from app.domain.ports import ICollectionStatusAdapter
        assert ICollectionStatusAdapter is not None

    def test_port_is_abstract(self):
        from app.domain.ports import ICollectionStatusAdapter
        import inspect
        assert inspect.isabstract(ICollectionStatusAdapter)

    def test_port_cannot_be_instantiated_directly(self):
        from app.domain.ports import ICollectionStatusAdapter
        with pytest.raises(TypeError):
            ICollectionStatusAdapter()

    def test_port_has_is_running_method(self):
        from app.domain.ports import ICollectionStatusAdapter
        assert hasattr(ICollectionStatusAdapter, "is_running")

    def test_port_has_start_method(self):
        from app.domain.ports import ICollectionStatusAdapter
        assert hasattr(ICollectionStatusAdapter, "start")

    def test_is_running_is_abstract(self):
        from app.domain.ports import ICollectionStatusAdapter
        assert "is_running" in ICollectionStatusAdapter.__abstractmethods__

    def test_start_is_abstract(self):
        from app.domain.ports import ICollectionStatusAdapter
        assert "start" in ICollectionStatusAdapter.__abstractmethods__

    def test_concrete_subclass_must_implement_both_methods(self):
        from app.domain.ports import ICollectionStatusAdapter

        class IncompleteAdapter(ICollectionStatusAdapter):
            def is_running(self) -> bool:
                return False
            # start() not implemented

        with pytest.raises(TypeError):
            IncompleteAdapter()

    def test_concrete_subclass_with_both_methods_is_instantiable(self):
        from app.domain.ports import ICollectionStatusAdapter

        class ConcreteAdapter(ICollectionStatusAdapter):
            def is_running(self) -> bool:
                return False

            async def start(self) -> None:
                pass

            def datapoints_collected(self) -> int:
                return 0

        adapter = ConcreteAdapter()
        assert adapter is not None


# =============================================================================
# ADAPTER BEHAVIOUR TESTS  (RED until app/adapters/collection_status_adapter.py exists)
# =============================================================================

class TestAsyncCollectionManagerAdapter:

    def test_adapter_is_importable(self):
        from app.adapters.collection_status_adapter import AsyncCollectionManagerAdapter
        assert AsyncCollectionManagerAdapter is not None

    def test_adapter_implements_port(self):
        from app.adapters.collection_status_adapter import AsyncCollectionManagerAdapter
        from app.domain.ports import ICollectionStatusAdapter
        assert issubclass(AsyncCollectionManagerAdapter, ICollectionStatusAdapter)

    def test_is_running_returns_false_when_manager_not_running(self, clean_collection_manager):
        from app.adapters.collection_status_adapter import AsyncCollectionManagerAdapter
        clean_collection_manager._is_running = False
        adapter = AsyncCollectionManagerAdapter(clean_collection_manager)
        assert adapter.is_running() is False

    def test_is_running_returns_true_when_manager_running(self, clean_collection_manager):
        from app.adapters.collection_status_adapter import AsyncCollectionManagerAdapter
        clean_collection_manager._is_running = True
        adapter = AsyncCollectionManagerAdapter(clean_collection_manager)
        assert adapter.is_running() is True

    @pytest.mark.asyncio
    async def test_start_delegates_to_manager(self, clean_collection_manager):
        from app.adapters.collection_status_adapter import AsyncCollectionManagerAdapter
        clean_collection_manager.start = AsyncMock(return_value=True)
        adapter = AsyncCollectionManagerAdapter(clean_collection_manager)
        await adapter.start()
        clean_collection_manager.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_raises_if_manager_already_running(self, clean_collection_manager):
        from app.adapters.collection_status_adapter import AsyncCollectionManagerAdapter
        clean_collection_manager._is_running = True
        clean_collection_manager.start = AsyncMock(side_effect=RuntimeError("Collection already running"))
        adapter = AsyncCollectionManagerAdapter(clean_collection_manager)
        with pytest.raises(RuntimeError, match="already running"):
            await adapter.start()
