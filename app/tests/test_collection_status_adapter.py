"""
Tests for ICollectionStatusAdapter port and AsyncCollectionManagerAdapter.

Section 1: Port contract — ICollectionStatusAdapter is an importable ABC
            with is_running() and start() abstract methods.

Section 2: Adapter behaviour — AsyncCollectionManagerAdapter correctly
            delegates is_running and start to an AsyncCollectionManager.
"""

import pytest


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

        adapter = ConcreteAdapter()
        assert adapter is not None
