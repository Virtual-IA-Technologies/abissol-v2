"""Consolidate navigation without deleting permission grants; index META status."""
from alembic import op
import sqlalchemy as sa

revision = "0008_navigation_queries"
down_revision = "0007_business_settings"
branch_labels = None
depends_on = None


def upgrade():
    menus = sa.table("menus", sa.column("slug", sa.String), sa.column("is_visible", sa.Boolean))
    op.execute(menus.update().where(menus.c.slug.in_(["medical-plans", "medical-dispatches", "smtp", "whatsapp"])).values(is_visible=False))
    op.create_index("ix_medical_dispatch_meta_state", "medical_dispatches", ["issuance_id", "kind", "status"])


def downgrade():
    op.drop_index("ix_medical_dispatch_meta_state", table_name="medical_dispatches")
    # Do not overwrite an administrator's later navigation choices.
