"""Identify disposable pilot emissions without allocating production numbers."""
from alembic import op
import sqlalchemy as sa
revision='0015_medical_test_batch'
down_revision='0014_invoice_delivery'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('medical_integration_credentials',sa.Column('test_only',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('medical_issuances',sa.Column('test_batch',sa.String(64),nullable=True))
    op.create_index('ix_medical_issuances_test_batch','medical_issuances',['test_batch'])

def downgrade():
    op.drop_column('medical_integration_credentials','test_only')
    op.drop_index('ix_medical_issuances_test_batch','medical_issuances')
    op.drop_column('medical_issuances','test_batch')
