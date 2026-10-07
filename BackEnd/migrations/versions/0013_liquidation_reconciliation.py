"""Bank identity and explicit reconciliation on existing vouchers."""
from alembic import op
import sqlalchemy as sa

revision='0013_liquidation_reconciliation'
down_revision='0012_document_archive'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('medical_vouchers',sa.Column('purpose',sa.String(24),nullable=False,server_default='deposit'))
    for name,length in [('bank',80),('account',34),('note',1000)]:
        op.add_column('medical_vouchers',sa.Column(name,sa.String(length)))
    op.add_column('medical_vouchers',sa.Column('verified_at',sa.DateTime()))
    op.add_column('medical_vouchers',sa.Column('verified_by',sa.Integer()))
    op.create_foreign_key('fk_medical_voucher_verifier','medical_vouchers','usuarios',['verified_by'],['id'])
    # Historical amounts and states are deliberately not reinterpreted.

def downgrade():
    op.drop_constraint('fk_medical_voucher_verifier','medical_vouchers',type_='foreignkey')
    for name in ['verified_by','verified_at','note','account','bank','purpose']:
        op.drop_column('medical_vouchers',name)
