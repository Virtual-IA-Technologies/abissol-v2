"""Authenticated source connectors and atomic coverage checks."""
from alembic import op
import sqlalchemy as sa

revision = "0009_external_emissions"
down_revision = "0008_navigation_queries"
branch_labels = depends_on = None


def upgrade():
    for name, size in (("first_names",100),("paternal_surname",80),("maternal_surname",80)):
        op.add_column("medical_issuances",sa.Column(name,sa.String(size),nullable=False,server_default=""))
    op.create_table("medical_coverage_locks",sa.Column("document_hash",sa.String(64),primary_key=True))
    op.create_table("medical_integration_credentials",
        sa.Column("id",sa.Integer,primary_key=True),
        sa.Column("source_id",sa.Integer,sa.ForeignKey("medical_sources.id"),nullable=False),
        sa.Column("actor_id",sa.Integer,sa.ForeignKey("usuarios.id"),nullable=False),
        sa.Column("token_hash",sa.String(64),nullable=False,unique=True),
        sa.Column("active",sa.Boolean,nullable=False),
        sa.Column("created_at",sa.DateTime,nullable=False))
    op.create_index("ix_medical_integration_credentials_source_id","medical_integration_credentials",["source_id"])


def downgrade():
    op.drop_table("medical_integration_credentials")
    op.drop_table("medical_coverage_locks")
    for name in ("first_names","paternal_surname","maternal_surname"):
        op.drop_column("medical_issuances",name)
