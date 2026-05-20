"""Tests for app.database: session generators and engine initialisation paths."""
import importlib
import os
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session


class TestGetDb:
    def test_yields_a_session(self):
        from app.database import get_db
        gen = get_db()
        db = next(gen)
        try:
            assert isinstance(db, Session)
        finally:
            gen.close()

    def test_closes_session_on_completion(self):
        from app.database import get_db
        gen = get_db()
        db = next(gen)
        closed = []
        _real_close = db.close
        db.close = lambda: (closed.append(True), _real_close())[1]
        try:
            next(gen)
        except StopIteration:
            pass
        assert closed


class TestGetDbSession:
    def test_yields_a_session(self):
        from app.database import get_db_session
        gen = get_db_session()
        db = next(gen)
        try:
            assert isinstance(db, Session)
        finally:
            gen.close()

    def test_closes_session_on_completion(self):
        from app.database import get_db_session
        gen = get_db_session()
        db = next(gen)
        closed = []
        _real_close = db.close
        db.close = lambda: (closed.append(True), _real_close())[1]
        try:
            next(gen)
        except StopIteration:
            pass
        assert closed


class TestNonTestingEngineInit:
    def test_creates_engine_with_database_url(self):
        """PostgreSQL branch (TESTING != '1') must call create_engine with DATABASE_URL."""
        import app.database as db_mod

        mock_engine = MagicMock()
        try:
            with patch.dict(
                os.environ,
                {"TESTING": "0", "DATABASE_URL": "postgresql://u:p@db/app"},
            ):
                with patch("sqlalchemy.create_engine", return_value=mock_engine) as mock_ce:
                    importlib.reload(db_mod)
            mock_ce.assert_called_with("postgresql://u:p@db/app")
        finally:
            importlib.reload(db_mod)
