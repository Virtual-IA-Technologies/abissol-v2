"""Persistent automatic boleta delivery, independent from imported history."""
from alembic import op
import sqlalchemy as sa

revision = '0006_fiscal_jobs'
down_revision = '0005_legacy_abissol'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('medical_fiscal_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('medical_invoices.id'), nullable=False, unique=True),
        sa.Column('environment', sa.String(20), nullable=False),
        sa.Column('series', sa.String(4), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('sent_at', sa.DateTime()),
        sa.Column('next_attempt_at', sa.DateTime(), nullable=False),
        sa.Column('error', sa.String(500)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('environment', 'series', 'number', name='uq_fiscal_number'))
    op.create_index('ix_medical_fiscal_jobs_state', 'medical_fiscal_jobs', ['state'])


def downgrade():
    op.drop_table('medical_fiscal_jobs')
