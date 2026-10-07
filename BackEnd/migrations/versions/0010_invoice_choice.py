"""Keep the requested fiscal document with the sale before queueing."""
from alembic import op
import sqlalchemy as sa
revision = "0010_invoice_choice"
down_revision = "0009_external_emissions"
branch_labels = depends_on = None

def upgrade():
    op.add_column('medical_issuances',sa.Column('billing_preference',sa.JSON,nullable=True))

def downgrade():
    op.drop_column('medical_issuances','billing_preference')
