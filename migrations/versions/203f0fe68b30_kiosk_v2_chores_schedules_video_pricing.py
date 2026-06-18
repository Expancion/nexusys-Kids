"""kiosk v2 chores schedules video pricing

Revision ID: 203f0fe68b30
Revises: a08cea3f93dc
Create Date: 2026-06-18 12:30:01.610528

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '203f0fe68b30'
down_revision = 'a08cea3f93dc'
branch_labels = None
depends_on = None


def _has_table(name):
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table, column):
    cols = [c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)]
    return column in cols


def upgrade():
    if not _has_table('child_schedule'):
        op.create_table('child_schedule',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('child_id', sa.Integer(), nullable=False),
        sa.Column('weekday', sa.Integer(), nullable=True),
        sa.Column('locked_from', sa.Time(), nullable=False),
        sa.Column('locked_to', sa.Time(), nullable=False),
        sa.Column('message', sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(['child_id'], ['child.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )

    if not _has_table('daily_chore'):
        op.create_table('daily_chore',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('child_id', sa.Integer(), nullable=False),
        sa.Column('weekday', sa.Integer(), nullable=False),
        sa.Column('chore_name', sa.String(length=100), nullable=False),
        sa.Column('chore_icon', sa.String(length=10), nullable=False),
        sa.Column('points_reward', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['child_id'], ['child.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )

    if not _has_table('chore_completion'):
        op.create_table('chore_completion',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chore_id', sa.Integer(), nullable=False),
        sa.Column('child_id', sa.Integer(), nullable=False),
        sa.Column('completed_date', sa.Date(), nullable=False),
        sa.Column('awarded_points', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['child_id'], ['child.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['chore_id'], ['daily_chore.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )

    if not _has_table('video_price_rule'):
        op.create_table('video_price_rule',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('video_id', sa.Integer(), nullable=False),
        sa.Column('time_from', sa.Time(), nullable=False),
        sa.Column('time_to', sa.Time(), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['kiosk_video.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )

    if not _has_column('kiosk_video', 'price'):
        with op.batch_alter_table('kiosk_video', schema=None) as batch_op:
            batch_op.add_column(sa.Column('price', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('kiosk_video', schema=None) as batch_op:
        batch_op.drop_column('price')

    op.drop_table('video_price_rule')
    op.drop_table('chore_completion')
    op.drop_table('daily_chore')
    op.drop_table('child_schedule')
