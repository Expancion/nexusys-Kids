"""nexus_junior_models

Revision ID: a08cea3f93dc
Revises:
Create Date: 2026-06-17 21:29:37.370478

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a08cea3f93dc'
down_revision = None
branch_labels = None
depends_on = None


def _has_table(name):
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade():
    if not _has_table('child'):
        op.create_table('child',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('avatar_icon', sa.String(length=10), nullable=False),
        sa.Column('avatar_color', sa.String(length=120), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('video_cost', sa.Integer(), nullable=False),
        sa.Column('daily_video_limit', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
        )

    if not _has_table('reward_task'):
        op.create_table('reward_task',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('icon', sa.String(length=10), nullable=False),
        sa.Column('points_value', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
        )

    if not _has_table('device'):
        op.create_table('device',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('child_id', sa.Integer(), nullable=False),
        sa.Column('device_key', sa.String(length=80), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('allowed', sa.Boolean(), nullable=False),
        sa.Column('locked_message', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['child_id'], ['child.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_key')
        )

    if not _has_table('point_transaction'):
        op.create_table('point_transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('child_id', sa.Integer(), nullable=False),
        sa.Column('delta', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=200), nullable=False),
        sa.Column('actor', sa.String(length=80), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['child_id'], ['child.id'], ),
        sa.PrimaryKeyConstraint('id')
        )

    if not _has_table('watch_session'):
        op.create_table('watch_session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('child_id', sa.Integer(), nullable=False),
        sa.Column('video_id', sa.Integer(), nullable=True),
        sa.Column('device_key', sa.String(length=80), nullable=True),
        sa.Column('points_spent', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['child_id'], ['child.id'], ),
        sa.ForeignKeyConstraint(['video_id'], ['kiosk_video.id'], ),
        sa.PrimaryKeyConstraint('id')
        )


def downgrade():
    op.drop_table('watch_session')
    op.drop_table('point_transaction')
    op.drop_table('device')
    op.drop_table('reward_task')
    op.drop_table('child')
