"""Reuse dispatch history for explicitly requested invoice emails."""
from alembic import op
import sqlalchemy as sa
revision='0014_invoice_delivery'
down_revision='0013_liquidation_reconciliation'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('medical_dispatches',sa.Column('invoice_id',sa.Integer(),nullable=True))
    op.create_foreign_key('fk_medical_dispatch_invoice','medical_dispatches','medical_invoices',['invoice_id'],['id'])
    op.create_index('ix_medical_dispatches_invoice_id','medical_dispatches',['invoice_id'])
def downgrade():
    op.drop_index('ix_medical_dispatches_invoice_id','medical_dispatches')
    op.drop_constraint('fk_medical_dispatch_invoice','medical_dispatches',type_='foreignkey')
    op.drop_column('medical_dispatches','invoice_id')
