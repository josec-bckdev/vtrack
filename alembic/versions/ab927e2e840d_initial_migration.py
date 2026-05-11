"""Initial migration

Revision ID: ab927e2e840d
Revises: 
Create Date: 2026-02-05 06:44:25.212667

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ab927e2e840d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Get inspector to check for existing tables (idempotent design)
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing_tables = inspector.get_table_names()
    
    # Create tables to match SQLAlchemy models in app.models
    if 'route_data' not in existing_tables:
        op.create_table(
            'route_data',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('ruta', sa.Integer(), nullable=False, index=False),
            sa.Column('ns_latitude', sa.Float(), nullable=False),
            sa.Column('ew_longitude', sa.Float(), nullable=False),
            sa.Column('position_ts', sa.DateTime(), nullable=True),
            sa.Column('route_status', sa.String(), nullable=False),
            sa.Column('route_status_ts', sa.DateTime(), nullable=True),
            sa.Column('student_status', sa.String(), nullable=False),
            sa.Column('student_status_ts', sa.DateTime(), nullable=True),
            sa.Column('collected_at', sa.DateTime(), nullable=False),
        )

    if 'collection_sessions' not in existing_tables:
        op.create_table(
            'collection_sessions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('start_time', sa.DateTime(), nullable=False),
            sa.Column('stop_time', sa.DateTime(), nullable=True),
            sa.Column('status', sa.String(), nullable=False),
            sa.Column('datapoints_count', sa.Integer(), nullable=True),
            sa.Column('last_update_time', sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop created tables
    op.drop_table('collection_sessions')
    op.drop_table('route_data')
