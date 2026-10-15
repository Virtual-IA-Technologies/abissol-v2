"""Presence scoped to authenticated ABISSOL device sessions."""
from alembic import op
import sqlalchemy as sa

revision = '0017_support_chat_presence'
down_revision = '0016_seller_access'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('support_chat_presence',
        sa.Column('device_session_id', sa.Integer(), sa.ForeignKey('device_sessions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('seen_at', sa.DateTime(), nullable=False))


def downgrade():
    op.drop_table('support_chat_presence')
