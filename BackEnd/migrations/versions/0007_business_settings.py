"""Settings for the emissions workspace."""
from alembic import op
import sqlalchemy as sa

revision = "0007_business_settings"
down_revision = "0006_fiscal_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("medical_business_settings", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("values", sa.JSON(), nullable=False))


def downgrade():
    op.drop_table("medical_business_settings")
