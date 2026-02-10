"""Create initial tables

Revision ID: c3f9a4b2e6f7
Revises: ab927e2e840d
Create Date: 2026-02-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3f9a4b2e6f7'
down_revision: Union[str, Sequence[str], None] = 'ab927e2e840d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create tables matching SQLAlchemy models."""
    op.create_table(
        'route_data',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ruta', sa.Integer(), nullable=False),
        sa.Column('ns_latitude', sa.Float(), nullable=False),
        sa.Column('ew_longitude', sa.Float(), nullable=False),
        sa.Column('position_ts', sa.DateTime(), nullable=True),
        sa.Column('route_status', sa.String(), nullable=False),
        sa.Column('route_status_ts', sa.DateTime(), nullable=True),
        sa.Column('student_status', sa.String(), nullable=False),
        sa.Column('student_status_ts', sa.DateTime(), nullable=True),
        sa.Column('collected_at', sa.DateTime(), nullable=False),
    )

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
    """Downgrade schema: drop created tables."""
    op.drop_table('collection_sessions')
    op.drop_table('route_data')
